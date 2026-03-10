from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa

# Ajustes para prod (Tailscale/Funnel)
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"

_default_host = os.getenv("PUBLIC_HOST", "").strip()
if not _default_host:
    _default_host = (os.getenv("DJANGO_ALLOWED_HOSTS", "example.com").split(",")[0].strip() or "example.com")

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", _default_host).split(",") if h.strip()]

_default_origin = f"https://{_default_host}"
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origin).split(",") if o.strip()]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "0").strip().lower() in ("1", "true", "yes", "on")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if TRUST_PROXY_HEADERS else None

if EMAIL_INSECURE_SKIP_VERIFY:
    raise ImproperlyConfigured("EMAIL_INSECURE_SKIP_VERIFY=1 no esta permitido en produccion")


def _validate_secret_value(label: str, value: str, min_length: int) -> None:
    raw = (value or "").strip()
    low = raw.lower()
    weak_values = {
        "",
        "change-me",
        "changeme",
        "default",
        "replace_with_strong_secret",
        "replace-with-strong-secret",
        "replace_with_strong_db_password",
        "replace-with-strong-db-password",
        "laschulas25",
        "laschulas25_secret_key",
    }
    if (
        low in weak_values
        or "replace" in low
        or "changeme" in low
        or len(raw) < min_length
    ):
        raise ImproperlyConfigured(
            f"{label} invalido o debil para produccion (minimo {min_length} caracteres y sin placeholders)"
        )


_validate_secret_value("DJANGO_SECRET_KEY", SECRET_KEY, 40)
_validate_secret_value("JWT_SECRET", os.getenv("JWT_SECRET", ""), 40)
_validate_secret_value("POSTGRES_PASSWORD", os.getenv("POSTGRES_PASSWORD", ""), 20)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1").strip()
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}


def _validate_secret_path(label: str, value: str) -> None:
    raw = (value or "").strip()
    if not raw:
        return
    path = Path(raw).expanduser().resolve()
    base = BASE_DIR.resolve()
    try:
        path.relative_to(base)
        raise ImproperlyConfigured(f"{label} no puede estar dentro del repo ({base})")
    except ValueError:
        pass
    if path.exists():
        mode = path.stat().st_mode & 0o777
        if mode & 0o077:
            raise ImproperlyConfigured(f"{label} debe tener permisos restrictivos (600 recomendado)")


_validate_secret_path("ARCA_CERT_PATH", ARCA_CERT_PATH)
_validate_secret_path("ARCA_KEY_PATH", ARCA_KEY_PATH)

STATIC_ROOT = os.getenv("STATIC_ROOT", "/app/staticfiles")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "/app/media")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
