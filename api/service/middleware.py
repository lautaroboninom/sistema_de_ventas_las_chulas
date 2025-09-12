# service/middleware.py
from django.db import connection
from django.conf import settings
from django.utils import timezone
import json
import jwt

class RLSMiddleware:
    """
    Setea variables de sesión (GUC) para que las POLÍTICAS RLS apliquen
    durante TODA la ejecución de la vista, y las limpia al final.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_id = None
        role = "anonymous"
        try:
            # Si hay Auth de DRF/JWT, respetamos lo que ya venga
            user_id = getattr(getattr(request, "user", None), "id", None)
            role = getattr(getattr(request, "user", None), "rol", None) or "anonymous"
        except Exception:
            pass

        try:
            # RLS variables solo para Postgres
            if connection.vendor == "postgresql":
                with connection.cursor() as cur:
                    if user_id:
                        cur.execute("SET app.user_id = %s;", [str(user_id)])
                    else:
                        cur.execute("RESET app.user_id;")
                    cur.execute("SET app.user_role = %s;", [str(role)])
            response = self.get_response(request)
        finally:
            try:
                if connection.vendor == "postgresql":
                    with connection.cursor() as cur:
                        cur.execute("RESET app.user_id;")
                        cur.execute("RESET app.user_role;")
            except Exception:
                pass
        return response


class ActivityLogMiddleware:
    """
    Auditoría a nivel aplicación (HTTP). Registra SOLO métodos de escritura
    (POST/PATCH/PUT/DELETE) con metadata mínima. Append-only.
    """
    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "AUDIT_LOG_ENABLED", False):
            return self.get_response(request)

        path = request.path or ""
        for pref in getattr(settings, "AUDIT_LOG_EXCLUDE_PREFIXES", []):
            if path.startswith(pref):
                return self.get_response(request)

        is_write = request.method in self.WRITE_METHODS
        user = getattr(request, "user", None)
        user_id = getattr(user, "id", None)
        role = getattr(user, "rol", None)
        ip = request.META.get("REMOTE_ADDR")
        ua = request.META.get("HTTP_USER_AGENT", "")[:512]

        body_json = None
        if is_write:
            try:
                if request.body:
                    raw = request.body[: settings.AUDIT_LOG_MAX_BODY]
                    body_json = json.loads(raw.decode("utf-8", errors="ignore"))
            except Exception:
                body_json = None

        response = self.get_response(request)

        if is_write:
            try:
                with connection.cursor() as cur:
                    if connection.vendor == "mysql":
                        cur.execute(
                            """
                            INSERT INTO audit_log (ts, user_id, role, method, path, ip, user_agent, status_code, body)
                            VALUES (now(), %s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON))
                            """,
                            [
                                user_id,
                                role,
                                request.method,
                                path,
                                ip,
                                ua,
                                getattr(response, "status_code", None),
                                json.dumps(body_json) if body_json is not None else None,
                            ],
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO audit_log (ts, user_id, role, method, path, ip, user_agent, status_code, body)
                            VALUES (now(), %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                            """,
                            [
                                user_id,
                                role,
                                request.method,
                                path,
                                ip,
                                ua,
                                getattr(response, "status_code", None),
                                json.dumps(body_json) if body_json is not None else None,
                            ],
                        )
            except Exception:
                # No romper la request por problemas de log
                pass

        return response
