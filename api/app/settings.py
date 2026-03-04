# app/settings.py
import os
from pathlib import Path
from corsheaders.defaults import default_headers, default_methods

BASE_DIR = Path(__file__).resolve().parent.parent

def _csv(name: str, default: str = ""):
    raw = os.getenv(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

def _bool_env(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")

# --- NÃºcleo / seguridad ---
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = _csv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# OrÃ­genes del navegador (con esquema http/https)
CORS_ALLOWED_ORIGINS = _csv("ALLOWED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# AuditorÃ­a
AUDIT_LOG_ENABLED = os.getenv("AUDIT_LOG_ENABLED", "0").lower() in ("1","true")
AUDIT_LOG_MAX_BODY = int(os.getenv("AUDIT_LOG_MAX_BODY", "4096"))
AUDIT_LOG_EXCLUDE_PREFIXES = _csv("AUDIT_LOG_EXCLUDE_PREFIXES", "")

# Branding / URLs pÃºblicas
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
PUBLIC_WEB_URL = os.getenv("PUBLIC_WEB_URL", FRONTEND_ORIGIN)
LOGO_PATH = os.getenv("LOGO_PATH", "/app/staticfiles/branding/logo-app.png")  # usado por PDF

# Nombre de la empresa (para emails/PDFs)
COMPANY_NAME = os.getenv("COMPANY_NAME", "Las Chulas")
COMPANY_CODE = (os.getenv("COMPANY_CODE") or "DEFAULT").strip().upper() or "DEFAULT"

# Company header for PDFs (static across companies)
COMPANY_HEADER_L1 = os.getenv("COMPANY_HEADER_L1", "")
COMPANY_HEADER_L2 = os.getenv("COMPANY_HEADER_L2", COMPANY_NAME)
COMPANY_HEADER_L3 = os.getenv("COMPANY_HEADER_L3", "")

# Datos de contacto para pie de pÃ¡gina del presupuesto (pueden cambiar vÃ­a entorno)
COMPANY_FOOTER_EMAIL = os.getenv("COMPANY_FOOTER_EMAIL", "")
COMPANY_FOOTER_CUIT = os.getenv("COMPANY_FOOTER_CUIT", "")
COMPANY_FOOTER_WEB = os.getenv("COMPANY_FOOTER_WEB", "")
COMPANY_FOOTER_WHATSAPP = os.getenv("COMPANY_FOOTER_WHATSAPP", "")

# Directorio opcional donde guardar copias de PDFs de presupuestos
# Si existe, se escriben allÃ­ ademÃ¡s de devolverse al cliente
QUOTES_SAVE_DIR = os.getenv(
    "QUOTES_SAVE_DIR",
    ""
)

# Email
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _bool_env("EMAIL_USE_TLS", "1")
EMAIL_USE_SSL = _bool_env("EMAIL_USE_SSL", "0")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "20"))
EMAIL_INSECURE_SKIP_VERIFY = _bool_env("EMAIL_INSECURE_SKIP_VERIFY", "0")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.com")
EMAIL_LEGAL_FOOTER = os.getenv(
    "EMAIL_LEGAL_FOOTER",
    (
        "La informaciÃ³n de este correo es confidencial y concierne Ãºnicamente a la persona a la que estÃ¡ dirigida. "
        "Se niega el consentimiento para que pueda ser empleada como prueba por el destinatario en los tÃ©rminos que autoriza el art. 318 del CCyCN. "
        "Si este mensaje no estÃ¡ dirigido a usted, por favor tenga presente que no tiene autorizaciÃ³n para leer el resto de este correo, copiarlo o derivarlo a cualquier otra persona que no sea aquella a la que estÃ¡ dirigido, como asÃ­ tampoco valerse del mismo. "
        "Si recibe este correo por error, por favor, avise al remitente, luego de lo cual rogamos a usted destruya el mensaje original. "
        "No se puede responsabilizar al remitente de ninguna forma por/o en relaciÃ³n con alguna consecuencia y/o daÃ±o que resulte del apropiado y completo envÃ­o y recepciÃ³n del contenido de este correo."
    ),
)

# Retail - Facturacion ARCA / AFIP WSFEv1
ARCA_WS_ENV = os.getenv("ARCA_WS_ENV", "homolog")  # homolog | prod
ARCA_WSFE_MOCK = os.getenv("ARCA_WSFE_MOCK", "1")  # usar mock en MVP hasta configurar certificados
ARCA_DEFAULT_PTO_VTA = int(os.getenv("ARCA_DEFAULT_PTO_VTA", "1"))
ARCA_DEFAULT_TIPO_CBTE = int(os.getenv("ARCA_DEFAULT_TIPO_CBTE", "6"))
ARCA_CUIT = os.getenv("ARCA_CUIT", "")
ARCA_CERT_PATH = os.getenv("ARCA_CERT_PATH", "")
ARCA_KEY_PATH = os.getenv("ARCA_KEY_PATH", "")
ARCA_WSAA_SERVICE = os.getenv("ARCA_WSAA_SERVICE", "wsfe")

# Retail - Tienda Nube
TIENDANUBE_CLIENT_ID = os.getenv("TIENDANUBE_CLIENT_ID", "")
TIENDANUBE_CLIENT_SECRET = os.getenv("TIENDANUBE_CLIENT_SECRET", "")
TIENDANUBE_STORE_ID = os.getenv("TIENDANUBE_STORE_ID", "")
TIENDANUBE_ACCESS_TOKEN = os.getenv("TIENDANUBE_ACCESS_TOKEN", "")
TIENDANUBE_WEBHOOK_SECRET = os.getenv("TIENDANUBE_WEBHOOK_SECRET", "")
TIENDANUBE_API_BASE = os.getenv("TIENDANUBE_API_BASE", "https://api.tiendanube.com/v1")
TIENDANUBE_USER_AGENT = os.getenv("TIENDANUBE_USER_AGENT", "LasChulasRetail (admin@localhost)")
TIENDANUBE_TIMEOUT_SECS = int(os.getenv("TIENDANUBE_TIMEOUT_SECS", "15"))

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
    "service.middleware.AuditUserMiddleware",         # set app.user_id/app.user_role por request
    "service.middleware.RLSMiddleware",               # RLS por-request
    "service.middleware.ActivityLogMiddleware",       # auditorÃ­a (con exclusiones por prefijo)
]

ROOT_URLCONF = "app.urls"
WSGI_APPLICATION = "app.wsgi.application"

# Templates (habilita carga de plantillas por app_dir)
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [],
        },
    }
]

# --- Base de datos: solo PostgreSQL ---
# Variables esperadas: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", os.getenv("PGDATABASE", "las_chulas_retail")),
        "USER": os.getenv("POSTGRES_USER", os.getenv("PGUSER", "postgres")),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", os.getenv("PGPASSWORD", "")),
        "HOST": os.getenv("POSTGRES_HOST", os.getenv("PGHOST", "postgres")),
        "PORT": os.getenv("POSTGRES_PORT", os.getenv("PGPORT", "5432")),
        "ATOMIC_REQUESTS": True,
        # ReutilizaciÃ³n de conexiones
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
    }
}

CACHES = {
    "default": {
        "BACKEND": os.getenv("DJANGO_CACHE_BACKEND", "django.core.cache.backends.locmem.LocMemCache"),
        "LOCATION": os.getenv("DJANGO_CACHE_LOCATION", "default"),
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "service.auth.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "service.permissions.MappedPermissionGuard",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "UNAUTHENTICATED_TOKEN": None,
    # Normaliza 401/403 y agrega WWW-Authenticate en 401
    "EXCEPTION_HANDLER": "service.exceptions.handler",
}

# Feature flag para permisos granulares por usuario.
PERMISSIONS_V2_ENABLED = os.getenv("PERMISSIONS_V2_ENABLED", "1").strip().lower() in ("1", "true", "yes")

# CORS
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + ["authorization"]
CORS_ALLOW_METHODS = list(default_methods)
# Solo Ãºtil en dev/LAN; no afecta prod si no se usa
CORS_ALLOW_PRIVATE_NETWORK = True

# Static
STATIC_URL = "/static/"
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", str(BASE_DIR / "media"))

# Password hashing: priorizar Argon2 (tenÃ©s argon2-cffi en requirements)
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

# --- Seguridad / AutenticaciÃ³n (vistas) ---
# TTL de tokens de restablecimiento (minutos)
TOKEN_TTL_MIN = int(os.getenv("TOKEN_TTL_MIN", "30"))

# Cooldown para envÃ­o de correos repetidos (minutos)
EMAIL_COOLDOWN_MIN = int(os.getenv("EMAIL_COOLDOWN_MIN", "1"))

# Intentos mÃ¡ximos de login y bloqueo temporal
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "5"))
LOGIN_LOCKOUT_SECONDS = max(1, LOGIN_LOCKOUT_MINUTES) * 60

# Requisito mÃ­nimo local de longitud de contraseÃ±a (ademÃ¡s de validators si aplica)
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))

# Cookies de autenticaciÃ³n (para JWT en cookie)
# Por default el login devuelve token en el body y TAMBIÃ‰N lo setea en cookie
# Si el front consume por cross-origin, usar: AUTH_COOKIE_SAMESITE=None y AUTH_COOKIE_SECURE=True (requiere HTTPS)
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "auth_token")
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "Lax")  # Lax | Strict | None
# Si no se define, se toma segÃºn DEBUG
_cookie_secure_env = os.getenv("AUTH_COOKIE_SECURE", "")
AUTH_COOKIE_SECURE = (not DEBUG) if _cookie_secure_env == "" else (_cookie_secure_env.lower() in ("1","true","yes"))
AUTH_COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN", "") or None

