# app/settings.py
import os
from pathlib import Path
from corsheaders.defaults import default_headers, default_methods

BASE_DIR = Path(__file__).resolve().parent.parent

def _csv(name: str, default: str = ""):
    raw = os.getenv(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

# --- Núcleo / seguridad ---
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = _csv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Orígenes del navegador (con esquema http/https)
CORS_ALLOWED_ORIGINS = _csv("ALLOWED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# Auditoría
AUDIT_LOG_ENABLED = os.getenv("AUDIT_LOG_ENABLED", "0").lower() in ("1","true")
AUDIT_LOG_MAX_BODY = int(os.getenv("AUDIT_LOG_MAX_BODY", "4096"))
AUDIT_LOG_EXCLUDE_PREFIXES = _csv("AUDIT_LOG_EXCLUDE_PREFIXES", "")

# Branding / URLs públicas
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
PUBLIC_WEB_URL = os.getenv("PUBLIC_WEB_URL", FRONTEND_ORIGIN)
LOGO_PATH = os.getenv("LOGO_PATH", "/code/service/static/logo.png")  # usado por PDF

# Email
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@sepid.com.ar")

# Zona horaria
TIME_ZONE = os.getenv("TZ", "America/Argentina/Buenos_Aires")
USE_TZ = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "service",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",          # debe ir arriba de CommonMiddleware
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "service.middleware.RLSMiddleware",               # RLS por-request
    "service.middleware.ActivityLogMiddleware",       # auditoría (con exclusiones por prefijo)
]

ROOT_URLCONF = "app.urls"
WSGI_APPLICATION = "app.wsgi.application"

# --- Base de datos: usar POSTGRES_* como en .env/.env.prod ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "servicio_tecnico"),
        "USER": os.getenv("POSTGRES_USER", "sepid"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "supersegura"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": True,  # necesario para SET LOCAL en el middleware RLS
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "service.auth.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "UNAUTHENTICATED_TOKEN": None,
}

# CORS
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + ["authorization"]
CORS_ALLOW_METHODS = list(default_methods)
# Solo útil en dev/LAN; no afecta prod si no se usa
CORS_ALLOW_PRIVATE_NETWORK = True

# Static
STATIC_URL = "/static/"

# Password hashing: priorizar Argon2 (tenés argon2-cffi en requirements)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# Endurecimiento cuando DEBUG=False
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
