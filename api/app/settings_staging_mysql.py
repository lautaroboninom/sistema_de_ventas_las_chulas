from .settings import *  # noqa
import os


# Base de datos: MySQL 8.0 para STAGING
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "servicio_tecnico"),
        "USER": os.getenv("MYSQL_USER", "sepid"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
        "HOST": os.getenv("MYSQL_HOST", "mysql"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "ATOMIC_REQUESTS": True,  # mantiene transacciones por request
        "OPTIONS": {
            # Modo estricto y charset por conexión
            "init_command": "SET sql_mode='STRICT_ALL_TABLES'",
            "charset": "utf8mb4",
        },
        # Reutilización de conexiones
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
    }
}

# Zona horaria consistente con la app
TIME_ZONE = os.getenv("TZ", "America/Argentina/Buenos_Aires")
USE_TZ = True

