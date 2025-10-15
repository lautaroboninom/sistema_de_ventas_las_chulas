import os
from django.conf import settings
from django.db import connection, transaction
from django.http import HttpResponse

from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from ..pdf import render_quote_pdf
from ..serializers import (
    QuoteDetailSerializer,
)
from .helpers import (
    q,
    exec_void,
    exec_returning,
    money,
    require_roles,
    _set_audit_user,
    _frontend_url,
)


def _ensure_quote(ingreso_id: int):
    """Return quote id for ingreso, creating it if missing.

    Handles possible PK sequence desync safely using a savepoint so that a
    failed insert does not leave the transaction in broken state.
    """
    row = q("SELECT id FROM quotes WHERE ingreso_id=%s", [ingreso_id], one=True)
    if row:
        return row["id"]

    # Attempt insert inside a savepoint; if it fails, the savepoint rollback
    # will clear the aborted state so we can continue.
    try:
        with transaction.atomic():
            new_id = exec_returning(
                "INSERT INTO quotes(ingreso_id) VALUES (%s) RETURNING id",
                [ingreso_id],
            )
            return new_id
    except Exception:
        # If another request raced or sequence was fixed, the row may exist now
        row2 = q("SELECT id FROM quotes WHERE ingreso_id=%s", [ingreso_id], one=True)
        if row2:
            return row2["id"]
        # Proactive sequence resync + retry once inside a savepoint
        if connection.vendor == "postgresql":
            try:
                with transaction.atomic():
                    with connection.cursor() as cur:
                        cur.execute(
                            "SELECT setval(pg_get_serial_sequence('quotes','id'), COALESCE((SELECT MAX(id) FROM quotes), 1))"
                        )
                    new_id2 = exec_returning(
                        "INSERT INTO quotes(ingreso_id) VALUES (%s) RETURNING id",
                        [ingreso_id],
                    )
                    return new_id2
            except Exception:
                pass
        # Last check
        row3 = q("SELECT id FROM quotes WHERE ingreso_id=%s", [ingreso_id], one=True)
        if row3:
            return row3["id"]
        # Give up; propagate to caller
        raise


def _load_quote_payload(ingreso_id: int):
    head = q(
        """
        SELECT q.id AS quote_id, q.estado, q.moneda, q.subtotal, q.iva_21, q.total
        FROM quotes q
        WHERE q.ingreso_id=%s
        """,
        [ingreso_id],
        one=True,
    )

    if not head:
        qid = _ensure_quote(ingreso_id)
        head = q(
            """
            SELECT q.id AS quote_id, q.estado, q.moneda, q.subtotal, q.iva_21, q.total
            FROM quotes q WHERE q.id=%s
            """,
            [qid],
            one=True,
        )

    items = q(
        """
        SELECT
          qi.id, qi.tipo, qi.repuesto_id, qi.descripcion, qi.qty, qi.precio_u,
          ROUND(qi.qty * qi.precio_u, 2) AS subtotal
        FROM quote_items qi
        JOIN quotes q ON q.id = qi.quote_id
        WHERE q.ingreso_id=%s
        ORDER BY qi.id ASC
        """,
        [ingreso_id],
    ) or []

    tot_rep = q(
        """
        SELECT COALESCE(SUM(qi.qty*qi.precio_u),0) AS x
        FROM quote_items qi
        JOIN quotes q ON q.id=qi.quote_id
        WHERE q.ingreso_id=%s AND qi.tipo='repuesto'
        """,
        [ingreso_id],
        one=True,
    )["x"]

    mano_obra = q(
        """
        SELECT COALESCE(SUM(qi.qty*qi.precio_u),0) AS x
        FROM quote_items qi
        JOIN quotes q ON q.id=qi.quote_id
        WHERE q.ingreso_id=%s AND qi.tipo='mano_obra'
        """,
        [ingreso_id],
        one=True,
    )["x"]

    subtotal_calc = sum((it.get("subtotal") or money(0)) for it in items)
    subtotal_calc = money(subtotal_calc)

    IVA = money("0.21")
    iva21_calc = money(subtotal_calc * IVA)
    total_calc = money(subtotal_calc + iva21_calc)

    return {
        "ingreso_id": ingreso_id,
        "quote_id": head["quote_id"],
        "estado": head["estado"],
        "moneda": head["moneda"],
        "items": items,
        "tot_repuestos": tot_rep,
        "mano_obra": mano_obra,
        "subtotal": subtotal_calc,
        "iva_21": iva21_calc,
        "total": total_calc,
    }


class QuoteDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor", "tecnico", "recepcion"])
        _ensure_quote(ingreso_id)
        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)


class QuoteItemsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor", "tecnico"])
        d = request.data or {}
        tipo = (d.get("tipo") or "").strip()
        if tipo not in ("repuesto", "mano_obra", "servicio"):
            raise ValidationError("tipo inválido")
        desc = (d.get("descripcion") or "").strip()
        if not desc:
            raise ValidationError("descripcion requerida")

        try:
            qty = money(d.get("qty"))
            precio = money(d.get("precio_u"))
        except (TypeError, ValueError):
            raise ValidationError("qty y precio_u deben ser numéricos")
        if qty < 0 or precio < 0:
            raise ValidationError("qty y precio_u no pueden ser negativos")
        repuesto_id = d.get("repuesto_id")

        qid = _ensure_quote(ingreso_id)
        _set_audit_user(request)
        exec_void(
            """
            INSERT INTO quote_items(quote_id, tipo, descripcion, qty, precio_u, repuesto_id)
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            [qid, tipo, desc, qty, precio, repuesto_id],
        )
        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data, status=201)


class QuoteItemDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, ingreso_id: int, item_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor", "tecnico"])
        d = request.data or {}
        sets, params = [], []
        if "tipo" in d:
            t = (d.get("tipo") or "").strip()
            if t not in ("repuesto", "mano_obra", "servicio"):
                raise ValidationError("tipo inválido")
            sets.append("tipo=%s"); params.append(t)
        if "descripcion" in d:
            sets.append("descripcion=%s"); params.append((d.get("descripcion") or "").strip())
        if "qty" in d:
            try:
                qv = float(d.get("qty"))
            except (TypeError, ValueError):
                raise ValidationError("qty debe ser numérico")
            if qv < 0:
                raise ValidationError("qty no puede ser negativo")
            sets.append("qty=%s"); params.append(qv)
        if "precio_u" in d:
            try:
                pv = float(d.get("precio_u"))
            except (TypeError, ValueError):
                raise ValidationError("precio_u debe ser numérico")
            if pv < 0:
                raise ValidationError("precio_u no puede ser negativo")
            sets.append("precio_u=%s"); params.append(pv)
        if "repuesto_id" in d:
            sets.append("repuesto_id=%s"); params.append(d.get("repuesto_id"))

        if sets:
            _set_audit_user(request)
            params += [ingreso_id, item_id]
            exec_void(
                f"""
                UPDATE quote_items qi
                   SET {', '.join(sets)}
                FROM quotes q
                WHERE qi.quote_id=q.id AND q.ingreso_id=%s AND qi.id=%s
                """,
                params,
            )
        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)

    def delete(self, request, ingreso_id: int, item_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor", "tecnico"])
        _set_audit_user(request)
        exec_void(
            """
            DELETE FROM quote_items qi
            USING quotes q
            WHERE qi.quote_id=q.id AND q.ingreso_id=%s AND qi.id=%s
            """,
            [ingreso_id, item_id],
        )
        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)


class QuoteResumenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor", "tecnico"])
        mo = request.data.get("mano_obra")
        if mo is None:
            raise ValidationError("mano_obra requerido")
        try:
            mo = float(mo)
        except (TypeError, ValueError):
            raise ValidationError("mano_obra debe ser numérico")
        if mo < 0:
            raise ValidationError("mano_obra no puede ser negativo")

        qid = _ensure_quote(ingreso_id)
        _set_audit_user(request)
        row = q(
            "SELECT id FROM quote_items WHERE quote_id=%s AND tipo='mano_obra' ORDER BY id LIMIT 1",
            [qid],
            one=True,
        )
        if row:
            exec_void(
                "UPDATE quote_items SET qty=1, precio_u=%s, descripcion='Mano de obra' WHERE id=%s",
                [mo, row["id"]],
            )
        else:
            exec_void(
                "INSERT INTO quote_items(quote_id, tipo, descripcion, qty, precio_u) VALUES (%s,'mano_obra','Mano de obra',1,%s)",
                [qid, mo],
            )
        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)


class EmitirPresupuestoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        autorizado_por = (request.data.get("autorizado_por") or "Cliente").strip()
        forma_pago = (request.data.get("forma_pago") or "A definir").strip()
        qid = _ensure_quote(ingreso_id)
        _set_audit_user(request)
        exec_void(
            """
            UPDATE quotes
               SET estado='presupuestado',
                   autorizado_por=%s,
                   forma_pago=%s,
                   fecha_emitido=now()
             WHERE id=%s
            """,
            [autorizado_por, forma_pago, qid],
        )
        exec_void("UPDATE ingresos SET presupuesto_estado='presupuestado' WHERE id=%s", [ingreso_id])

        fname, pdf = render_quote_pdf(ingreso_id)
        try:
            save_dir = getattr(settings, "QUOTES_SAVE_DIR", None)
            if save_dir and pdf:
                os.makedirs(save_dir, exist_ok=True)
                dest = os.path.join(save_dir, fname)
                with open(dest, "wb") as f:
                    f.write(pdf)
        except Exception:
            pass
        pdf_url = f"/api/quotes/{ingreso_id}/pdf/"
        exec_void("UPDATE quotes SET pdf_url=%s WHERE id=%s", [pdf_url, qid])
        data = _load_quote_payload(ingreso_id); data["pdf_url"] = pdf_url
        return Response(QuoteDetailSerializer(data).data)


class QuotePdfView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor", "tecnico", "recepcion"])
        fname, pdf = render_quote_pdf(ingreso_id)
        if not pdf:
            raise ValidationError("Ingreso no encontrado o sin presupuesto")
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{fname}"'
        return resp


class AprobarPresupuestoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        qid = _ensure_quote(ingreso_id)
        _set_audit_user(request)
        exec_void(
            """
            UPDATE quotes
               SET estado='aprobado',
                   fecha_aprobado=now()
             WHERE id=%s
            """,
            [qid],
        )
        exec_void(
            """
            UPDATE ingresos
               SET presupuesto_estado='aprobado',
                   estado = CASE
                              WHEN estado IN ('ingresado','diagnosticado','presupuestado')
                              THEN 'reparar'
                              ELSE estado
                            END
             WHERE id=%s
            """,
            [ingreso_id],
        )

        try:
            row = q(
                """
                SELECT
                  u.email, COALESCE(u.nombre,'') AS tecnico_nombre,
                  c.razon_social AS cliente,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                  COALESCE(d.numero_serie,'') AS numero_serie
                FROM ingresos t
                LEFT JOIN users   u ON u.id = t.asignado_a
                JOIN devices      d ON d.id = t.device_id
                JOIN customers    c ON c.id = d.customer_id
                LEFT JOIN marcas  b ON b.id = d.marca_id
                LEFT JOIN models  m ON m.id = d.model_id
                WHERE t.id=%s
                """,
                [ingreso_id],
                one=True,
            ) or {}
            to_email = (row.get("email") or "").strip()
            if to_email:
                os_label = f"OS {str(ingreso_id).zfill(6)}"
                link = _frontend_url(request, f"/ingresos/{ingreso_id}")
                subject = f"{os_label} - Presupuesto aprobado"
                body_lines = [
                    f"Hola {row.get('tecnico_nombre') or ''},",
                    "",
                    f"El presupuesto de la {os_label} fue Aprobado.",
                    "",
                    "Detalle del equipo:",
                    f"- Cliente: {row.get('cliente') or '-'}",
                    f"- Marca/Modelo: {row.get('marca') or '-'} / {row.get('modelo') or '-'}",
                    f"- Tipo: {row.get('tipo_equipo') or '-'}",
                    f"- N° de serie: {row.get('numero_serie') or '-'}",
                    "",
                    f"Abrir hoja de servicio: {link}",
                    "",
                    "Aviso automático - no responder a este correo.",
                ]
                body = "\n".join(body_lines)
                from django.core.mail import send_mail
                send_mail(subject, body, getattr(settings, 'DEFAULT_FROM_EMAIL', None), [to_email], fail_silently=True)
        except Exception:
            pass

        try:
            fname, pdf = render_quote_pdf(ingreso_id)
            save_dir = getattr(settings, "QUOTES_SAVE_DIR", None)
            if save_dir and pdf:
                import os
                os.makedirs(save_dir, exist_ok=True)
                dest = os.path.join(save_dir, fname)
                with open(dest, "wb") as f:
                    f.write(pdf)
        except Exception:
            pass

        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)


class AnularPresupuestoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin"])
        row = q("SELECT presupuesto_estado FROM ingresos WHERE id=%s", [ingreso_id], one=True)
        if not row:
            raise ValidationError("Ingreso no encontrado")
        if (row.get("presupuesto_estado") or "").strip() != "presupuestado":
            raise ValidationError("Solo se puede anular cuando el presupuesto está 'presupuestado'.")

        qid = _ensure_quote(ingreso_id)
        exec_void(
            """
            UPDATE quotes
               SET estado='pendiente',
                   fecha_emitido=NULL,
                   fecha_aprobado=NULL,
                   pdf_url=NULL
             WHERE id=%s
            """,
            [qid],
        )
        exec_void("UPDATE ingresos SET presupuesto_estado='pendiente' WHERE id=%s", [ingreso_id])
        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)


class NoAplicaPresupuestoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        row = q("SELECT presupuesto_estado FROM ingresos WHERE id=%s", [ingreso_id], one=True)
        if not row:
            raise ValidationError("Ingreso no encontrado")
        cur = (row.get("presupuesto_estado") or "").strip()
        if cur in ("presupuestado", "aprobado"):
            raise ValidationError("Primero debe anular el presupuesto para marcar 'No aplica'.")

        qid = _ensure_quote(ingreso_id)
        _set_audit_user(request)
        exec_void(
            """
            UPDATE quotes
               SET estado='no_aplica',
                   fecha_emitido=NULL,
                   fecha_aprobado=NULL,
                   pdf_url=NULL
             WHERE id=%s
            """,
            [qid],
        )
        exec_void("UPDATE ingresos SET presupuesto_estado='no_aplica' WHERE id=%s", [ingreso_id])
        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)


class QuitarNoAplicaPresupuestoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        row = q("SELECT presupuesto_estado FROM ingresos WHERE id=%s", [ingreso_id], one=True)
        if not row:
            raise ValidationError("Ingreso no encontrado")
        cur = (row.get("presupuesto_estado") or "").strip()
        if cur != "no_aplica":
            raise ValidationError("Solo se puede quitar cuando esta en 'no_aplica'.")

        qid = _ensure_quote(ingreso_id)
        _set_audit_user(request)
        exec_void(
            """
            UPDATE quotes
               SET estado='pendiente',
                   fecha_emitido=NULL,
                   fecha_aprobado=NULL,
                   pdf_url=NULL
             WHERE id=%s
            """,
            [qid],
        )
        exec_void("UPDATE ingresos SET presupuesto_estado='pendiente' WHERE id=%s", [ingreso_id])
        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)


__all__ = [
    'QuoteDetailView',
    'QuoteItemsView',
    'QuoteItemDetailView',
    'QuoteResumenView',
    'EmitirPresupuestoView',
    'QuotePdfView',
    'AprobarPresupuestoView',
    'AnularPresupuestoView',
    'NoAplicaPresupuestoView',
    'QuitarNoAplicaPresupuestoView',
]
