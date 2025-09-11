# service/views.py
from django.db import connection, transaction, IntegrityError
import os
import secrets, hashlib, datetime as dt
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.exceptions import PermissionDenied, ValidationError, AuthenticationFailed
from django.utils.dateparse import parse_datetime
from django.contrib.auth.hashers import make_password
from .auth import issue_token, verify_hash
from .models import User, Ingreso, Quote, Customer
from .serializers import (
    IngresoSerializer, QuoteDetailSerializer,QuoteItemSerializer,
    IngresoListItemSerializer, IngresoDetailSerializer,
    IngresoDetailWithAccesoriosSerializer,
)
from decimal import Decimal, ROUND_HALF_UP
from .pdf import ( render_quote_pdf, render_remito_salida_pdf)

TOKEN_TTL_MIN = 30       # vence en 30 minutos
COOLDOWN_MIN  = 1       # máx 1 mail cada 1 minutos por usuario
ROLE_CHOICES = [
    ("tecnico", "Técnico"),
    ("admin", "Administración"),
    ("jefe", "Jefe"),
    ("jefe_veedor", "Jefe veedor"),
    ("recepcion", "Recepción"),
]
ROLE_KEYS = [r for r, _ in ROLE_CHOICES]
TWO = Decimal("0.01")

def money(x):
    """Normaliza a Decimal con 2 decimales (ROUND_HALF_UP). Acepta Decimal/str/float/int/None."""
    if x is None:
        return Decimal("0.00")
    if isinstance(x, Decimal):
        return x.quantize(TWO, rounding=ROUND_HALF_UP)
    return Decimal(str(x)).quantize(TWO, rounding=ROUND_HALF_UP)

def exec_void(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
def _set_audit_user(request):
    with connection.cursor() as cur:
        cur.execute(
            "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
            [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
             getattr(request, "user_role", "")]
        )
# ---------------------------------------
# Utilidades DB
def q(sql, params=None, one=False):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        if cur.description:
            cols = [c[0] for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            return (rows[0] if rows else None) if one else rows
        return None

def exec_returning(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
        return row[0] if row else None

def _fetchall_dicts(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

def _frontend_url(request, path: str) -> str:
    try:
        base = (
            getattr(settings, 'PUBLIC_WEB_URL', '')
            or getattr(settings, 'FRONTEND_ORIGIN', '')
        ).strip()
        if base:
            return f"{base.rstrip('/')}{path}"
        # Fallback: mismo host de la request
        return request.build_absolute_uri(path)
    except Exception:
        return path

# ---------------------------------------
# Helpers auth/roles
def _rol(request):
    return getattr(request.user, "rol", None) or (getattr(request.user, "data", {}) or {}).get("rol")

def require_roles(request, roles):
    r = _rol(request)
    expanded = set(roles)
    # Si el endpoint acepta "jefe", también aceptar "jefe_veedor"
    if "jefe" in expanded:
        expanded.add("jefe_veedor")
    if r not in expanded:
        raise PermissionDenied("No autorizado")

def require_jefe(request):
    if _rol(request) not in ("jefe", "jefe_veedor"):
        raise PermissionDenied("Solo Jefe")

def _is(role, request):
    return getattr(getattr(request, "user", None), "rol", None) == role

def _in(roles, request):
    return getattr(getattr(request, "user", None), "rol", None) in roles

def _ensure_quote(ingreso_id: int):
    """Garantiza que exista la cabecera quote para el ingreso."""
    row = q("SELECT id FROM quotes WHERE ingreso_id=%s", [ingreso_id], one=True)
    if row:
        return row["id"]
    return exec_returning(
        "INSERT INTO quotes(ingreso_id) VALUES (%s) ON CONFLICT (ingreso_id) DO NOTHING RETURNING id",
        [ingreso_id]
    ) or q("SELECT id FROM quotes WHERE ingreso_id=%s", [ingreso_id], one=True)["id"]


def _load_quote_payload(ingreso_id: int):
    # leer cabecera (sin escribir nada)

    head = q("""
        SELECT q.id AS quote_id, q.estado, q.moneda, q.subtotal, q.iva_21, q.total
        FROM quotes q
        WHERE q.ingreso_id=%s
    """, [ingreso_id], one=True)

    if not head:
        qid = _ensure_quote(ingreso_id)
        head = q("""
            SELECT q.id AS quote_id, q.estado, q.moneda, q.subtotal, q.iva_21, q.total
            FROM quotes q WHERE q.id=%s
        """, [qid], one=True)

    items = q("""
        SELECT
          qi.id, qi.tipo, qi.repuesto_id, qi.descripcion, qi.qty, qi.precio_u,
          round(qi.qty * qi.precio_u, 2) AS subtotal
        FROM quote_items qi
        JOIN quotes q ON q.id = qi.quote_id
        WHERE q.ingreso_id=%s
        ORDER BY qi.id ASC
    """, [ingreso_id])

    # agregados
    tot_rep = q("""
        SELECT COALESCE(SUM(qi.qty*qi.precio_u),0) AS x
        FROM quote_items qi
        JOIN quotes q ON q.id=qi.quote_id
        WHERE q.ingreso_id=%s AND qi.tipo='repuesto'
    """, [ingreso_id], one=True)["x"]

    mano_obra = q("""
        SELECT COALESCE(SUM(qi.qty*qi.precio_u),0) AS x
        FROM quote_items qi
        JOIN quotes q ON q.id=qi.quote_id
        WHERE q.ingreso_id=%s AND qi.tipo='mano_obra'
    """, [ingreso_id], one=True)["x"]

    # Sumar siempre en Decimal
    subtotal_calc = sum((it.get("subtotal") or Decimal("0.00")) for it in items)
    subtotal_calc = money(subtotal_calc)

    IVA = Decimal("0.21")
    iva21_calc = money(subtotal_calc * IVA)
    total_calc = money(subtotal_calc + iva21_calc)

    payload = {
        "ingreso_id": ingreso_id,
        "quote_id": head["quote_id"],
        "estado": head["estado"],
        "moneda": head["moneda"],
        "items": items,
        # total de repuestos se calcula directamente por ítems tipo 'repuesto'
        "tot_repuestos": tot_rep,
        "mano_obra": mano_obra,
        "subtotal": subtotal_calc,
        "iva_21": iva21_calc,
        "total": total_calc,
    }
    return payload
# ---------------------------------------
# Ping y Login
@api_view(["GET"])
@permission_classes([AllowAny])
@authentication_classes([])
def ping(request):
    return Response({"ok": True})

def _normalize_role(s: str) -> str:
    s = (s or "").strip().lower().replace(" ", "_").replace("-", "_")
    return s
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        password = (request.data.get("password") or "")

        # 1) No aceptar credenciales incompletas
        if not email or not password:
            raise AuthenticationFailed("Email y contraseña requeridos.")

        # 2) Buscar usuario activo
        try:
            user = User.objects.get(email=email, activo=True)
        except User.DoesNotExist:
            raise AuthenticationFailed("Usuario o contraseña inválidos.")

        # 3) Bloquear login si aún no tiene password seteada
        if not user.hash_pw:
            raise AuthenticationFailed("El usuario aún no tiene contraseña. Usá 'Olvidé mi contraseña' para inicializarla.")

        # 4) Validar contraseña
        if not verify_hash(password, user.hash_pw):
            raise AuthenticationFailed("Usuario o contraseña inválidos.")

        # 5) Emitir token
        token = issue_token(user)
        return Response({
            "token": token,
            "user": {
                "id": user.id,
                "nombre": user.nombre,
                "rol": _normalize_role(user.rol),
                "perm_ingresar": getattr(user, "perm_ingresar", False),
            },
        })

class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        ua = request.META.get("HTTP_USER_AGENT", "")
        ip = request.META.get("REMOTE_ADDR", "")

        # Siempre devolvemos 200 para evitar enumeración de usuarios
        ok_response = Response({"ok": True})

        if not email:
            return ok_response

        user = q("SELECT id, email, nombre, activo FROM users WHERE LOWER(email)=%s", [email], one=True)
        if not user or not user.get("activo"):
            return ok_response

        # Rate limit simple
        recent = q("""
          SELECT id FROM password_reset_tokens
          WHERE user_id=%s AND used_at IS NULL AND expires_at>now()
            AND created_at > now() - interval '%s minutes'
          ORDER BY id DESC LIMIT 1
        """, [user["id"], COOLDOWN_MIN], one=True)
        if recent:
            return ok_response

        # Generar token y guardar hash
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        exp = timezone.now() + dt.timedelta(minutes=TOKEN_TTL_MIN)

        exec_void("""
          INSERT INTO password_reset_tokens(user_id, token_hash, expires_at, ip, user_agent)
          VALUES (%s,%s,%s,%s,%s)
        """, [user["id"], token_hash, exp, ip, ua])

        url = f'{getattr(settings,"FRONTEND_ORIGIN","http://localhost:5173")}/restablecer?t={token}'
        subj = "Recuperación de contraseña"
        txt  = f"Hola {user['nombre']},\n\nUsá este enlace para restablecer tu contraseña (válido {TOKEN_TTL_MIN} minutos):\n{url}\n\nSi no fuiste vos, ignorá este correo."
        html = f"""
          <p>Hola {user['nombre']},</p>
          <p>Usá este enlace para restablecer tu contraseña (válido {TOKEN_TTL_MIN} minutos):</p>
          <p><a href="{url}">{url}</a></p>
          <p>Si no fuiste vos, ignorá este correo.</p>
        """
        try:
            send_mail(subj, txt, settings.DEFAULT_FROM_EMAIL, [email], html_message=html, fail_silently=True)
        except Exception:
            pass  # en dev con backend de consola igual lo vas a ver

        return ok_response


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        token = (request.data.get("token") or "").strip()
        password = (request.data.get("password") or "").strip()
        if not token or not password:
            return Response({"detail": "token y password requeridos"}, status=400)

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        row = q("""
          SELECT prt.id, prt.user_id
          FROM password_reset_tokens prt
          WHERE prt.token_hash=%s AND prt.used_at IS NULL AND prt.expires_at>now()
        """, [token_hash], one=True)

        if not row:
            return Response({"detail": "Token inválido o vencido"}, status=400)

        # Actualizar password
        hashed = make_password(password)
        q("UPDATE users SET hash_pw=%s WHERE id=%s", [hashed, row["user_id"]])

        # Marcar usado
        q("UPDATE password_reset_tokens SET used_at=now() WHERE id=%s", [row["id"]])

        return Response({"ok": True})

# ---------------------------------------
# Vistas de técnico / ingresos
class CatalogoTecnicosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        rows = q("""
          SELECT id, nombre
          FROM users
          WHERE activo=true AND rol IN ('tecnico','jefe','jefe_veedor')
          ORDER BY nombre
        """)
        return Response(rows)

class MisPendientesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe", "tecnico","jefe_veedor"])
        with connection.cursor() as cur:
            cur.execute(
                "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                 getattr(request, "user_role", "")]
            )
            cur.execute("""
              SELECT t.id, t.estado, t.presupuesto_estado,
                     t.motivo, c.razon_social,
                     d.numero_serie,
                     COALESCE(b.nombre,'') AS marca,
                     COALESCE(m.nombre,'') AS modelo,
                     t.fecha_ingreso
              FROM ingresos t
              JOIN devices d ON d.id=t.device_id
              JOIN customers c ON c.id=d.customer_id
              LEFT JOIN marcas b ON b.id=d.marca_id
              LEFT JOIN models m ON m.id=d.model_id
              LEFT JOIN locations loc ON loc.id = t.ubicacion_id
              WHERE t.asignado_a = %s
                AND loc.nombre ILIKE 'taller'
                AND t.estado::text NOT IN ('entregado','liberado')
              ORDER BY
                 (t.motivo = 'urgente control') DESC,
                 t.fecha_ingreso ASC;
            """, [getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", None)])
            data = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(data, many=True).data)

class QuoteDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor", "tecnico", "recepcion"])
        _ensure_quote(ingreso_id)
        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)


class QuoteItemsView(APIView):
    """POST crea ítem (repuesto / mano_obra / servicio)"""
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
            qty    = money(d.get("qty"))
            precio = money(d.get("precio_u"))
        except (TypeError, ValueError):
            raise ValidationError("qty y precio_u deben ser numéricos")
        if qty < 0 or precio < 0:
            raise ValidationError("qty y precio_u no pueden ser negativos")
        repuesto_id = d.get("repuesto_id")

        qid = _ensure_quote(ingreso_id)
        _set_audit_user(request)
        exec_void("""
          INSERT INTO quote_items(quote_id, tipo, descripcion, qty, precio_u, repuesto_id)
          VALUES (%s,%s,%s,%s,%s,%s)
        """, [qid, tipo, desc, qty, precio, repuesto_id])

        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data, status=201)


class QuoteItemDetailView(APIView):
    """PATCH/DELETE de un ítem puntual"""
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
            if qv < 0: raise ValidationError("qty no puede ser negativo")  
            sets.append("qty=%s"); params.append(qv)
        if "precio_u" in d:
            try:
                pv = float(d.get("precio_u"))
            except (TypeError, ValueError):
                raise ValidationError("precio_u debe ser numérico")
            if pv < 0: raise ValidationError("precio_u no puede ser negativo")
            sets.append("precio_u=%s"); params.append(pv)
        if "repuesto_id" in d:
            sets.append("repuesto_id=%s"); params.append(d.get("repuesto_id"))

        if sets:
            _set_audit_user(request)
            params += [ingreso_id, item_id]
            exec_void(f"""
              UPDATE quote_items qi
                 SET {', '.join(sets)}
              FROM quotes q
              WHERE qi.quote_id=q.id AND q.ingreso_id=%s AND qi.id=%s
            """, params)

        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)

    def delete(self, request, ingreso_id: int, item_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor", "tecnico"])
        _set_audit_user(request)
        exec_void("""
          DELETE FROM quote_items qi
          USING quotes q
          WHERE qi.quote_id=q.id AND q.ingreso_id=%s AND qi.id=%s
        """, [ingreso_id, item_id])

        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)


class QuoteResumenView(APIView):
    """
    PATCH { mano_obra: number }
    Upsertea un único renglón 'mano_obra' (qty=1) y recalcula totales.
    """
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
        # ¿ya hay mano_obra? -> upsert (mantengo uno solo)
        row = q("SELECT id FROM quote_items WHERE quote_id=%s AND tipo='mano_obra' ORDER BY id LIMIT 1", [qid], one=True)
        if row:
            exec_void("UPDATE quote_items SET qty=1, precio_u=%s, descripcion='Mano de obra' WHERE id=%s", [mo, row["id"]])
        else:
            exec_void("INSERT INTO quote_items(quote_id, tipo, descripcion, qty, precio_u) VALUES (%s,'mano_obra','Mano de obra',1,%s)", [qid, mo])

        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)

class EmitirPresupuestoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, ingreso_id):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])

        autorizado_por = (request.data.get("autorizado_por") or "Cliente").strip()
        forma_pago     = (request.data.get("forma_pago") or "A definir").strip()

        qid = _ensure_quote(ingreso_id)
        _set_audit_user(request)

        # Emitir presupuesto: se usa 'presupuestado' en la cabecera de la quote
        exec_void("""
          UPDATE quotes
             SET estado='presupuestado',
                 autorizado_por=%s,
                 forma_pago=%s,
                 fecha_emitido=now()
           WHERE id=%s
        """, [autorizado_por, forma_pago, qid])

        # Ingreso: usar el nombre viejo 'presupuestado'
        exec_void("UPDATE ingresos SET presupuesto_estado='presupuestado' WHERE id=%s", [ingreso_id])

        # PDF (generar y guardar copia en disco si está configurado)
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

        exec_void("SELECT recalc_quote_subtotal(%s)", [ingreso_id])
        data = _load_quote_payload(ingreso_id); data["pdf_url"] = pdf_url
        return Response(QuoteDetailSerializer(data).data)


class QuotePdfView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor", "tecnico", "recepcion"])

        fname, pdf = render_quote_pdf(ingreso_id)   # <- ahora sí, 2 valores
        if not pdf:
            raise ValidationError("Ingreso no encontrado o sin presupuesto")

        resp = HttpResponse(pdf, content_type="application/pdf")
        # inline para abrir en el navegador con un nombre amigable
        resp["Content-Disposition"] = f'inline; filename="{fname}"'
        return resp



# --- Aprobar presupuesto -> estado: aprobado ---
class AprobarPresupuestoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, ingreso_id):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        qid = _ensure_quote(ingreso_id)
        _set_audit_user(request)

        exec_void("""
          UPDATE quotes
             SET estado='aprobado',
                 fecha_aprobado=now()
           WHERE id=%s
        """, [qid])

        # Reflejar en ingreso según regla
        exec_void("""
          UPDATE ingresos
             SET presupuesto_estado='aprobado',
                 estado = CASE
                            WHEN estado IN ('ingresado','diagnosticado','presupuestado')
                            THEN 'reparar'
                            ELSE estado
                          END
           WHERE id=%s
        """, [ingreso_id])

        exec_void("SELECT recalc_quote_subtotal(%s)", [ingreso_id])

        # Enviar aviso por mail al técnico asignado (con detalles del equipo)
        try:
            row = q("""
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
            """, [ingreso_id], one=True) or {}
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
                    "Aviso automático — no responder a este correo.",
                ]
                body = "\n".join(body_lines)
                send_mail(subject, body, getattr(settings, 'DEFAULT_FROM_EMAIL', None), [to_email], fail_silently=True)
        except Exception:
            pass

        # Generar y guardar PDF en carpeta destino (si corresponde)
        try:
            fname, pdf = render_quote_pdf(ingreso_id)
            save_dir = getattr(settings, "QUOTES_SAVE_DIR", None)
            if save_dir and pdf:
                os.makedirs(save_dir, exist_ok=True)
                dest = os.path.join(save_dir, fname)
                with open(dest, "wb") as f:
                    f.write(pdf)
        except Exception:
            pass

        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)

class ComenzarReparacionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, ingreso_id: int):
        require_roles(request, ["tecnico","jefe","jefe_veedor"])
        _set_audit_user(request)
        # Si ya está en reparar, OK; si venía de estados previos válidos, permitir; si no, 409
        row = q("SELECT estado FROM ingresos WHERE id=%s", [ingreso_id], one=True)
        if not row:
            return Response({"detail": "Ingreso no encontrado"}, status=404)
        if row["estado"] == "reparar":
            return Response({"ok": True})
        if row["estado"] in ("ingresado","diagnosticado","presupuestado"):
            exec_void("UPDATE ingresos SET estado='reparar' WHERE id=%s", [ingreso_id])
            return Response({"ok": True})
        return Response({"detail": f"No se puede comenzar desde estado '{row['estado']}'"}, status=409)



# --- anular presupuesto ---
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

        exec_void("""
            UPDATE quotes
               SET estado='pendiente',
                   fecha_emitido=NULL,
                   fecha_aprobado=NULL,
                   pdf_url=NULL
             WHERE id=%s
        """, [qid])

        exec_void("UPDATE ingresos SET presupuesto_estado='pendiente' WHERE id=%s", [ingreso_id])

        exec_void("SELECT recalc_quote_subtotal(%s)", [ingreso_id])
        data = _load_quote_payload(ingreso_id)
        return Response(QuoteDetailSerializer(data).data)



class PendientesPresupuestoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            cur.execute(
                "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                 getattr(request, "user_role", "")]
            )
            cur.execute("""
              SELECT t.id, t.estado, t.presupuesto_estado,
                     c.razon_social,
                     d.numero_serie,
                     COALESCE(b.nombre,'') AS marca,
                     COALESCE(m.nombre,'') AS modelo,
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
              WHERE t.presupuesto_estado = 'pendiente'
                AND loc.nombre ILIKE 'taller'
                AND t.estado = 'diagnosticado'
              ORDER BY t.fecha_servicio ASC;
            """)
            data = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(data, many=True).data)

class PresupuestadosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            cur.execute(
                "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                 getattr(request, "user_role", "")]
            )
            cur.execute("""
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
                  t.fecha_ingreso,
                  q.id AS presupuesto_id,
                  q.id AS presupuesto_numero,
                  q.subtotal AS presupuesto_monto,
                  'ARS' AS presupuesto_moneda,
                  q.fecha_emitido AS presupuesto_fecha_emision,
                  NULL::timestamp AS presupuesto_fecha_envio
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
                  AND loc.nombre ILIKE 'taller'
                  AND t.estado NOT IN ('entregado','liberado', 'alquilado')
                ORDER BY COALESCE(q.fecha_emitido, t.fecha_ingreso) ASC;
            """)
            return Response(_fetchall_dicts(cur))

class MarcarReparadoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, ingreso_id):
        require_roles(request, ["tecnico","jefe","jefe_veedor"])
        _set_audit_user(request)
        exec_void("UPDATE ingresos SET estado='reparado' WHERE id=%s", [ingreso_id])
        return Response({"ok": True})


class EntregarIngresoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe","jefe_veedor","admin","recepcion"])
        data = request.data or {}

        remito = (data.get("remito_salida") or "").strip()
        if not remito:
            return Response({"detail": "remito_salida requerido"}, status=400)

        factura = (data.get("factura_numero") or "").strip() or None
        fecha_entrega = data.get("fecha_entrega") or None

        user_id = getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")
        user_role = getattr(request, "user_role", "")

        # IMPORTANTE: mismo transaction + mismo cursor para SET LOCAL + UPDATE
        with transaction.atomic():
            with connection.cursor() as cur:
                # Seteamos GUC para RLS en esta transacción
                cur.execute("SET LOCAL app.user_id = %s;", [str(user_id)])
                cur.execute("SET LOCAL app.user_role = %s;", [user_role])

                # Hacemos el UPDATE en el MISMO cursor/conexión
                cur.execute("""
                    UPDATE ingresos
                       SET estado='entregado',
                           remito_salida=%s,
                           factura_numero=%s,
                           fecha_entrega=COALESCE(%s, now())
                     WHERE id=%s
                """, [remito, factura, fecha_entrega, ingreso_id])

        return Response({"ok": True})


class GeneralPorClienteView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, customer_id):
        with connection.cursor() as cur:
            cur.execute(
                "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                 getattr(request, "user_role", "")]
            )
            cur.execute("""
                SELECT
                  t.id, t.estado, t.presupuesto_estado, t.fecha_ingreso, t.ubicacion_id,
                  COALESCE(loc.nombre,'') AS ubicacion_nombre,
                  c.id AS customer_id, c.razon_social,
                  d.numero_serie,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo
                FROM ingresos t
                JOIN devices   d ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                WHERE c.id = %s
                  AND loc.nombre ILIKE 'taller'
                  AND t.estado NOT IN ('entregado', 'alquilado')
                ORDER BY t.fecha_ingreso ASC;
            """, [customer_id])
            return Response(_fetchall_dicts(cur))


class ListosParaRetiroView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            cur.execute("SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                        [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                         getattr(request, "user_role", "")])
            cur.execute("SELECT * FROM vw_listos_para_retiro ORDER BY id DESC;")
            return Response(_fetchall_dicts(cur))

class CustomersListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            cur.execute("SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                        [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                         getattr(request, "user_role", "")])
            cur.execute("SELECT id, razon_social FROM customers ORDER BY razon_social;")
            return Response(_fetchall_dicts(cur))

# ---------------------------------------

def os_label(_id: int) -> str:
    return f"OS {str(_id).zfill(6)}"

class NuevoIngresoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        data = request.data or {}
        cliente = data.get("cliente") or {}
        equipo  = data.get("equipo") or {}
        motivo = (data.get("motivo") or "").strip().lower()
        numero_interno = (equipo.get("numero_interno") or "").strip()
        if numero_interno and not numero_interno.upper().startswith("MG"):
            numero_interno = "MG " + numero_interno

        # Ubicación: si no viene, buscar 'Taller'
        ubicacion_id = data.get("ubicacion_id")
        if not ubicacion_id:
            t = q(
                "SELECT id FROM locations WHERE LOWER(nombre)=LOWER(%s) LIMIT 1",
                ["taller"], one=True
            )
            if not t:
                return Response(
                    {"detail": "No se encontró la ubicación 'Taller' en el catálogo. Creala en 'locations'."},
                    status=400
                )
            ubicacion_id = t["id"]

        informe_preliminar = (data.get("informe_preliminar") or "").strip()
        accesorios_text = (data.get("accesorios") or "").strip()
        accesorios_items = data.get("accesorios_items") or []

        if not motivo:
            return Response({"detail": "motivo requerido"}, status=400)
        
        if not equipo.get("marca_id") or not equipo.get("modelo_id"):
            return Response({"detail": "equipo.marca_id y equipo.modelo_id son requeridos"}, status=400)

        # Cliente
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
            return Response({"detail": "El código no corresponde a la razón social seleccionada."}, status=400)
        if cliente.get("razon_social") and c["razon_social"].lower() != cliente["razon_social"].lower():
            return Response({"detail": "La razón social no corresponde al código seleccionado."}, status=400)

        customer_id = c["id"]

        # Marca/Modelo
        marca = q("SELECT id FROM marcas WHERE id=%s", [equipo["marca_id"]], one=True)
        model = q("SELECT id FROM models WHERE id=%s AND marca_id=%s", [equipo["modelo_id"], equipo["marca_id"]], one=True)
        if not marca or not model:
            return Response({"detail": "Marca o modelo inexistente"}, status=400)

        # ---- Propietario (opcional) ----
        prop = data.get("propietario") or {}
        prop_nombre   = (prop.get("nombre") or "").strip()
        prop_contacto = (prop.get("contacto") or "").strip()
        prop_doc      = (prop.get("doc") or "").strip()
        # Equipo
        numero_serie = (equipo.get("numero_serie") or "").strip()
        garantia_bool = bool(equipo.get("garantia"))

        dev = q("SELECT id FROM devices WHERE numero_serie=%s", [numero_serie], one=True) if numero_serie else None
        if dev:
            device_id = dev["id"]
        else:
            device_id = exec_returning(
                """
                INSERT INTO devices (customer_id, marca_id, model_id, numero_serie, garantia_bool, n_de_control)
                VALUES (%s, %s, %s, NULLIF(%s,''), %s, NULLIF(%s,''))
                RETURNING id
                """,
                [customer_id, equipo["marca_id"], equipo["modelo_id"], numero_serie, garantia_bool, numero_interno]
            )
        if numero_interno:
            exec_void("UPDATE devices SET n_de_control = NULLIF(%s,'') WHERE id=%s", [numero_interno, device_id])

        # --- Garantía de reparación por N/S: último ingreso < 90 días ---
        from django.utils import timezone
        auto_gar_rep = False
        if numero_serie:
            row_last = q("""
              SELECT MAX(t.fecha_ingreso) AS last_in
                FROM ingresos t
                JOIN devices d ON d.id = t.device_id
               WHERE d.numero_serie = %s
            """, [numero_serie], one=True)
            last_in = row_last and row_last.get("last_in")
            if last_in:
                delta = (timezone.now() - last_in).days
                auto_gar_rep = delta <= 90
        garantia_rep_payload = bool(data.get("garantia_reparacion"))
        garantia_rep_final = garantia_rep_payload or auto_gar_rep

        # ---- Técnico asignado ----
        # 1) viene en payload -> ok; 2) default por modelo -> ok
        tecnico_id = data.get("tecnico_id")
        if not tecnico_id:
            tdef = q("SELECT tecnico_id FROM models WHERE id=%s", [equipo["modelo_id"]], one=True)
            tecnico_id = tdef["tecnico_id"] if tdef else None

        # ✅ 3) fallback por marca si el modelo no tiene
        if not tecnico_id:
            tmarca = q("SELECT tecnico_id FROM marcas WHERE id=%s", [equipo["marca_id"]], one=True)
            tecnico_id = (tmarca or {}).get("tecnico_id")

        # Validación
        if tecnico_id:
            tech = q("SELECT id FROM users WHERE id=%s AND activo=true AND rol IN ('tecnico','jefe')",
         [tecnico_id], one=True)
            if not tech:
                return Response({"detail": "Técnico inválido o inactivo"}, status=400)

        # Usuario
        uid = getattr(request.user, "id", None) or getattr(request, "user_id", None)
        if not uid:
            return Response({"detail": "Usuario no autenticado"}, status=401)
        exec_void("SELECT set_config('app.user_id', %s, true)", [str(uid)])
        
        # Ingreso (usa DEFAULT 'ingresado')
        ingreso_id = exec_returning("""
            INSERT INTO ingresos (
              device_id, motivo, ubicacion_id, recibido_por, asignado_a,
              informe_preliminar, accesorios,
              propietario_nombre, propietario_contacto, propietario_doc,
              garantia_reparacion
            )
            VALUES (%s,%s,%s,%s,%s,
                    %s,%s,
                    NULLIF(%s,''), NULLIF(%s,''), NULLIF(%s,''),
                    %s)
            RETURNING id
          """, [device_id, motivo, ubicacion_id, uid, tecnico_id,
                informe_preliminar, accesorios_text,
                prop_nombre, prop_contacto, prop_doc,
                garantia_rep_final])

        # Insertar accesorios normalizados si vienen
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
        if not ns:
            return Response({"within_90_days": False, "last_ingreso": None})
        row = q("""
          SELECT MAX(t.fecha_ingreso) AS last_in
            FROM ingresos t
            JOIN devices d ON d.id = t.device_id
           WHERE d.numero_serie = %s
        """, [ns], one=True)
        last_in = row and row.get("last_in")
        if not last_in:
            return Response({"within_90_days": False, "last_ingreso": None})
        from django.utils import timezone
        within = (timezone.now() - last_in).days <= 90
        return Response({"within_90_days": within, "last_ingreso": last_in})
# ---------------------------------------
# Catálogos
class CatalogoMarcasView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        rows = q("""
            SELECT b.id, b.nombre,
                b.tecnico_id,
                COALESCE(u.nombre,'') AS tecnico_nombre
            FROM marcas b
            LEFT JOIN users u ON u.id = b.tecnico_id
            ORDER BY b.nombre
        """)
        return Response(rows)

class CatalogoModelosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        marca_id = request.GET.get("marca_id")
        if not marca_id:
            return Response({"detail": "marca_id requerido"}, status=400)

        rows = q("""
            SELECT m.id, m.nombre,
                   m.tecnico_id,
                   COALESCE(u.nombre,'') AS tecnico_nombre,
                   COALESCE(m.tipo_equipo,'') AS tipo_equipo
            FROM models m
            LEFT JOIN users u ON u.id = m.tecnico_id
            WHERE m.marca_id=%s
            ORDER BY m.nombre
        """, [marca_id])
        return Response(rows)


class TiposEquipoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Compatibilidad: si existe la tabla externa "equipos" (legado), usarla.
        # Evitamos errores de transacción consultando to_regclass en vez de TRY/EXCEPT.
        reg = q("SELECT to_regclass('public.equipos') AS reg", one=True)
        if reg and reg.get("reg"):
            rows = q("""
                SELECT "IdEquipos" AS id, "Equipo" AS nombre
                FROM equipos
                ORDER BY "Equipo"
            """) or []
            return Response(rows)

        # Fallback: tipos desde models.tipo_equipo + catálogo extendido suministrado
        usados = q("""
            SELECT DISTINCT TRIM(m.tipo_equipo) AS nombre
            FROM models m
            WHERE COALESCE(TRIM(m.tipo_equipo),'') <> ''
        """) or []
        usados_set = { (r.get('nombre') or '').strip().upper() for r in usados }

        catalogo_fijo = [
            "ACUMULADOR DE OXIGENO","ALARGUE DE SENSOR","ALARMA DE ESPIROMETRO","ALTO FLUJO","AMBIENTE OXIMETRO DE","ANALIZADOR DE OXIGENO","ARTROSCOPIO","ASPIRADOR","ASPIRADOR A BATERAS","BALANZA","BAÑO TERMOSTATICO","BATERIA PORTATIL","BATERY PACK","BBB","BLENDER DE OXIGENO","BOMBA DE ALIMENTACION","BOMBA DE ALIMENTACION","BOMBA DE ASPIRACION DE DRENAJE","BOMBA DE INFUSION","BOMBA SACA LECHE","BPAP","BPAP AUTO","BPAP AUTO C/HUMIDIF","BPAP C/AVAPS","BPAP C/BIFLEX","BPAP C/FREC.","BPAP C/HUMIDIFICADOR","CABEZALES DE BOMBA","CABLE DE CONEXIÓN 12V","CABLE PACIENTE","CABLE TRANSMISION DATOS","CALENTADOR HUMIDIFICADOR","CANISTER DE CAL SODADA","CAPNOGRAFO","CAPNOMETRO","CAPOTA DE INCUBADORA","CARDIODESFIBRILADOR","CARGADOR DE BATERIAS","CENTRAL DE MONITOREO","COLCHON DE AIRE","COLPOSCOPIO","COMPRESOR DE COLCHON ANTI ESCARAS","COMPRESOR DE CONCENTRADOR","COMPRESOR DE RESPIRADOR","COMPRESOR PARA BOTA","CONCENTRADOR DE OXIGENO","CONCENTRADOR PORTATIL DE OXIGENO","CONECTOR PLASTICO","CONTRA ANGULO","CONTROL DE MICROMOTOR","COUGH ASIST","CPAP","CPAP AUTO","CPAP AUTO C/HUMIDIF","CPAP C/CFLEX","CPAP C/HUMIDIF","CRANEOMOTRO","CUNA PEDIATRICA","DESFIBRILADOR","DETECTOR FETAL","ELECTROBISTURI","ELECTROCARDIOGRAFO","ELECTROCOAGULADOR","ELECTRODO PASIVO ELECTROVISTURI","ESPIROMETRO MA-1","ESTABILIZADOR DE TENSION","ESTUFA DE LABORATORIO","FERULA DE TORONTO","FLOWMETER","FRONTOLUZ","FUENTE DE ALIMENTACION","FUENTE DE FIBRA OPTICA","GENERADOR DE MARCAPASOS","GENERADOR DE OZONO","GRUPO CONTROL DE SERVOCUNA","GRUPO MOTOR DE INCUBADORA","HOLTER","IMPRESORA","INCUBADOR DE MONITORES BIOLOGICOS","INCUBADORA","INCUBADORA DE TRANSPORTE","LAMPARA DE ODONTOLOGIA","LARINGOSCOPIO","LASER INFRAROJO","LUMINOTERAPIA","LUMINOTERAPIA LED","MAGNETO","MANGUERA DE ALTA PRESION","MANOMETROS","MARCAPASO","MEDIDOR DE OXIGENO","MESA DE ANESTESIA","MOCHILA O2 425L","MODULO DE ENTRADA","MONITOR AUXILIAR","MONITOR CARDIACO","MONITOR DE APNEA","MONITOR DE PORTERO ELECTRICO","MONITOR DE PRESION NO INVASIVO","MONITOR DE SEG ELECTRICA","MONITOR FETAL","MONITOR LED","MONITOR MULTIPARAMETRICO","MONITOR PRE PARTO","MOTO NEBULIZADOR","MOTORES CON TURBINA","NEBULIZADOR","ONDA CORTA","OTOSCOPIO","OXICAPNOGRAFO","OXIMETRO DE PULSO","OXIMETRO DE PULSO C/CURVA","PACK DE BATERIA","PALETAS DE DESFIBRILADOR","PANEL DE SERVOCUNA","PARA RECARGAR","PEDAL DE ELECTROBISTURI","PIE PORTASUEROS","PIE RODANTE DE MONITOR","PIEZA DE MANO","PLACA INDIFERENTE DE ELECTROBISTURI","PLAQUETA DE OXIMETRO DE PULSO","POLIGRAFO","PORTA FUELLE DE RESPIRADOR","PROLONGADOR DE SENSOR","PUNTA DE ASPIRADOR ULTRASONICO","RECTOSCOPIO","REGULADOR DE MOCHILA","RELOJES","RESPIRADOR","SELLADORA DE BOLSAS","SENSOR DE GOTA","SENSOR DE OXIMETRO DE PULSO","SENSOR DE TEMPERATURA","SENSOR DE XFLUJO","SERVICIO DE GUARDIA","SERVOCUNA","SIERRA ORTOPEDICA","SOPORTE DE PALETAS DESFIBRILADOR","SWICH TPLINK","TAPA DE CALENTADOR","TAPA DE CONCENTRADOR","TAPA DE HUMIDIFICADOR","TAPA DE RESPIRADOR","TENSIOMETRO","TERMINALES DE SENSOR","TRANSFORMADOR","TUBO DE OXIGENO 1M","TUBO DE OXIGENO 6 M3","ULTRASONIDO","UPS","VALVULA AHORRADORA","VALVULA DE MESA DE ANESTESIA","VALVULA DE PEEP","VALVULA EXPIROMETRIA","VALVULA REDUCTORA DE PRESION","VENTILADOR","OTRO"
        ]
        # Combinar usados + catálogo fijo
        nombres = sorted({ *(n for n in usados_set if n), *catalogo_fijo })
        rows = [{ "id": i+1, "nombre": n } for i, n in enumerate(nombres)]
        return Response(rows)

# views.py
class ModeloTipoEquipoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, marca_id: int, modelo_id: int):
        d = request.data or {}
        tipo_nombre = (d.get("tipo_equipo") or "").strip()
        tipo_id = d.get("tipo_equipo_id")

        if tipo_id is not None and not tipo_nombre:
            reg = q("SELECT to_regclass('public.equipos') AS reg", one=True)
            if reg and reg.get("reg"):
                r = q('SELECT "Equipo" AS equipo FROM equipos WHERE "IdEquipos"=%s', [tipo_id], one=True)
                if not r:
                    return Response({"detail": "Tipo de equipo inexistente"}, status=400)
                tipo_nombre = r["equipo"]
            else:
                return Response({"detail": "tipo_equipo_id no disponible en este entorno"}, status=400)

        # permitir limpiar
        tipo_nombre = tipo_nombre or ""

        exec_void("""
            UPDATE models
               SET tipo_equipo = NULLIF(%s,'')
             WHERE id=%s AND marca_id=%s
        """, [tipo_nombre, modelo_id, marca_id])

        return Response({"ok": True})

class CatalogoUbicacionesView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response(q("SELECT id, nombre FROM locations ORDER BY id"))

class CatalogoMotivosView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        rows = q("""
          SELECT e.enumlabel AS value, e.enumlabel AS label
          FROM pg_type t
          JOIN pg_enum e ON e.enumtypid = t.oid
          WHERE t.typname = 'motivo_ingreso'
          ORDER BY (e.enumlabel = 'urgente control') DESC, e.enumlabel ASC
        """)
        return Response(rows)

# Accesorios: catálogo y por ingreso
class CatalogoAccesoriosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        rows = q("SELECT id, nombre FROM catalogo_accesorios WHERE activo ORDER BY nombre")
        return Response(rows)

class IngresoAccesoriosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, ingreso_id: int):
        require_roles(request, ["jefe","admin","jefe_veedor","tecnico","recepcion"])
        rows = q(
            """
              SELECT ia.id, ia.accesorio_id, ca.nombre AS accesorio_nombre, ia.referencia, ia.descripcion
              FROM ingreso_accesorios ia
              JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id AND ca.activo
              WHERE ia.ingreso_id=%s
              ORDER BY ia.id
            """,
            [ingreso_id]
        )
        return Response(rows)

    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe","admin","jefe_veedor","tecnico","recepcion"])
        d = request.data or {}
        try:
            acc_id = int(d.get("accesorio_id"))
        except (TypeError, ValueError):
            return Response({"detail": "accesorio_id requerido"}, status=400)
        acc = q("SELECT id FROM catalogo_accesorios WHERE id=%s AND activo", [acc_id], one=True)
        if not acc:
            return Response({"detail": "accesorio inválido"}, status=400)
        ref = (d.get("referencia") or "").strip() or None
        desc = (d.get("descripcion") or "").strip() or None
        _set_audit_user(request)
        new_id = exec_returning(
            "INSERT INTO ingreso_accesorios(ingreso_id, accesorio_id, referencia, descripcion) VALUES (%s,%s,%s,%s) RETURNING id",
            [ingreso_id, acc_id, ref, desc]
        )
        row = q(
            """
              SELECT ia.id, ia.accesorio_id, ca.nombre AS accesorio_nombre, ia.referencia, ia.descripcion
              FROM ingreso_accesorios ia
              JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id
              WHERE ia.id=%s
            """,
            [new_id], one=True
        )
        return Response(row, status=201)

class IngresoAccesorioDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, ingreso_id: int, item_id: int):
        require_roles(request, ["jefe","admin","jefe_veedor","tecnico","recepcion"])
        _set_audit_user(request)
        exec_void(
            "DELETE FROM ingreso_accesorios WHERE ingreso_id=%s AND id=%s",
            [ingreso_id, item_id]
        )
        return Response({"ok": True})

# ---------------------------------------
# Derivación a servicio externo
class DerivarIngresoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, ingreso_id: int):
        data = request.data or {}
        # Compat: aceptar proveedor_id (nuevo) o external_service_id (viejo nombre)
        proveedor_id = data.get("proveedor_id") or data.get("external_service_id")
        if not proveedor_id:
            return Response({"detail": "proveedor_id requerido"}, status=400)

        ing = q("SELECT id FROM ingresos WHERE id=%s", [ingreso_id], one=True)
        if not ing:
            return Response({"detail": "Ingreso no encontrado"}, status=404)

        prov = q("SELECT id FROM proveedores_externos WHERE id=%s", [proveedor_id], one=True)
        if not prov:
            return Response({"detail": "Proveedor externo inválido"}, status=400)

        # Insertar en el nuevo log
        exec_returning("""
            INSERT INTO equipos_derivados (ingreso_id, proveedor_id, remit_deriv, fecha_deriv, comentarios, estado)
            VALUES (%s, %s, %s, COALESCE(%s::date, CURRENT_DATE), %s, 'derivado')
            RETURNING id
        """, [ingreso_id, proveedor_id, data.get("remit_deriv"), data.get("fecha_deriv"), data.get("comentarios")])

        # Reflejar estado del ingreso (como venías haciendo)
        q("UPDATE ingresos SET estado='derivado' WHERE id=%s", [ingreso_id])

        return Response({"ok": True})
# ---------------------------------------
# Usuarios (ABM + permisos)
class UsuariosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        rows = q("""
            SELECT id, nombre, email, rol, activo, COALESCE(perm_ingresar,false) AS perm_ingresar
            FROM users
            ORDER BY id ASC
        """)
        return Response(rows)

    @transaction.atomic
    def post(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        data = request.data or {}
        nombre = (data.get("nombre") or "").strip()
        email = (data.get("email") or "").strip().lower()
        rol_raw = (data.get("rol") or "tecnico")
        # Seguridad: no se acepta password directo por API de alta/ABM

        # normalizar: "Jefe veedor" / "jefe-veedor" -> "jefe_veedor"
        rol = rol_raw.strip().lower().replace(" ", "_").replace("-", "_")

        if not nombre or not email:
            raise ValidationError("Nombre y email son requeridos")
        if rol not in ROLE_KEYS:
            raise ValidationError("Rol inválido")

        existed = q("SELECT id FROM users WHERE email=%s", [email], one=True)
        q("""
            INSERT INTO users(nombre, email, rol, activo)
            VALUES (%(n)s, %(e)s, %(r)s, true)
            ON CONFLICT (email) DO UPDATE
            SET nombre = EXCLUDED.nombre,
                rol = EXCLUDED.rol
        """, {"n": nombre, "e": email, "r": rol})

        # Enviar invitación de bienvenida si es nuevo
        if not existed:
            try:
                user = q("SELECT id, nombre, email FROM users WHERE email=%s", [email], one=True)
                if user:
                    # Generar token y enviar correo de bienvenida con link para setear contraseña
                    token = secrets.token_urlsafe(32)
                    token_hash = hashlib.sha256(token.encode()).hexdigest()
                    exp = timezone.now() + dt.timedelta(minutes=TOKEN_TTL_MIN)
                    ua = request.META.get("HTTP_USER_AGENT", "")
                    ip = request.META.get("REMOTE_ADDR", "")
                    exec_void(
                        """
                        INSERT INTO password_reset_tokens(user_id, token_hash, expires_at, ip, user_agent)
                        VALUES (%s,%s,%s,%s,%s)
                        """,
                        [user["id"], token_hash, exp, ip, ua]
                    )
                    base = getattr(settings, "PUBLIC_WEB_URL", None) or getattr(settings, "FRONTEND_ORIGIN", "http://localhost:5173")
                    url = f"{(base or '').rstrip('/')}/restablecer?t={token}"
                    subj = "Bienvenido a SEPID — Configurá tu contraseña"
                    txt  = (
                        f"Hola {user['nombre']},\n\n"
                        f"Te damos la bienvenida al sistema de reparaciones de SEPID. "
                        f"Usá este enlace para establecer tu contraseña (válido {TOKEN_TTL_MIN} minutos):\n{url}\n\n"
                        f"Si no esperabas este correo, ignoralo."
                    )
                    html = f"""
                        <p>Hola {user['nombre']},</p>
                        <p>Bienvenido al sistema de reparaciones de <strong>SEPID</strong>.</p>
                        <p>Usá este enlace para establecer tu contraseña (válido {TOKEN_TTL_MIN} minutos):</p>
                        <p><a href="{url}">{url}</a></p>
                        <p>Si no esperabas este correo, ignoralo.</p>
                    """
                    try:
                        send_mail(subj, txt, settings.DEFAULT_FROM_EMAIL, [user["email"]], html_message=html, fail_silently=True)
                    except Exception:
                        pass
            except Exception:
                # No bloquear el alta si el correo falla
                pass

        return Response({"ok": True, "invited": not existed})
    
class UsuarioActivoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def patch(self, request, uid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        activo = bool(request.data.get("activo"))
        q("UPDATE users SET activo = %(a)s WHERE id = %(id)s", {"a": activo, "id": uid})
        return Response({"ok": True, "activo": activo})

class UsuarioResetPassView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def patch(self, request, uid):
        # Nuevo comportamiento más seguro: envía un enlace por email para que el usuario
        # establezca (o reestablezca) su contraseña. No se permite fijarla directamente.
        require_jefe(request)
        user = q("SELECT id, email, nombre, activo FROM users WHERE id=%s", [uid], one=True)
        if not user or not user.get("activo"):
            return Response({"detail": "Usuario inexistente o inactivo"}, status=404)

        # Generar token válido y enviarlo por mail
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        exp = timezone.now() + dt.timedelta(minutes=TOKEN_TTL_MIN)
        ua = request.META.get("HTTP_USER_AGENT", "")
        ip = request.META.get("REMOTE_ADDR", "")
        exec_void(
            """
            INSERT INTO password_reset_tokens(user_id, token_hash, expires_at, ip, user_agent)
            VALUES (%s,%s,%s,%s,%s)
            """,
            [user["id"], token_hash, exp, ip, ua]
        )
        base = getattr(settings, "PUBLIC_WEB_URL", None) or getattr(settings, "FRONTEND_ORIGIN", "http://localhost:5173")
        url = f"{(base or '').rstrip('/')}/restablecer?t={token}"
        subj = "SEPID — Enlace para establecer tu contraseña"
        txt  = (
            f"Hola {user['nombre']},\n\n"
            f"Solicitaron un enlace para establecer o restablecer tu contraseña. "
            f"Usá este enlace (válido {TOKEN_TTL_MIN} minutos):\n{url}\n\n"
            f"Si no fuiste vos, ignorá este correo."
        )
        html = f"""
            <p>Hola {user['nombre']},</p>
            <p>Solicitaron un enlace para establecer o restablecer tu contraseña.</p>
            <p>Usá este enlace (válido {TOKEN_TTL_MIN} minutos):</p>
            <p><a href="{url}">{url}</a></p>
            <p>Si no fuiste vos, ignorá este correo.</p>
        """
        try:
            send_mail(subj, txt, settings.DEFAULT_FROM_EMAIL, [user["email"]], html_message=html, fail_silently=True)
        except Exception:
            pass

        return Response({"ok": True, "sent": True})

class UsuarioRolePermView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def patch(self, request, uid):
        require_jefe(request)
        rol = request.data.get("rol")
        perm_ing = request.data.get("perm_ingresar")

        sets, params = [], {"id": uid}
        if rol is not None:
            r = (rol or "").strip().lower()
            if r not in ROLE_KEYS:
                raise ValidationError("Rol inválido")
            sets.append("rol = %(rol)s")
            params["rol"] = r
        if perm_ing is not None:
            sets.append("perm_ingresar = %(p)s")
            params["p"] = bool(perm_ing)

        if not sets:
            return Response({"ok": True})
        q(f"UPDATE users SET {', '.join(sets)} WHERE id = %(id)s", params)
        return Response({"ok": True})
    
class UsuarioDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, uid):
        require_jefe(request)
        try:
            with transaction.atomic():
                # Limpiar referencias conocidas
                exec_void("UPDATE ingresos SET asignado_a = NULL WHERE asignado_a = %s", [uid])
                exec_void("UPDATE ingresos SET recibido_por = NULL WHERE recibido_por = %s", [uid])  # si existe la FK
                exec_void("UPDATE models   SET tecnico_id  = NULL WHERE tecnico_id  = %s", [uid])
                exec_void("UPDATE marcas   SET tecnico_id  = NULL WHERE tecnico_id  = %s", [uid])
                # Eventos de ingreso: preservar historial pero desvincular usuario
                exec_void("UPDATE ingreso_events SET usuario_id = NULL WHERE usuario_id = %s", [uid])

                # Borrar el usuario
                exec_void("DELETE FROM users WHERE id = %s", [uid])
        except IntegrityError:
            # Aún queda alguna referencia (otra FK en otra tabla)
            return Response(
                {"detail": "No se pudo eliminar: el usuario está referenciado por otros registros. "
                           "Reasigná/desasigná esas referencias o desactivá el usuario."},
                status=409,
            )
        return Response({"ok": True})

# ---------------------------------------
# Clientes / Marcas / Modelos / Proveedores externos
class ClientesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor", "recepcion"])
        return Response(q("SELECT id, razon_social, cod_empresa, telefono FROM customers ORDER BY razon_social"))
    def post(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        d = request.data or {}
        if not (d.get("razon_social") and d.get("cod_empresa")):
            raise ValidationError("razon_social y cod_empresa son requeridos")
        q("""INSERT INTO customers(razon_social, cod_empresa, telefono)
             VALUES (%(rs)s, %(ce)s, %(tel)s)""",
          {"rs": d["razon_social"], "ce": d["cod_empresa"], "tel": d.get("telefono")})
        return Response({"ok": True})

class ClienteDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, cid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        q("DELETE FROM customers WHERE id = %(id)s", {"id": cid})
        return Response({"ok": True})

class MarcasView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor", "tecnico", "recepcion"])
        return Response(q("SELECT id, nombre FROM marcas ORDER BY nombre"))
    def post(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        n = (request.data.get("nombre") or "").strip()
        if not n:
            raise ValidationError("nombre requerido")
        q("INSERT INTO marcas(nombre) VALUES (%(n)s) ON CONFLICT DO NOTHING", {"n": n})
        return Response({"ok": True})

class ModeloTecnicoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def patch(self, request, bid, mid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        tecnico_id = request.data.get("tecnico_id")
        if tecnico_id:
            ok = q("SELECT id FROM users WHERE id=%s AND activo=true AND rol IN ('tecnico','jefe')",
                [tecnico_id], one=True)

            if not ok: raise ValidationError("Técnico inválido")
        q("UPDATE models SET tecnico_id=%s WHERE id=%s AND marca_id=%s", [tecnico_id, mid, bid])
        return Response({"ok": True, "tecnico_id": tecnico_id})

class MarcaTecnicoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def patch(self, request, bid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        tecnico_id = request.data.get("tecnico_id")
        if tecnico_id:
            ok = q("SELECT id FROM users WHERE id=%s AND activo=true AND rol IN ('tecnico','jefe')",
                [tecnico_id], one=True)

            if not ok: raise ValidationError("Técnico inválido")
        q("UPDATE marcas SET tecnico_id=%s WHERE id=%s", [tecnico_id, bid])
        return Response({"ok": True, "tecnico_id": tecnico_id})

class MarcaAplicarTecnicoAModelosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, bid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        q("""
           UPDATE models m
           SET tecnico_id = b.tecnico_id
           FROM marcas b
           WHERE m.marca_id = b.id
             AND b.id = %s
             AND m.tecnico_id IS NULL
        """, [bid])
        return Response({"ok": True})

class IngresoAsignarTecnicoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def patch(self, request, ingreso_id):
        require_roles(request, ["jefe", "admin","jefe_veedor"])  # o sumá "recepcion" si querés
        tecnico_id = request.data.get("tecnico_id")
        if tecnico_id is None:
            return Response({"detail": "tecnico_id requerido"}, status=400)
        ok = q("SELECT id FROM users WHERE id=%s AND activo=true AND rol IN ('tecnico','jefe')",
                [tecnico_id], one=True)
        if not ok:
            return Response({"detail": "Técnico inválido"}, status=400)
        q("UPDATE ingresos SET asignado_a=%s WHERE id=%s", [tecnico_id, ingreso_id])
        return Response({"ok": True, "asignado_a": tecnico_id})


class MarcaDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, bid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        q("DELETE FROM marcas WHERE id = %(id)s", {"id": bid})
        return Response({"ok": True})

class ModelosPorMarcaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, bid):
        require_roles(request, ["jefe", "admin","jefe_veedor", "tecnico", "recepcion"])
        rows = q("""
          SELECT m.id, m.nombre, m.tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre,
                 COALESCE(m.tipo_equipo,'') AS tipo_equipo
          FROM models m
          LEFT JOIN users u ON u.id = m.tecnico_id
          WHERE m.marca_id=%s
          ORDER BY m.nombre
        """, [bid])
        return Response(rows)

    def post(self, request, bid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        n = (request.data.get("nombre") or "").strip()
        tipo_equipo = (request.data.get("tipo_equipo") or "").strip() or None
        tecnico_id = request.data.get("tecnico_id")

        if not n:
            raise ValidationError("nombre requerido")

        if tecnico_id:
            ok = q(
                "SELECT id FROM users WHERE id=%s AND activo=true AND rol IN ('tecnico','jefe')",
                [tecnico_id],
                one=True,
            )
            if not ok:
                raise ValidationError("Técnico inválido")

        q("""
          INSERT INTO models(marca_id, nombre, tecnico_id, tipo_equipo)
          VALUES (%(b)s, %(n)s, %(t)s, NULLIF(%(te)s,''))
          ON CONFLICT (marca_id, nombre) DO UPDATE
             SET tecnico_id = EXCLUDED.tecnico_id,
                 tipo_equipo = COALESCE(EXCLUDED.tipo_equipo, models.tipo_equipo)
        """, {"b": bid, "n": n, "t": tecnico_id, "te": tipo_equipo})

        return Response({"ok": True})


class ModeloDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, mid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        q("DELETE FROM models WHERE id = %(id)s", {"id": mid})
        return Response({"ok": True})

class ProveedoresExternosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor", "tecnico", "recepcion"])
        return Response(q("SELECT id, nombre, contacto FROM proveedores_externos ORDER BY nombre"))

    def post(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        d = request.data or {}
        n = (d.get("nombre") or "").strip()
        if not n:
            raise ValidationError("nombre requerido")
        q("INSERT INTO proveedores_externos(nombre, contacto) VALUES (%(n)s, %(c)s) ON CONFLICT DO NOTHING",
          {"n": n, "c": d.get("contacto")})
        return Response({"ok": True})

    def delete(self, request, pid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        q("DELETE FROM proveedores_externos WHERE id = %(id)s", {"id": pid})
        return Response({"ok": True})


class PendientesGeneralView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        tecnico_raw = (request.GET.get("tecnico_id") or "").strip()

        with connection.cursor() as cur:
            cur.execute(
                "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                [
                    str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                    getattr(request, "user_role", "")
                ]
            )

            sql = """
                SELECT t.id, t.estado, t.presupuesto_estado,
                        t.motivo, c.razon_social,
                       d.numero_serie,
                       COALESCE(b.nombre,'') AS marca,
                       COALESCE(m.nombre,'') AS modelo,
                       t.fecha_ingreso
                FROM ingresos t
                JOIN devices d   ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                WHERE loc.nombre ILIKE 'taller'
                  AND t.estado NOT IN ('liberado','entregado', 'alquilado')
            """
            params = []
            if tecnico_raw.isdigit():
                sql += " AND t.asignado_a = %s"
                params.append(int(tecnico_raw))

            sql += """
                ORDER BY
                  (t.motivo = 'urgente control') DESC, 
                  t.fecha_ingreso ASC
            """
            cur.execute(sql, params)
            rows = _fetchall_dicts(cur)

        return Response(IngresoListItemSerializer(rows, many=True).data)


class AprobadosParaRepararView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            cur.execute(
                "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                 getattr(request, "user_role", "")]
            )
            cur.execute("""
                SELECT
                  t.id,
                  t.estado,
                  t.presupuesto_estado,
                  c.razon_social,
                  d.numero_serie,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  t.fecha_ingreso,
                  q.fecha_aprobado AS fecha_aprobacion
                FROM ingresos t
                JOIN devices d ON d.id=t.device_id
                JOIN customers c ON c.id=d.customer_id
                LEFT JOIN marcas b ON b.id=d.marca_id
                LEFT JOIN models m ON m.id=d.model_id
                LEFT JOIN quotes q ON q.ingreso_id = t.id
                LEFT JOIN locations loc ON loc.id = t.ubicacion_id
                WHERE loc.nombre ILIKE 'taller'
                  AND (
                        (t.presupuesto_estado = 'aprobado'
                        AND t.estado NOT IN ('reparado','entregado','derivado','liberado','alquilado'))
                        OR t.estado = 'reparar'
                      )
                  AND t.estado NOT IN ('reparado','entregado','derivado','liberado','alquilado')
                ORDER BY COALESCE(q.fecha_aprobado, t.fecha_ingreso) ASC;
            """)
            data = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(data, many=True).data)

class AprobadosYReparadosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            cur.execute(
                "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                 getattr(request, "user_role", "")]
            )
            cur.execute("""
              SELECT t.id, t.estado, t.presupuesto_estado,
                     c.razon_social,
                     d.numero_serie,
                     COALESCE(b.nombre,'') AS marca,
                     COALESCE(m.nombre,'') AS modelo,
                     t.fecha_ingreso,
                     ev.fecha_reparado
              FROM ingresos t
              JOIN devices d ON d.id=t.device_id
              JOIN customers c ON c.id=d.customer_id
              LEFT JOIN marcas b ON b.id=d.marca_id
              LEFT JOIN models m ON m.id=d.model_id
              LEFT JOIN locations loc ON loc.id = t.ubicacion_id
              LEFT JOIN LATERAL (
                SELECT e.ts AS fecha_reparado
                FROM ingreso_events e
                WHERE e.ingreso_id = t.id AND e.a_estado = 'reparado'
                ORDER BY e.ts DESC, e.id DESC
                LIMIT 1
              ) ev ON TRUE
              WHERE t.estado IN ('reparado')
                AND loc.nombre ILIKE 'taller'
              ORDER BY COALESCE(ev.fecha_reparado, t.fecha_ingreso) DESC;
            """)
            rows = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(rows, many=True).data)

class LiberadosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            cur.execute(
                "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                 getattr(request, "user_role", "")]
            )
            cur.execute("""
                SELECT
                  t.id,
                  t.estado,
                  t.presupuesto_estado,
                  c.razon_social,
                  d.numero_serie,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  t.fecha_ingreso,
                  t.ubicacion_id,
                  COALESCE(l.nombre,'') AS ubicacion_nombre,
                  ev.fecha_listo
                FROM ingresos t
                JOIN devices   d ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas    b ON b.id = d.marca_id
                LEFT JOIN models    m ON m.id = d.model_id
                LEFT JOIN locations l ON l.id = t.ubicacion_id
                LEFT JOIN LATERAL (
                  SELECT e.ts AS fecha_listo
                  FROM ingreso_events e
                  WHERE e.ingreso_id = t.id AND e.a_estado = 'liberado'
                  ORDER BY e.ts DESC, e.id DESC
                  LIMIT 1
                ) ev ON TRUE
                WHERE t.estado = 'liberado'
                  AND l.nombre ILIKE 'taller'
                ORDER BY COALESCE(ev.fecha_listo, t.fecha_ingreso) DESC;
            """)
            rows = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(rows, many=True).data)
    
class GeneralEquiposView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        qtxt = (request.GET.get("q") or "").strip()
        estado = (request.GET.get("estado") or "").strip().lower()
        ubicacion_id = (request.GET.get("ubicacion_id") or "").strip()
        solo_taller = (request.GET.get("solo_taller") or "1") in ("1","true","t","yes","y")
        with connection.cursor() as cur:
            cur.execute(
                "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                 getattr(request, "user_role", "")]
            )
            base = """
              SELECT t.id, t.estado, t.presupuesto_estado, t.fecha_ingreso, t.ubicacion_id,
                     COALESCE(loc.nombre, '') AS ubicacion_nombre,
                     c.razon_social,
                     d.numero_serie,
                     COALESCE(b.nombre,'') AS marca,
                     COALESCE(m.nombre,'') AS modelo
              FROM ingresos t
              JOIN devices d ON d.id=t.device_id
              JOIN customers c ON c.id=d.customer_id
              LEFT JOIN marcas b ON b.id=d.marca_id
              LEFT JOIN models m ON m.id=d.model_id
              LEFT JOIN locations loc ON loc.id = t.ubicacion_id
              WHERE 1=1
            """
            params = []
            if solo_taller:
                base += " AND loc.nombre ILIKE 'taller'"
            if estado:
                base += " AND t.estado = %s"
                params.append(estado)
            if ubicacion_id.isdigit():
                base += " AND t.ubicacion_id = %s"
                params.append(int(ubicacion_id))
            if qtxt:
                base += " AND (c.razon_social ILIKE %s OR d.numero_serie ILIKE %s OR b.nombre ILIKE %s OR m.nombre ILIKE %s)"
                like = f"%{qtxt}%"
                params += [like, like, like, like]
            base += " ORDER BY t.fecha_ingreso DESC LIMIT 1000"
            cur.execute(base, params)
            data = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(data, many=True).data)
        
class IngresoDetalleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ingreso_id: int):
        row = q("""
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
              t.accesorios,
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
        """, [ingreso_id], one=True)
        if not row:
            return Response({"detail": "Ingreso no encontrado"}, status=404)
        row["os"] = os_label(row["id"])
        accs = q("""
          SELECT ia.id, ia.accesorio_id, ca.nombre AS accesorio_nombre, ia.referencia, ia.descripcion
          FROM ingreso_accesorios ia
          JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id AND ca.activo
          WHERE ia.ingreso_id=%s
          ORDER BY ia.id
        """, [ingreso_id])
        row["accesorios_items"] = accs
        return Response(IngresoDetailWithAccesoriosSerializer(row).data)

    def patch(self, request, ingreso_id: int):
        # Roles con acceso
        ROL_EDIT_DIAG = {"tecnico", "jefe", "jefe_veedor", "admin"}
        ROL_EDIT_UBIC = {"tecnico", "jefe", "jefe_veedor", "admin", "recepcion"}
        ROL_EDIT_BASICS = {"jefe", "jefe_veedor"}  # edición de datos de cliente/equipo

        rol = _rol(request)
        d = request.data or {}

        # Setear variables de auditoría en la sesión DB (para triggers audit.*)
        _set_audit_user(request)
        exec_void("SET LOCAL app.ingreso_id = %s", [ingreso_id])

        # Estado y asignación actuales
        row_est = q("SELECT estado, asignado_a FROM ingresos WHERE id=%s", [ingreso_id], one=True)
        if not row_est:
            return Response({"detail": "Ingreso no encontrado"}, status=404)
        estado_actual = (row_est["estado"] or "").lower()
        asignado_a = row_est["asignado_a"]

        sets_no_estado, params_no_estado = [], []

        # --- Ubicación ---
        if "ubicacion_id" in d:
            if rol not in ROL_EDIT_UBIC:
                raise PermissionDenied("No autorizado para modificar ubicación")
            ubicacion_id = d.get("ubicacion_id")
            if not ubicacion_id:
                raise ValidationError("ubicacion_id requerido")
            u = q("SELECT id FROM locations WHERE id=%s", [ubicacion_id], one=True)
            if not u:
                raise ValidationError("Ubicación inexistente")
            sets_no_estado.append("ubicacion_id=%s")
            params_no_estado.append(ubicacion_id)

        # --- Diagnóstico (texto y señales asociadas) ---
        # diag_present será verdadero si el técnico cargó al menos uno de:
        #   - descripción del problema (no vacía)
        #   - trabajos realizados (no vacío)
        #   - fecha de servicio (válida y no vacía)
        desc_present = False
        trab_present = False
        fecha_present = False
        if "descripcion_problema" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado para modificar diagnóstico")
            desc = (d.get("descripcion_problema") or "").strip()
            desc_present = bool(desc)
            sets_no_estado.append("descripcion_problema=%s")
            params_no_estado.append(desc)

        # --- Trabajos realizados ---
        if "trabajos_realizados" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado para modificar trabajos")
            trab_present = bool((d.get("trabajos_realizados") or "").strip())
            sets_no_estado.append("trabajos_realizados=%s")
            params_no_estado.append(d.get("trabajos_realizados"))

        # --- Accesorios ---
        if "accesorios" in d:
            if rol not in ROL_EDIT_UBIC:
                raise PermissionDenied("No autorizado para modificar accesorios")
            sets_no_estado.append("accesorios=%s")
            params_no_estado.append(d.get("accesorios"))

        # --- Fecha de servicio ---
        if "fecha_servicio" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado para modificar fecha de servicio")
            val = d.get("fecha_servicio")
            if val is None or (isinstance(val, str) and val.strip() == ""):
                sets_no_estado.append("fecha_servicio=NULL")
            else:
                dt = parse_datetime(val)
                if not dt:
                    raise ValidationError("fecha_servicio inválida")
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_current_timezone())
                sets_no_estado.append("fecha_servicio=%s")
                params_no_estado.append(dt)
                fecha_present = True

        # --- NUEVOS CAMPOS ---
        # Garantía de reparación
        if "garantia_reparacion" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado")
            sets_no_estado.append("garantia_reparacion=%s")
            params_no_estado.append(bool(d.get("garantia_reparacion")))

        # Faja de garantía
        if "faja_garantia" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado")
            sets_no_estado.append("faja_garantia = NULLIF(%s,'')")
            params_no_estado.append((d.get("faja_garantia") or "").strip())

        # Número interno MG -> devices.n_de_control
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

        # Propietario (del ingreso)
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

        # Cliente (customers)
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

        # Equipo: N° de serie
        if "numero_serie" in d:
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar N/S")
            ns = (d.get("numero_serie") or "").strip()
            exec_void(
                "UPDATE devices SET numero_serie = NULLIF(%s,'') WHERE id = (SELECT device_id FROM ingresos WHERE id=%s)",
                [ns, ingreso_id],
            )

        # Alquiler (propio del ingreso)
        if "alquilado" in d:
            if rol not in ROL_EDIT_UBIC:
                raise PermissionDenied("No autorizado")
            sets_no_estado.append("alquilado=%s")
            params_no_estado.append(bool(d.get("alquilado")))
            # Si se marcó como alquilado, reflejar en el estado del equipo
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

        # --- Transición de estado ---
        # Antes solo se promovía con descripción. Ahora también con trabajos o fecha de servicio.
        diag_present = desc_present or trab_present or fecha_present
        promote_from_ingresado = diag_present and estado_actual == "ingresado"
        promote_from_asignado  = diag_present and estado_actual == "asignado"

        if promote_from_ingresado:
            if not asignado_a:
                raise ValidationError("Antes de diagnosticar, asigná un técnico al ingreso.")
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

class DerivacionesPorIngresoView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, ingreso_id):
        require_roles(request, ["jefe", "admin","jefe_veedor", "tecnico", "recepcion"])
        rows = q("""
          SELECT ed.id, ed.ingreso_id, ed.proveedor_id, pe.nombre AS proveedor,
                 ed.remit_deriv, ed.fecha_deriv, ed.fecha_entrega, ed.estado, ed.comentarios
          FROM equipos_derivados ed
          JOIN proveedores_externos pe ON pe.id = ed.proveedor_id
          WHERE ed.ingreso_id=%s
          ORDER BY ed.fecha_deriv DESC, ed.id DESC
        """, [ingreso_id])
        return Response(rows)

class EquiposDerivadosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["jefe","admin","tecnico","recepcion"])
        rows = q("""
          SELECT t.id,
                 t.estado,
                 c.razon_social,
                 d.numero_serie,
                 COALESCE(b.nombre,'') AS marca,
                 COALESCE(m.nombre,'') AS modelo,
                 t.fecha_ingreso,
                 ed.fecha_deriv,
                 ed.fecha_entrega,
                 ed.estado      AS estado_derivacion,
                 pe.nombre      AS proveedor
          FROM ingresos t
          JOIN devices d ON d.id=t.device_id
          JOIN customers c ON c.id=d.customer_id
          LEFT JOIN marcas b ON b.id=d.marca_id
          LEFT JOIN models m ON m.id=d.model_id
          JOIN LATERAL (
            SELECT e.*
            FROM equipos_derivados e
            WHERE e.ingreso_id = t.id
            ORDER BY e.fecha_deriv DESC, e.id DESC
            LIMIT 1
          ) ed ON TRUE
          LEFT JOIN proveedores_externos pe ON pe.id = ed.proveedor_id
          WHERE t.estado = 'derivado'
          ORDER BY ed.fecha_deriv DESC, t.id DESC
        """)
        return Response(rows)

class CatalogoRolesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        # [{value,label}, ...]
        return Response([{"value": k, "label": v} for k, v in ROLE_CHOICES])

class CerrarReparacionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe","jefe_veedor","admin"])
        r = (request.data or {}).get("resolucion")
        if r not in ("reparado","no_reparado","no_se_encontro_falla","presupuesto_rechazado"):
            return Response({"detail": "resolución inválida"}, status=400)

        with connection.cursor() as cur:
            cur.execute(
                "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                [str(getattr(getattr(request,"user",None),"id",None) or getattr(request,"user_id","")),
                 getattr(request,"user_role","")]
            )
            cur.execute("""
                 UPDATE ingresos
                    SET resolucion = %s
                  WHERE id = %s
            """, [r, ingreso_id])
        return Response({"ok": True})

class RemitoSalidaPdfView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, ingreso_id: int):
        require_roles(request, ["jefe", "admin", "recepcion","jefe_veedor"])
        _set_audit_user(request)

        cur_row = q("SELECT resolucion, estado FROM ingresos WHERE id=%s", [ingreso_id], one=True)
        if not cur_row:
            return Response(status=404)
        if not cur_row["resolucion"] and cur_row["estado"] != 'liberado':
            return Response({"detail": "No se puede liberar sin resolución"}, status=409)

        exec_void("""
          UPDATE ingresos
             SET estado = 'liberado'
           WHERE id=%s AND estado <> 'entregado'
        """, [ingreso_id])

        pdf_bytes, fname = render_remito_salida_pdf(ingreso_id, printed_by=getattr(request.user, "nombre", ""))
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{fname}"'
        return resp

class IngresoHistorialView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, ingreso_id: int):
        # Solo lectura para roles de supervisión/administración
        require_roles(request, ["jefe", "jefe_veedor", "admin"])
        rows = q(
            """
              SELECT ts, user_id, user_role, table_name, record_id, column_name, old_value, new_value
              FROM audit.change_log
              WHERE ingreso_id = %s
              ORDER BY ts DESC, id DESC
            """,
            [ingreso_id]
        ) or []
        return Response(rows)


class BuscarAccesorioPorReferenciaView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        require_roles(request, ["tecnico","jefe","jefe_veedor","admin","recepcion"])
        ref = (request.GET.get("ref") or "").strip()
        if not ref:
            return Response([], status=200)
        like = f"%{ref}%"
        with connection.cursor() as cur:
            cur.execute(
                "SET LOCAL app.user_id = %s; SET LOCAL app.user_role = %s;",
                [str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", "")),
                 getattr(request, "user_role", "")]
            )
            cur.execute("""
                SELECT
                  t.id,
                  t.estado,
                  t.presupuesto_estado,
                  t.fecha_ingreso,
                  c.razon_social,
                  d.numero_serie,
                  COALESCE(b.nombre,'') AS marca,
                  COALESCE(m.nombre,'') AS modelo,
                  ia.referencia,
                  COALESCE(ca.nombre,'') AS accesorio_nombre
                FROM ingreso_accesorios ia
                JOIN ingresos t ON t.id = ia.ingreso_id
                JOIN devices  d ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id
                WHERE (ia.referencia ILIKE %s)
                ORDER BY t.fecha_ingreso DESC, t.id DESC;
            """, [like])
            rows = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(rows, many=True).data)
