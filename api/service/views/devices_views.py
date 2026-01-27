from django.db import connection, transaction
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .helpers import q, exec_void, require_roles, _fetchall_dicts, _set_audit_user


class DeviceIdentificadoresView(APIView):
    """
    Permite corregir numero_serie y numero_interno (MG) de un device ya existente,
    aplicando las mismas reglas de normalización y unicidad que en ingresos.
    """

    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def patch(self, request, device_id: int):
        require_roles(request, ["jefe", "jefe_veedor", "admin"])
        _set_audit_user(request)
        data = request.data or {}
        numero_serie = (data.get("numero_serie") or "").strip()
        numero_interno = (data.get("numero_interno") or "").strip()
        if numero_interno and not numero_interno.upper().startswith(("MG", "NM", "NV", "CE")):
            numero_interno = "MG " + numero_interno

        # Verificar que el device exista
        dev = q(
            "SELECT id, COALESCE(numero_serie,'') AS numero_serie, COALESCE(numero_interno,'') AS numero_interno "
            "FROM devices WHERE id=%s",
            [device_id],
            one=True,
        )
        if not dev:
            return Response({"detail": "Device inexistente"}, status=404)

        updates = []
        params = []

        # Validar numero_serie si viene
        if numero_serie:
            ns_key = numero_serie.replace(" ", "").replace("-", "").upper()
            other = q(
                """
                SELECT id
                  FROM devices
                 WHERE REPLACE(REPLACE(UPPER(numero_serie),' ',''),'-','') = %s
                   AND id <> %s
                 LIMIT 1
                """,
                [ns_key, device_id],
                one=True,
            )
            if other:
                return Response(
                    {
                        "detail": "El número de serie ya está asignado a otro equipo.",
                        "conflict_type": "NS_DUPLICATE",
                        "conflict_device_id": other["id"],
                    },
                    status=400,
                )
            updates.append("numero_serie = %s")
            params.append(numero_serie)

        # Validar numero_interno si viene
        if numero_interno:
            if connection.vendor == "postgresql":
                conflict = q(
                    """
                    SELECT id
                      FROM devices
                     WHERE id <> %s
                       AND numero_interno ~* '^(MG|NM|NV|CE)\\s*\\d{1,4}$'
                       AND UPPER(REGEXP_REPLACE(numero_interno,
                           '^(MG|NM|NV|CE)\\s*(\\d{1,4})$', '\\1 ' || LPAD('\\2',4,'0'))) =
                           UPPER(REGEXP_REPLACE(%s,
                           '^(MG|NM|NV|CE)\\s*(\\d{1,4})$', '\\1 ' || LPAD('\\2',4,'0')))
                     LIMIT 1
                    """,
                    [device_id, numero_interno],
                    one=True,
                )
            else:
                conflict = q(
                    "SELECT id FROM devices WHERE id <> %s AND numero_interno = %s LIMIT 1",
                    [device_id, numero_interno],
                    one=True,
                )
            if conflict:
                return Response(
                    {
                        "detail": "El número interno ya está asignado a otro equipo.",
                        "conflict_type": "MG_DUPLICATE",
                        "conflict_device_id": conflict["id"],
                    },
                    status=400,
                )
            updates.append("numero_interno = NULLIF(%s,'')")
            params.append(numero_interno)

        if not updates:
            return Response({"detail": "No se enviaron cambios"}, status=400)

        params.append(device_id)
        sql = "UPDATE devices SET " + ", ".join(updates) + " WHERE id=%s"
        exec_void(sql, params)
        return Response({"ok": True})


class DevicesListView(APIView):
    """
    Listado de devices (equipos) con info de propiedad (MG/propio), último cliente
    y datos básicos de identificación. Solo visible para roles de sistema.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request, ["jefe", "jefe_veedor", "admin"])
        q_raw = (request.GET.get("q") or "").strip()
        propio_raw = (request.GET.get("propio") or "").strip().lower()
        alquilado_raw = (request.GET.get("alquilado") or "").strip().lower()
        sort_raw = (request.GET.get("sort") or "").strip()
        page_raw = (request.GET.get("page") or "").strip()
        page_size_raw = (request.GET.get("page_size") or "").strip()

        page = int(page_raw) if page_raw.isdigit() and int(page_raw) > 0 else 1
        try:
            page_size = int(page_size_raw) if page_size_raw else 0
        except Exception:
            page_size = 0
        if page_size < 0:
            page_size = 0
        if page_size > 0:
            page_size = min(page_size, 500)

        with connection.cursor() as cur:
            # Identificar id de cliente propio (MG BIO) si existe
            cur.execute(
                "SELECT id FROM customers WHERE LOWER(razon_social) LIKE %s ORDER BY id ASC LIMIT 1",
                ["%mg%bio%"],
            )
            row_mg_owner = cur.fetchone()
            mg_owner_id = row_mg_owner[0] if row_mg_owner else None

            wh, params = [], []
            if q_raw:
                like = f"%{q_raw}%"
                wh.append(
                    "("
                    "LOWER(COALESCE(d.numero_serie,'')) LIKE LOWER(%s) OR "
                    "LOWER(COALESCE(d.numero_interno,'')) LIKE LOWER(%s) OR "
                    "LOWER(COALESCE(c.razon_social,'')) LIKE LOWER(%s) OR "
                    "LOWER(COALESCE(b.nombre,'')) LIKE LOWER(%s) OR "
                    "LOWER(COALESCE(m.nombre,'')) LIKE LOWER(%s)"
                    ")"
                )
                params.extend([like, like, like, like, like])

            if propio_raw in ("1", "true", "yes", "y", "t"):
                wh.append(
                    "("
                    "d.numero_interno ~* '^(MG|NM|NV|CE)\\s*\\d{1,4}$' OR "
                    "d.numero_serie ~* '^(MG|NM|NV|CE)\\s*\\d{1,4}$'"
                    ")"
                )
            if alquilado_raw in ("1", "true", "yes", "y", "t"):
                wh.append("COALESCE(d.alquilado,false) = true")
            elif alquilado_raw in ("0", "false", "no", "n"):
                wh.append("COALESCE(d.alquilado,false) = false")

            where_sql = (" WHERE " + " AND ".join(wh)) if wh else ""

            sort_map = {
                "id": "d.id",
                "-id": "d.id DESC",
                "ns": "d.numero_serie",
                "-ns": "d.numero_serie DESC",
                "mg": "d.numero_interno",
                "-mg": "d.numero_interno DESC",
                "marca": "b.nombre",
                "-marca": "b.nombre DESC",
                "modelo": "m.nombre",
                "-modelo": "m.nombre DESC",
                "cliente": "c.razon_social",
                "-cliente": "c.razon_social DESC",
                "ubicacion": "loc.nombre",
                "-ubicacion": "loc.nombre DESC",
            }
            order_sql = sort_map.get(sort_raw or "", "d.id DESC")

            limit_sql = ""
            limit_params = []
            overfetch = 0
            if page_size > 0:
                overfetch = 1
                limit_sql = " LIMIT %s OFFSET %s"
                limit_params.extend([page_size + overfetch, max(0, (page - 1) * page_size)])

            sql = f"""
                SELECT
                  d.id,
                  d.customer_id,
                  COALESCE(c.razon_social,'') AS customer_nombre,
                  d.marca_id,
                  d.model_id,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  COALESCE(d.numero_serie,'') AS numero_serie,
                  COALESCE(d.numero_interno,'') AS numero_interno,
                  COALESCE(d.tipo_equipo,'') AS tipo_equipo,
                  COALESCE(d.variante,'') AS variante,
                  d.garantia_vence,
                  COALESCE(d.alquilado,false) AS alquilado,
                  COALESCE(d.alquiler_a,'') AS alquiler_a,
                  d.ubicacion_id,
                  COALESCE(loc.nombre,'') AS ubicacion_nombre,
                  d.propietario,
                  d.propietario_nombre,
                  d.propietario_contacto,
                  d.propietario_doc,
                  lasti.ingreso_id AS last_ingreso_id,
                  NULL::integer AS last_customer_id,
                  ''::text AS last_customer_nombre,
                  lasti.fecha_ingreso AS last_fecha_ingreso,
                  (CASE WHEN (d.numero_interno ~* '^(MG|NM|NV|CE)\\s*\\d{{1,4}}$'
                              OR d.numero_serie ~* '^(MG|NM|NV|CE)\\s*\\d{{1,4}}$')
                        THEN TRUE ELSE FALSE END) AS es_propietario_mg,
                  (CASE WHEN (d.numero_interno ~* '^(MG|NM|NV|CE)\\s*\\d{{1,4}}$'
                              OR d.numero_serie ~* '^(MG|NM|NV|CE)\\s*\\d{{1,4}}$')
                             AND COALESCE(d.alquilado,false) = false
                             AND d.customer_id IS NOT NULL
                             AND (%s IS NULL OR d.customer_id <> %s)
                        THEN TRUE ELSE FALSE END) AS vendido
                FROM devices d
                LEFT JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN locations loc ON loc.id = d.ubicacion_id
                LEFT JOIN LATERAL (
                  SELECT i.id AS ingreso_id,
                         COALESCE(i.fecha_ingreso, i.fecha_creacion) AS fecha_ingreso
                    FROM ingresos i
                   WHERE i.device_id = d.id
                   ORDER BY COALESCE(i.fecha_ingreso, i.fecha_creacion) DESC, i.id DESC
                   LIMIT 1
                ) lasti ON TRUE
                {where_sql}
                ORDER BY {order_sql}
                {limit_sql}
            """
            cur.execute(sql, [mg_owner_id, mg_owner_id] + params + limit_params)
            rows = _fetchall_dicts(cur)
        # Conteo total (fuera del cursor anterior)
        with connection.cursor() as cur2:
            cur2.execute("SELECT COUNT(*) FROM devices")
            total_count = cur2.fetchone()[0]

        if page_size == 0:
            return Response({"items": rows, "total_count": total_count})
        has_next = False
        if len(rows) > page_size:
            has_next = True
            rows = rows[:page_size]
        return Response({
            "items": rows,
            "page": page,
            "page_size": page_size,
            "has_next": bool(has_next),
            "total_count": total_count,
        })


__all__ = [
    "DeviceIdentificadoresView",
    "DevicesListView",
]


def _norm_mg(value: str):
    import re
    s = (value or "").strip().upper()
    m = re.match(r"^(MG|NM|NV|CE)\s*(\d{1,4})$", s, re.IGNORECASE)
    if not m:
        return None
    pref = m.group(1).upper()
    num = m.group(2).zfill(4)
    return f"{pref} {num}"


class DevicesMergeView(APIView):
    """
    Unificar dos devices en uno solo, moviendo sus ingresos al destino.
    - Se mantiene el device destino (target_id) y se elimina el source_id.
    - Se puede fijar un nuevo numero_serie para el destino.
    - El numero_interno se mantiene del destino; si el destino no tiene MG y el source sí,
      se copia si no hay conflicto.
    - Si ambos MG existen y difieren, devuelve error.
    """

    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        require_roles(request, ["jefe", "jefe_veedor", "admin"])
        _set_audit_user(request)
        data = request.data or {}
        try:
            target_id = int(data.get("target_id"))
            source_id = int(data.get("source_id"))
        except Exception:
            return Response({"detail": "target_id y source_id requeridos"}, status=400)
        if target_id == source_id:
            return Response({"detail": "target_id y source_id deben ser distintos"}, status=400)

        new_ns = (data.get("numero_serie") or "").strip()
        copy_mg_if_missing = bool(data.get("copy_mg_if_missing"))

        target = q(
            "SELECT id, numero_serie, numero_interno FROM devices WHERE id=%s",
            [target_id],
            one=True,
        )
        source = q(
            "SELECT id, numero_serie, numero_interno FROM devices WHERE id=%s",
            [source_id],
            one=True,
        )
        if not target or not source:
            return Response({"detail": "Device destino o fuente inexistente"}, status=404)

        mg_target = _norm_mg(target.get("numero_interno") or "")
        mg_source = _norm_mg(source.get("numero_interno") or "")

        # MG conflict check
        if mg_target and mg_source and mg_target != mg_source:
            return Response(
                {
                    "detail": "Los equipos a unificar tienen números internos distintos.",
                    "conflict_type": "MG_MISMATCH",
                    "mg_target": mg_target,
                    "mg_source": mg_source,
                },
                status=400,
            )

        # NS requerido
        if not new_ns:
            return Response({"detail": "numero_serie requerido para unificar"}, status=400)
        ns_key = new_ns.replace(" ", "").replace("-", "").upper()
        ns_conflict = q(
            """
            SELECT id FROM devices
             WHERE REPLACE(REPLACE(UPPER(numero_serie),' ',''),'-','') = %s
               AND id NOT IN (%s, %s)
             LIMIT 1
            """,
            [ns_key, target_id, source_id],
            one=True,
        )
        if ns_conflict:
            return Response(
                {
                    "detail": "El número de serie ya está asignado a otro equipo.",
                    "conflict_type": "NS_DUPLICATE",
                    "conflict_device_id": ns_conflict["id"],
                },
                status=400,
            )

        # Si vamos a copiar MG desde source, validar que no choque con otros
        mg_to_apply = mg_target
        if not mg_target and mg_source and copy_mg_if_missing:
            mg_to_apply = mg_source
            mg_conflict = q(
                """
                SELECT id
                  FROM devices
                 WHERE id NOT IN (%s,%s)
                   AND numero_interno ~* '^(MG|NM|NV|CE)\\s*\\d{1,4}$'
                   AND UPPER(REGEXP_REPLACE(numero_interno,
                       '^(MG|NM|NV|CE)\\s*(\\d{1,4})$', '\\1 ' || LPAD('\\2',4,'0'))) =
                       UPPER(REGEXP_REPLACE(%s,
                       '^(MG|NM|NV|CE)\\s*(\\d{1,4})$', '\\1 ' || LPAD('\\2',4,'0')))
                 LIMIT 1
                """,
                [target_id, source_id, mg_to_apply],
                one=True,
            )
            if mg_conflict:
                return Response(
                    {
                        "detail": "El número interno a copiar ya está asignado a otro equipo.",
                        "conflict_type": "MG_DUPLICATE",
                        "conflict_device_id": mg_conflict["id"],
                    },
                    status=400,
                )

        # 1) Limpiar N/S del source para evitar choque de índice al setear en target
        exec_void("UPDATE devices SET numero_serie = NULL WHERE id=%s", [source_id])
        # 2) Aplicar N/S en target
        exec_void("UPDATE devices SET numero_serie = NULLIF(%s,'') WHERE id=%s", [new_ns, target_id])
        # 3) Copiar MG al target si corresponde (primero liberar MG en source para no violar índice)
        if mg_to_apply and mg_to_apply != mg_target:
            try:
                exec_void("UPDATE devices SET numero_interno = NULL WHERE id=%s", [source_id])
                exec_void("UPDATE devices SET numero_interno = %s WHERE id=%s", [mg_to_apply, target_id])
            except Exception as e:
                return Response(
                    {
                        "detail": "No se pudo asignar el número interno al destino (posible duplicado).",
                        "conflict_type": "MG_UNIQUE_CONSTRAINT",
                        "numero_interno_input": mg_to_apply,
                        "error": str(e),
                    },
                    status=400,
                )
        # 4) Mover ingresos al target
        exec_void("UPDATE ingresos SET device_id=%s WHERE device_id=%s", [target_id, source_id])
        # 5) Eliminar el source
        exec_void("DELETE FROM devices WHERE id=%s", [source_id])

        return Response({
            "ok": True,
            "target_id": target_id,
            "source_id": source_id,
            "applied_numero_serie": new_ns,
            "applied_numero_interno": mg_to_apply,
        })
