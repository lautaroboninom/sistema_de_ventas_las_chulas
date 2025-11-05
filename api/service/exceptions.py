from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, AuthenticationFailed, PermissionDenied


def _as_text(detail):
    try:
        # DRF detail may be ErrorDetail or list/dict
        if isinstance(detail, (list, tuple)):
            return "; ".join(map(str, detail))
        if isinstance(detail, dict):
            # Flatten first level for readability
            parts = []
            for k, v in detail.items():
                parts.append(f"{k}: {v}")
            return "; ".join(parts)
        return str(detail)
    except Exception:
        return str(detail)


def handler(exc, context):
    """Exception handler consistente para 401/403.

    - 401 cuando no hay autenticación o el token es inválido/expirado.
    - 403 cuando el usuario autenticado no tiene permisos.
    - Cuerpo JSON estándar: { code, detail }.
    - Agrega WWW-Authenticate en 401 para clientes que lo usen.
    """
    response = drf_exception_handler(exc, context)

    if response is None:
        return response

    status_code = getattr(response, "status_code", None)

    # Mapear tipos a códigos consistentes
    code = None
    detail_text = None

    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        status_code = status.HTTP_401_UNAUTHORIZED
        code = "not_authenticated"
        detail_text = _as_text(getattr(exc, "detail", "No autenticado"))
    elif isinstance(exc, PermissionDenied):
        status_code = status.HTTP_403_FORBIDDEN
        code = "permission_denied"
        detail_text = _as_text(getattr(exc, "detail", "No autorizado"))
    else:
        # Mantener otras respuestas pero normalizar shape si tiene 'detail'
        data = getattr(response, "data", {}) or {}
        detail = data.get("detail")
        if detail is not None and not isinstance(detail, (dict, list)):
            detail_text = _as_text(detail)
            code = data.get("code") or str(getattr(getattr(exc, "default_code", "error"), "value", "error"))
        else:
            # dejar tal cual
            return response

    # Construir payload consistente
    payload = {"code": code or "error", "detail": detail_text or ""}
    new_resp = Response(payload, status=status_code)

    if status_code == status.HTTP_401_UNAUTHORIZED:
        try:
            new_resp["WWW-Authenticate"] = 'Bearer realm="api"'
        except Exception:
            pass

    return new_resp

