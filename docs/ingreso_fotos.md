# Fotos de Ingreso

Este módulo permite adjuntar evidencias fotográficas a cada Ingreso desde la pestaña "Diagnóstico y Reparación" de la Hoja de Servicio.

## API

Rutas bajo `/api/` (todas requieren JWT válido):

- `GET /ingresos/<id>/fotos/` — Lista paginada (`page`, `page_size`) ordenada por `created_at` descendente.
- `POST /ingresos/<id>/fotos/` — Sube una o varias imágenes (`multipart/form-data`). Campos de respuesta: `uploaded` y `errors`.
- `PATCH /ingresos/<id>/fotos/<media_id>/` — Actualiza el comentario opcional.
- `DELETE /ingresos/<id>/fotos/<media_id>/` — Elimina la foto y sus miniaturas.
- `GET /ingresos/<id>/fotos/<media_id>/archivo/` — Descarga el original.
- `GET /ingresos/<id>/fotos/<media_id>/miniatura/` — Obtiene la miniatura (inline).

Permisos:

- Ver: mismos roles que pueden ver el Ingreso (técnico asignado, recepción, jefes, admin).
- Subir/Eliminar/Comentar: técnico asignado, jefes y admins.

## Límites y validaciones

- Tipos permitidos por defecto: `image/jpeg`, `image/png` (HEIC opcional si está instalada `pillow-heif`).
- Peso máximo por archivo: 10 MB (`INGRESO_MEDIA_MAX_SIZE_MB`).
- Máximo por Ingreso: 50 archivos (`INGRESO_MEDIA_MAX_FILES`).
- Miniaturas generadas en servidor (`INGRESO_MEDIA_THUMB_MAX`).
- Todos los nombres y metadatos se sanitizan; no se exponen datos EXIF sensibles.

## Configuración por ambiente

Variables de entorno disponibles (ver `.env.example`):

```
INGRESO_MEDIA_MAX_SIZE_MB=10
INGRESO_MEDIA_MAX_FILES=50
INGRESO_MEDIA_THUMB_MAX=512
INGRESO_MEDIA_ALLOWED_MIME=image/jpeg,image/png
INGRESO_MEDIA_STORAGE_PREFIX=ingresos
```

El almacenamiento usa `default_storage`, por lo que funciona igual con archivos locales o S3 según los ajustes existentes.

## Logs y auditoría

Cada operación (alta, comentario, baja) dispara logs (`service.views`) y respeta los triggers/auditoría existentes al setear `app.ingreso_id` en PostgreSQL.

