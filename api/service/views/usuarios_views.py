import secrets
import hashlib
import datetime as dt

from django.conf import settings
from django.db import connection, transaction, IntegrityError
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from django.core.mail import send_mail

from .helpers import (
    q,
    exec_void,
    require_roles,
    require_jefe,
    _email_append_footer_text,
    _email_append_footer_html,
    TOKEN_TTL_MIN,
)
from ..roles import ROLE_KEYS, ROLE_CHOICES


class UsuariosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        rows = q(
            """
            SELECT id, nombre, email, rol, activo, COALESCE(perm_ingresar,false) AS perm_ingresar
            FROM users
            ORDER BY id ASC
            """
        )
        return Response(rows)

    @transaction.atomic
    def post(self, request):
        require_roles(request, ["jefe", "admin","jefe_veedor"])
        data = request.data or {}
        nombre = (data.get("nombre") or "").strip()
        email = (data.get("email") or "").strip().lower()
        rol_raw = (data.get("rol") or "tecnico")
        rol = rol_raw.strip().lower().replace(" ", "_").replace("-", "_")

        if not nombre or not email:
            raise ValidationError("Nombre y email son requeridos")
        if rol not in ROLE_KEYS:
            raise ValidationError("Rol invalido")

        existed = q("SELECT id FROM users WHERE email=%s", [email], one=True)
        q(
            """
            INSERT INTO users(nombre, email, rol, activo)
            VALUES (%(n)s, %(e)s, %(r)s, true)
            ON CONFLICT (email) DO UPDATE
            SET nombre = EXCLUDED.nombre,
                rol = EXCLUDED.rol
            """,
            {"n": nombre, "e": email, "r": rol},
        )

        if not existed:
            try:
                user = q("SELECT id, nombre, email FROM users WHERE email=%s", [email], one=True)
                if user:
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
                        [user["id"], token_hash, exp, ip, ua],
                    )
                    base = getattr(settings, "PUBLIC_WEB_URL", None) or getattr(settings, "FRONTEND_ORIGIN", "http://localhost:5173")
                    url = f"{(base or '').rstrip('/')}/restablecer?t={token}"
                    subj = "Bienvenido a SEPID - Configura tu contrasena"
                    txt = (
                        f"Hola {user['nombre']},\n\n"
                        f"Te damos la bienvenida al sistema de reparaciones de SEPID. "
                        f"Usa este enlace para establecer tu contrasena (valido {TOKEN_TTL_MIN} minutos):\n{url}\n\n"
                        f"Si no esperabas este correo, ignoralo."
                    )
                    html = f"""
                        <p>Hola {user['nombre']},</p>
                        <p>Bienvenido al sistema de reparaciones de <strong>SEPID</strong>.</p>
                        <p>Usa este enlace para establecer tu contrasena (valido {TOKEN_TTL_MIN} minutos):</p>
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
        require_jefe(request)
        user = q("SELECT id, email, nombre, activo FROM users WHERE id=%s", [uid], one=True)
        if not user or not user.get("activo"):
            return Response({"detail": "Usuario inexistente o inactivo"}, status=404)

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
            [user["id"], token_hash, exp, ip, ua],
        )
        base = getattr(settings, "PUBLIC_WEB_URL", None) or getattr(settings, "FRONTEND_ORIGIN", "http://localhost:5173")
        url = f"{(base or '').rstrip('/')}/restablecer?t={token}"
        subj = "SEPID - Enlace para establecer tu contrasena"
        txt = (
            f"Hola {user['nombre']},\n\n"
            f"Solicitaron un enlace para establecer o restablecer tu contrasena. "
            f"Usa este enlace (valido {TOKEN_TTL_MIN} minutos):\n{url}\n\n"
            f"Si no fuiste vos, ignora este correo."
        )
        html = f"""
            <p>Hola {user['nombre']},</p>
            <p>Solicitaron un enlace para establecer o restablecer tu contrasena.</p>
            <p>Usa este enlace (valido {TOKEN_TTL_MIN} minutos):</p>
            <p><a href="{url}">{url}</a></p>
            <p>Si no fuiste vos, ignora este correo.</p>
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
                raise ValidationError("Rol invalido")
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
                exec_void("UPDATE ingresos SET asignado_a = NULL WHERE asignado_a = %s", [uid])
                exec_void("UPDATE ingresos SET recibido_por = NULL WHERE recibido_por = %s", [uid])
                exec_void("UPDATE models   SET tecnico_id  = NULL WHERE tecnico_id  = %s", [uid])
                exec_void("UPDATE marcas   SET tecnico_id  = NULL WHERE tecnico_id  = %s", [uid])
                exec_void("UPDATE ingreso_events SET usuario_id = NULL WHERE usuario_id = %s", [uid])
                exec_void("DELETE FROM users WHERE id = %s", [uid])
        except IntegrityError:
            return Response(
                {"detail": "No se pudo eliminar: el usuario esta referenciado por otros registros. Reasigne/desasigne esas referencias o desactive el usuario."},
                status=409,
            )
        return Response({"ok": True})


class CatalogoRolesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles(request, ["jefe", "admin"])  # mantener restriccion como en legacy
        return Response([{"value": k, "label": v} for k, v in ROLE_CHOICES])


class CatalogoTecnicosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        rows = q(
            """
            SELECT id, nombre
            FROM users
            WHERE activo=true AND rol IN ('tecnico','jefe','jefe_veedor')
            ORDER BY nombre
            """
        ) or []
        return Response(rows)


__all__ = [
    'UsuariosView',
    'UsuarioActivoView',
    'UsuarioResetPassView',
    'UsuarioRolePermView',
    'UsuarioDeleteView',
    'CatalogoRolesView',
    'CatalogoTecnicosView',
]
