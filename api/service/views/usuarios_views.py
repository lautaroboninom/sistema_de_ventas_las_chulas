import datetime as dt
import hashlib
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from ..ip_utils import get_client_ip
from ..permission_catalog import PERMISSION_CODES, get_catalog
from ..permissions import (
    EFFECT_ALLOW,
    EFFECT_DENY,
    EFFECT_INHERIT,
    apply_overrides,
    require_permission,
    reset_overrides,
    resolve_effective_permissions,
)
from ..roles import ROLE_CHOICES, ROLE_KEYS
from .helpers import TOKEN_TTL_MIN, _set_audit_user, q, require_roles_strict


def _load_user(uid):
    row = q(
        '''
        SELECT id, nombre, email, rol, activo
        FROM users
        WHERE id=%s
        ''',
        [uid],
        one=True,
    )
    if not row:
        raise ValidationError('Usuario no encontrado')
    row['rol'] = (row.get('rol') or '').strip().lower()
    return row


def _load_overrides(uid):
    rows = q(
        '''
        SELECT permission_code, effect
        FROM user_permission_overrides
        WHERE user_id=%s
        ORDER BY permission_code
        ''',
        [uid],
    ) or []
    out = {}
    for item in rows:
        code = (item.get('permission_code') or '').strip()
        effect = (item.get('effect') or '').strip().lower()
        if code and effect in (EFFECT_ALLOW, EFFECT_DENY):
            out[code] = effect
    return out


def _serialize_permissions(uid):
    user_row = _load_user(uid)
    overrides = _load_overrides(uid)
    effective = resolve_effective_permissions(user_id=uid, role=user_row.get('rol'), overrides=overrides)
    merged = {code: EFFECT_INHERIT for code in PERMISSION_CODES}
    merged.update(overrides)
    return {
        'user': user_row,
        'editable': user_row.get('rol') != 'admin',
        'overrides': merged,
        'effective_permissions': effective,
        'raw_overrides': overrides,
    }


def _create_reset_token(user_id, request):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = timezone.now() + dt.timedelta(minutes=TOKEN_TTL_MIN)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    ip = get_client_ip(request.META) or ''
    q(
        '''
        INSERT INTO password_reset_tokens(user_id, token_hash, expires_at, ip, user_agent)
        VALUES (%s, %s, %s, %s, %s)
        ''',
        [user_id, token_hash, expires_at, ip, user_agent],
    )
    return token


def _send_reset_mail(user_row, token):
    base = (
        (getattr(settings, 'PUBLIC_WEB_URL', '') or '').strip()
        or (getattr(settings, 'FRONTEND_ORIGIN', '') or '').strip()
        or 'http://localhost:5173'
    )
    reset_url = f"{base.rstrip('/')}/restablecer?t={token}"
    company = (getattr(settings, 'COMPANY_NAME', '') or 'Las Chulas').strip()
    subject = f'{company} - Enlace para restablecer contrasena'
    text_body = (
        f"Hola {user_row.get('nombre', '')},\n\n"
        f"Usa este enlace para establecer o restablecer tu contrasena (valido {TOKEN_TTL_MIN} minutos):\n"
        f"{reset_url}\n\n"
        'Si no fuiste vos, ignora este correo.'
    )
    html_body = (
        f"<p>Hola {user_row.get('nombre', '')},</p>"
        '<p>Usa este enlace para establecer o restablecer tu contrasena '
        f"(valido {TOKEN_TTL_MIN} minutos):</p>"
        f"<p><a href=\"{reset_url}\">{reset_url}</a></p>"
        '<p>Si no fuiste vos, ignora este correo.</p>'
    )
    try:
        send_mail(
            subject,
            text_body,
            settings.DEFAULT_FROM_EMAIL,
            [user_row.get('email', '')],
            html_message=html_body,
            fail_silently=True,
        )
    except Exception:
        pass


class UsuariosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles_strict(request, ['admin'])
        rows = q(
            '''
            SELECT u.id, u.nombre, u.email, u.rol, u.activo,
                   COALESCE(p.cnt,0) AS permisos_personalizados
            FROM users u
            LEFT JOIN (
              SELECT user_id, COUNT(*) AS cnt
              FROM user_permission_overrides
              GROUP BY user_id
            ) p ON p.user_id=u.id
            ORDER BY u.id
            '''
        ) or []
        return Response(rows)

    @transaction.atomic
    def post(self, request):
        require_roles_strict(request, ['admin'])
        _set_audit_user(request)
        data = request.data or {}
        nombre = (data.get('nombre') or data.get('name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        rol = (data.get('rol') or 'empleado').strip().lower()
        if not nombre or not email:
            raise ValidationError('nombre y email son requeridos')
        if rol not in ROLE_KEYS:
            raise ValidationError('rol invalido')

        uid = q('SELECT id FROM users WHERE LOWER(email)=LOWER(%s)', [email], one=True)
        if uid:
            q('UPDATE users SET nombre=%s, rol=%s WHERE id=%s', [nombre, rol, uid['id']])
            return Response({'ok': True, 'id': uid['id'], 'created': False})

        new_id = q(
            '''
            INSERT INTO users(nombre, email, rol, activo)
            VALUES (%s,%s,%s,TRUE)
            RETURNING id
            ''',
            [nombre, email, rol],
            one=True,
        )
        return Response({'ok': True, 'id': new_id['id'], 'created': True}, status=201)


class UsuarioActivoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, uid):
        require_roles_strict(request, ['admin'])
        _set_audit_user(request)
        activo = bool((request.data or {}).get('activo'))
        q('UPDATE users SET activo=%s WHERE id=%s', [activo, uid])
        return Response({'ok': True, 'activo': activo})


class UsuarioResetPassView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def patch(self, request, uid):
        require_roles_strict(request, ['admin'])
        user_row = q(
            '''
            SELECT id, nombre, email, activo
            FROM users
            WHERE id=%s
            ''',
            [uid],
            one=True,
        )
        if not user_row or not user_row.get('activo'):
            return Response({'detail': 'Usuario inexistente o inactivo'}, status=404)

        _set_audit_user(request)
        token = _create_reset_token(user_row['id'], request)
        _send_reset_mail(user_row, token)
        return Response({'ok': True, 'sent': True})


class UsuarioRolePermView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def patch(self, request, uid):
        require_roles_strict(request, ['admin'])
        _set_audit_user(request)
        data = request.data or {}
        rol = (data.get('rol') or '').strip().lower()
        if not rol:
            raise ValidationError('rol requerido')
        if rol not in ROLE_KEYS:
            raise ValidationError('rol invalido')

        prev = q('SELECT rol FROM users WHERE id=%s', [uid], one=True)
        if not prev:
            raise ValidationError('Usuario no encontrado')
        prev_role = (prev.get('rol') or '').strip().lower()

        q('UPDATE users SET rol=%s WHERE id=%s', [rol, uid])
        if rol == 'admin' or prev_role == 'admin':
            reset_overrides(uid)
        return Response({'ok': True})


class UsuarioDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def delete(self, request, uid):
        require_roles_strict(request, ['admin'])
        target_user = _load_user(uid)

        current_user_id = getattr(getattr(request, 'user', None), 'id', None)
        if current_user_id is not None and int(current_user_id) == int(uid):
            raise ValidationError('No se puede eliminar tu propio usuario')

        if target_user.get('rol') == 'admin' and target_user.get('activo'):
            other_active_admins = q(
                '''
                SELECT COUNT(*)::int AS cnt
                FROM users
                WHERE rol='admin' AND activo=TRUE AND id<>%s
                ''',
                [uid],
                one=True,
            )
            if int((other_active_admins or {}).get('cnt') or 0) < 1:
                raise ValidationError('No se puede eliminar el ultimo admin activo')

        _set_audit_user(request)
        try:
            q('DELETE FROM users WHERE id=%s', [uid])
        except IntegrityError:
            return Response(
                {
                    'detail': (
                        'No se pudo eliminar: el usuario esta referenciado por otros registros. '
                        'Reasigna esas referencias o desactiva el usuario.'
                    )
                },
                status=409,
            )
        return Response({'ok': True})


class CatalogoRolesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles_strict(request, ['admin'])
        return Response([{'value': key, 'label': label} for key, label in ROLE_CHOICES])


class CatalogoPermisosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        require_roles_strict(request, ['admin'])
        require_permission(request, 'action.config.editar')
        return Response({'permissions': get_catalog(), 'effects': [EFFECT_INHERIT, EFFECT_ALLOW, EFFECT_DENY]})


class UsuarioPermisosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, uid):
        require_roles_strict(request, ['admin'])
        require_permission(request, 'action.config.editar')
        return Response(_serialize_permissions(uid))

    @transaction.atomic
    def put(self, request, uid):
        require_roles_strict(request, ['admin'])
        require_permission(request, 'action.config.editar')
        data = request.data or {}
        overrides = data.get('overrides')
        if not isinstance(overrides, dict):
            raise ValidationError('overrides requerido y debe ser objeto')

        user_row = _load_user(uid)
        if user_row.get('rol') == 'admin':
            raise PermissionDenied('No se editan permisos granulares para rol admin')

        _set_audit_user(request)
        try:
            apply_overrides(uid, overrides, updated_by=getattr(request.user, 'id', None))
        except ValueError as exc:
            raise ValidationError(str(exc))
        return Response(_serialize_permissions(uid))


class UsuarioPermisosResetView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, uid):
        require_roles_strict(request, ['admin'])
        require_permission(request, 'action.config.editar')
        user_row = _load_user(uid)
        if user_row.get('rol') == 'admin':
            raise PermissionDenied('No se editan permisos granulares para rol admin')
        _set_audit_user(request)
        reset_overrides(uid)
        return Response(_serialize_permissions(uid))


__all__ = [
    'UsuariosView',
    'UsuarioActivoView',
    'UsuarioResetPassView',
    'UsuarioRolePermView',
    'UsuarioDeleteView',
    'CatalogoRolesView',
    'CatalogoPermisosView',
    'UsuarioPermisosView',
    'UsuarioPermisosResetView',
]
