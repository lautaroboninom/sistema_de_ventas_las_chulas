# service/views.py


# service/views.py
from django.db import connection, transaction, IntegrityError
import unicodedata
import os
import secrets, hashlib, datetime as dt
import logging
import json
from urllib import request as urlrequest
from urllib.parse import quote
from django.conf import settings
from django.core.cache import cache
from django.template.loader import get_template
from django.core.mail import send_mail
from django.core.files.storage import default_storage
from django.utils import timezone
from django.http import HttpResponse, FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import permissions
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.exceptions import PermissionDenied, ValidationError, AuthenticationFailed
from django.utils.dateparse import parse_datetime, parse_date
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from .auth import issue_token, verify_hash, JWT_TTL_MIN as AUTH_JWT_TTL_MIN
from .ip_utils import get_client_ip
from .models import User, Ingreso, Quote, Customer
from .serializers import (
    IngresoSerializer, QuoteDetailSerializer,QuoteItemSerializer,
    IngresoListItemSerializer, IngresoDetailSerializer,
    IngresoDetailWithAccesoriosSerializer,
    IngresoMediaItemSerializer,
)
from decimal import Decimal, ROUND_HALF_UP
from .pdf import ( render_quote_pdf, render_remito_salida_pdf)
from .media_utils import (process_upload, save_processed_image, delete_media_paths, MediaValidationError, MediaProcessingError)
from .roles import ROLE_CHOICES, ROLE_KEYS
from .constants import DEFAULT_LOCATION_NAMES, LOCATION_NAME_REMAPS
logger = logging.getLogger(__name__)

TOKEN_TTL_MIN = 30       # vence en 30 minutos
COOLDOWN_MIN  = 1       # máx 1 mail cada 1 minutos por usuario
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "5"))
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
LOGIN_LOCKOUT_SECONDS = max(1, LOGIN_LOCKOUT_MINUTES) * 60

# Pie legal para correos (solo emails, no en el sitio)
EMAIL_LEGAL_FOOTER = getattr(settings, "EMAIL_LEGAL_FOOTER", (
    "La información de este correo es confidencial y concierne únicamente a la persona a la que está dirigida. "
    "Se niega el consentimiento para que pueda ser empleada como prueba por el destinatario en los términos que autoriza el art. 318 del CCyCN. "
    "Si este mensaje no está dirigido a usted, por favor tenga presente que no tiene autorización para leer el resto de este correo, copiarlo o derivarlo a cualquier otra persona que no sea aquella a la que está dirigido, como así­ tampoco valerse del mismo. "
    "Si recibe este correo por error, por favor, avise al remitente, luego de lo cual rogamos a usted destruya el mensaje original. "
    "No se puede responsabilizar al remitente de ninguna forma por/o en relación con alguna consecuencia y/o daño que resulte del apropiado y completo enví­o y recepción del contenido de este correo."
))

def _load_email_footer_text() -> str:
    """Obtiene el pie legal desde plantilla (txt) o settings como fallback."""
    try:
        tpl = get_template("email/_legal_footer.txt")
        text = (tpl.render({}) or "").strip()
        if text:
            return text
    except Exception:
        pass
    return EMAIL_LEGAL_FOOTER

# Rebind de constantes locales a valores centralizados en settings
try:
    TOKEN_TTL_MIN = getattr(settings, 'TOKEN_TTL_MIN', TOKEN_TTL_MIN)
    COOLDOWN_MIN = getattr(settings, 'EMAIL_COOLDOWN_MIN', COOLDOWN_MIN)
    LOGIN_MAX_ATTEMPTS = getattr(settings, 'LOGIN_MAX_ATTEMPTS', LOGIN_MAX_ATTEMPTS)
    LOGIN_LOCKOUT_MINUTES = getattr(settings, 'LOGIN_LOCKOUT_MINUTES', LOGIN_LOCKOUT_MINUTES)
    LOGIN_LOCKOUT_SECONDS = getattr(settings, 'LOGIN_LOCKOUT_SECONDS', LOGIN_LOCKOUT_SECONDS)
    PASSWORD_MIN_LENGTH = getattr(settings, 'PASSWORD_MIN_LENGTH', PASSWORD_MIN_LENGTH)
except Exception:
    pass

def _email_append_footer_text(txt: str) -> str:
    try:
        base = (txt or "").rstrip()
        footer = _load_email_footer_text()
        if not footer:
            return base
        return f"{base}\n\n{footer}"
    except Exception:
        return txt

def _email_append_footer_html(html: str) -> str:
    try:
        # Cargar HTML dedicado si está disponible
        try:
            tpl = get_template("email/_legal_footer.html")
            footer_html = (tpl.render({}) or "").strip()
        except Exception:
            footer_html = ""
        if not footer_html:
            # Fallback: derivar a partir de texto
            text = _load_email_footer_text()
            if text:
                style = "font-size:10px;color:#6b7280;text-align:justify;line-height:1.3;margin-top:12px;"
                footer_html = f"<hr style=\"border:none;border-top:1px solid #e5e7eb;margin:12px 0;\"/><div style=\"{style}\">{text}</div>"
        return (html or "") + (footer_html or "")
    except Exception:
        return html

def _login_rate_key(email: str, ip: str) -> str:
    email = (email or "").strip().lower()
    ip = ip or ""
    return f"login-attempt:{email}:{ip}"

def _is_login_locked(key: str) -> bool:
    try:
        attempts = cache.get(key, 0) or 0
        return attempts >= getattr(settings, "LOGIN_MAX_ATTEMPTS", 5)
    except Exception:
        logger.debug('No se pudo leer el cache de login', exc_info=True)
        return False

def _register_login_failure(key: str) -> None:
    try:
        attempts = (cache.get(key, 0) or 0) + 1
        cache.set(key, attempts, getattr(settings, "LOGIN_LOCKOUT_SECONDS", 300))
        if attempts >= getattr(settings, "LOGIN_MAX_ATTEMPTS", 5):
            logger.warning('Login bloqueado por demasiados intentos')
    except Exception:
        logger.debug('No se pudo registrar intento fallido de login', exc_info=True)

def _reset_login_failure(key: str) -> None:
    try:
        cache.delete(key)
    except Exception:
        logger.debug('No se pudo limpiar el estado de login', exc_info=True)

def _validate_password_strength(password: str) -> None:
    if len(password) < getattr(settings, "PASSWORD_MIN_LENGTH", 8):
        raise ValidationError(f"La contrasena debe tener al menos {getattr(settings, 'PASSWORD_MIN_LENGTH', 8)} caracteres.")
    classes = 0
    if any(c.islower() for c in password):
        classes += 1
    if any(c.isupper() for c in password):
        classes += 1
    if any(c.isdigit() for c in password):
        classes += 1
    if any(not c.isalnum() for c in password):
        classes += 1
    if classes < 3:
        raise ValidationError('La contrasena debe combinar mayusculas, minusculas, numeros o simbolos.')

_DEPRECATED_ROLE_CHOICES = [
    ("tecnico", "Técnico"),
    ("admin", "Administración"),
    ("jefe", "Jefe"),
    ("jefe_veedor", "Jefe veedor"),
    ("recepcion", "Recepción"),
]
_DEPRECATED_ROLE_KEYS = [r for r, _ in _DEPRECATED_ROLE_CHOICES]
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
    if connection.vendor == "postgresql":
        uid = str(getattr(getattr(request, "user", None), "id", None) or getattr(request, "user_id", ""))
        role = getattr(request, "user_role", "")
        with connection.cursor() as cur:
            # SET (no LOCAL) para compatibilidad fuera de transacciones explí­citas
            cur.execute("SET app.user_id = %s;", [uid])
            cur.execute("SET app.user_role = %s;", [role])
# ---------------------------------------
# Utilidades DB
_SUSPECT_UTF8 = ("íƒ", "í‚", "Â¤", "Â¢", "\ufffd")


def _fix_text_value(val):
    if isinstance(val, bytes):
        try:
            return val.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return val.decode("latin1")
            except Exception:
                return val.decode("utf-8", errors="ignore")
    if isinstance(val, str):
        if not val:
            return val
        if any(ch in val for ch in _SUSPECT_UTF8):
            try:
                return val.encode("latin1").decode("utf-8")
            except Exception:
                return val
        # Fix common mojibake: strings containing 'Ã' or 'Â'
        if ("Ã" in val) or ("Â" in val):
            try:
                fixed = val.encode("latin1").decode("utf-8")
                return fixed
            except Exception:
                pass
    return val


def _fix_row(row):
    if isinstance(row, dict):
        return {k: _fix_text_value(v) for k, v in row.items()}
    return row


def q(sql, params=None, one=False):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        if cur.description:
            cols = [c[0] for c in cur.description]
            rows = [_fix_row(dict(zip(cols, r))) for r in cur.fetchall()]
            if one:
                return rows[0] if rows else None
            return rows
        return None


def exec_returning(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
        return row[0] if row else None

def last_insert_id():
    """Devuelve el último ID autoincremental según el motor actual."""
    if connection.vendor == "postgresql":
        row = q("SELECT LASTVAL() AS id", one=True)
    else:
        row = q("SELECT LAST_INSERT_ID() AS id", one=True)
    return row and row.get("id")

# ------------------------------
# Catálogo 'motivo' (ENUM) utils
# ------------------------------
def _norm_txt(val: str) -> str:
    """Lowercase + remove diacritics; also runs through _fix_text_value."""
    try:
        s = _fix_text_value(val)
        s = "" if s is None else str(s)
        # strip + lowercase + remove diacritics
        s = s.strip().lower()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        return s
    except Exception:
        return (val or "").strip().lower()

def _get_motivo_enum_values() -> list:
    """Obtiene los valores válidos del ENUM ingresos.motivo para el motor actual.
    Fallback defensivo si falla la introspección.
    """
    try:
        if connection.vendor == "postgresql":
            rows = q(
                """
                SELECT e.enumlabel AS v
                  FROM pg_type t
                  JOIN pg_enum e ON e.enumtypid = t.oid
                 WHERE t.typname = 'motivo_ingreso'
                """
            ) or []
            vals = [(_fix_text_value(r.get("v"))) for r in rows]
        else:
            row = q(
                """
                SELECT COLUMN_TYPE AS ct
                  FROM information_schema.columns
                 WHERE table_schema = DATABASE()
                   AND table_name = 'ingresos'
                   AND column_name = 'motivo'
                """,
                one=True,
            )
            vals = []
            if row and (row.get("ct") or "").lower().startswith("enum("):
                ct = row["ct"][5:-1]  # contenido dentro de enum(...)
                for p in ct.split(","):
                    v = p.strip().strip("'")
                    if v:
                        vals.append(_fix_text_value(v))
        vals = [v for v in (vals or []) if v]
        if vals:
            return vals
    except Exception:
        pass
    # Fallback estable (incluye acentos correctos)
    return [
        "urgente control",
        "reparación",
        "service preventivo",
        "baja alquiler",
        "reparación alquiler",
        "devolución demo",
        "otros",
    ]

def _get_motivo_enum_values_raw() -> list:
    """Devuelve las etiquetas del ENUM exactamente como están en DB (sin corrección)."""
    try:
        if connection.vendor == "postgresql":
            rows = q(
                """
                SELECT e.enumlabel AS v
                  FROM pg_type t
                  JOIN pg_enum e ON e.enumtypid = t.oid
                 WHERE t.typname = 'motivo_ingreso'
                """
            ) or []
            return [r.get("v") for r in rows if r.get("v")]
        else:
            row = q(
                """
                SELECT COLUMN_TYPE AS ct
                  FROM information_schema.columns
                 WHERE table_schema = DATABASE()
                   AND table_name = 'ingresos'
                   AND column_name = 'motivo'
                """,
                one=True,
            )
            vals = []
            if row and (row.get("ct") or "").lower().startswith("enum("):
                ct = row["ct"][5:-1]
                for p in ct.split(","):
                    v = p.strip().strip("'")
                    if v:
                        vals.append(v)
            return vals
    except Exception:
        return []

def _map_motivo_to_db_label(user_value: str):
    """Mapea el valor recibido a la etiqueta RAW del ENUM en DB, tolerando tildes/caso."""
    user_value = (user_value or "").strip()
    if not user_value:
        return None
    raw_vals = _get_motivo_enum_values_raw()
    if not raw_vals:
        return None
    by_key = {}
    for raw in raw_vals:
        disp = _fix_text_value(raw)
        for cand in (raw, disp):
            k1 = (cand or "").strip().lower()
            k2 = _norm_txt(cand)
            if k1 and k1 not in by_key:
                by_key[k1] = raw
            if k2 and k2 not in by_key:
                by_key[k2] = raw
    k_user1 = user_value.strip().lower()
    k_user2 = _norm_txt(user_value)
    return by_key.get(k_user1) or by_key.get(k_user2)

def _fetchall_dicts(cur):
    cols = [c[0] for c in cur.description]
    return [_fix_row(dict(zip(cols, row))) for row in cur.fetchall()]


MEDIA_VIEW_ROLES = {"jefe", "admin", "jefe_veedor", "recepcion", "tecnico"}
MEDIA_MANAGE_ROLES = {"jefe", "admin", "jefe_veedor", "tecnico"}

# Base SELECT for ingreso_media queries
MEDIA_SELECT_BASE = """
    SELECT
      im.id, im.ingreso_id, im.usuario_id,
      COALESCE(u.nombre, '') AS usuario_nombre,
      im.comentario, im.mime_type, im.size_bytes, im.width, im.height,
      im.original_name, im.storage_path, im.thumbnail_path,
      im.created_at, im.updated_at
    FROM ingreso_media im
    LEFT JOIN users u ON u.id = im.usuario_id
"""

def _fetch_media_row(ingreso_id: int, media_id: int):
    sql = MEDIA_SELECT_BASE + " WHERE im.ingreso_id=%s AND im.id=%s"
    return q(sql, [ingreso_id, media_id], one=True)


def _fetch_media_page(ingreso_id: int, limit: int, offset: int):
    sql = (
        MEDIA_SELECT_BASE
        + " WHERE im.ingreso_id=%s"
        + " ORDER BY im.created_at DESC, im.id DESC"
        + " LIMIT %s OFFSET %s"
    )
    return q(sql, [ingreso_id, limit, offset])


def _current_user_id(request):
    uid = getattr(getattr(request, "user", None), "id", None)
    if uid is not None:
        return uid
    try:
        return int(getattr(request, "user_id", None))
    except (TypeError, ValueError):
        return None


def _fetch_ingreso_assignation(ingreso_id: int):
    return q("SELECT id, asignado_a FROM ingresos WHERE id=%s", [ingreso_id], one=True)


def _ensure_media_view_perm(request, ingreso_row):
    rol = _rol(request)
    if rol in MEDIA_VIEW_ROLES - {"tecnico"}:
        return
    if rol == "tecnico" and ingreso_row and ingreso_row.get("asignado_a") == _current_user_id(request):
        return
    raise PermissionDenied("No autorizado para ver fotos del ingreso")


def _ensure_media_manage_perm(request, ingreso_row):
    rol = _rol(request)
    if rol in MEDIA_MANAGE_ROLES - {"tecnico"}:
        return
    if rol == "tecnico" and ingreso_row and ingreso_row.get("asignado_a") == _current_user_id(request):
        return
    raise PermissionDenied("No autorizado para gestionar fotos del ingreso")


def _serialize_media_row(row, ingreso_id: int, request=None):
    base_path = f"/api/ingresos/{ingreso_id}/fotos/{row['id']}"
    item = {
        "id": row.get("id"),
        "ingreso_id": ingreso_id,
        "usuario_id": row.get("usuario_id"),
        "usuario_nombre": row.get("usuario_nombre", ""),
        "comentario": row.get("comentario"),
        "mime_type": row.get("mime_type"),
        "size_bytes": row.get("size_bytes"),
        "width": row.get("width"),
        "height": row.get("height"),
        "original_name": row.get("original_name"),
        "url": base_path + "/archivo/",
        "thumbnail_url": base_path + "/miniatura/",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
    return IngresoMediaItemSerializer(item).data


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

# ======================================
# Métricas helpers (business hours, fechas)
# ======================================

WORKDAY_START_HOUR = int(os.getenv("WORKDAY_START_HOUR", "9"))
WORKDAY_END_HOUR = int(os.getenv("WORKDAY_END_HOUR", "17"))
WORKDAYS = set(int(x) for x in os.getenv("WORKDAYS", "0,1,2,3,4").split(",") if x != "")  # 0=Lunes


def _tz_aware(dtobj: dt.datetime):
    if not isinstance(dtobj, dt.datetime):
        return None
    if timezone.is_naive(dtobj):
        return timezone.make_aware(dtobj, timezone.get_current_timezone())
    return dtobj


def _clamp_to_work_window_forward(ts: dt.datetime) -> dt.datetime:
    ts = _tz_aware(ts)
    if ts is None:
        return ts
    d = ts
    while d.weekday() not in WORKDAYS:
        d = (d + dt.timedelta(days=1)).replace(hour=WORKDAY_START_HOUR, minute=0, second=0, microsecond=0)
    start = d.replace(hour=WORKDAY_START_HOUR, minute=0, second=0, microsecond=0)
    end = d.replace(hour=WORKDAY_END_HOUR, minute=0, second=0, microsecond=0)
    if d < start:
        return start
    if d > end:
        d = d + dt.timedelta(days=1)
        while d.weekday() not in WORKDAYS:
            d = d + dt.timedelta(days=1)
        return d.replace(hour=WORKDAY_START_HOUR, minute=0, second=0, microsecond=0)
    return d


def _clamp_to_work_window_backward(ts: dt.datetime) -> dt.datetime:
    ts = _tz_aware(ts)
    if ts is None:
        return ts
    d = ts
    while d.weekday() not in WORKDAYS:
        d = (d - dt.timedelta(days=1)).replace(hour=WORKDAY_END_HOUR, minute=0, second=0, microsecond=0)
    start = d.replace(hour=WORKDAY_START_HOUR, minute=0, second=0, microsecond=0)
    end = d.replace(hour=WORKDAY_END_HOUR, minute=0, second=0, microsecond=0)
    if d > end:
        return end
    if d < start:
        d = d - dt.timedelta(days=1)
        while d.weekday() not in WORKDAYS:
            d = d - dt.timedelta(days=1)
        return d.replace(hour=WORKDAY_END_HOUR, minute=0, second=0, microsecond=0)
    return d


def _holidays_country():
    try:
        return getattr(settings, 'HOLIDAYS_COUNTRY', None) or os.getenv('HOLIDAYS_COUNTRY', 'AR')
    except Exception:
        return 'AR'


def _parse_extra_holidays_env():
    s = os.getenv('HOLIDAYS_EXTRA_DATES', '')
    out = set()
    if not s:
        return out
    for part in s.split(','):
        part = (part or '').strip()
        if not part:
            continue
        date_s = part.split(':', 1)[0].strip()
        try:
            y, m, d = [int(x) for x in date_s.split('-')]
            out.add(dt.date(y, m, d))
        except Exception:
            continue
    return out


def _fetch_nager_year(country: str, year: int):
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
    try:
        with urlrequest.urlopen(url, timeout=8) as resp:
            if getattr(resp, 'status', 200) != 200:
                return []
            data = json.loads(resp.read().decode('utf-8'))
            dates = []
            for it in data or []:
                ds = (it.get('date') or '').strip()  # 'YYYY-MM-DD'
                try:
                    y, m, d = [int(x) for x in ds.split('-')]
                    dates.append(dt.date(y, m, d))
                except Exception:
                    continue
            return dates
    except Exception:
        return []


def _get_year_holidays(country: str, year: int):
    ck = f"holidays:year:{country}:{year}"
    cached = cache.get(ck)
    if cached is not None:
        return cached
    dates = set(_fetch_nager_year(country, year))
    # Fallback/overlay con DB local (si existe)
    try:
        rows = q("SELECT fecha FROM feriados WHERE YEAR(fecha)=%s", [year]) or []
        dates |= {r.get('fecha') for r in rows if r.get('fecha')}
    except Exception:
        pass
    # Extras por ENV
    dates |= _parse_extra_holidays_env()
    cache.set(ck, dates, 12 * 3600)
    return dates


def _holidays_between(d1: dt.date, d2: dt.date):
    try:
        country = _holidays_country()
        k = f"holidays:{country}:{d1.isoformat()}:{d2.isoformat()}"
        cached = cache.get(k)
        if cached is not None:
            return cached
        cur = d1
        out = set()
        seen_years = set()
        while cur <= d2:
            if cur.year not in seen_years:
                out |= _get_year_holidays(country, cur.year)
                seen_years.add(cur.year)
            cur += dt.timedelta(days=1)
        out = {d for d in out if d1 <= d <= d2}
        cache.set(k, out, 6 * 3600)
        return out
    except Exception:
        return set()


def business_minutes_between(start, end, holidays=None):
    if not start or not end:
        return 0
    s = _clamp_to_work_window_forward(_tz_aware(start))
    e = _clamp_to_work_window_backward(_tz_aware(end))
    if not s or not e or e <= s:
        return 0
    total = 0
    day = s.date()
    end_day = e.date()
    if holidays is None:
        holidays = _holidays_between(day, end_day)
    while day <= end_day:
        if (day.weekday() in WORKDAYS) and (day not in (holidays or set())):
            ws = dt.datetime.combine(day, dt.time(hour=WORKDAY_START_HOUR, tzinfo=s.tzinfo))
            we = dt.datetime.combine(day, dt.time(hour=WORKDAY_END_HOUR, tzinfo=s.tzinfo))
            seg_ini = max(ws, s)
            seg_fin = min(we, e)
            if seg_fin > seg_ini:
                total += int((seg_fin - seg_ini).total_seconds() // 60)
        day = day + dt.timedelta(days=1)
    return max(0, total)


def _parse_range_params(request):
    tz = timezone.get_current_timezone()
    now = timezone.now()
    from_s = request.GET.get("from") or request.GET.get("desde")
    to_s = request.GET.get("to") or request.GET.get("hasta")
    if from_s:
        try:
            d = parse_date(from_s)
            from_dt = timezone.make_aware(dt.datetime.combine(d, dt.time.min), tz)
        except Exception:
            from_dt = now - dt.timedelta(days=30)
    else:
        from_dt = now - dt.timedelta(days=30)
    if to_s:
        try:
            d = parse_date(to_s)
            to_dt = timezone.make_aware(dt.datetime.combine(d, dt.time.max), tz)
        except Exception:
            to_dt = now
    else:
        to_dt = now
    return from_dt, to_dt


def _first_event_ts_map(state_name: str):
    rows = q(
        """
        SELECT ingreso_id, MIN(ts) AS ts
        FROM ingreso_events
        WHERE a_estado=%s
        GROUP BY ingreso_id
        """,
        [state_name],
    ) or []
    return {r["ingreso_id"]: r["ts"] for r in rows}


def _metrics_build_diag_map():
    diag = q(
        """
        SELECT i.id AS ingreso_id,
               COALESCE(di.ts, i.fecha_servicio, i.fecha_ingreso) AS diag_ts,
               i.fecha_ingreso
        FROM ingresos i
        LEFT JOIN (
          SELECT ingreso_id, MIN(ts) AS ts
          FROM ingreso_events
          WHERE a_estado='diagnosticado'
          GROUP BY ingreso_id
        ) di ON di.ingreso_id=i.id
        """
    ) or []
    return {r["ingreso_id"]: {"diag_ts": r["diag_ts"], "fecha_ingreso": r["fecha_ingreso"]} for r in diag}


def _daterange_months(start_dt: dt.datetime, end_dt: dt.datetime):
    y, m = start_dt.year, start_dt.month
    while (y < end_dt.year) or (y == end_dt.year and m <= end_dt.month):
        yield y, m
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1


def _month_key(y, m):
    return f"{y:04d}-{m:02d}"


def _calc_percentiles(values, percent_list=(50, 75, 90, 95)):
    arr = sorted([float(v) for v in values if v is not None])
    n = len(arr)
    if n == 0:
        return {f"p{p}": None for p in percent_list} | {"avg": None, "count": 0}
    def pct(p):
        if n == 1:
            return arr[0]
        k = (p/100.0) * (n - 1)
        f = int(k)
        c = min(f + 1, n - 1)
        if f == c:
            return arr[f]
        d0 = arr[f] * (c - k)
        d1 = arr[c] * (k - f)
        return d0 + d1
    out = {f"p{p}": pct(p) for p in percent_list}
    out["avg"] = sum(arr) / n
    out["count"] = n
    return out

_DEPRECATED_DEFAULT_LOCATION_NAMES = [
    "Taller",
    "Estanterí­a de Alquiler",
    "Sarmiento",
    "Depósito SEPID",
    "Desguace",
]



def ensure_default_locations():
    # Usar nombres canónicos corregidos (evita duplicados por encoding)
    
    NAMES = [
        "Taller",
        "Estanterí­a de Alquiler",
        "Sarmiento",
        "Depósito SEPID",
        "Desguace",
    ]
    REMAPS = {
        "estanteria alquileres": "Estanterí­a de Alquiler",
        "estanteria de alquiler": "Estanterí­a de Alquiler",
        "estanterí­a de aluiler": "Estanterí­a de Alquiler",
        "estanteria de aluiler": "Estanterí­a de Alquiler",
    }
    with connection.cursor() as cur:
        for alias, target in LOCATION_NAME_REMAPS.items():
            cur.execute(
                "UPDATE locations SET nombre=%s WHERE LOWER(nombre)=LOWER(%s)",
                [target, alias],
            )
        for name in DEFAULT_LOCATION_NAMES:
            cur.execute(
                """
                INSERT INTO locations (nombre)
                SELECT %s
                FROM (SELECT 1) AS _seed
                WHERE NOT EXISTS (
                    SELECT 1 FROM locations WHERE LOWER(nombre)=LOWER(%s)
                )
                """,
                [name, name],
            )


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
    if connection.vendor == "postgresql":
        try:
            # Insertar si no existe y devolver id
            new_id = exec_returning(
                "INSERT INTO quotes(ingreso_id) VALUES (%s) RETURNING id",
                [ingreso_id],
            )
            return new_id
        except Exception:
            # Si ya existe por condición de carrera, recuperar id existente
            row2 = q("SELECT id FROM quotes WHERE ingreso_id=%s", [ingreso_id], one=True)
            if row2:
                return row2["id"]
            raise
    else:
        # MySQL upsert + obtener id: ON DUPLICATE KEY + LAST_INSERT_ID
        exec_void(
            """
            INSERT INTO quotes(ingreso_id) VALUES (%s)
            ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)
            """,
            [ingreso_id],
        )
        # LAST_INSERT_ID() devuelve el id nuevo o el existente por el UPDATE anterior
        rid = last_insert_id()
        return rid or q("SELECT id FROM quotes WHERE ingreso_id=%s", [ingreso_id], one=True)["id"]

def os_label(_id: int) -> str:
    """Etiqueta legible para Orden de Servicio."""
    try:
        return f"OS {str(int(_id)).zfill(6)}"
    except Exception:
        return f"OS {str(_id)}"

class NuevoIngresoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        data = request.data or {}
        cliente = data.get("cliente") or {}
        equipo  = data.get("equipo") or {}
        # Motivo de ingreso: validar y normalizar contra ENUM de DB
        motivo_raw = (data.get("motivo") or "").strip()
        if not motivo_raw:
            return Response({"detail": "motivo requerido"}, status=400)
        # Mapear al label EXACTO del ENUM en DB (tolerando acentos/caso)
        motivo_label_raw = _map_motivo_to_db_label(motivo_raw)
        if not motivo_label_raw:
            valid_motivos = _get_motivo_enum_values()
            return Response({"detail": "motivo inválido", "valid_values": valid_motivos}, status=400)
        motivo = motivo_label_raw
        # Número interno (MG): normalizar prefijo
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

        # Opcionales: remito de ingreso y fecha de ingreso
        remito_ingreso = (data.get("remito_ingreso") or "").strip()
        fecha_ingreso_dt = None
        _fi_raw = data.get("fecha_ingreso")
        if _fi_raw is not None and str(_fi_raw).strip() != "":
            _fi_str = str(_fi_raw).strip()
            _dt = parse_datetime(_fi_str)
            if not _dt:
                _d = parse_date(_fi_str)
                if _d:
                    from datetime import datetime
                    _dt = datetime(_d.year, _d.month, _d.day, 0, 0, 0)
            if _dt:
                if timezone.is_naive(_dt):
                    _dt = timezone.make_aware(_dt, timezone.get_current_timezone())
                fecha_ingreso_dt = _dt

        # motivo ya validado arriba
        
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

        # Si ya existe un ingreso NO ENTREGADO para el mismo cliente y N/S,
        # devolver ese ingreso en lugar de crear uno nuevo (evita duplicados).
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

        # Importante: no reutilizar un equipo por n° de serie si pertenece a otro cliente.
        # Solo se reutiliza si coincide el numero_serie Y el customer_id resuelto arriba.
        dev = None
        if numero_serie:
            dev = q(
                "SELECT id FROM devices WHERE numero_serie=%s AND customer_id=%s",
                [numero_serie, customer_id],
                one=True,
            )
        dev = None
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

        # --- Garantí­a de reparación por N/S o N° interno (MG): última fecha_entrega < 90 dí­as ---
        
        auto_gar_rep = False
        last_out_candidates = []
        # Por número de serie
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
            last_out_ns = row_last_ns and row_last_ns.get("last_out")
            if last_out_ns:
                last_out_candidates.append(last_out_ns)
        # Por número interno (MG)
        if numero_interno:
            row_last_mg = q(
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
            last_out_mg = row_last_mg and row_last_mg.get("last_out")
            if last_out_mg:
                last_out_candidates.append(last_out_mg)
        if last_out_candidates:
            last_out = max(last_out_candidates)
            auto_gar_rep = (timezone.now() - last_out).days <= 90
        garantia_rep_payload = bool(data.get("garantia_reparacion"))
        garantia_rep_final = garantia_rep_payload or auto_gar_rep

        # ---- Técnico asignado ----
        # 1) viene en payload -> ok; 2) default por modelo -> ok
        tecnico_id = data.get("tecnico_id")
        if not tecnico_id:
            tdef = q("SELECT tecnico_id FROM models WHERE id=%s", [equipo["modelo_id"]], one=True)
            tecnico_id = tdef["tecnico_id"] if tdef else None

        # í¢ÂœÂ… 3) fallback por marca si el modelo no tiene
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
        _set_audit_user(request)
        
        # Ingreso (usa DEFAULT 'ingresado')
        equipo_variante = (request.data.get("equipo_variante") or "").strip() or None
        if connection.vendor == "postgresql":
            ingreso_id = exec_returning(
                """
                INSERT INTO ingresos (
                  device_id, motivo, ubicacion_id, recibido_por, asignado_a,
                  informe_preliminar, accesorios, equipo_variante,
                  propietario_nombre, propietario_contacto, propietario_doc,
                  garantia_reparacion
                )
                VALUES (%s,%s,%s,%s,%s,
                        %s,%s,%s,
                        NULLIF(%s,''), NULLIF(%s,''), NULLIF(%s,''),
                        %s)
                RETURNING id
                """,
                [device_id, motivo, ubicacion_id, uid, tecnico_id,
                 informe_preliminar, accesorios_text, equipo_variante,
                 prop_nombre, prop_contacto, prop_doc,
                 garantia_rep_final]
            )
        else:
            exec_void(
                """
                INSERT INTO ingresos (
                  device_id, motivo, ubicacion_id, recibido_por, asignado_a,
                  informe_preliminar, accesorios, equipo_variante,
                  propietario_nombre, propietario_contacto, propietario_doc,
                  garantia_reparacion
                )
                VALUES (%s,%s,%s,%s,%s,
                        %s,%s,%s,
                        NULLIF(%s,''), NULLIF(%s,''), NULLIF(%s,''),
                        %s)
                """,
                [device_id, motivo, ubicacion_id, uid, tecnico_id,
                 informe_preliminar, accesorios_text, equipo_variante,
                 prop_nombre, prop_contacto, prop_doc,
                 garantia_rep_final]
            )
            ingreso_id = last_insert_id()

        # Aplicar remito_ingreso y/o fecha_ingreso si fueron provistos
        sets, params = [], []
        if remito_ingreso:
            sets.append("remito_ingreso = NULLIF(%s,'')")
            params.append(remito_ingreso)
        if fecha_ingreso_dt is not None:
            sets.append("fecha_ingreso = %s")
            params.append(fecha_ingreso_dt)
        if sets:
            params.append(ingreso_id)
            exec_void(
                f"UPDATE ingresos SET {', '.join(sets)} WHERE id=%s",
                params,
            )

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
        mg = (request.GET.get("numero_interno") or request.GET.get("mg") or "").strip()
        if mg and not mg.upper().startswith("MG"):
            mg = "MG " + mg
        if not ns and not mg:
            return Response({"within_90_days": False, "last_ingreso": None})

        last_out_candidates = []
        # Buscar por número de serie
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

        # Buscar por número interno (MG)
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
        # Mantenemos la clave last_ingreso por compatibilidad (aunque es fecha_entrega)
        return Response({"within_90_days": within, "last_ingreso": last_out})
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

    def post(self, request):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        data = request.data or {}
        nombre = (data.get("nombre") or "").strip()
        if not nombre:
            raise ValidationError("nombre requerido")

        tecnico_raw = data.get("tecnico_id")
        tecnico_id = None
        if tecnico_raw not in (None, "", "null"):
            try:
                tecnico_id = int(tecnico_raw)
            except (TypeError, ValueError):
                raise ValidationError("tecnico_id inválido")

        existing = q(
            "SELECT id FROM marcas WHERE LOWER(nombre)=LOWER(%s)",
            [nombre],
            one=True,
        )

        _set_audit_user(request)

        if existing:
            sets = ["nombre=%s"]
            params = [nombre]
            if "tecnico_id" in data:
                if tecnico_id is None:
                    sets.append("tecnico_id=NULL")
                else:
                    sets.append("tecnico_id=%s")
                    params.append(tecnico_id)
            params.append(existing["id"])
            exec_void(
                f"UPDATE marcas SET {', '.join(sets)} WHERE id=%s",
                params,
            )
            return Response({"ok": True, "id": existing["id"], "updated": True})

        cols = ["nombre"]
        placeholders = ["%s"]
        params = [nombre]
        if tecnico_id is not None:
            cols.append("tecnico_id")
            placeholders.append("%s")
            params.append(tecnico_id)
        try:
            exec_void(
                f"INSERT INTO marcas({', '.join(cols)}) VALUES ({', '.join(placeholders)})",
                params,
            )
        except IntegrityError:
            existing = q(
                "SELECT id FROM marcas WHERE LOWER(nombre)=LOWER(%s)",
                [nombre],
                one=True,
            )
            if existing:
                return Response({"ok": True, "id": existing["id"], "updated": False})
            raise
        mid = last_insert_id()
        return Response({"ok": True, "id": mid, "created": True})


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
                COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                COALESCE(m.variante,'') AS variante
            FROM models m
            LEFT JOIN users u ON u.id = m.tecnico_id
            WHERE m.marca_id=%s
            ORDER BY m.nombre
        """, [marca_id])
        return Response(rows)


class CatalogoTiposView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _canon(value: str) -> str:
        if not value:
            return ""
        return " ".join(str(value).strip().split()).upper()

    def get(self, request, bid: int):
        try:
            marca_id = int(bid)
        except (TypeError, ValueError):
            return Response({"detail": "parametros invalidos"}, status=400)

        rows = q(
                """
                SELECT id, nombre, activo
                FROM marca_tipos_equipo
                WHERE marca_id=%s
                ORDER BY nombre
                """,
                [marca_id],
            ) or []

        data = []
        for row in rows:
            data.append({
                "id": row.get("id"),
                "name": row.get("nombre"),
                "label": self._canon(row.get("nombre")),
                "active": bool(row.get("activo")),
            })

        return Response(data)


class CatalogoModelosDeTipoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _canon(value: str) -> str:
        if not value:
            return ""
        return " ".join(str(value).strip().split()).upper()

    def get(self, request, bid: int, tid: int):
        try:
            marca_id = int(bid)
            tipo_id = int(tid)
        except (TypeError, ValueError):
            return Response({"detail": "parametros invalidos"}, status=400)

        rows = q(
            """
            SELECT id, nombre, alias, activo
            FROM marca_series
            WHERE marca_id=%s AND tipo_id=%s
            ORDER BY nombre
            """,
            [marca_id, tipo_id],
        ) or []

        data = []
        for row in rows:
            data.append({
                "id": row.get("id"),
                "name": row.get("nombre"),
                "label": self._canon(row.get("nombre")),
                "alias": row.get("alias") or "",
                "active": bool(row.get("activo")),
            })

        return Response(data)


class CatalogoVariantesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _canon(value: str) -> str:
        if not value:
            return ""
        return " ".join(str(value).strip().split()).upper()

    def get(self, request, bid: int, mid: int):
        try:
            marca_id = int(bid)
            modelo_id = int(mid)
        except (TypeError, ValueError):
            return Response({"detail": "parametros invalidos"}, status=400)

        modelo_row = q(
            "SELECT tipo_id FROM marca_series WHERE id=%s AND marca_id=%s",
            [modelo_id, marca_id],
            one=True,
        )
        if not modelo_row:
            return Response([])

        tipo_id = modelo_row.get("tipo_id")
        variantes = q(
            """
            SELECT id, nombre, activo
            FROM marca_series_variantes
            WHERE marca_id=%s AND tipo_id=%s AND serie_id=%s
            ORDER BY nombre
            """,
            [marca_id, tipo_id, modelo_id],
        ) or []

        data = []
        for row in variantes:
            data.append({
                "id": row.get("id"),
                "name": row.get("nombre"),
                "label": self._canon(row.get("nombre")),
                "active": bool(row.get("activo")),
            })

        return Response(data)


class CatalogoMarcasPorTipoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, tipo_nombre: str):
        nombre = (tipo_nombre or "").strip()
        if not nombre:
            return Response([])
        rows = q(
            """
            SELECT DISTINCT m.id, m.nombre
            FROM marcas m
            JOIN marca_tipos_equipo t ON t.marca_id = m.id
            WHERE UPPER(TRIM(t.nombre)) = UPPER(TRIM(%s))
            ORDER BY m.nombre
            """,
            [nombre],
        ) or []
        return Response(rows)

class CatalogoTiposCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        d = request.data or {}
        try:
            marca_id = int(d.get("marca_id"))
        except (TypeError, ValueError):
            return Response({"detail": "marca_id requerido"}, status=400)
        nombre = (d.get("name") or d.get("nombre") or "").strip()
        if not nombre:
            return Response({"detail": "name requerido"}, status=400)
        active = d.get("active")
        activo_val = bool(active) if active is not None else True

        _set_audit_user(request)

        if connection.vendor == "postgresql":
            # No PK auto de MySQL; upsert manual
            existing = q(
                "SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND UPPER(nombre)=UPPER(%s)",
                [marca_id, nombre], one=True,
            )
            if existing:
                if active is not None:
                    exec_void("UPDATE marca_tipos_equipo SET activo=%s WHERE id=%s", [activo_val, existing["id"]])
                return Response({"ok": True, "id": existing["id"], "updated": False})
            exec_void(
                "INSERT INTO marca_tipos_equipo(marca_id, nombre, activo) VALUES (%s,%s,%s)",
                [marca_id, nombre, activo_val],
            )
            new_id = last_insert_id()
            return Response({"ok": True, "id": new_id, "created": True})
        else:
            exec_void(
                """
                INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
                VALUES (%s,%s,%s)
                ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id), activo=VALUES(activo)
                """,
                [marca_id, nombre, int(activo_val)],
            )
            new_id = last_insert_id()
            return Response({"ok": True, "id": new_id, "created": True})


class CatalogoTipoDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, tipo_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        row = q("SELECT id, marca_id, nombre, activo FROM marca_tipos_equipo WHERE id=%s", [tipo_id], one=True)
        if not row:
            return Response({"detail": "tipo no encontrado"}, status=404)

        d = request.data or {}
        nombre = d.get("name") if "name" in d else d.get("nombre") if "nombre" in d else None
        nombre = (nombre or "").strip() if nombre is not None else None
        active = d.get("active") if "active" in d else None

        sets = []
        params = []
        if nombre is not None and nombre != row.get("nombre"):
            # Unicidad por marca
            clash = q(
                "SELECT id FROM marca_tipos_equipo WHERE marca_id=%s AND id<>%s AND UPPER(nombre)=UPPER(%s)",
                [row["marca_id"], tipo_id, nombre], one=True,
            )
            if clash:
                return Response({"detail": "ya existe un tipo con ese nombre"}, status=409)
            sets.append("nombre=%s")
            params.append(nombre)
        if active is not None:
            sets.append("activo=%s")
            params.append(bool(active))

        if not sets:
            return Response({"ok": True})

        params.append(tipo_id)
        _set_audit_user(request)
        exec_void(f"UPDATE marca_tipos_equipo SET {', '.join(sets)} WHERE id=%s", params)
        return Response({"ok": True})

    def delete(self, request, tipo_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        exec_void("DELETE FROM marca_tipos_equipo WHERE id=%s", [tipo_id])
        return Response({"ok": True})


class CatalogoModelosCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        d = request.data or {}
        try:
            marca_id = int(d.get("marca_id"))
            tipo_id = int(d.get("tipo_id"))
        except (TypeError, ValueError):
            return Response({"detail": "marca_id y tipo_id requeridos"}, status=400)
        nombre = (d.get("name") or d.get("nombre") or "").strip()
        alias = d.get("alias")
        alias = (alias or "").strip()
        alias = alias if alias else None
        active = d.get("active")
        activo_val = bool(active) if active is not None else True

        _set_audit_user(request)

        if connection.vendor == "postgresql":
            existing = q(
                "SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND UPPER(nombre)=UPPER(%s)",
                [marca_id, tipo_id, nombre], one=True,
            )
            if existing:
                sets = []
                params = []
                if alias is not None:
                    sets.append("alias=%s")
                    params.append(alias)
                if active is not None:
                    sets.append("activo=%s")
                    params.append(activo_val)
                if sets:
                    params.append(existing["id"])
                    exec_void(f"UPDATE marca_series SET {', '.join(sets)} WHERE id=%s", params)
                return Response({"ok": True, "id": existing["id"], "updated": False})
            exec_void(
                "INSERT INTO marca_series(marca_id, tipo_id, nombre, alias, activo) VALUES (%s,%s,%s,%s,%s)",
                [marca_id, tipo_id, nombre, alias, activo_val],
            )
            new_id = last_insert_id()
            return Response({"ok": True, "id": new_id, "created": True})
        else:
            exec_void(
                """
                INSERT INTO marca_series(marca_id, tipo_id, nombre, alias, activo)
                VALUES (%s,%s,%s, NULLIF(%s,''), %s)
                ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id), alias=VALUES(alias), activo=VALUES(activo)
                """,
                [marca_id, tipo_id, nombre, alias or "", int(activo_val)],
            )
            new_id = last_insert_id()
            return Response({"ok": True, "id": new_id, "created": True})


class CatalogoModeloDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, serie_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        row = q("SELECT id, marca_id, tipo_id, nombre, alias, activo FROM marca_series WHERE id=%s", [serie_id], one=True)
        if not row:
            return Response({"detail": "serie no encontrada"}, status=404)
        d = request.data or {}
        nombre = d.get("name") if "name" in d else d.get("nombre") if "nombre" in d else None
        nombre = (nombre or "").strip() if nombre is not None else None
        alias = d.get("alias") if "alias" in d else None
        alias = (alias or "").strip() if alias is not None else None
        active = d.get("active") if "active" in d else None

        sets = []
        params = []
        if nombre is not None and nombre != row.get("nombre"):
            clash = q(
                "SELECT id FROM marca_series WHERE marca_id=%s AND tipo_id=%s AND id<>%s AND UPPER(nombre)=UPPER(%s)",
                [row["marca_id"], row["tipo_id"], serie_id, nombre], one=True,
            )
            if clash:
                return Response({"detail": "ya existe una serie con ese nombre"}, status=409)
            sets.append("nombre=%s")
            params.append(nombre)
        if alias is not None:
            sets.append("alias=%s")
            params.append(alias if alias else None)
        if active is not None:
            sets.append("activo=%s")
            params.append(bool(active))

        if not sets:
            return Response({"ok": True})

        params.append(serie_id)
        _set_audit_user(request)
        exec_void(f"UPDATE marca_series SET {', '.join(sets)} WHERE id=%s", params)
        return Response({"ok": True})

    def delete(self, request, serie_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        exec_void("DELETE FROM marca_series WHERE id=%s", [serie_id])
        return Response({"ok": True})


class CatalogoVariantesCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        d = request.data or {}
        try:
            marca_id = int(d.get("marca_id"))
            tipo_id = int(d.get("tipo_id"))
            serie_id = int(d.get("serie_id"))
        except (TypeError, ValueError):
            return Response({"detail": "marca_id, tipo_id y serie_id requeridos"}, status=400)
        nombre = (d.get("name") or d.get("nombre") or "").strip()
        if not nombre:
            return Response({"detail": "name requerido"}, status=400)
        active = d.get("active")
        activo_val = bool(active) if active is not None else True

        _set_audit_user(request)

        if connection.vendor == "postgresql":
            existing = q(
                """
                SELECT id FROM marca_series_variantes
                WHERE marca_id=%s AND tipo_id=%s AND serie_id=%s AND UPPER(nombre)=UPPER(%s)
                """,
                [marca_id, tipo_id, serie_id, nombre], one=True,
            )
            if existing:
                if active is not None:
                    exec_void("UPDATE marca_series_variantes SET activo=%s WHERE id=%s", [activo_val, existing["id"]])
                return Response({"ok": True, "id": existing["id"], "updated": False})
            exec_void(
                "INSERT INTO marca_series_variantes(marca_id, tipo_id, serie_id, nombre, activo) VALUES (%s,%s,%s,%s,%s)",
                [marca_id, tipo_id, serie_id, nombre, activo_val],
            )
            new_id = last_insert_id()
            return Response({"ok": True, "id": new_id, "created": True})
        else:
            exec_void(
                """
                INSERT INTO marca_series_variantes(marca_id, tipo_id, serie_id, nombre, activo)
                VALUES (%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id), activo=VALUES(activo)
                """,
                [marca_id, tipo_id, serie_id, nombre, int(activo_val)],
            )
            new_id = last_insert_id()
            return Response({"ok": True, "id": new_id, "created": True})


class CatalogoVarianteDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, variante_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        row = q(
            "SELECT id, marca_id, tipo_id, serie_id, nombre, activo FROM marca_series_variantes WHERE id=%s",
            [variante_id], one=True,
        )
        if not row:
            return Response({"detail": "variante no encontrada"}, status=404)
        d = request.data or {}
        nombre = d.get("name") if "name" in d else d.get("nombre") if "nombre" in d else None
        nombre = (nombre or "").strip() if nombre is not None else None
        active = d.get("active") if "active" in d else None

        sets = []
        params = []
        if nombre is not None and nombre != row.get("nombre"):
            clash = q(
                """
                SELECT id FROM marca_series_variantes
                WHERE marca_id=%s AND tipo_id=%s AND serie_id=%s AND id<>%s AND UPPER(nombre)=UPPER(%s)
                """,
                [row["marca_id"], row["tipo_id"], row["serie_id"], variante_id, nombre], one=True,
            )
            if clash:
                return Response({"detail": "ya existe una variante con ese nombre"}, status=409)
            sets.append("nombre=%s")
            params.append(nombre)
        if active is not None:
            sets.append("activo=%s")
            params.append(bool(active))

        if not sets:
            return Response({"ok": True})

        params.append(variante_id)
        _set_audit_user(request)
        exec_void(f"UPDATE marca_series_variantes SET {', '.join(sets)} WHERE id=%s", params)
        return Response({"ok": True})

    def delete(self, request, variante_id: int):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        exec_void("DELETE FROM marca_series_variantes WHERE id=%s", [variante_id])
        return Response({"ok": True})

class TiposEquipoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Compatibilidad: si existe la tabla externa "equipos" (legado), usarla.
        if connection.vendor == "postgresql":
            reg = q("SELECT to_regclass('public.equipos') AS reg", one=True)
            if reg and reg.get("reg"):
                rows = q(
                    """
                    SELECT "IdEquipos" AS id, "Equipo" AS nombre
                    FROM equipos
                    ORDER BY "Equipo"
                    """
                ) or []
                return Response(rows)
        else:
            chk = q(
                """
                SELECT COUNT(*) AS n
                FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = 'equipos'
                """,
                one=True,
            )
            if chk and chk.get("n"):
                rows = q(
                    """
                    SELECT IdEquipos AS id, Equipo AS nombre
                    FROM equipos
                    ORDER BY Equipo
                    """
                ) or []
                return Response(rows)

        # Fallback: tipos desde models.tipo_equipo + catálogo extendido suministrado
        internos = []
        try:
            internos = q(
                """
                SELECT DISTINCT UPPER(TRIM(nombre)) AS nombre
                FROM marca_tipos_equipo
                WHERE activo = TRUE
                ORDER BY 1
                """
            ) or []
        except Exception:
            internos = []

        usados_set = set()

        catalogo_fijo = []
        # Combinar usados + catálogo fijo
        internos_set = { (r.get('nombre') or '').strip().upper() for r in (internos or []) }
        nombres = sorted(internos_set)
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

        # Asegurar presencia del tipo en el catálogo por marca para evitar
        # inconsistencias en el front (series/variantes esperan esta fila)
        if tipo_nombre:
            # Buscar coincidencia case/acentos-insensitive y normalizar el nombre exacto
            row = q(
                """
                SELECT id, nombre
                  FROM marca_tipos_equipo
                 WHERE marca_id=%s AND UPPER(TRIM(nombre)) = UPPER(TRIM(%s))
                 LIMIT 1
                """,
                [marca_id, tipo_nombre],
                one=True,
            )
            if row:
                # Si existe con diferencias de acentuación/espacios, actualizamos al texto elegido
                if (row.get("nombre") or "").strip() != tipo_nombre:
                    exec_void("UPDATE marca_tipos_equipo SET nombre=%s WHERE id=%s", [tipo_nombre, row["id"]])
            else:
                if connection.vendor == "postgresql":
                    exec_void(
                        """
                        INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
                        VALUES (%s,%s,TRUE)
                        ON CONFLICT (marca_id, nombre) DO UPDATE SET activo=EXCLUDED.activo
                        """,
                        [marca_id, tipo_nombre],
                    )
                else:
                    exec_void(
                        """
                        INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
                        VALUES (%s,%s,TRUE)
                        ON DUPLICATE KEY UPDATE activo=VALUES(activo)
                        """,
                        [marca_id, tipo_nombre],
                    )

        return Response({"ok": True})

class ModeloVarianteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, marca_id: int, modelo_id: int):
        d = request.data or {}
        variante = (d.get("variante") or "").strip()
        exec_void(
            """
            UPDATE models
               SET variante = NULLIF(%s,'')
             WHERE id=%s AND marca_id=%s
            """,
            [variante, modelo_id, marca_id],
        )
        return Response({"ok": True})

class CatalogoUbicacionesView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        ensure_default_locations()
        return Response(q("SELECT id, nombre FROM locations ORDER BY id"))

# Accesorios: catálogo y por ingreso
class CatalogoAccesoriosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        if connection.vendor == "mysql":
            exists = q(
                """
                SELECT COUNT(*) AS n
                FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = 'catalogo_accesorios'
                """,
                one=True,
            )
            if not exists or not exists.get("n"):
                return Response([])
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
        if connection.vendor == "mysql":
            exists = q(
                """
                SELECT COUNT(*) AS n
                FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = 'catalogo_accesorios'
                """,
                one=True,
            )
            if not exists or not exists.get("n"):
                raise ValidationError("Catálogo de accesorios no disponible en este entorno")
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
        exec_void(
            "INSERT INTO ingreso_accesorios(ingreso_id, accesorio_id, referencia, descripcion) VALUES (%s,%s,%s,%s)",
            [ingreso_id, acc_id, ref, desc]
        )
        new_id = q("SELECT LAST_INSERT_ID() AS id", one=True)["id"]
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


class IngresoMediaListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, ingreso_id: int):
        ingreso_row = _fetch_ingreso_assignation(ingreso_id)
        if not ingreso_row:
            return Response({"detail": "Ingreso no encontrado"}, status=404)
        _ensure_media_view_perm(request, ingreso_row)

        try:
            page = int(request.GET.get("page", "1"))
        except ValueError:
            page = 1
        if page < 1:
            page = 1

        raw_page_size = request.GET.get("page_size") or request.GET.get("pageSize") or "20"
        try:
            page_size = int(raw_page_size)
        except ValueError:
            page_size = 20

        max_files = int(getattr(settings, "INGRESO_MEDIA_MAX_FILES", 50) or 50)
        max_page_size = min(max_files, 100)
        page_size = max(1, min(page_size, max_page_size))
        offset = (page - 1) * page_size

        total_row = q("SELECT COUNT(*) AS c FROM ingreso_media WHERE ingreso_id=%s", [ingreso_id], one=True) or {}
        try:
            total = int(total_row.get("c") or 0)
        except (TypeError, ValueError):
            total = 0

        rows = _fetch_media_page(ingreso_id, page_size, offset) or []
        items = [_serialize_media_row(r, ingreso_id, request) for r in rows]

        max_size_mb = int(getattr(settings, "INGRESO_MEDIA_MAX_SIZE_MB", 10) or 10)
        thumb_max = int(getattr(settings, "INGRESO_MEDIA_THUMB_MAX", 512) or 512)
        remaining = max(0, max_files - total)

        payload = {
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": items,
            "has_next": (page * page_size) < total,
            "has_previous": page > 1,
            "limits": {
                "max_files": max_files,
                "max_size_mb": max_size_mb,
                "thumb_max": thumb_max,
            },
            "remaining_slots": remaining,
        }
        return Response(payload)

    def post(self, request, ingreso_id: int):
        ingreso_row = _fetch_ingreso_assignation(ingreso_id)
        if not ingreso_row:
            return Response({"detail": "Ingreso no encontrado"}, status=404)
        _ensure_media_manage_perm(request, ingreso_row)

        uploads = []
        for key in request.FILES:
            uploads.extend(request.FILES.getlist(key) or [])
        if not uploads:
            return Response({"detail": "No se recibieron archivos"}, status=400)

        max_files = int(getattr(settings, "INGRESO_MEDIA_MAX_FILES", 50) or 50)
        existing_row = q("SELECT COUNT(*) AS c FROM ingreso_media WHERE ingreso_id=%s", [ingreso_id], one=True) or {}
        existing_count = int(existing_row.get("c") or 0)
        if existing_count >= max_files:
            return Response({"detail": "Limite de fotos alcanzado"}, status=422)
        available = max_files - existing_count
        if len(uploads) > available:
            return Response({"detail": f"Solo se pueden subir {available} fotos adicionales"}, status=422)

        max_size_mb = int(getattr(settings, "INGRESO_MEDIA_MAX_SIZE_MB", 10) or 10)
        thumb_max = int(getattr(settings, "INGRESO_MEDIA_THUMB_MAX", 512) or 512)
        max_size_bytes = max_size_mb * 1024 * 1024
        allowed_mime = getattr(settings, "INGRESO_MEDIA_ALLOWED_MIME", ["image/jpeg", "image/png"]) or ["image/jpeg", "image/png"]

        user_id = _current_user_id(request)
        _set_audit_user(request)

        uploaded_items = []
        errors = []

        for up in uploads:
            storage_path = None
            thumb_path = None
            try:
                processed = process_upload(up, max_size_bytes=max_size_bytes, thumb_max=thumb_max, allowed_mime=allowed_mime)
                storage_path, thumb_path = save_processed_image(ingreso_id, processed)
                with transaction.atomic():
                    if connection.vendor == "postgresql":
                        exec_void("SET LOCAL app.ingreso_id = %s", [ingreso_id])
                    exec_void(
                        "INSERT INTO ingreso_media (ingreso_id, usuario_id, storage_path, thumbnail_path, original_name, mime_type, size_bytes, width, height) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        [
                            ingreso_id,
                            user_id,
                            storage_path,
                            thumb_path,
                            processed.display_name,
                            processed.mime_type,
                            len(processed.content),
                            processed.width,
                            processed.height,
                        ],
                    )
                media_id = last_insert_id()
                row = _fetch_media_row(ingreso_id, media_id)
                if row:
                    uploaded_items.append(_serialize_media_row(row, ingreso_id, request))
                logger.info("Ingreso %s: usuario %s subio foto %s", ingreso_id, user_id, media_id)
            except MediaValidationError as exc:
                delete_media_paths([storage_path, thumb_path])
                errors.append({
                    "name": getattr(up, "name", ""),
                    "detail": str(exc),
                    "status": getattr(exc, "status_code", 400),
                })
            except MediaProcessingError as exc:
                delete_media_paths([storage_path, thumb_path])
                errors.append({
                    "name": getattr(up, "name", ""),
                    "detail": str(exc),
                    "status": 422,
                })
            except Exception as exc:
                delete_media_paths([storage_path, thumb_path])
                logger.exception("Fallo al guardar foto de ingreso", exc_info=exc)
                errors.append({
                    "name": getattr(up, "name", ""),
                    "detail": "Error inesperado al guardar la foto",
                    "status": 500,
                })

        if not uploaded_items:
            status_code = errors[0].get("status", 400) if errors else 400
            detail = errors[0].get("detail", "No se pudo subir la foto") if errors else "No se pudo subir la foto"
            return Response({"detail": detail, "errors": errors}, status=status_code)

        remaining = max(0, max_files - (existing_count + len(uploaded_items)))
        status_code = 201 if not errors else 207
        return Response({
            "uploaded": uploaded_items,
            "errors": errors,
            "remaining_slots": remaining,
        }, status=status_code)


class IngresoMediaDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, ingreso_id: int, media_id: int):
        ingreso_row = _fetch_ingreso_assignation(ingreso_id)
        if not ingreso_row:
            return Response({"detail": "Ingreso no encontrado"}, status=404)
        _ensure_media_manage_perm(request, ingreso_row)
        row = _fetch_media_row(ingreso_id, media_id)
        if not row:
            return Response({"detail": "Foto no encontrada"}, status=404)

        comentario = None
        if isinstance(request.data, dict):
            comentario = request.data.get("comentario")
        comentario = (comentario or "").strip() or None

        _set_audit_user(request)
        now = timezone.now()
        with transaction.atomic():
            if connection.vendor == "postgresql":
                exec_void("SET LOCAL app.ingreso_id = %s", [ingreso_id])
            exec_void(
                "UPDATE ingreso_media SET comentario=%s, updated_at=%s WHERE ingreso_id=%s AND id=%s",
                [comentario, now, ingreso_id, media_id],
            )
        row = _fetch_media_row(ingreso_id, media_id)
        if row:
            logger.info("Ingreso %s: usuario %s actualizo comentario de foto %s", ingreso_id, _current_user_id(request), media_id)
            return Response(_serialize_media_row(row, ingreso_id, request))
        return Response({"detail": "Foto no encontrada"}, status=404)

    def delete(self, request, ingreso_id: int, media_id: int):
        ingreso_row = _fetch_ingreso_assignation(ingreso_id)
        if not ingreso_row:
            return Response({"detail": "Ingreso no encontrado"}, status=404)
        _ensure_media_manage_perm(request, ingreso_row)
        row = _fetch_media_row(ingreso_id, media_id)
        if not row:
            return Response({"detail": "Foto no encontrada"}, status=404)

        storage_path = row.get("storage_path")
        thumb_path = row.get("thumbnail_path")

        _set_audit_user(request)
        with transaction.atomic():
            if connection.vendor == "postgresql":
                exec_void("SET LOCAL app.ingreso_id = %s", [ingreso_id])
            exec_void("DELETE FROM ingreso_media WHERE ingreso_id=%s AND id=%s", [ingreso_id, media_id])

        delete_media_paths([storage_path, thumb_path])
        logger.info("Ingreso %s: usuario %s elimino foto %s", ingreso_id, _current_user_id(request), media_id)
        return Response({"ok": True})


class IngresoMediaFileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ingreso_id: int, media_id: int):
        ingreso_row = _fetch_ingreso_assignation(ingreso_id)
        if not ingreso_row:
            return Response({"detail": "Ingreso no encontrado"}, status=404)
        _ensure_media_view_perm(request, ingreso_row)
        row = _fetch_media_row(ingreso_id, media_id)
        if not row:
            return Response({"detail": "Foto no encontrada"}, status=404)

        storage_path = row.get("storage_path")
        if not storage_path:
            return Response({"detail": "Archivo no disponible"}, status=404)

        try:
            file_obj = default_storage.open(storage_path, "rb")
        except FileNotFoundError:
            return Response({"detail": "Archivo no disponible"}, status=410)
        except Exception:
            return Response({"detail": "No se pudo abrir el archivo"}, status=500)

        mime = row.get("mime_type") or "application/octet-stream"
        response = FileResponse(file_obj, content_type=mime)
        size_bytes = row.get("size_bytes")
        if size_bytes:
            response["Content-Length"] = str(size_bytes)
        filename = row.get("original_name") or f"ingreso-{ingreso_id}-foto-{media_id}"
        try:
            quoted = quote(filename)
        except Exception:
            quoted = filename
        response["Content-Disposition"] = f'attachment; filename="{filename}"; filename*=UTF-8''{quoted}'
        response["Cache-Control"] = "private, max-age=86400"
        return response


class IngresoMediaThumbnailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ingreso_id: int, media_id: int):
        ingreso_row = _fetch_ingreso_assignation(ingreso_id)
        if not ingreso_row:
            return Response({"detail": "Ingreso no encontrado"}, status=404)
        _ensure_media_view_perm(request, ingreso_row)
        row = _fetch_media_row(ingreso_id, media_id)
        if not row:
            return Response({"detail": "Foto no encontrada"}, status=404)
        thumb_path = row.get("thumbnail_path")
        if not thumb_path:
            return Response({"detail": "Miniatura no disponible"}, status=404)
        try:
            file_obj = default_storage.open(thumb_path, "rb")
        except FileNotFoundError:
            return Response({"detail": "Miniatura no disponible"}, status=410)
        except Exception:
            return Response({"detail": "No se pudo abrir la miniatura"}, status=500)
        response = FileResponse(file_obj, content_type="image/jpeg")
        response["Content-Disposition"] = 'inline; filename="thumbnail.jpg"'
        response["Cache-Control"] = "private, max-age=86400"
        return response


# Derivación a servicio externo
class DerivarIngresoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, ingreso_id: int):
        # Auditorí­a y control de permisos
        require_roles(request, ["jefe", "admin", "jefe_veedor", "tecnico", "recepcion"])
        _set_audit_user(request)

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
        exec_void(""" 
            INSERT INTO equipos_derivados (ingreso_id, proveedor_id, remit_deriv, fecha_deriv, comentarios, estado) 
            VALUES (%s, %s, %s, COALESCE(%s, CURRENT_DATE), %s, 'derivado') 
        """, [ingreso_id, proveedor_id, data.get("remit_deriv"), data.get("fecha_deriv"), data.get("comentarios")]) 

        # Reflejar estado del ingreso solo si cambia (auditable por trigger)
        exec_void("UPDATE ingresos SET estado='derivado' WHERE id=%s AND estado <> 'derivado'", [ingreso_id])

        return Response({"ok": True})

class DevolverDerivacionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, ingreso_id: int, deriv_id: int):
        # Roles similares a consulta de derivaciones
        require_roles(request, ["jefe", "admin", "jefe_veedor", "tecnico", "recepcion"])
        _set_audit_user(request)

        # Validar existencia y pertenencia
        row = q(
            "SELECT id FROM equipos_derivados WHERE id=%s AND ingreso_id=%s",
            [deriv_id, ingreso_id],
            one=True,
        )
        if not row:
            return Response({"detail": "Derivación no encontrada"}, status=404)

        data = request.data or {}
        fecha = data.get("fecha_entrega") or None

        # Marcar fecha de devolución y estado
        exec_void(
            """
            UPDATE equipos_derivados
               SET fecha_entrega = COALESCE(%s, CURRENT_DATE),
                   estado = 'devuelto'
             WHERE id = %s
            """,
            [fecha, deriv_id],
        )

        # También reencolar el ingreso como 'ingresado' (solo si cambia)
        exec_void("UPDATE ingresos SET estado='ingresado' WHERE id=%s AND estado <> 'ingresado'", [ingreso_id])
        # Actualizar comentario del último evento de estado para dejar trazabilidad clara
        try:
            exec_void(
                """
                UPDATE ingreso_events SET comentario='Devolución de externo'
                WHERE id = (
                  SELECT id FROM ingreso_events
                   WHERE ingreso_id=%s AND a_estado='ingresado'
                   ORDER BY ts DESC, id DESC
                   LIMIT 1
                )
                """,
                [ingreso_id],
            )
        except Exception:
            pass

        # Enviar aviso al técnico asignado (si tiene email)
        try:
            info = q(
                """
                SELECT u.email AS tech_email, COALESCE(u.nombre,'') AS tech_nombre,
                       c.razon_social,
                       d.numero_serie,
                       COALESCE(b.nombre,'') AS marca,
                       COALESCE(m.nombre,'') AS modelo,
                       COALESCE(m.tipo_equipo,'') AS tipo_equipo
                  FROM ingresos t
                  JOIN devices d   ON d.id = t.device_id
                  JOIN customers c ON c.id = d.customer_id
                  LEFT JOIN marcas b ON b.id = d.marca_id
                  LEFT JOIN models m ON m.id = d.model_id
                  LEFT JOIN users  u ON u.id = t.asignado_a
                 WHERE t.id=%s
                """,
                [ingreso_id],
                one=True,
            )
            email = (info or {}).get("tech_email")
            if email:
                subj = f"Aviso: equipo devuelto de externo — OS #{ingreso_id}"
                txt = (
                    f"Hola {info.get('tech_nombre','')},\n\n"
                    f"El equipo derivado fue devuelto del servicio externo y se reencoló como 'ingresado'.\n\n"
                    f"Cliente: {info.get('razon_social','')}\n"
                    f"Equipo: {info.get('marca','')} {info.get('modelo','')}\n"
                    f"Número de serie: {info.get('numero_serie','')}\n\n"
                    f"Hoja de servicio: /ingresos/{ingreso_id}\n"
                )
                try:
                    txt = _email_append_footer_text(txt)
                    send_mail(subj, txt, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
                except Exception:
                    pass
        except Exception:
            pass

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
        if connection.vendor == "postgresql":
            q("""
                INSERT INTO users(nombre, email, rol, activo)
                VALUES (%(n)s, %(e)s, %(r)s, true)
                ON CONFLICT (email) DO UPDATE
                SET nombre = EXCLUDED.nombre,
                    rol = EXCLUDED.rol
            """, {"n": nombre, "e": email, "r": rol})
        else:
            q(
                """
                INSERT INTO users(nombre, email, rol, activo)
                VALUES (%s,%s,%s,true)
                ON DUPLICATE KEY UPDATE nombre=VALUES(nombre), rol=VALUES(rol)
                """,
                [nombre, email, rol],
            )

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
                        txt = _email_append_footer_text(txt)
                        html = _email_append_footer_html(html)
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
        # Nuevo comportamiento más seguro: enví­a un enlace por email para que el usuario
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
            txt = _email_append_footer_text(txt)
            html = _email_append_footer_html(html)
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
        # Compatibilidad: usar SELECT * para no romper si la DB aún no tiene columnas nuevas (telefono_2, email)
        return Response(q("SELECT * FROM customers ORDER BY razon_social"))
    def post(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        d = request.data or {}
        if not (d.get("razon_social") and d.get("cod_empresa")):
            raise ValidationError("razon_social y cod_empresa son requeridos")
        q("""INSERT INTO customers(razon_social, cod_empresa, telefono, telefono_2, email)
             VALUES (%(rs)s, %(ce)s, %(tel)s, %(tel2)s, %(email)s)""",
          {"rs": d["razon_social"], "ce": d["cod_empresa"], "tel": d.get("telefono"), "tel2": d.get("telefono_2"), "email": d.get("email")})
        return Response({"ok": True})

class ClienteDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, cid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        # No permitir borrar si tiene referencias (devices/ingresos)
        refs = q(
            """
            SELECT
              (SELECT COUNT(*) FROM devices d WHERE d.customer_id = %s) AS cnt_devices,
              (SELECT COUNT(*)
                 FROM ingresos t
                 JOIN devices d ON d.id = t.device_id
                WHERE d.customer_id = %s) AS cnt_ingresos
            """,
            [cid, cid], one=True
        ) or {"cnt_devices": 0, "cnt_ingresos": 0}
        if refs["cnt_devices"] or refs["cnt_ingresos"]:
            return Response(
                {"detail": f"No se puede eliminar: el cliente tiene {refs['cnt_devices']} equipos y {refs['cnt_ingresos']} ingresos asociados."},
                status=409
            )
        try:
            q("DELETE FROM customers WHERE id = %(id)s", {"id": cid})
            return Response({"ok": True})
        except IntegrityError:
            return Response({"detail": "No se pudo eliminar por restricciones de integridad."}, status=409)

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
        if connection.vendor == "postgresql":
            q("INSERT INTO marcas(nombre) VALUES (%(n)s) ON CONFLICT DO NOTHING", {"n": n})
        else:
            q("INSERT IGNORE INTO marcas(nombre) VALUES (%s)", [n])
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
        if connection.vendor == "postgresql":
            q(
                """
                UPDATE models m
                   SET tecnico_id = b.tecnico_id
                  FROM marcas b
                 WHERE m.marca_id = b.id
                   AND b.id = %s
                   AND m.tecnico_id IS NULL
                """,
                [bid],
            )
        else:
            q(
                """
                UPDATE models m
                JOIN marcas b ON m.marca_id = b.id
                   SET m.tecnico_id = b.tecnico_id
                 WHERE b.id = %s
                   AND m.tecnico_id IS NULL
                """,
                [bid],
            )
        return Response({"ok": True})

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
        q("UPDATE ingresos SET asignado_a=%s WHERE id=%s", [tecnico_id, ingreso_id])
        return Response({"ok": True, "asignado_a": tecnico_id})


class MarcaDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, bid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        # Pre-chequeo para dar un error amigable si tiene modelos asociados
        try:
            row = q("SELECT COUNT(*) AS cnt FROM models WHERE marca_id=%s", [bid], one=True)
            if row and (row.get("cnt") or 0) > 0:
                return Response({
                    "detail": "No se puede eliminar la marca: tiene modelos asociados. Elimine o reasigne los modelos primero.",
                    "models_count": int(row.get("cnt") or 0),
                }, status=409)
            # Intento de borrado (protección ante condiciones de carrera)
            exec_void("DELETE FROM marcas WHERE id = %s", [bid])
            return Response({"ok": True})
        except IntegrityError:
            # Fallback: restricciones de FK (p.ej. RESTRICT desde models)
            return Response({
                "detail": "No se puede eliminar la marca por restricciones de integridad (tiene referencias activas).",
            }, status=409)

    def patch(self, request, bid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        d = request.data or {}
        nombre = (d.get("nombre") or d.get("name") or "").strip()
        if not nombre:
            return Response({"detail": "nombre requerido"}, status=400)
        row = q("SELECT id FROM marcas WHERE id=%s", [bid], one=True)
        if not row:
            return Response({"detail": "marca no encontrada"}, status=404)
        clash = q("SELECT id FROM marcas WHERE id<>%s AND LOWER(nombre)=LOWER(%s)", [bid, nombre], one=True)
        if clash:
            return Response({"detail": "ya existe una marca con ese nombre"}, status=409)
        exec_void("UPDATE marcas SET nombre=%s WHERE id=%s", [nombre, bid])
        return Response({"ok": True})

class ModelosPorMarcaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, bid):
        require_roles(request, ["jefe", "admin","jefe_veedor", "tecnico", "recepcion"])
        rows = q("""
          SELECT m.id, m.nombre, m.tecnico_id, COALESCE(u.nombre,'') AS tecnico_nombre,
                 COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                 COALESCE(m.variante,'') AS variante
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
        variante = (request.data.get("variante") or "").strip() or None
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

        if connection.vendor == "postgresql":
            q("""
              INSERT INTO models(marca_id, nombre, tecnico_id, tipo_equipo, variante)
              VALUES (%(b)s, %(n)s, %(t)s, NULLIF(%(te)s,''), NULLIF(%(va)s,''))
              ON CONFLICT (marca_id, nombre) DO UPDATE
                 SET tecnico_id = EXCLUDED.tecnico_id,
                     tipo_equipo = COALESCE(EXCLUDED.tipo_equipo, models.tipo_equipo),
                     variante = COALESCE(EXCLUDED.variante, models.variante)
            """, {"b": bid, "n": n, "t": tecnico_id, "te": tipo_equipo, "va": variante})
        else:
            q(
                """
                INSERT INTO models(marca_id, nombre, tecnico_id, tipo_equipo, variante)
                VALUES (%s, %s, %s, NULLIF(%s,''), NULLIF(%s,''))
                ON DUPLICATE KEY UPDATE
                  tecnico_id = VALUES(tecnico_id),
                  tipo_equipo = IFNULL(VALUES(tipo_equipo), tipo_equipo),
                  variante = IFNULL(VALUES(variante), variante)
                """,
                [bid, n, tecnico_id, tipo_equipo, variante],
            )

        # Si se cargó tipo_equipo al crear/actualizar, asegurarlo en marca_tipos_equipo
        if tipo_equipo:
            if connection.vendor == "postgresql":
                q(
                    """
                    INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
                    VALUES (%s,%s,TRUE)
                    ON CONFLICT (marca_id, nombre) DO UPDATE SET activo=EXCLUDED.activo
                    """,
                    [bid, tipo_equipo],
                )
            else:
                q(
                    """
                    INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
                    VALUES (%s,%s,TRUE)
                    ON DUPLICATE KEY UPDATE activo=VALUES(activo)
                    """,
                    [bid, tipo_equipo],
                )

        return Response({"ok": True})


class ModeloDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, mid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        try:
            exec_void("DELETE FROM models WHERE id = %s", [mid])
            return Response({"ok": True})
        except IntegrityError:
            return Response({
                "detail": "No se puede eliminar el modelo por restricciones de integridad.",
            }, status=409)

    def patch(self, request, mid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        d = request.data or {}
        nombre = (d.get("nombre") or d.get("name") or "").strip()
        if not nombre:
            return Response({"detail": "nombre requerido"}, status=400)
        row = q("SELECT id, marca_id FROM models WHERE id=%s", [mid], one=True)
        if not row:
            return Response({"detail": "modelo no encontrado"}, status=404)
        marca_id = row.get("marca_id")
        clash = q(
            "SELECT id FROM models WHERE marca_id=%s AND id<>%s AND LOWER(nombre)=LOWER(%s)",
            [marca_id, mid, nombre], one=True,
        )
        if clash:
            return Response({"detail": "ya existe un modelo con ese nombre para la marca"}, status=409)
        exec_void("UPDATE models SET nombre=%s WHERE id=%s", [nombre, mid])
        return Response({"ok": True})


class ModelMergeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        d = request.data or {}
        try:
            source_id = int(d.get("source_id"))
            target_id = int(d.get("target_id"))
        except Exception:
            return Response({"detail": "source_id y target_id requeridos"}, status=400)
        if source_id == target_id:
            return Response({"detail": "source y target no pueden ser iguales"}, status=400)

        src = q("SELECT id, marca_id, COALESCE(TRIM(tipo_equipo), '') AS tipo, nombre FROM models WHERE id=%s", [source_id], one=True)
        dst = q("SELECT id, marca_id, COALESCE(TRIM(tipo_equipo), '') AS tipo, nombre FROM models WHERE id=%s", [target_id], one=True)
        if not src or not dst:
            return Response({"detail": "modelo source/target inexistente"}, status=404)
        if src["marca_id"] != dst["marca_id"]:
            return Response({"detail": "Solo se puede unificar dentro de la misma marca"}, status=409)

        # Reglas: unificar solo si ambos tienen mismo tipo_equipo no vací­o
        tipo_a = (src.get("tipo") or "").strip()
        tipo_b = (dst.get("tipo") or "").strip()
        if not tipo_a or not tipo_b or tipo_a.lower() != tipo_b.lower():
            return Response({"detail": "No se puede unificar: los tipos de equipo no coinciden o están vací­os"}, status=409)

        with transaction.atomic():
            # mover devices al target
            exec_void("UPDATE devices SET model_id=%s WHERE model_id=%s", [target_id, source_id])
            # eliminar modelo source (cascadeará en model_hierarchy si corresponde)
            exec_void("DELETE FROM models WHERE id=%s", [source_id])

        moved = q("SELECT COUNT(*) AS cnt FROM devices WHERE model_id=%s", [target_id], one=True)
        return Response({"ok": True, "devices_now_point_to": target_id, "moved_count": moved.get("cnt") if moved else None})


class MarcaMergeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        d = request.data or {}
        try:
            source_id = int(d.get("source_id"))
            target_id = int(d.get("target_id"))
        except Exception:
            return Response({"detail": "source_id y target_id requeridos"}, status=400)
        if source_id == target_id:
            return Response({"detail": "source y target no pueden ser iguales"}, status=400)

        a = q("SELECT id, nombre FROM marcas WHERE id=%s", [source_id], one=True)
        b = q("SELECT id, nombre FROM marcas WHERE id=%s", [target_id], one=True)
        if not a or not b:
            return Response({"detail": "marca source/target inexistente"}, status=404)

        with transaction.atomic():
            # Para cada modelo de la marca source, si existe un homónimo en target, unificar devices y borrar; si no, mover el modelo a target.
            modelos = q("SELECT id, nombre, COALESCE(TRIM(tipo_equipo),'' ) AS tipo FROM models WHERE marca_id=%s", [source_id]) or []
            for mm in modelos:
                dup = q(
                    "SELECT id FROM models WHERE marca_id=%s AND LOWER(TRIM(nombre))=LOWER(TRIM(%s)) AND LOWER(COALESCE(TRIM(tipo_equipo),''))=LOWER(COALESCE(TRIM(%s),'')) LIMIT 1",
                    [target_id, mm.get("nombre"), mm.get("tipo")],
                    one=True,
                )
                if dup:
                    exec_void("UPDATE devices SET model_id=%s WHERE model_id=%s", [dup.get("id"), mm.get("id")])
                    exec_void("DELETE FROM models WHERE id=%s", [mm.get("id")])
                else:
                    exec_void("UPDATE models SET marca_id=%s WHERE id=%s", [target_id, mm.get("id")])

            # Mover devices con marca_id directo
            exec_void("UPDATE devices SET marca_id=%s WHERE marca_id=%s", [target_id, source_id])

            # Borrar marca source (cascada en tablas jerárquicas si aplica)
            exec_void("DELETE FROM marcas WHERE id=%s", [source_id])

        return Response({"ok": True, "target_id": target_id})


class MarcaDeleteCascadeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, bid):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        try:
            with transaction.atomic():
                # Desvincular devices que referencian a modelos/marcas de esta marca
                exec_void(
                    """
                    UPDATE devices
                       SET model_id = NULL
                     WHERE model_id IN (SELECT id FROM models WHERE marca_id = %s)
                    """,
                    [bid],
                )
                exec_void("UPDATE devices SET marca_id = NULL WHERE marca_id = %s", [bid])

                # Borrar modelos de la marca
                exec_void("DELETE FROM models WHERE marca_id = %s", [bid])

                # Las tablas jerárquicas tienen ON DELETE CASCADE por marca/modelo
                # Borrar marca
                exec_void("DELETE FROM marcas WHERE id = %s", [bid])
            return Response({"ok": True})
        except IntegrityError:
            return Response({
                "detail": "No se pudo eliminar en cascada por restricciones de integridad.",
            }, status=409)

class ProveedoresExternosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor", "tecnico", "recepcion"])
        sql = (
            "SELECT id, nombre, contacto, telefono, email, direccion, notas "
            "FROM proveedores_externos ORDER BY nombre"
        )
        return Response(q(sql))

    def post(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        data = request.data or {}

        nombre = (data.get("nombre") or "").strip()
        if not nombre:
            raise ValidationError("nombre requerido")

        def _clean(key):
            if key not in data:
                return None, False
            val = data.get(key)
            if val is None:
                return None, True
            sval = str(val).strip()
            if not sval:
                return None, True
            return sval, True

        contacto, contacto_set = _clean("contacto")
        telefono, telefono_set = _clean("telefono")
        email, email_set = _clean("email")
        if email and email_set:
            email = email.lower()
        direccion, direccion_set = _clean("direccion")
        notas, notas_set = _clean("notas")

        existing = q(
            "SELECT id FROM proveedores_externos WHERE LOWER(nombre)=LOWER(%s)",
            [nombre],
            one=True,
        )

        _set_audit_user(request)

        if existing:
            sets = ["nombre=%s"]
            params = [nombre]
            if contacto_set:
                if contacto is None:
                    sets.append("contacto=NULL")
                else:
                    sets.append("contacto=%s")
                    params.append(contacto)
            if telefono_set:
                if telefono is None:
                    sets.append("telefono=NULL")
                else:
                    sets.append("telefono=%s")
                    params.append(telefono)
            if email_set:
                if email is None:
                    sets.append("email=NULL")
                else:
                    sets.append("email=%s")
                    params.append(email)
            if direccion_set:
                if direccion is None:
                    sets.append("direccion=NULL")
                else:
                    sets.append("direccion=%s")
                    params.append(direccion)
            if notas_set:
                if notas is None:
                    sets.append("notas=NULL")
                else:
                    sets.append("notas=%s")
                    params.append(notas)
            params.append(existing["id"])
            exec_void(
                f"UPDATE proveedores_externos SET {', '.join(sets)} WHERE id=%s",
                params,
            )
            return Response({"ok": True, "id": existing["id"], "updated": True})

        params = [
            nombre,
            contacto,
            telefono,
            email,
            direccion,
            notas,
        ]
        try:
            exec_void(
                "INSERT INTO proveedores_externos"
                " (nombre, contacto, telefono, email, direccion, notas)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                params,
            )
        except IntegrityError:
            existing = q(
                "SELECT id FROM proveedores_externos WHERE LOWER(nombre)=LOWER(%s)",
                [nombre],
                one=True,
            )
            if existing:
                return Response({"ok": True, "id": existing["id"], "updated": False})
            raise
        pid = last_insert_id()
        return Response({"ok": True, "id": pid, "created": True})

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


class AprobadosParaRepararView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute("""
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
            """, ["taller"])
            data = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(data, many=True).data)

class AprobadosYReparadosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute("""
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
                SELECT e.ingreso_id, e.ts AS fecha_reparado,
                       ROW_NUMBER() OVER (PARTITION BY e.ingreso_id ORDER BY e.ts DESC, e.id DESC) AS rn
                FROM ingreso_events e
                WHERE e.a_estado = 'reparado'
              ) ev ON ev.ingreso_id = t.id AND ev.rn = 1
              WHERE t.estado IN ('reparado')
                AND LOWER(loc.nombre) = LOWER(%s)
              ORDER BY COALESCE(ev.fecha_reparado, t.fecha_ingreso) DESC;
            """, ["taller"])
            rows = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(rows, many=True).data)

class LiberadosView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        with connection.cursor() as cur:
            _set_audit_user(request)
            cur.execute("""
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
                  t.ubicacion_id,
                  COALESCE(l.nombre,'') AS ubicacion_nombre,
                  ev.fecha_listo
                FROM ingresos t
                JOIN devices   d ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas    b ON b.id = d.marca_id
                LEFT JOIN models    m ON m.id = d.model_id
                LEFT JOIN locations l ON l.id = t.ubicacion_id
                LEFT JOIN (
                  SELECT e.ingreso_id, e.ts AS fecha_listo,
                         ROW_NUMBER() OVER (PARTITION BY e.ingreso_id ORDER BY e.ts DESC, e.id DESC) AS rn
                  FROM ingreso_events e
                  WHERE e.a_estado = 'liberado'
                ) ev ON ev.ingreso_id = t.id AND ev.rn = 1
                WHERE t.estado = 'liberado'
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
        excluir_raw = (request.GET.get("excluir_estados") or "").strip()
        excluir_estados = []
        if excluir_raw:
            for part in excluir_raw.replace(';', ',').split(','):
                val = part.strip().lower()
                if val:
                    excluir_estados.append(val)
        with connection.cursor() as cur:
            _set_audit_user(request)
            base = """
              SELECT t.id, t.estado, t.presupuesto_estado, t.fecha_ingreso, t.fecha_entrega, t.ubicacion_id,
                     COALESCE(loc.nombre, '') AS ubicacion_nombre,
                     c.razon_social,
                     d.numero_serie,
                     COALESCE(d.n_de_control,'') AS numero_interno,
                     COALESCE(b.nombre,'') AS marca,
                     COALESCE(m.nombre,'') AS modelo,
                     COALESCE(m.tipo_equipo,'') AS tipo_equipo
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
                base += " AND LOWER(loc.nombre) = LOWER(%s)"
                params.append("taller")
            if estado:
                base += " AND t.estado = %s"
                params.append(estado)
            if ubicacion_id.isdigit():
                base += " AND t.ubicacion_id = %s"
                params.append(int(ubicacion_id))
            if excluir_estados:
                placeholders = ', '.join(['%s'] * len(excluir_estados))
                base += ' AND t.estado NOT IN (' + placeholders + ')' 
                params.extend(excluir_estados)
            if qtxt:
                base += " AND (LOWER(c.razon_social) LIKE LOWER(%s) OR LOWER(d.numero_serie) LIKE LOWER(%s) OR LOWER(d.n_de_control) LIKE LOWER(%s) OR LOWER(b.nombre) LIKE LOWER(%s) OR LOWER(m.nombre) LIKE LOWER(%s))"
                like = f"%{qtxt}%"
                params += [like, like, like, like, like]
            base += " ORDER BY t.id DESC"
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

        # Setear variables de auditorí­a en la sesión DB (para triggers audit.*)
        _set_audit_user(request)
        if connection.vendor == "postgresql":
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
        #   - descripción del problema (no vací­a)
        #   - trabajos realizados (no vací­o)
        #   - fecha de servicio (válida y no vací­a)
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

        # --- Entrega (remito, factura, fecha) ---
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
                        raise ValidationError("fecha_entrega inválida")
                    if timezone.is_naive(dt):
                        dt = timezone.make_aware(dt, timezone.get_current_timezone())
                    sets_no_estado.append("fecha_entrega=%s")
                    params_no_estado.append(dt)

        # --- NUEVOS CAMPOS ---
        # Garantí­a de reparación
        if "garantia_reparacion" in d:
            if rol not in ROL_EDIT_DIAG:
                raise PermissionDenied("No autorizado")
            sets_no_estado.append("garantia_reparacion=%s")
            params_no_estado.append(bool(d.get("garantia_reparacion")))

        # Faja de garantí­a
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

        # Remito de ingreso
        if "remito_ingreso" in d:
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar remito de ingreso")
            sets_no_estado.append("remito_ingreso = NULLIF(%s,'')")
            params_no_estado.append((d.get("remito_ingreso") or "").strip())

        # Informe preliminar
        if "informe_preliminar" in d:
            if rol not in ROL_EDIT_BASICS:
                raise PermissionDenied("No autorizado para editar informe preliminar")
            sets_no_estado.append("informe_preliminar = NULLIF(%s,'')")
            params_no_estado.append((d.get("informe_preliminar") or "").strip())

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
        # Antes solo se promoví­a con descripción. Ahora también con trabajos o fecha de servicio.
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
                 ed.id         AS deriv_id,
                 c.razon_social,
                 d.numero_serie,
                 COALESCE(b.nombre,'') AS marca,
                 COALESCE(m.nombre,'') AS modelo,
                 COALESCE(m.tipo_equipo,'') AS tipo_equipo,
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
          JOIN (
            SELECT e.*, ROW_NUMBER() OVER (
              PARTITION BY e.ingreso_id ORDER BY e.fecha_deriv DESC, e.id DESC
            ) AS rn
            FROM equipos_derivados e
          ) ed ON ed.ingreso_id = t.id AND ed.rn = 1
          LEFT JOIN proveedores_externos pe ON pe.id = ed.proveedor_id
          WHERE t.estado = 'derivado'
          ORDER BY ed.fecha_deriv DESC, t.id DESC
        """)
        return Response(rows)

class CatalogoRolesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        # [{value,label}, ...]
        return Response([{"value": k, "label": _fix_text_value(v)} for k, v in ROLE_CHOICES])

class CerrarReparacionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, ingreso_id: int):
        require_roles(request, ["jefe","jefe_veedor","admin"])
        r = (request.data or {}).get("resolucion")
        if r not in ("reparado","no_reparado","no_se_encontro_falla","presupuesto_rechazado"):
            return Response({"detail": "resolución inválida"}, status=400)

        with connection.cursor() as cur:
            _set_audit_user(request)
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
        if connection.vendor == "postgresql":
            rows = q(
                """
                  SELECT ts, user_id, user_role, table_name, record_id, column_name, old_value, new_value
                  FROM audit.change_log
                  WHERE ingreso_id = %s
                  ORDER BY ts DESC, id DESC
                """,
                [ingreso_id]
            ) or []
        else:
            rows = q(
                """
                  SELECT ts, user_id, user_role, table_name, record_id, column_name, old_value, new_value
                  FROM (
                    SELECT
                      e.ts AS ts,
                      e.usuario_id AS user_id,
                      COALESCE(u.rol, '') AS user_role,
                      'ingresos' AS table_name,
                      e.ticket_id AS record_id,
                      'estado' AS column_name,
                      NULLIF(e.de_estado, '') AS old_value,
                      NULLIF(e.a_estado, '') AS new_value,
                      e.id AS order_id
                    FROM ingreso_events e
                    LEFT JOIN users u ON u.id = e.usuario_id
                    WHERE e.ticket_id = %s
                    UNION ALL
                    SELECT
                      e.ts AS ts,
                      e.usuario_id AS user_id,
                      COALESCE(u.rol, '') AS user_role,
                      'ingresos' AS table_name,
                      e.ticket_id AS record_id,
                      'comentario' AS column_name,
                      NULL AS old_value,
                      NULLIF(e.comentario, '') AS new_value,
                      e.id AS order_id
                    FROM ingreso_events e
                    LEFT JOIN users u ON u.id = e.usuario_id
                    WHERE e.ticket_id = %s
                      AND e.comentario IS NOT NULL
                      AND TRIM(e.comentario) <> ''
                  ) AS log_rows
                  ORDER BY ts DESC, order_id DESC, column_name
                """,
                [ingreso_id, ingreso_id]
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
            _set_audit_user(request)
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
                  COALESCE(m.tipo_equipo,'') AS tipo_equipo,
                  ia.referencia,
                  COALESCE(ca.nombre,'') AS accesorio_nombre
                FROM ingreso_accesorios ia
                JOIN ingresos t ON t.id = ia.ingreso_id
                JOIN devices  d ON d.id = t.device_id
                JOIN customers c ON c.id = d.customer_id
                LEFT JOIN marcas b ON b.id = d.marca_id
                LEFT JOIN models m ON m.id = d.model_id
                LEFT JOIN catalogo_accesorios ca ON ca.id = ia.accesorio_id
                WHERE (LOWER(ia.referencia) LIKE LOWER(%s))
                ORDER BY t.fecha_ingreso DESC, t.id DESC;
            """, [like])
            rows = _fetchall_dicts(cur)
        return Response(IngresoListItemSerializer(rows, many=True).data)










class TiposEquipoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        rows = q(
            """
            SELECT DISTINCT TRIM(nombre) AS nombre
            FROM marca_tipos_equipo
            WHERE activo = TRUE
            ORDER BY 1
            """
        ) or []
        return Response([{ 'id': i+1, 'nombre': r.get('nombre') } for i, r in enumerate(rows)])

    def post(self, request):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        d = request.data or {}
        new_name = (d.get("nombre") or "").strip()
        old_name = (d.get("rename_from") or "").strip()
        if not new_name:
            return Response({"detail": "nombre requerido"}, status=400)

        _set_audit_user(request)

        if old_name and old_name.lower() != new_name.lower():
            if connection.vendor == "postgresql":
                exec_void(
                    """
                    INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
                    SELECT marca_id, %s, activo
                    FROM marca_tipos_equipo
                    WHERE UPPER(nombre)=UPPER(%s)
                    ON CONFLICT (marca_id, nombre) DO UPDATE SET activo=EXCLUDED.activo
                    """,
                    [new_name, old_name],
                )
                exec_void("DELETE FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER(%s)", [old_name])
            else:
                exec_void(
                    """
                    INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
                    SELECT marca_id, %s, activo
                    FROM marca_tipos_equipo
                    WHERE UPPER(nombre)=UPPER(%s)
                    ON DUPLICATE KEY UPDATE activo=VALUES(activo)
                    """,
                    [new_name, old_name],
                )
                exec_void("DELETE FROM marca_tipos_equipo WHERE UPPER(nombre)=UPPER(%s)", [old_name])

            exec_void(
                "UPDATE models SET tipo_equipo=%s WHERE UPPER(TRIM(tipo_equipo))=UPPER(TRIM(%s))",
                [new_name, old_name],
            )
            return Response({"ok": True, "renamed": True})

        row = q("SELECT id FROM marcas ORDER BY id LIMIT 1", one=True)
        if not row:
            return Response({"detail": "No hay marcas disponibles para registrar el tipo"}, status=400)
        marca_id = row.get("id")
        if connection.vendor == "postgresql":
            exec_void(
                """
                INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
                VALUES (%s,%s,TRUE)
                ON CONFLICT (marca_id, nombre) DO UPDATE SET activo=EXCLUDED.activo
                """,
                [marca_id, new_name],
            )
        else:
            exec_void(
                """
                INSERT INTO marca_tipos_equipo(marca_id, nombre, activo)
                VALUES (%s,%s,TRUE)
                ON DUPLICATE KEY UPDATE activo=VALUES(activo)
                """,
                [marca_id, new_name],
            )
        return Response({"ok": True, "created": True})

    def delete(self, request):
        require_roles(request, ["jefe", "admin", "jefe_veedor"])
        nombre = (request.GET.get("nombre") or "").strip()
        if not nombre:
            return Response({"detail": "nombre requerido"}, status=400)
        _set_audit_user(request)
        exec_void("DELETE FROM marca_tipos_equipo WHERE UPPER(TRIM(nombre))=UPPER(TRIM(%s))", [nombre])
        exec_void("UPDATE models SET tipo_equipo=NULL WHERE UPPER(TRIM(tipo_equipo))=UPPER(TRIM(%s))", [nombre])
        return Response({"ok": True})






