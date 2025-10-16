from django.db import connection, transaction
import os
import json
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponse
from io import BytesIO
from openpyxl import Workbook
from django.conf import settings
from django.core.mail import send_mail

from .helpers import (
    _fetchall_dicts,
    _get_motivo_enum_values,
    _get_motivo_enum_values_raw,
    _map_motivo_to_db_label,
    _norm_txt,
    _rol,
    _set_audit_user,
    exec_returning,
    exec_void,
    last_insert_id,
    os_label,
    q,
    require_roles,
)
from ..serializers import (
    IngresoDetailSerializer,
    IngresoDetailWithAccesoriosSerializer,
    IngresoListItemSerializer,
)


class MisPendientesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe", "tecnico", "jefe_veedor"])
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute(
                """
                SELECT t.id,
                       t.estado,
                       t.presupuesto_estado,
                       t.motivo,
                       c.razon_social,
                       d.numero_serie,
                       COALESCE(b.nombre,'') AS marca,
                       COALESCE(m.nombre,'') AS modelo,
                       COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                       t.fecha_ingreso,
                       CASE WHEN ed.estado = 'devuelto' THEN true ELSE false END AS derivado_devuelto
                FROM ingresos t
                JOIN devices d ON d.id=t.device_id
                JOIN customers c ON c.id=d.customer_id
                LEFT JOIN marcas b ON b.id=d.marca_id
                LEFT JOIN models m ON m.id=d.model_id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                LEFT JOIN (
                  SELECT e.*, ROW_NUMBER() OVER (
                    PARTITION BY e.ingreso_id ORDER BY e.fecha_deriv DESC, e.id DESC
                  ) AS rn
                  FROM equipos_derivados e
                ) ed ON ed.ingreso_id = t.id AND ed.rn = 1
                WHERE t.asignado_a = %s
                  AND LOWER(loc.nombre) = LOWER(%s)
                  AND t.estado NOT IN ('entregado','liberado')
                ORDER BY
                   (CASE WHEN ed.estado = 'devuelto' THEN 1 ELSE 0 END) DESC,
                   (t.motivo = 'urgente control') DESC,
                   t.fecha_ingreso ASC;
                """,
                [
                    getattr(getattr(request, "user", None), "id", None)
                    or getattr(request, "user_id", None),
                    "taller",
                ],
            )
            data = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(data, many=True).data)


class PendientesPresupuestoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute(
                """
                SELECT t.id, t.estado, t.presupuesto_estado,
                       c.razon_social,
                       d.numero_serie,
                       COALESCE(b.nombre,'') AS marca,
                       COALESCE(m.nombre,'') AS modelo,
                       COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                       t.fecha_ingreso,
                       t.fecha_servicio,
                       q.fecha_emitido AS presupuesto_fecha_emision
                FROM ingresos t
                JOIN devices d ON d.id=t.device_id
                JOIN customers c ON c.id=d.customer_id
                LEFT JOIN marcas b ON b.id=d.marca_id
                LEFT JOIN models m ON m.id=d.model_id
                LEFT JOIN quotes q ON q.ingreso_id = t.id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                WHERE COALESCE(t.presupuesto_estado, 'pendiente') = 'pendiente'
                  AND LOWER(loc.nombre) = LOWER(%s)
                  AND t.estado NOT IN ('entregado','liberado','alquilado')
                  AND (
                       t.estado = 'diagnosticado'
                    OR t.fecha_servicio IS NOT NULL
                  )
                ORDER BY COALESCE(t.fecha_servicio, t.fecha_ingreso) ASC;
                """,
                ["taller"],
            )
            data = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(data, many=True).data)


class PresupuestadosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute(
                """
                SELECT
                  t.id,
                  t.estado,
                  CASE
                    WHEN t.presupuesto_estado IS NOT NULL THEN t.presupuesto_estado::text
                    WHEN q.estado::text IN ('emitido','enviado','presupuestado') THEN 'presupuestado'
                    ELSE q.estado::text
                  END AS presupuesto_estado,
                  c.razon_social,
                  d.numero_serie,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                  t.fecha_ingreso,
                  q.id AS presupuesto_id,
                  q.id AS presupuesto_numero,
                  -- Monto mostrado: Subtotal del presupuesto (mano de obra + repuestos), sin IVA
                  COALESCE((
                    SELECT ROUND(SUM(qi.qty * qi.precio_u), 2)
                    FROM quote_items qi
                    WHERE qi.quote_id = q.id
                  ), 0) AS presupuesto_monto,
                  COALESCE(q.moneda, 'ARS') AS presupuesto_moneda,
                  q.fecha_emitido AS presupuesto_fecha_emision,
                  NULL AS presupuesto_fecha_envio 
                FROM ingresos t
                JOIN devices d ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN quotes q ON q.ingreso_id = t.id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                WHERE (
                        q.estado::text IN ('emitido','enviado','presupuestado')
                        OR t.presupuesto_estado = 'presupuestado'
                      )
                  AND LOWER(loc.nombre) = LOWER(%s)
                  AND t.estado NOT IN ('entregado','liberado', 'alquilado')
                ORDER BY COALESCE(q.fecha_emitido, t.fecha_ingreso) ASC;
                """,
                ["taller"],
            )
            return Response(_fetchall_dicts(cur))


class PresupuestadosExportView(APIView):
    """
    Exporta a Excel (.xlsx) filas de 'presupuestados' dadas por sus IDs.

    Parámetros query:
      - ids: lista separada por comas de IDs de ingresos. Ej: ?ids=10,11,15

    Columnas:
      OS, Cliente, Equipo, N/S, Monto sin IVA, Fecha emisión
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ids_raw = (request.GET.get("ids") or "").strip()
        if not ids_raw:
            return Response({"detail": "Parámetro 'ids' requerido"}, status=400)

        try:
            ids = [int(x) for x in ids_raw.split(",") if x.strip()]
        except Exception:
            return Response({"detail": "Parámetro 'ids' inválido"}, status=400)

        # Evitar excesos accidentales
        if len(ids) > 1000:
            return Response({"detail": "Demasiados IDs (máximo 1000)"}, status=400)

        # Traer datos necesarios. Reutilizamos estructura del listado 'presupuestados'.
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute(
                """
                SELECT
                  t.id,
                  c.razon_social AS cliente,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                  d.numero_serie,
                  COALESCE(d.n_de_control,'') AS numero_interno,
                  q.fecha_emitido AS fecha_emision,
                  COALESCE((
                    SELECT ROUND(SUM(qi.qty * qi.precio_u), 2)
                      FROM quote_items qi
                     WHERE qi.quote_id = q.id
                  ), 0) AS subtotal_sin_iva
                FROM ingresos t
                JOIN devices d   ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN quotes q ON q.ingreso_id = t.id
               WHERE t.id = ANY(%s)
               ORDER BY COALESCE(q.fecha_emitido, t.fecha_ingreso, NOW()) ASC
                """,
                [ids],
            )
            rows = _fetchall_dicts(cur)

        # Construir Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Presupuestados"

        headers = [
            "OS",
            "Cliente",
            "Equipo",
            "N/S",
            "Monto sin IVA",
            "Fecha emisión",
        ]
        ws.append(headers)

        def _equipolabel(r):
            tipo = (r.get("tipo_equipo") or "").strip()
            marca = (r.get("marca") or "").strip()
            modelo = (r.get("modelo") or "").strip()
            parts = [p for p in [tipo, marca, modelo] if p]
            return " | ".join(parts) if parts else "-"

        def _ns(r):
            interno = (r.get("numero_interno") or "").strip()
            serie = (r.get("numero_serie") or "").strip()
            return interno or serie or "-"

        for r in rows:
            os_txt = os_label(r.get("id"))
            equipo = _equipolabel(r)
            ns_val = _ns(r)
            monto = r.get("subtotal_sin_iva")
            fecha = r.get("fecha_emision")
            # Serializar fecha a texto corto si existe
            if fecha is not None:
                try:
                    fecha_txt = fecha.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    fecha_txt = str(fecha)
            else:
                fecha_txt = "-"

            ws.append([
                os_txt,
                r.get("cliente") or "-",
                equipo,
                ns_val,
                float(monto) if (monto is not None) else None,
                fecha_txt,
            ])

        # Ajuste simple de ancho de columnas (opcional)
        try:
            widths = [10, 40, 40, 20, 18, 20]
            for idx, w in enumerate(widths, start=1):
                col = ws.column_dimensions[chr(64 + idx)]
                col.width = w
        except Exception:
            pass

        # Serializar a binario y responder
        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)

        fname = f"presupuestados_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
        resp = HttpResponse(
            bio.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = f"attachment; filename=\"{fname}\""
        return resp


class MarcarReparadoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, ingreso_id: int):
        require_roles(request, ["tecnico", "jefe", "jefe_veedor"])
        # Solo el técnico asignado puede marcar como reparado (salvo jefes)
        try:
            if _rol(request) == "tecnico":
                row = q("SELECT asignado_a FROM ingresos WHERE id=%s", [ingreso_id], one=True)
                uid = getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", None)
                if not row or int(row.get("asignado_a") or 0) != int(uid or 0):
                    raise PermissionDenied("Solo el técnico asignado puede marcar como reparado")
        except PermissionDenied:
            raise
        except Exception:
            # En duda, permitir solo a roles superiores
            if _rol(request) == "tecnico":
                raise PermissionDenied("Solo el técnico asignado puede marcar como reparado")
        _set_audit_user(request)
        exec_void("UPDATE ingresos SET estado='reparado' WHERE id=%s", [ingreso_id])
        return Response({"ok": True})


class EntregarIngresoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "jefe_veedor", "admin", "recepcion"])
        data = request.data or {}
        remito = (data.get("remito_salida") or "").strip()
        if not remito:
            return Response({"detail": "remito_salida requerido"}, status=400)
        factura = (data.get("factura_numero") or "").strip() or None
        fecha_entrega = data.get("fecha_entrega") or None
        _set_audit_user(request)
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ingresos
                       SET estado='entregado',
                           remito_salida=%s,
                           factura_numero=%s,
                           fecha_entrega=COALESCE(%s, now())
                     WHERE id=%s
                    """,
                    [remito, factura, fecha_entrega, ingreso_id],
                )
        return Response({"ok": True})


class ListosParaRetiroView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            _set_audit_user(request)
            # Fallback sin vista: equipos en 'taller' con estado 'liberado'.
            # Devuelve columnas esperadas por el front: id, estado, resolucion,
            # cliente, numero_serie, numero_interno (MG), marca, modelo, tipo_equipo,
            # fecha_ingreso, fecha_listo (desde ingreso_events), fecha_entrega.
            cur.execute(
                """
                SELECT
                  t.id,
                  t.estado,
                  t.presupuesto_estado,
                  t.resolucion,
                  c.razon_social,
                  d.numero_serie,
                  COALESCE(d.n_de_control,'') AS numero_interno,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                  t.fecha_ingreso,
                  ev.ts AS fecha_listo,
                  t.fecha_entrega
                FROM ingresos t
                JOIN devices   d ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                LEFT JOIN (
                  SELECT ingreso_id, MAX(ts) AS ts
                    FROM ingreso_events
                   WHERE a_estado = 'liberado'
                   GROUP BY ingreso_id
                ) ev ON ev.ingreso_id = t.id
                WHERE LOWER(loc.nombre) = LOWER(%s)
                  AND t.estado = 'liberado'
                ORDER BY COALESCE(ev.ts, t.fecha_ingreso, NOW()) DESC, t.id DESC
                """,
                ["taller"],
            )
            return Response(_fetchall_dicts(cur))


class GeneralPorClienteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, customer_id):
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute(
                """
                SELECT
                  t.id, t.estado, t.presupuesto_estado, t.fecha_ingreso, t.ubicacion_id,
                  q.fecha_emitido AS presupuesto_fecha_emision,
                  COALESCE(loc.nombre,'') AS ubicacion_nombre,
                  c.id AS customer_id, c.razon_social,
                  d.numero_serie,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo
                FROM ingresos t
                JOIN devices   d ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN quotes q ON q.ingreso_id = t.id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                WHERE c.id = %s
                  AND LOWER(loc.nombre) = LOWER(%s)
                  AND t.estado NOT IN ('entregado', 'alquilado')
                ORDER BY t.fecha_ingreso DESC;
                """,
                [customer_id, "taller"],
            )
            return Response(_fetchall_dicts(cur))


class GeneralPorClienteExportView(APIView):
    """
    Exporta a Excel (.xlsx) el "general por cliente" (no entregados / no alquilados).

    GET /api/clientes/<customer_id>/general/export/
      Parámetros opcionales:
        - ids: lista separada por comas para limitar la exportación a esos ingresos

    Columnas del Excel:
      OS, Cliente, Equipo, N/S, Estado, Fecha ingreso
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, customer_id):
        ids_raw = (request.GET.get("ids") or "").strip()
        ids = None
        if ids_raw:
            try:
                ids = [int(x) for x in ids_raw.split(",") if x.strip()]
            except Exception:
                return Response({"detail": "Parámetro 'ids' inválido"}, status=400)
            if len(ids) > 1000:
                return Response({"detail": "Demasiados IDs (máximo 1000)"}, status=400)

        with connection.cursor() as cur:
            _set_audit_user(request)
            if ids:
                cur.execute(
                    """
                    SELECT
                      t.id,
                      c.razon_social AS cliente,
                      COALESCE(b.nombre,'') AS marca,
                      COALESCE(m.nombre,'') AS modelo,
                      COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                      d.numero_serie,
                      COALESCE(d.n_de_control,'') AS numero_interno,
                      t.estado,
                      t.presupuesto_estado,
                      t.fecha_ingreso
                    FROM ingresos t
                    JOIN devices   d ON d.id = t.device_id
                    JOIN customers c ON c.id = d.customer_id
                    LEFT JOIN marcas b ON b.id = d.marca_id
                    LEFT JOIN models m ON m.id = d.model_id
                    LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                   WHERE c.id = %s
                     AND t.id = ANY(%s)
                     AND LOWER(loc.nombre) = LOWER(%s)
                     AND t.estado NOT IN ('entregado','alquilado')
                   ORDER BY t.fecha_ingreso DESC, t.id DESC
                    """,
                    [customer_id, ids, "taller"],
                )
            else:
                cur.execute(
                    """
                    SELECT
                      t.id,
                      c.razon_social AS cliente,
                      COALESCE(b.nombre,'') AS marca,
                      COALESCE(m.nombre,'') AS modelo,
                      COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                      d.numero_serie,
                      COALESCE(d.n_de_control,'') AS numero_interno,
                      t.estado,
                      t.presupuesto_estado,
                      t.fecha_ingreso
                    FROM ingresos t
                    JOIN devices   d ON d.id = t.device_id
                    JOIN customers c ON c.id = d.customer_id
                    LEFT JOIN marcas b ON b.id = d.marca_id
                    LEFT JOIN models m ON m.id = d.model_id
                    LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                   WHERE c.id = %s
                     AND LOWER(loc.nombre) = LOWER(%s)
                     AND t.estado NOT IN ('entregado','alquilado')
                   ORDER BY t.fecha_ingreso DESC, t.id DESC
                    """,
                    [customer_id, "taller"],
                )
            rows = _fetchall_dicts(cur)

        wb = Workbook()
        ws = wb.active
        ws.title = "General por cliente"
        headers = ["OS", "Cliente", "Equipo", "N/S", "Estado", "Presupuesto", "Fecha ingreso"]
        ws.append(headers)

        def _equipolabel(r):
            tipo = (r.get("tipo_equipo") or "").strip()
            marca = (r.get("marca") or "").strip()
            modelo = (r.get("modelo") or "").strip()
            parts = [p for p in [tipo, marca, modelo] if p]
            return " | ".join(parts) if parts else "-"

        def _ns(r):
            interno = (r.get("numero_interno") or "").strip()
            serie = (r.get("numero_serie") or "").strip()
            return interno or serie or "-"

        def _presu_label(v):
            if not v:
                return "-"
            try:
                s = str(v).strip()
            except Exception:
                return str(v)
            if not s:
                return "-"
            if s == "presupuestado":
                return "Presupuestado"
            if s == "no_aplica":
                return "No aplica"
            return s[:1].upper() + s[1:]

        for r in rows:
            os_txt = os_label(r.get("id"))
            equipo = _equipolabel(r)
            ns_val = _ns(r)
            estado = (r.get("estado") or "-")
            presu = _presu_label(r.get("presupuesto_estado"))
            fecha = r.get("fecha_ingreso")
            if fecha is not None:
                try:
                    fecha_txt = fecha.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    fecha_txt = str(fecha)
            else:
                fecha_txt = "-"

            ws.append([
                os_txt,
                r.get("cliente") or "-",
                equipo,
                ns_val,
                estado,
                presu,
                fecha_txt,
            ])

        try:
            widths = [10, 40, 40, 20, 16, 16, 20]
            for idx, w in enumerate(widths, start=1):
                col = ws.column_dimensions[chr(64 + idx)]
                col.width = w
        except Exception:
            pass

        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)

        fname = f"general_cliente_{customer_id}_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
        resp = HttpResponse(
            bio.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = f"attachment; filename=\"{fname}\""
        return resp


class AprobadosParaRepararView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute(
                """
                SELECT
                  t.id,
                  t.estado,
                  t.presupuesto_estado,
                  c.razon_social,
                  d.numero_serie,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                  t.fecha_ingreso,
                  q.fecha_aprobado AS fecha_aprobacion
                FROM ingresos t
                JOIN devices d ON d.id=t.device_id
                JOIN customers c ON c.id=d.customer_id
                LEFT JOIN marcas b ON b.id=d.marca_id
                LEFT JOIN models m ON m.id=d.model_id
                LEFT JOIN quotes q ON q.ingreso_id = t.id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                WHERE LOWER(loc.nombre) = LOWER(%s)
                  AND (
                        (t.presupuesto_estado = 'aprobado'
                        AND t.estado NOT IN ('reparado','entregado','derivado','liberado','alquilado'))
                        OR t.estado = 'reparar'
                      )
                  AND t.estado NOT IN ('reparado','entregado','derivado','liberado','alquilado')
                ORDER BY COALESCE(q.fecha_aprobado, t.fecha_ingreso) ASC;
            """,
                ["taller"],
            )
            data = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(data, many=True).data)


class AprobadosYReparadosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute(
                """
              SELECT t.id, t.estado, t.presupuesto_estado,
                     c.razon_social,
                     d.numero_serie,
                     COALESCE(b.nombre,'') AS marca,
                     COALESCE(m.nombre,'') AS modelo,
                     COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                     t.fecha_ingreso,
                     ev.fecha_reparado
              FROM ingresos t
              JOIN devices d ON d.id=t.device_id
              JOIN customers c ON c.id=d.customer_id
              LEFT JOIN marcas b ON b.id=d.marca_id
              LEFT JOIN models m ON m.id=d.model_id
              LEFT JOIN locations loc ON loc.id = t.ubicacion_id
              LEFT JOIN (
                SELECT ingreso_id, MAX(ts) AS fecha_reparado
                FROM ingreso_events
                WHERE a_estado='reparado'
                GROUP BY ingreso_id
              ) ev ON ev.ingreso_id = t.id
              WHERE LOWER(loc.nombre) = LOWER(%s)
                AND t.estado IN ('reparado')
              ORDER BY (ev.fecha_reparado IS NULL) ASC, ev.fecha_reparado ASC, t.fecha_ingreso ASC;
            """,
                ["taller"],
            )
            data = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(data, many=True).data)


class AprobadosCombinadosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute(
                """
                -- Aprobados (incluye 'aprobado' y 'reparar' activos en taller)
                SELECT
                  t.id,
                  t.estado,
                  t.presupuesto_estado,
                  c.razon_social,
                  d.numero_serie,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                  t.fecha_ingreso,
                  q.fecha_aprobado AS fecha_aprobacion,
                  NULL::timestamp AS fecha_reparado,
                  0 AS grp,
                  COALESCE(q.fecha_aprobado, t.fecha_ingreso) AS fecha_ref
                FROM ingresos t
                JOIN devices d ON d.id=t.device_id
                JOIN customers c ON c.id=d.customer_id
                LEFT JOIN marcas b ON b.id=d.marca_id
                LEFT JOIN models m ON m.id=d.model_id
                LEFT JOIN quotes q ON q.ingreso_id = t.id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                WHERE LOWER(loc.nombre) = LOWER(%s)
                  AND (
                        (t.presupuesto_estado = 'aprobado'
                         AND t.estado NOT IN ('reparado','entregado','derivado','liberado','alquilado'))
                        OR t.estado = 'reparar'
                      )
                  AND t.estado NOT IN ('reparado','entregado','derivado','liberado','alquilado')
                UNION ALL
                -- Reparados en taller
                SELECT
                  t.id,
                  t.estado,
                  t.presupuesto_estado,
                  c.razon_social,
                  d.numero_serie,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                  t.fecha_ingreso,
                  NULL::timestamp AS fecha_aprobacion,
                  ev.fecha_reparado,
                  1 AS grp,
                  ev.fecha_reparado AS fecha_ref
                FROM ingresos t
                JOIN devices d ON d.id=t.device_id
                JOIN customers c ON c.id=d.customer_id
                LEFT JOIN marcas b ON b.id=d.marca_id
                LEFT JOIN models m ON m.id=d.model_id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                LEFT JOIN (
                  SELECT ingreso_id, MAX(ts) AS fecha_reparado
                  FROM ingreso_events
                  WHERE a_estado='reparado'
                  GROUP BY ingreso_id
                ) ev ON ev.ingreso_id = t.id
                WHERE LOWER(loc.nombre) = LOWER(%s)
                  AND t.estado IN ('reparado')
                ORDER BY grp ASC, fecha_ref ASC, fecha_ingreso ASC;
                """,
                ["taller", "taller"],
            )
            data = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(data, many=True).data)

class LiberadosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute(
                """
                SELECT
                  t.id,
                  t.estado,
                  t.presupuesto_estado,
                  c.razon_social,
                  d.numero_serie,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                  t.fecha_ingreso,
                  t.fecha_entrega
                FROM ingresos t
                JOIN devices d ON d.id=t.device_id
                JOIN customers c ON c.id=d.customer_id
                LEFT JOIN marcas b ON b.id=d.marca_id
                LEFT JOIN models m ON m.id=d.model_id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                WHERE LOWER(loc.nombre) = LOWER(%s)
                  AND t.estado IN ('liberado')
                ORDER BY t.fecha_entrega DESC, t.id DESC;
                """,
                ["taller"],
            )
            return Response(_fetchall_dicts(cur))


class GeneralEquiposView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        ubic = (request.GET.get("ubicacion") or "").strip()
        estado_raw = (request.GET.get("estado") or "").strip()
        q_raw = (request.GET.get("q") or "").strip()
        estados = [e.strip() for e in estado_raw.split(",") if e.strip()] if estado_raw else []

        with connection.cursor() as cur:
            _set_audit_user(request)
            wh, params = [], []
            if ubic:
                wh.append("LOWER(loc.nombre) = LOWER(%s)")
                params.append(ubic)
            if estados:
                placeholders = ",".join(["%s"] * len(estados))
                wh.append(f"t.estado IN ({placeholders})")
                params.extend(estados)
            # Búsqueda exacta por N/S o por MG (formato 'MG ####')
            if q_raw:
                needle = q_raw.strip()
                needle_ns = needle.replace(" ", "").upper()
                import re as _re
                m = _re.match(r"^MG\s*(\d{4})$", needle, _re.IGNORECASE)
                if m:
                    mg_no_space = ("MG" + m.group(1)).upper()
                    wh.append("(REPLACE(UPPER(d.n_de_control),' ','') = %s OR REPLACE(UPPER(d.numero_serie),' ','') = %s)")
                    params.extend([mg_no_space, mg_no_space])
                else:
                    wh.append("REPLACE(UPPER(d.numero_serie),' ','') = %s")
                    params.append(needle_ns)

            where_sql = (" WHERE " + " AND ".join(wh)) if wh else ""
            sql = f"""
                SELECT
                  t.id, t.estado, t.presupuesto_estado, t.fecha_ingreso, t.fecha_entrega, t.ubicacion_id,
                  q.fecha_emitido AS presupuesto_fecha_emision,
                  COALESCE(loc.nombre,'') AS ubicacion_nombre,
                  c.id AS customer_id, c.razon_social,
                  d.numero_serie,
                  COALESCE(d.n_de_control,'') AS numero_interno,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                  NULLIF(t.equipo_variante,'') AS equipo_variante
                FROM ingresos t
                JOIN devices   d ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN quotes q ON q.ingreso_id = t.id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                {where_sql}
                ORDER BY t.fecha_ingreso DESC, t.id DESC
            """
            cur.execute(sql, params)
            rows = _fetchall_dicts(cur)
        return Response(rows)


class IngresoAsignarTecnicoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def patch(self, request, ingreso_id):
        require_roles(request, ["jefe", "admin"]) 
        tecnico_id = request.data.get("tecnico_id")
        if tecnico_id is None:
            return Response({"detail": "tecnico_id requerido"}, status=400)
        ok = q("SELECT id FROM users WHERE id=%s AND activo=true AND rol IN ('tecnico','jefe')",
                [tecnico_id], one=True)
        if not ok:
            return Response({"detail": "Técnico inválido"}, status=400)
        exec_void("UPDATE ingresos SET asignado_a=%s WHERE id=%s", [tecnico_id, ingreso_id])
        # Marcar solicitud aceptada si existe la tabla auxiliar
        try:
            exec_void(
                """
                UPDATE ingreso_assignment_requests
                   SET accepted_at = now(), status = 'aceptado'
                 WHERE ingreso_id = %s
                   AND usuario_id = %s
                   AND accepted_at IS NULL
                   AND canceled_at IS NULL
                """,
                [ingreso_id, tecnico_id],
            )
        except Exception:
            pass
        return Response({"ok": True, "asignado_a": tecnico_id})


class IngresoSolicitarAsignacionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ingreso_id: int):
        # Solo técnicos pueden solicitar
        require_roles(request, ["tecnico"])
        uid = getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", None)
        if not uid:
            return Response({"detail": "Usuario inválido"}, status=400)

        # Si ya está asignado a este técnico, responder OK y no hacer nada
        try:
            cur = q("SELECT asignado_a FROM ingresos WHERE id=%s", [ingreso_id], one=True)
            if cur and int(cur.get("asignado_a") or 0) == int(uid):
                return Response({"ok": True, "already_assigned": True, "email_sent": False})
        except Exception:
            pass

        # Intentar registrar solicitud en tabla auxiliar (si existe)
        try:
            exec_void(
                """
                INSERT INTO ingreso_assignment_requests(ingreso_id, usuario_id, status, created_at)
                VALUES (%s, %s, 'pendiente', now())
                """,
                [ingreso_id, uid],
            )
        except Exception:
            pass  # tabla puede no existir; continuar con notificación

        # Enviar notificación por email (reportar éxito/fracaso)
        email_sent = False
        try:
            # Datos del ingreso para el cuerpo
            info = q(
                """
                SELECT c.razon_social AS cliente,
                       COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                       COALESCE(b.nombre,'') AS marca,
                       COALESCE(m.nombre,'') AS modelo,
                       COALESCE(d.numero_serie,'') AS numero_serie
                  FROM ingresos t
                  JOIN devices d   ON d.id = t.device_id
                  JOIN customers c ON c.id = d.customer_id
                  LEFT JOIN marcas b ON b.id = d.marca_id
                  LEFT JOIN models m ON m.id = d.model_id
                 WHERE t.id=%s
                """,
                [ingreso_id],
                one=True,
            ) or {}
            os_txt = os_label(ingreso_id)
            tech_name = getattr(request.user, "nombre", "")
            cliente = info.get("cliente") or ""
            equipo = " | ".join([p for p in [info.get("tipo_equipo") or "", info.get("marca") or "", info.get("modelo") or ""] if p])
            ns = info.get("numero_serie") or ""

            subject = f"Solicitud de asignación {os_txt} - {cliente}"
            lines = [
                f"El técnico {tech_name} solicita asignación.",
                f"OS: {os_txt}",
                f"Cliente: {cliente}",
                f"Equipo: {equipo or '-'}",
                f"N/S: {ns or '-'}",
            ]
            # Agregar link al frontend si está configurado
            fe = getattr(settings, "FRONTEND_ORIGIN", "") or ""
            if fe:
                lines.append("")
                try:
                    base = fe.rstrip('/')
                except Exception:
                    base = fe
                lines.append(f"Abrir hoja: {base}/ingresos/{ingreso_id}")
            body = "\n".join(lines)

            # Destinatarios: ASSIGNMENT_REQUEST_RECIPIENTS (coma), o fallback a emails conocidos
            recips = []
            try:
                raw = os.getenv("ASSIGNMENT_REQUEST_RECIPIENTS", "")
            except Exception:
                raw = ""
            if raw:
                recips = [x.strip() for x in raw.split(",") if x.strip()]
            # Fallbacks
            if not recips:
                fallback1 = getattr(settings, "COMPANY_FOOTER_EMAIL_2", None)
                fallback2 = getattr(settings, "COMPANY_FOOTER_EMAIL", None)
                recips = [x for x in [fallback1, fallback2] if x]

            if recips:
                try:
                    sent = send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", None), recips, fail_silently=False)
                    email_sent = bool(sent and sent > 0)
                except Exception:
                    email_sent = False
        except Exception:
            email_sent = False

        return Response({"ok": True, "email_sent": bool(email_sent)})


class PendientesGeneralView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        tecnico_raw = (request.GET.get("tecnico_id") or "").strip()

        with connection.cursor() as cur:
            _set_audit_user(request)

            sql = """
                SELECT t.id,
                       t.estado,
                       t.presupuesto_estado,
                       t.motivo,
                       c.razon_social,
                       d.numero_serie,
                       COALESCE(b.nombre,'') AS marca,
                       COALESCE(m.nombre,'') AS modelo,
                       COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                       NULLIF(t.equipo_variante,'') AS equipo_variante,
                       t.fecha_ingreso,
                       CASE WHEN ed.estado = 'devuelto' THEN true ELSE false END AS derivado_devuelto
                FROM ingresos t
                JOIN devices d   ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                LEFT JOIN (
                  SELECT e.*, ROW_NUMBER() OVER (
                    PARTITION BY e.ingreso_id ORDER BY e.fecha_deriv DESC, e.id DESC
                  ) AS rn
                  FROM equipos_derivados e
                ) ed ON ed.ingreso_id = t.id AND ed.rn = 1
                WHERE LOWER(loc.nombre) = LOWER(%s)
                  AND t.estado NOT IN ('liberado','entregado', 'alquilado')
            """
            params = ["taller"]
            if tecnico_raw.isdigit():
                sql += " AND t.asignado_a = %s"
                params.append(int(tecnico_raw))

            sql += """
                ORDER BY
                  (CASE WHEN ed.estado = 'devuelto' THEN 1 ELSE 0 END) DESC,
                  (t.motivo = 'urgente control') DESC,
                  t.fecha_ingreso ASC
            """
            cur.execute(sql, params)
            rows = _fetchall_dicts(cur)

        return Response(IngresoListItemSerializer(rows, many=True).data)


class IngresoHistorialView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "jefe_veedor", "admin"])
        if connection.vendor == "postgresql":
            # change_log (si existe) + audit_log
            rows = []
            try:
                rows = q(
                    """
                      SELECT ts, user_id, user_role, table_name, record_id, column_name, old_value, new_value
                      FROM audit.change_log
                      WHERE ingreso_id = %s
                      ORDER BY ts DESC, id DESC
                    """,
                    [ingreso_id]
                ) or []
            except Exception:
                rows = []
            # Complementar con auditoría HTTP (audit_log) para mostrar payloads
            pat1 = f"/api/ingresos/{ingreso_id}/%"
            pat2 = f"/api/ingresos/{ingreso_id}/"
            pat3 = f"/api/quotes/{ingreso_id}/%"
            pat4 = f"/api/quotes/{ingreso_id}/"
            al_rows = q(
                """
                SELECT id AS _id, ts, user_id, role AS user_role, method, path, body
                  FROM audit_log
                 WHERE path LIKE %s OR path = %s OR path LIKE %s OR path = %s
                 ORDER BY ts DESC, id DESC
                """,
                [pat1, pat2, pat3, pat4]
            ) or []
            out = []
            for r in (al_rows or []):
                path = (r.get("path") or "").lower()
                method = (r.get("method") or "").upper()
                table_name = "ingresos"
                record_id = ingreso_id
                if "/accesorios/" in path:
                    table_name = "ingreso_accesorios"
                elif "/fotos/" in path:
                    table_name = "ingreso_media"
                elif "/quotes/" in path or "/presupuestos/" in path:
                    table_name = "quotes"
                body = r.get("body")
                parsed = None
                if isinstance(body, (dict, list)):
                    parsed = body
                elif isinstance(body, str) and body.strip():
                    try:
                        parsed = json.loads(body)
                    except Exception:
                        parsed = None
                if not isinstance(parsed, dict):
                    out.append({
                        "ts": r.get("ts"),
                        "user_id": r.get("user_id"),
                        "user_role": r.get("user_role"),
                        "table_name": table_name,
                        "record_id": record_id,
                        "column_name": f"{method} {r.get('path')}",
                        "old_value": None,
                        "new_value": None,
                    })
                    continue
                for k, v in parsed.items():
                    if isinstance(v, (dict, list)):
                        new_v = json.dumps(v, ensure_ascii=False)[:512]
                    else:
                        new_v = str(v)
                    out.append({
                        "ts": r.get("ts"),
                        "user_id": r.get("user_id"),
                        "user_role": r.get("user_role"),
                        "table_name": table_name,
                        "record_id": record_id,
                        "column_name": k,
                        "old_value": None,
                        "new_value": new_v,
                    })
            rows = (rows or []) + out
            rows.sort(key=lambda x: (x.get("ts") or ""), reverse=True)
        else:
            # 1) Cambios de estado (ingreso_events)
            ev_rows = q(
                """
                SELECT 
                  e.id AS _id,
                  e.ts AS ts,
                  e.usuario_id AS user_id,
                  u.rol AS user_role,
                  'ingresos' AS table_name,
                  e.ingreso_id AS record_id,
                  'estado' AS column_name,
                  e.de_estado AS old_value,
                  e.a_estado AS new_value
                FROM ingreso_events e
                LEFT JOIN users u ON u.id = e.usuario_id
                WHERE e.ingreso_id = %s
                ORDER BY e.ts DESC, e.id DESC
                """,
                [ingreso_id]
            ) or []

            # 2) Cambios por HTTP (audit_log): mostramos payload por clave como "nuevo valor"
            pat1 = f"/api/ingresos/{ingreso_id}/%"
            pat2 = f"/api/ingresos/{ingreso_id}/"
            pat3 = f"/api/quotes/{ingreso_id}/%"
            pat4 = f"/api/quotes/{ingreso_id}/"
            al_rows = q(
                """
                SELECT id AS _id, ts, user_id, role AS user_role, method, path, body
                  FROM audit_log
                 WHERE path LIKE %s OR path = %s OR path LIKE %s OR path = %s
                 ORDER BY ts DESC, id DESC
                """,
                [pat1, pat2, pat3, pat4]
            ) or []

            out = list(ev_rows)
            for r in (al_rows or []):
                path = (r.get("path") or "").lower()
                method = (r.get("method") or "").upper()
                table_name = "ingresos"
                record_id = ingreso_id
                # Heurística por ruta
                if "/accesorios/" in path:
                    table_name = "ingreso_accesorios"
                elif "/fotos/" in path:
                    table_name = "ingreso_media"
                elif "/quotes/" in path or "/presupuestos/" in path:
                    table_name = "quotes"

                body = r.get("body")
                parsed = None
                if isinstance(body, (dict, list)):
                    parsed = body
                elif isinstance(body, str) and body.strip():
                    try:
                        parsed = json.loads(body)
                    except Exception:
                        parsed = None

                # Si no hay JSON, igual generamos una entrada genérica
                if not isinstance(parsed, dict):
                    out.append({
                        "ts": r.get("ts"),
                        "user_id": r.get("user_id"),
                        "user_role": r.get("user_role"),
                        "table_name": table_name,
                        "record_id": record_id,
                        "column_name": f"{method} {r.get('path')}",
                        "old_value": None,
                        "new_value": None,
                    })
                    continue

                # Expandimos por claves del payload
                for k, v in parsed.items():
                    # Valores como string (acotados) para visualización
                    if isinstance(v, (dict, list)):
                        new_v = json.dumps(v, ensure_ascii=False)[:512]
                    else:
                        new_v = str(v)
                    out.append({
                        "ts": r.get("ts"),
                        "user_id": r.get("user_id"),
                        "user_role": r.get("user_role"),
                        "table_name": table_name,
                        "record_id": record_id,
                        "column_name": k,
                        "old_value": None,
                        "new_value": new_v,
                    })

            # Orden final por fecha desc y sin modificar formato esperado
            out.sort(key=lambda x: (x.get("ts") or "",), reverse=True)
            rows = out
        return Response(rows)


class CerrarReparacionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe","jefe_veedor","admin"])
        r = (request.data or {}).get("resolucion")
        if r not in ("reparado","no_reparado","no_se_encontro_falla","presupuesto_rechazado"):
            return Response({"detail": "resolucion inválida"}, status=400)

        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute("""
                 UPDATE ingresos
                    SET resolucion = %s
                  WHERE id = %s
            """, [r, ingreso_id])
        return Response({"ok": True})


class NuevoIngresoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        # Best-effort: ensure PK sequences are aligned to prevent duplicate key
        # errors due to out-of-sync sequences after legacy imports.
        try:
            from .helpers_impl import repair_pk_sequence
            repair_pk_sequence('devices')
            repair_pk_sequence('ingresos')
        except Exception:
            pass
        data = request.data or {}
        cliente = data.get("cliente") or {}
        equipo = data.get("equipo") or {}

        # Empresa a facturar (branding de PDFs). Default SEPID; valida solo dos valores.
        empresa_facturar = (data.get("empresa_facturar") or "SEPID").strip().upper()
        if empresa_facturar not in ("SEPID", "MGBIO"):
            empresa_facturar = "SEPID"

        motivo_raw = (data.get("motivo") or "").strip()
        if not motivo_raw:
            return Response({"detail": "motivo requerido"}, status=400)

        motivo_label_raw = _map_motivo_to_db_label(motivo_raw)
        if not motivo_label_raw:
            valid_motivos = _get_motivo_enum_values()
            return Response({"detail": "motivo invalido", "valid_values": valid_motivos}, status=400)

        raw_vals = _get_motivo_enum_values_raw() or []
        if raw_vals:
            target = None
            norm_target = _norm_txt(motivo_label_raw)
            for rv in raw_vals:
                if _norm_txt(rv) == norm_target:
                    target = rv
                    break
            if not target:
                target = next((x for x in raw_vals if _norm_txt(x) == _norm_txt('otros')), raw_vals[0])
            motivo = target
        else:
            motivo = motivo_label_raw

        numero_interno = (equipo.get("numero_interno") or "").strip()
        if numero_interno and not numero_interno.upper().startswith("MG"):
            numero_interno = "MG " + numero_interno

        ubicacion_id = data.get("ubicacion_id")
        if not ubicacion_id:
            t = q("SELECT id FROM locations WHERE LOWER(nombre)=LOWER(%s) LIMIT 1", ["taller"], one=True)
            if not t:
                return Response({"detail": "No se encontro la ubicacion 'Taller' en el catalogo. Creala en 'locations'."}, status=400)
            ubicacion_id = t["id"]

        informe_preliminar = (data.get("informe_preliminar") or "").strip()
        accesorios_text = (data.get("accesorios") or "").strip()
        comentarios_text = (data.get("comentarios") or "").strip() or None
        accesorios_items = data.get("accesorios_items") or []

        remito_ingreso = (data.get("remito_ingreso") or "").strip()
        fecha_ingreso_dt = None
        _fi_raw = data.get("fecha_ingreso")
        if _fi_raw is not None and str(_fi_raw).strip() != "":
            _fi_str = str(_fi_raw).strip()
            _dt = parse_datetime(_fi_str)
            if not _dt:
                _d = parse_date(_fi_str)
                if _d:
                    from datetime import datetime as _dtc
                    _dt = _dtc(_d.year, _d.month, _d.day, 0, 0, 0)
            if _dt:
                if timezone.is_naive(_dt):
                    _dt = timezone.make_aware(_dt, timezone.get_current_timezone())
                fecha_ingreso_dt = _dt

        if not equipo.get("marca_id") or not equipo.get("modelo_id"):
            return Response({"detail": "equipo.marca_id y equipo.modelo_id son requeridos"}, status=400)

        c = None
        if cliente.get("id"):
            c = q("SELECT id, cod_empresa, razon_social FROM customers WHERE id=%s", [cliente["id"]], one=True)
        elif cliente.get("cod_empresa"):
            c = q("SELECT id, cod_empresa, razon_social FROM customers WHERE cod_empresa=%s", [cliente["cod_empresa"]], one=True)
        elif cliente.get("razon_social"):
            c = q("SELECT id, cod_empresa, razon_social FROM customers WHERE LOWER(razon_social)=LOWER(%s)", [cliente["razon_social"]], one=True)
        else:
            return Response({"detail": "Debe seleccionar un cliente"}, status=400)

        if not c:
            return Response({"detail": "Cliente inexistente"}, status=400)

        if cliente.get("cod_empresa") and c["cod_empresa"] != cliente["cod_empresa"]:
            return Response({"detail": "El codigo no corresponde a la razon social seleccionada."}, status=400)
        if cliente.get("razon_social") and c["razon_social"].lower() != (cliente["razon_social"] or "").lower():
            return Response({"detail": "La razon social no corresponde al codigo seleccionado."}, status=400)

        customer_id = c["id"]

        marca = q("SELECT id FROM marcas WHERE id=%s", [equipo["marca_id"]], one=True)
        model = q("SELECT id FROM models WHERE id=%s AND marca_id=%s", [equipo["modelo_id"], equipo["marca_id"]], one=True)
        if not marca or not model:
            return Response({"detail": "Marca o modelo inexistente"}, status=400)

        prop = data.get("propietario") or {}
        prop_nombre = (prop.get("nombre") or "").strip()
        prop_contacto = (prop.get("contacto") or "").strip()
        prop_doc = (prop.get("doc") or "").strip()

        numero_serie = (equipo.get("numero_serie") or "").strip()
        garantia_bool = bool(equipo.get("garantia"))

        if numero_serie:
            dup = q(
                """
                SELECT t.id
                  FROM ingresos t
                  JOIN devices d ON d.id = t.device_id
                 WHERE d.customer_id = %s
                   AND d.numero_serie = %s
                   AND t.estado <> 'entregado'
                 ORDER BY t.id DESC
                 LIMIT 1
                """,
                [customer_id, numero_serie],
                one=True,
            )
            if dup:
                existing_id = dup["id"]
                return Response({"ok": True, "ingreso_id": existing_id, "os": os_label(existing_id), "existing": True})

        # Auto-chequeo de garantía de fábrica por N/S si el usuario no la marcó
        if numero_serie and not garantia_bool:
            try:
                from ..trazabilidad import find_serial_sale_date
                fch, _meta = find_serial_sale_date(numero_serie)
                if fch is not None:
                    en_garantia = (timezone.localdate() - fch).days <= 365
                    if en_garantia:
                        garantia_bool = True
            except Exception:
                pass

        dev = None
        if numero_serie:
            dev = q(
                "SELECT id FROM devices WHERE numero_serie=%s AND customer_id=%s",
                [numero_serie, customer_id],
                one=True,
            )
        dev = dev if dev else None
        if dev:
            device_id = dev["id"]
        else:
            if connection.vendor == "postgresql":
                device_id = exec_returning(
                    """
                    INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
                    VALUES (%s, %s, %s, NULLIF(%s,''), %s, NULLIF(%s,''))
                    RETURNING id
                    """,
                    [customer_id, equipo["marca_id"], equipo["modelo_id"], numero_serie, garantia_bool, numero_interno]
                )
            else:
                exec_void(
                    """
                    INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
                    VALUES (%s, %s, %s, NULLIF(%s,''), %s, NULLIF(%s,''))
                    """,
                    [customer_id, equipo["marca_id"], equipo["modelo_id"], numero_serie, garantia_bool, numero_interno]
                )
                device_id = last_insert_id()
        if numero_interno:
            exec_void("UPDATE devices SET n_de_control = NULLIF(%s,'') WHERE id=%s", [numero_interno, device_id])

        auto_gar_rep = False
        last_out_candidates = []
        if numero_serie:
            row_last_ns = q(
                """
                SELECT MAX(t.fecha_entrega) AS last_out
                  FROM ingresos t
                  JOIN devices d ON d.id = t.device_id
                 WHERE d.numero_serie = %s
                   AND t.fecha_entrega IS NOT NULL
                """,
                [numero_serie],
                one=True,
            )
            last_ns = row_last_ns and row_last_ns.get("last_out")
            if last_ns:
                last_out_candidates.append(last_ns)
        if numero_interno:
            row_mg = q(
                """
                SELECT MAX(t.fecha_entrega) AS last_out
                  FROM ingresos t
                  JOIN devices d ON d.id = t.device_id
                 WHERE d.n_de_control = %s
                   AND t.fecha_entrega IS NOT NULL
                """,
                [numero_interno],
                one=True,
            )
            last_mg = row_mg and row_mg.get("last_out")
            if last_mg:
                last_out_candidates.append(last_mg)
        if last_out_candidates:
            try:
                last_out = max(last_out_candidates)
                auto_gar_rep = (timezone.now() - last_out).days <= 90
            except Exception:
                auto_gar_rep = False
        garantia_rep_payload = bool(data.get("garantia_reparacion"))
        garantia_rep_final = garantia_rep_payload or auto_gar_rep

        tecnico_id = data.get("tecnico_id")
        if not tecnico_id:
            tdef = q("SELECT tecnico_id FROM models WHERE id=%s", [equipo["modelo_id"]], one=True)
            tecnico_id = tdef["tecnico_id"] if tdef else None
        if not tecnico_id:
            tmarca = q("SELECT tecnico_id FROM marcas WHERE id=%s", [equipo["marca_id"]], one=True)
            tecnico_id = (tmarca or {}).get("tecnico_id")
        if tecnico_id:
            tech = q("SELECT id FROM users WHERE id=%s AND activo=true AND rol IN ('tecnico','jefe')",
                     [tecnico_id], one=True)
            if not tech:
                return Response({"detail": "Tecnico invalido o inactivo"}, status=400)

        uid = getattr(request.user, "id", None) or getattr(request, "user_id", None)
        if not uid:
            return Response({"detail": "Usuario no autenticado"}, status=401)
        _set_audit_user(request)

        # PostgreSQL-only build: motivo es texto válido según enum del modelo

        equipo_variante = (request.data.get("equipo_variante") or "").strip() or None
        ingreso_id = exec_returning(
            """
            INSERT INTO ingresos (
              device_id, motivo, ubicacion_id, recibido_por, asignado_a,
              informe_preliminar, accesorios, comentarios, equipo_variante,
              propietario_nombre, propietario_contacto, propietario_doc,
              garantia_reparacion
            )
            VALUES (%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,
                    NULLIF(%s,''), NULLIF(%s,''), NULLIF(%s,''),
                    %s)
            RETURNING id
            """,
            [device_id, motivo, ubicacion_id, uid, tecnico_id,
             informe_preliminar, accesorios_text, comentarios_text, equipo_variante,
             prop_nombre, prop_contacto, prop_doc,
             garantia_rep_final]
        )

        # Setear empresa_facturar si la columna existe en la base
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                     WHERE table_name = 'ingresos'
                       AND column_name = 'empresa_facturar'
                       AND table_schema = ANY(current_schemas(true))
                     LIMIT 1
                    """
                )
                exists = cur.fetchone() is not None
                if exists:
                    exec_void("UPDATE ingresos SET empresa_facturar=%s WHERE id=%s", [empresa_facturar, ingreso_id])
        except Exception:
            # Mejor no romper si no existe la columna
            pass

        sets, params = [], []
        if remito_ingreso:
            sets.append("remito_ingreso = NULLIF(%s,'')")
            params.append(remito_ingreso)
        if fecha_ingreso_dt is not None:
            sets.append("fecha_ingreso = %s")
            params.append(fecha_ingreso_dt)
        if fecha_ingreso_dt is None:
            sets.append("fecha_ingreso = COALESCE(fecha_ingreso, NOW())")

        if sets:
            params.append(ingreso_id)
            exec_void(
                f"UPDATE ingresos SET {', '.join(sets)} WHERE id=%s",
                params,
            )

        for it in (accesorios_items or []):
            try:
                acc_id = int(it.get("accesorio_id"))
            except (TypeError, ValueError):
                continue
            ref = (it.get("referencia") or "").strip() or None
            desc = (it.get("descripcion") or "").strip() or None
            exec_void(
              "INSERT INTO ingreso_accesorios(ingreso_id, accesorio_id, referencia, descripcion) VALUES (%s,%s,%s,%s)",
              [ingreso_id, acc_id, ref, desc]
            )

        return Response({"ok": True, "ingreso_id": ingreso_id, "os": os_label(ingreso_id)}, status=201)


class GarantiaReparacionCheckView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        ns = (request.GET.get("numero_serie") or "").strip()
        mg = (request.GET.get("numero_interno") or request.GET.get("mg") or "").strip()
        if mg and not mg.upper().startswith("MG"):
            mg = "MG " + mg
        if not ns and not mg:
            return Response({"within_90_days": False, "last_ingreso": None})

        last_out_candidates = []
        if ns:
            row_ns = q(
                """
                SELECT MAX(t.fecha_entrega) AS last_out
                  FROM ingresos t
                  JOIN devices d ON d.id = t.device_id
                 WHERE d.numero_serie = %s
                   AND t.fecha_entrega IS NOT NULL
                """,
                [ns],
                one=True,
            )
            last_ns = row_ns and row_ns.get("last_out")
            if last_ns:
                last_out_candidates.append(last_ns)

        if mg:
            row_mg = q(
                """
                SELECT MAX(t.fecha_entrega) AS last_out
                  FROM ingresos t
                  JOIN devices d ON d.id = t.device_id
                 WHERE d.n_de_control = %s
                   AND t.fecha_entrega IS NOT NULL
                """,
                [mg],
                one=True,
            )
            last_mg = row_mg and row_mg.get("last_out")
            if last_mg:
                last_out_candidates.append(last_mg)

        if not last_out_candidates:
            return Response({"within_90_days": False, "last_ingreso": None})

        last_out = max(last_out_candidates)
        within = (timezone.now() - last_out).days <= 90
        return Response({"within_90_days": within, "last_ingreso": last_out})


class GarantiaFabricaCheckView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        from ..trazabilidad import find_serial_sale_date
        ns = (request.GET.get("numero_serie") or "").strip()
        marca = (request.GET.get("marca") or "").strip()
        if not ns:
            return Response({"within_365_days": False, "fecha_venta": None, "found": False})
        fecha, meta = find_serial_sale_date(ns, brand_hint=marca or None)
        if not fecha:
            return Response({"within_365_days": False, "fecha_venta": None, "found": False})
        # Comparar con hoy (timezone aware -> usar date de Buenos Aires)
        today = timezone.localdate()
        within = (today - fecha).days <= 365
        return Response({
            "within_365_days": bool(within),
            "fecha_venta": fecha.isoformat(),
            "found": True,
            "meta": meta,
        })


class IngresoDetalleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ingreso_id: int):
        row = q(
            """
            SELECT
              t.id,
              t.motivo,
              t.estado,
              t.presupuesto_estado,
              t.resolucion,
              t.fecha_ingreso,
              t.fecha_servicio,
              t.garantia_reparacion,
              t.faja_garantia,
              t.remito_ingreso,
              t.remito_salida,
              t.factura_numero,
              t.fecha_entrega,
              t.alquilado,
              t.alquiler_a,
              t.alquiler_remito,
              t.alquiler_fecha,
              t.informe_preliminar,
              t.descripcion_problema,
              t.trabajos_realizados,
              t.comentarios,
              t.accesorios,
              t.equipo_variante,
              t.ubicacion_id,
              COALESCE(l.nombre,'') AS ubicacion_nombre,
              t.asignado_a,
              COALESCE(u.nombre,'') AS asignado_a_nombre,
              t.propietario_nombre,
              t.propietario_contacto,
              t.propietario_doc,
              d.id AS device_id,
              COALESCE(d.numero_serie,'') AS numero_serie,
              COALESCE(d.n_de_control,'') AS numero_interno,
              COALESCE(d.garantia_bool,false) AS garantia,
              d.marca_id,
              COALESCE(b.nombre,'') AS marca,
              d.model_id,
              COALESCE(m.nombre,'') AS modelo,
              COALESCE(m.tipo_equipo,'') AS tipo_equipo,
              COALESCE(m.tipo_equipo,'') AS tipo_equipo,
              c.id AS customer_id,
              c.razon_social,
              c.cod_empresa,
              c.telefono
            FROM ingresos t
            JOIN devices d ON d.id = t.device_id
            JOIN customers c ON c.id = d.customer_id
            LEFT JOIN marcas b ON b.id = d.marca_id
            LEFT JOIN models m ON m.id = d.model_id
            LEFT JOIN locations l ON l.id = t.ubicacion_id
            LEFT JOIN users u ON u.id = t.asignado_a
            WHERE t.id = %s
            """,
            [ingreso_id],
            one=True,
        )
        if not row:
            return Response({"detail": "Ingreso no encontrado"}, status=404)
        row["os"] = os_label(row["id"])
        if not row.get("fecha_creacion"):
            row["fecha_creacion"] = row.get("fecha_ingreso")
        if "tipo_equipo_nombre" not in row:
            row["tipo_equipo_nombre"] = row.get("tipo_equipo") or ""
        try:
            from datetime import date as _date, datetime as _dt
            fs = row.get("fecha_servicio")
            if fs and isinstance(fs, _date) and not isinstance(fs, _dt):
                row["fecha_servicio"] = _dt(fs.year, fs.month, fs.day, 0, 0, 0, tzinfo=None)
        except Exception:
            pass
        accs = q(
            """
          SELECT ia.id, ia.accesorio_id, ca.nombre AS accesorio_nombre, ia.referencia, ia.descripcion
          FROM ingreso_accesorios ia
          JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id AND ca.activo
          WHERE ia.ingreso_id=%s
          ORDER BY ia.id
            """,
            [ingreso_id],
        )
        row["accesorios_items"] = accs
        # Resolver técnico solicitado (última solicitud pendiente si existe)
        try:
            req = q(
                """
                SELECT r.usuario_id AS uid, COALESCE(u.nombre,'') AS nombre
                  FROM ingreso_assignment_requests r
                  LEFT JOIN users u ON u.id = r.usuario_id
                 WHERE r.ingreso_id = %s
                   AND r.canceled_at IS NULL
                   AND (r.accepted_at IS NULL)
                 ORDER BY r.created_at DESC, r.id DESC
                 LIMIT 1
                """,
                [ingreso_id],
                one=True,
            )
        except Exception:
            req = None
        if not req:
            # Fallback: usar audit_log si la auditoría está habilitada/cargada
            try:
                path1 = f"/api/ingresos/{ingreso_id}/solicitar-asignacion/"
                path2 = f"/api/ingresos/{ingreso_id}/solicitar-asignacion"
                req = q(
                    """
                    SELECT al.user_id AS uid, COALESCE(u.nombre,'') AS nombre
                      FROM audit_log al
                      LEFT JOIN users u ON u.id = al.user_id
                     WHERE al.method = 'POST'
                       AND (al.path = %s OR al.path = %s)
                     ORDER BY al.ts DESC, al.id DESC
                     LIMIT 1
                    """,
                    [path1, path2],
                    one=True,
                )
            except Exception:
                req = None
        if req:
            row["tecnico_solicitado_id"] = req.get("uid")
            row["tecnico_solicitado_nombre"] = req.get("nombre") or ""
        else:
            row["tecnico_solicitado_id"] = None
            row["tecnico_solicitado_nombre"] = ""
        return Response(IngresoDetailWithAccesoriosSerializer(row).data)

    def patch(self, request, ingreso_id: int):
        ROL_EDIT_DIAG = {"tecnico", "jefe", "jefe_veedor", "admin"}
        ROL_EDIT_UBIC = {"tecnico", "jefe", "jefe_veedor", "admin", "recepcion"}
        ROL_EDIT_BASICS = {"jefe", "jefe_veedor", "admin"}

        rol = _rol(request)
        d = request.data or {}
        _set_audit_user(request)
        if connection.vendor == "postgresql":
            exec_void("SET LOCAL app.ingreso_id = %s", [ingreso_id])

        row_est = q("SELECT estado, asignado_a FROM ingresos WHERE id=%s", [ingreso_id], one=True)
        if not row_est:
            return Response({"detail": "Ingreso no encontrado"}, status=404)
        estado_actual = (row_est["estado"] or "").lower()
        asignado_a = row_est["asignado_a"]

        sets_no_estado, params_no_estado = [], []

        if "ubicacion_id" in d:
            if rol not in ROL_EDIT_UBIC:
                raise PermissionDenied("No autorizado para modificar ubicacion")
            ubicacion_id = d.get("ubicacion_id")
            if not ubicacion_id:
                raise ValidationError("ubicacion_id requerido")
            u = q("SELECT id FROM locations WHERE id=%s", [ubicacion_id], one=True)
            if not u:
                raise ValidationError("Ubicacion inexistente")
            sets_no_estado.append("ubicacion_id=%s")
            params_no_estado.append(ubicacion_id)

        desc_present = False
        trab_present = False
        fecha_present = False
        if "descripcion_problema" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado para modificar diagnostico")
            desc = (d.get("descripcion_problema") or "").strip()
            desc_present = bool(desc)
            sets_no_estado.append("descripcion_problema=%s")
            params_no_estado.append(desc)
        if "trabajos_realizados" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado para modificar trabajos")
            trab_present = bool((d.get("trabajos_realizados") or "").strip())
            sets_no_estado.append("trabajos_realizados=%s")
            params_no_estado.append(d.get("trabajos_realizados"))
        if "accesorios" in d:
            if rol not in ROL_EDIT_UBIC:
                raise PermissionDenied("No autorizado para modificar accesorios")
            sets_no_estado.append("accesorios=%s")
            params_no_estado.append(d.get("accesorios"))
        if "fecha_servicio" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado para modificar fecha de servicio")
            val = d.get("fecha_servicio")
            if val is None or (isinstance(val, str) and val.strip() == ""):
                sets_no_estado.append("fecha_servicio=NULL")
            else:
                dt = parse_datetime(val)
                if not dt:
                    raise ValidationError("fecha_servicio invalida")
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_current_timezone())
                sets_no_estado.append("fecha_servicio=%s")
                params_no_estado.append(dt)
                fecha_present = True
        # Si el rol es técnico, solo el asignado puede editar diagnóstico/trabajos/fecha
        if rol == "tecnico" and any(k in d for k in ("descripcion_problema", "trabajos_realizados", "fecha_servicio")):
            uid = getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", None)
            if int(asignado_a or 0) != int(uid or 0):
                raise PermissionDenied("Solo el técnico asignado puede editar diagnóstico y reparación")
        if any(k in d for k in ("remito_salida", "factura_numero", "fecha_entrega")):
            if _rol(request) not in {"jefe", "jefe_veedor", "admin", "recepcion"}:
                raise PermissionDenied("No autorizado para editar datos de entrega")
            if "remito_salida" in d:
                sets_no_estado.append("remito_salida = NULLIF(%s,'')")
                params_no_estado.append((d.get("remito_salida") or "").strip())
            if "factura_numero" in d:
                sets_no_estado.append("factura_numero = NULLIF(%s,'')")
                params_no_estado.append((d.get("factura_numero") or "").strip())
            if "fecha_entrega" in d:
                val = d.get("fecha_entrega")
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    sets_no_estado.append("fecha_entrega=NULL")
                else:
                    dt = parse_datetime(val)
                    if not dt:
                        raise ValidationError("fecha_entrega invalida")
                    if timezone.is_naive(dt):
                        dt = timezone.make_aware(dt, timezone.get_current_timezone())
                    sets_no_estado.append("fecha_entrega=%s")
                    params_no_estado.append(dt)
        if "garantia_reparacion" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado")
            sets_no_estado.append("garantia_reparacion=%s")
            params_no_estado.append(bool(d.get("garantia_reparacion")))
        if "faja_garantia" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado")
            sets_no_estado.append("faja_garantia = NULLIF(%s,'')")
            params_no_estado.append((d.get("faja_garantia") or "").strip())
        if "numero_interno" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado")
            val = (d.get("numero_interno") or "").strip()
            if val and not val.upper().startswith("MG"):
                val = "MG " + val
            exec_void(
                "UPDATE devices SET n_de_control = NULLIF(%s,'') WHERE id = (SELECT device_id FROM ingresos WHERE id=%s)",
                [val, ingreso_id]
            )
        if any(k in d for k in ("propietario_nombre", "propietario_contacto", "propietario_doc")):
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar datos del propietario")
            if "propietario_nombre" in d:
                sets_no_estado.append("propietario_nombre = NULLIF(%s,'')")
                params_no_estado.append((d.get("propietario_nombre") or "").strip())
            if "propietario_contacto" in d:
                sets_no_estado.append("propietario_contacto = NULLIF(%s,'')")
                params_no_estado.append((d.get("propietario_contacto") or "").strip())
            if "propietario_doc" in d:
                sets_no_estado.append("propietario_doc = NULLIF(%s,'')")
                params_no_estado.append((d.get("propietario_doc") or "").strip())
        if any(k in d for k in ("razon_social", "cod_empresa", "telefono")):
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar datos del cliente")
            rs = d.get("razon_social")
            ce = d.get("cod_empresa")
            tel = d.get("telefono")
            sets, params = [], []
            if rs is not None:
                sets.append("razon_social = NULLIF(%s,'')")
                params.append((rs or "").strip())
            if ce is not None:
                sets.append("cod_empresa = NULLIF(%s,'')")
                params.append((ce or "").strip())
            if tel is not None:
                sets.append("telefono = NULLIF(%s,'')")
                params.append((tel or "").strip())
            if sets:
                params.append(ingreso_id)
                exec_void(
                    f"""
                    UPDATE customers
                       SET {', '.join(sets)}
                     WHERE id = (
                        SELECT d.customer_id FROM devices d
                        JOIN ingresos t ON t.device_id = d.id
                        WHERE t.id=%s
                     )
                    """,
                    params,
                )
        if "numero_serie" in d:
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar N/S")
            ns = (d.get("numero_serie") or "").strip()
            exec_void(
                "UPDATE devices SET numero_serie = NULLIF(%s,'') WHERE id = (SELECT device_id FROM ingresos WHERE id=%s)",
                [ns, ingreso_id],
            )
            # Si no vino 'garantia' explícito, auto-chequear por N/S
            if "garantia" not in d:
                try:
                    from ..trazabilidad import find_serial_sale_date
                    fch, _meta = find_serial_sale_date(ns)
                    if fch is not None:
                        en_garantia = (timezone.localdate() - fch).days <= 365
                        exec_void(
                            "UPDATE devices SET garantia_bool=%s WHERE id = (SELECT device_id FROM ingresos WHERE id=%s)",
                            [bool(en_garantia), ingreso_id],
                        )
                except Exception:
                    pass
        # Permitir actualizar variante de equipo (texto libre)
        if "equipo_variante" in d:
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar variante del equipo")
            sets_no_estado.append("equipo_variante = NULLIF(%s,'')")
            params_no_estado.append((d.get("equipo_variante") or "").strip())
        if "remito_ingreso" in d:
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar remito de ingreso")
            sets_no_estado.append("remito_ingreso = NULLIF(%s,'')")
            params_no_estado.append((d.get("remito_ingreso") or "").strip())
        if "informe_preliminar" in d:
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar informe preliminar")
            sets_no_estado.append("informe_preliminar = NULLIF(%s,'')")
            params_no_estado.append((d.get("informe_preliminar") or "").strip())
        if "garantia" in d:
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar garantia de fábrica")
            exec_void(
                "UPDATE devices SET garantia_bool=%s WHERE id = (SELECT device_id FROM ingresos WHERE id=%s)",
                [bool(d.get("garantia")), ingreso_id],
            )
        if "comentarios" in d:
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar comentarios")
            sets_no_estado.append("comentarios = NULLIF(%s,'')")
            params_no_estado.append((d.get("comentarios") or "").strip())
        # Actualizar marca/modelo del dispositivo asociado al ingreso
        if ("marca_id" in d) or ("modelo_id" in d):
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar marca/modelo")
            marca_id = d.get("marca_id")
            modelo_id = d.get("modelo_id")
            # Traer device actual
            cur_dev = q("SELECT device_id FROM ingresos WHERE id=%s", [ingreso_id], one=True)
            if not cur_dev:
                return Response({"detail": "Ingreso no encontrado"}, status=404)
            device_id = cur_dev["device_id"]
            if modelo_id is not None:
                # Validar modelo y obtener su marca
                md = q("SELECT id, marca_id FROM models WHERE id=%s", [modelo_id], one=True)
                if not md:
                    raise ValidationError("modelo_id invalido")
                modelo_marca = md["marca_id"]
                if marca_id is not None and int(marca_id) != int(modelo_marca):
                    raise ValidationError("modelo_id no pertenece a la marca_id indicada")
                # Ajustar marca al del modelo si no fue provista
                exec_void("UPDATE devices SET model_id=%s, marca_id=%s WHERE id=%s", [modelo_id, modelo_marca, device_id])
            elif marca_id is not None:
                # Validar marca
                mk = q("SELECT id FROM marcas WHERE id=%s", [marca_id], one=True)
                if not mk:
                    raise ValidationError("marca_id invalida")
                # Si el modelo actual no corresponde a la nueva marca, ponerlo en NULL
                row = q("SELECT model_id FROM devices WHERE id=%s", [device_id], one=True)
                cur_model = row and row.get("model_id")
                if cur_model:
                    ok = q("SELECT 1 FROM models WHERE id=%s AND marca_id=%s", [cur_model, marca_id], one=True)
                    if not ok:
                        exec_void("UPDATE devices SET marca_id=%s, model_id=NULL WHERE id=%s", [marca_id, device_id])
                    else:
                        exec_void("UPDATE devices SET marca_id=%s WHERE id=%s", [marca_id, device_id])
        if "alquilado" in d:
            if rol not in ROL_EDIT_UBIC:
                raise PermissionDenied("No autorizado")
            sets_no_estado.append("alquilado=%s")
            params_no_estado.append(bool(d.get("alquilado")))
            try:
                if bool(d.get("alquilado")):
                    sets_no_estado.append("estado='alquilado'")
            except Exception:
                pass
        if "alquiler_a" in d:
            if rol not in ROL_EDIT_UBIC:
                raise PermissionDenied("No autorizado")
            sets_no_estado.append("alquiler_a=NULLIF(%s,'')")
            params_no_estado.append((d.get("alquiler_a") or "").strip())
        if "alquiler_remito" in d:
            if rol not in ROL_EDIT_UBIC:
                raise PermissionDenied("No autorizado")
            sets_no_estado.append("alquiler_remito=NULLIF(%s,'')")
            params_no_estado.append((d.get("alquiler_remito") or "").strip())
        if "alquiler_fecha" in d:
            if rol not in ROL_EDIT_UBIC:
                raise PermissionDenied("No autorizado")
            sets_no_estado.append("alquiler_fecha=%s")
            params_no_estado.append(d.get("alquiler_fecha") or None)

        diag_present = desc_present or trab_present or fecha_present
        promote_from_ingresado = diag_present and estado_actual == "ingresado"
        promote_from_asignado = diag_present and estado_actual == "asignado"
        if promote_from_ingresado:
            if not asignado_a:
                raise ValidationError("Antes de diagnosticar, asigne un tecnico al ingreso")
            with transaction.atomic():
                if sets_no_estado:
                    params_tmp = list(params_no_estado) + [ingreso_id]
                    q(f"UPDATE ingresos SET {', '.join(sets_no_estado)} WHERE id=%s", params_tmp)
                q("UPDATE ingresos SET estado='diagnosticado' WHERE id=%s AND estado='ingresado'", [ingreso_id])
            return Response({"ok": True})
        if promote_from_asignado:
            sets_no_estado.append("estado='diagnosticado'")
        if not sets_no_estado:
            return Response({"ok": True})
        params_no_estado.append(ingreso_id)
        q(f"UPDATE ingresos SET {', '.join(sets_no_estado)} WHERE id=%s", params_no_estado)
        return Response({"ok": True})


__all__ = [
    'MisPendientesView',
    'PendientesPresupuestoView',
    'PresupuestadosView',
    'AprobadosParaRepararView',
    'AprobadosYReparadosView',
    'LiberadosView',
    'GeneralEquiposView',
    'GeneralPorClienteView',
    'MarcarReparadoView',
    'EntregarIngresoView',
    'IngresoAsignarTecnicoView',
    'PendientesGeneralView',
    'IngresoHistorialView',
    'CerrarReparacionView',
]
