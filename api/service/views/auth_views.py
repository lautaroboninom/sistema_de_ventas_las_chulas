import datetime as dt
import hashlib
import logging
import secrets

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..auth import issue_token, verify_hash, JWT_TTL_MIN
from ..ip_utils import get_client_ip
from ..models import User
from ..permissions import resolve_effective_permissions
from .helpers import (
    COOLDOWN_MIN,
    TOKEN_TTL_MIN,
    exec_void,
    q,
    _set_audit_user,
    _is_login_locked,
    _login_rate_key,
    _register_login_failure,
    _reset_login_failure,
)

logger = logging.getLogger("security.auth")


def _ip_rate_limit_key(prefix: str, ip: str) -> str:
    return f"security-rate:{prefix}:{ip or 'unknown'}"


def _consume_ip_rate_limit(prefix: str, ip: str, limit: int) -> bool:
    window = int(getattr(settings, "AUTH_RATE_WINDOW_SECONDS", 60) or 60)
    max_hits = max(1, int(limit or 1))
    key = _ip_rate_limit_key(prefix, ip)
    try:
        hits = cache.get(key, 0) or 0
        hits += 1
        cache.set(key, hits, window)
        return hits <= max_hits
    except Exception:
        return True


@api_view(["GET"])  # publico
@permission_classes([AllowAny])
def ping(request):
    return Response({"ok": True, "server_utc": timezone.now().isoformat()})


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
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
        ip = get_client_ip(request.META) or ""

        if not email or not password:
            raise AuthenticationFailed("Email y contrasena requeridos.")

        if not _consume_ip_rate_limit("login", ip, getattr(settings, "LOGIN_RATE_LIMIT_MAX", 20)):
            logger.warning("login_rate_limited ip=%s email=%s", ip, email)
            raise AuthenticationFailed("Demasiadas solicitudes. Proba mas tarde.")

        key = _login_rate_key(email, ip)
        if _is_login_locked(key):
            logger.warning("login_lockout_active ip=%s email=%s", ip, email)
            raise AuthenticationFailed("Demasiados intentos. Proba mas tarde.")

        try:
            user = User.objects.get(email=email, activo=True)
        except User.DoesNotExist:
            _register_login_failure(key)
            logger.warning("login_failed_invalid_user ip=%s email=%s", ip, email)
            raise AuthenticationFailed("Usuario o contrasena invalidos.")

        if not getattr(user, "hash_pw", ""):
            raise AuthenticationFailed(
                "El usuario aun no tiene contrasena. Usa \"Olvide mi contrasena\" para inicializarla."
            )

        if not verify_hash(password, user.hash_pw):
            _register_login_failure(key)
            logger.warning("login_failed_invalid_password ip=%s email=%s", ip, email)
            raise AuthenticationFailed("Usuario o contrasena invalidos.")

        _reset_login_failure(key)
        token = issue_token(user)
        permissions_map = resolve_effective_permissions(user_id=user.id, role=user.rol)
        resp = Response(
            {
                "user": {
                    "id": user.id,
                    "nombre": user.nombre,
                    "rol": _normalize_role(user.rol),
                    "email": getattr(user, "email", ""),
                    "permissions": permissions_map,
                },
                "features": {},
            }
        )
        try:
            cookie_name = getattr(settings, "AUTH_COOKIE_NAME", "auth_token")
            cookie_secure = getattr(settings, "AUTH_COOKIE_SECURE", (not getattr(settings, "DEBUG", False)))
            cookie_samesite = getattr(settings, "AUTH_COOKIE_SAMESITE", "Lax")
            cookie_domain = getattr(settings, "AUTH_COOKIE_DOMAIN", None) or None
            max_age = int(JWT_TTL_MIN) * 60
            resp.set_cookie(
                cookie_name,
                token,
                max_age=max_age,
                httponly=True,
                secure=bool(cookie_secure),
                samesite=cookie_samesite,
                domain=cookie_domain,
            )
        except Exception:
            logger.exception("login_cookie_set_failed ip=%s email=%s", ip, email)
        logger.info("login_success user_id=%s ip=%s", user.id, ip)
        return resp


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        ua = request.META.get("HTTP_USER_AGENT", "")
        ip = get_client_ip(request.META) or ""

        ok_response = Response({"ok": True})
        if not _consume_ip_rate_limit("forgot", ip, getattr(settings, "FORGOT_RATE_LIMIT_MAX", 10)):
            logger.warning("forgot_rate_limited ip=%s email=%s", ip, email)
            return ok_response
        if not email:
            return ok_response

        user = q(
            "SELECT id, email, nombre, activo FROM users WHERE LOWER(email)=%s",
            [email],
            one=True,
        )
        if not user or not user.get("activo"):
            return ok_response

        recent = q(
            """
            SELECT id FROM password_reset_tokens
             WHERE user_id=%(uid)s AND used_at IS NULL AND expires_at>NOW()
               AND created_at > NOW() - (%(mins)s || ' minutes')::interval
             ORDER BY id DESC LIMIT 1
            """,
            {"uid": user["id"], "mins": COOLDOWN_MIN},
            one=True,
        )
        if recent:
            return ok_response

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        exp = timezone.now() + dt.timedelta(minutes=TOKEN_TTL_MIN)

        _set_audit_user(request)
        exec_void(
            """
            INSERT INTO password_reset_tokens(user_id, token_hash, expires_at, ip, user_agent)
            VALUES (%s,%s,%s,%s,%s)
            """,
            [user["id"], token_hash, exp, ip, ua],
        )

        origin = getattr(settings, "FRONTEND_ORIGIN", "http://localhost:5173")
        url = f"{origin}/restablecer?t={token}"
        subj = "Recuperacion de contrasena"
        txt = (
            f"Hola {user['nombre']},\n\n"
            f"Usa este enlace para restablecer tu contrasena (valido {TOKEN_TTL_MIN} minutos):\n{url}\n\n"
            "Si no fuiste vos, ignora este correo."
        )
        html = (
            f"<p>Hola {user['nombre']},</p>"
            f"<p>Usa este enlace para restablecer tu contrasena (valido {TOKEN_TTL_MIN} minutos):</p>"
            f"<p><a href=\"{url}\">{url}</a></p>"
            "<p>Si no fuiste vos, ignora este correo.</p>"
        )
        try:
            send_mail(
                subj,
                txt,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html,
                fail_silently=True,
            )
        except Exception:
            pass
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
        row = q(
            """
            SELECT prt.id, prt.user_id
              FROM password_reset_tokens prt
             WHERE prt.token_hash=%s AND prt.used_at IS NULL AND prt.expires_at>NOW()
            """,
            [token_hash],
            one=True,
        )
        if not row:
            return Response({"detail": "Token invalido o vencido"}, status=400)

        hashed = make_password(password)
        _set_audit_user(request)
        exec_void("UPDATE users SET hash_pw=%s WHERE id=%s", [hashed, row["user_id"]])
        exec_void(
            "UPDATE password_reset_tokens SET used_at=NOW() WHERE id=%s",
            [row["id"]],
        )
        return Response({"ok": True})


class SessionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        u = getattr(request, "user", None)
        if not getattr(u, "id", None):
            return Response({"detail": "no autenticado"}, status=401)
        permissions_map = resolve_effective_permissions(
            user_id=getattr(u, "id", None),
            role=getattr(u, "rol", ""),
        )
        return Response(
            {
                "user": {
                    "id": u.id,
                    "nombre": getattr(u, "nombre", ""),
                    "rol": _normalize_role(getattr(u, "rol", "")),
                    "email": getattr(u, "email", ""),
                    "permissions": permissions_map,
                },
                "features": {},
            }
        )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        resp = Response({"ok": True, "time": timezone.now().isoformat()})
        try:
            cookie_name = getattr(settings, "AUTH_COOKIE_NAME", "auth_token")
            cookie_domain = getattr(settings, "AUTH_COOKIE_DOMAIN", None) or None
            cookie_samesite = getattr(settings, "AUTH_COOKIE_SAMESITE", "Lax")
            resp.delete_cookie(cookie_name, domain=cookie_domain, samesite=cookie_samesite)
        except Exception:
            pass
        return resp


def csrf_failure(request, reason=""):
    ip = get_client_ip(getattr(request, "META", {}) or {})
    logger.warning("csrf_rejected path=%s ip=%s reason=%s", getattr(request, "path", ""), ip, reason)
    return JsonResponse({"detail": "CSRF token invalido o ausente"}, status=403)
