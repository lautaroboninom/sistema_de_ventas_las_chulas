import os
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework.exceptions import PermissionDenied

from ..permission_policy import resolve_permission_code_for_request
from ..permissions import permissions_v2_enabled, require_any_permission, require_permission

# Auth/login throttling constants
TOKEN_TTL_MIN = int(os.getenv('TOKEN_TTL_MIN', '30'))
COOLDOWN_MIN = int(os.getenv('EMAIL_COOLDOWN_MIN', '1'))
LOGIN_MAX_ATTEMPTS = int(os.getenv('LOGIN_MAX_ATTEMPTS', '5'))
LOGIN_LOCKOUT_MINUTES = int(os.getenv('LOGIN_LOCKOUT_MINUTES', '5'))
LOGIN_LOCKOUT_SECONDS = max(1, LOGIN_LOCKOUT_MINUTES) * 60
PASSWORD_MIN_LENGTH = int(os.getenv('PASSWORD_MIN_LENGTH', '8'))

TWO = Decimal('0.01')


def _login_rate_key(email: str, ip: str) -> str:
    email_norm = (email or '').strip().lower()
    ip_norm = ip or ''
    return f'login-attempt:{email_norm}:{ip_norm}'


def _is_login_locked(key: str) -> bool:
    try:
        attempts = cache.get(key, 0) or 0
        return attempts >= getattr(settings, 'LOGIN_MAX_ATTEMPTS', LOGIN_MAX_ATTEMPTS)
    except Exception:
        return False


def _register_login_failure(key: str) -> None:
    try:
        attempts = (cache.get(key, 0) or 0) + 1
        cache.set(key, attempts, getattr(settings, 'LOGIN_LOCKOUT_SECONDS', LOGIN_LOCKOUT_SECONDS))
    except Exception:
        pass


def _reset_login_failure(key: str) -> None:
    try:
        cache.delete(key)
    except Exception:
        pass


def _validate_password_strength(password: str) -> None:
    if len(password or '') < getattr(settings, 'PASSWORD_MIN_LENGTH', PASSWORD_MIN_LENGTH):
        raise ValueError('weak password')
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
        raise ValueError('weak password')


def money(x):
    if x is None:
        return Decimal('0.00')
    if isinstance(x, Decimal):
        return x.quantize(TWO, rounding=ROUND_HALF_UP)
    return Decimal(str(x)).quantize(TWO, rounding=ROUND_HALF_UP)


def _fetchall_dicts(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def q(sql, params=None, one=False):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        if not cur.description:
            return None
        rows = _fetchall_dicts(cur)
        if one:
            return rows[0] if rows else None
        return rows


def exec_void(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])


def exec_returning(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
        return row[0] if row else None


def last_insert_id():
    row = q('SELECT LASTVAL() AS id', one=True)
    return row and row.get('id')


def _set_audit_user(request):
    if connection.vendor != 'postgresql':
        return
    uid = getattr(request, 'user_id', None)
    if uid is None:
        uid = getattr(getattr(request, 'user_obj', None), 'id', None)
    uid = '' if uid is None else str(uid)
    role = getattr(request, 'user_role', None)
    if role is None:
        role = getattr(getattr(request, 'user_obj', None), 'rol', '')
    with connection.cursor() as cur:
        cur.execute('SET app.user_id = %s;', [uid])
        cur.execute('SET app.user_role = %s;', [role])


def _rol(request):
    return (getattr(getattr(request, 'user', None), 'rol', None) or '').strip().lower()


def _require_mapped_permission(request):
    if not permissions_v2_enabled():
        return False
    code = resolve_permission_code_for_request(request)
    if not code:
        return False
    if isinstance(code, (list, tuple, set)):
        require_any_permission(request, code)
        return True
    require_permission(request, code)
    return True


def require_roles(request, roles):
    if _require_mapped_permission(request):
        return
    role = _rol(request)
    expected = {(r or '').strip().lower() for r in (roles or [])}
    if role not in expected:
        raise PermissionDenied('No autorizado')


def require_roles_strict(request, roles):
    if _require_mapped_permission(request):
        return
    role = _rol(request)
    expected = {(r or '').strip().lower() for r in (roles or [])}
    if role not in expected:
        raise PermissionDenied('No autorizado')


def require_jefe(request):
    # Compatibilidad con codigo antiguo: en retail el rol equivalente es admin.
    require_roles(request, ['admin'])


def _is(role, request):
    return _rol(request) == (role or '').strip().lower()


def _in(roles, request):
    expected = {(r or '').strip().lower() for r in (roles or [])}
    return _rol(request) in expected


def _frontend_url(request, path: str) -> str:
    try:
        base = (getattr(settings, 'PUBLIC_WEB_URL', '') or getattr(settings, 'FRONTEND_ORIGIN', '')).strip()
        if base:
            return f"{base.rstrip('/')}{path}"
        return request.build_absolute_uri(path)
    except Exception:
        return path


__all__ = [
    'TOKEN_TTL_MIN',
    'COOLDOWN_MIN',
    'LOGIN_MAX_ATTEMPTS',
    'LOGIN_LOCKOUT_MINUTES',
    'LOGIN_LOCKOUT_SECONDS',
    'PASSWORD_MIN_LENGTH',
    '_login_rate_key',
    '_is_login_locked',
    '_register_login_failure',
    '_reset_login_failure',
    '_validate_password_strength',
    'q',
    'exec_void',
    'exec_returning',
    'last_insert_id',
    '_set_audit_user',
    '_fetchall_dicts',
    'require_roles',
    'require_roles_strict',
    'require_jefe',
    'require_permission',
    '_rol',
    '_is',
    '_in',
    'money',
    '_frontend_url',
]
