# TODO Presupuesto: incluir imágenes de Hoja de Servicio en PDF

Objetivo
- Incluir imágenes subidas en “Archivos” del ingreso en el PDF del presupuesto.
- Ubicación: debajo de “Detalle Rep. (Diagnóstico / Trabajos a realizar)” y antes de “Total Neto:”.

Alcance / Arquitectura
- Backend-only: modificar el render del PDF del presupuesto (ReportLab).
- Fuente de datos: `ingreso_media` (solo `mime_type` imagen). Usar `thumbnail_path` preferentemente; fallback a `storage_path`.
- Sin cambios de frontend ni de schema. La vista sigue usando `/api/quotes/{ingreso_id}/pdf/`.

Puntos de inserción
- Función: `api/service/pdf.py:render_quote_pdf`.
- Insertar nueva sección inmediatamente después del bloque de diagnóstico/trabajos (cerca de `api/service/pdf.py:672`) y antes de los totales (cerca de `api/service/pdf.py:677`).

Detalles de implementación
- Query imágenes (recientes primero):
  - `SELECT ... FROM ingreso_media WHERE ingreso_id=%s AND mime_type LIKE 'image/%' ORDER BY created_at DESC, id DESC`.
- Render grid:
  - Configurable columnas y alto fijo por imagen, manteniendo aspect ratio.
  - Saltar archivos faltantes/corruptos sin romper el PDF (try/except por imagen).
  - Priorizar miniaturas para reducir tamaño del PDF; si no hay, usar original.
- Settings nuevos (en `api/app/settings.py`):
  - `QUOTE_IMAGES_MAX` (default 6)
  - `QUOTE_IMAGES_PER_ROW` (default 3)
  - `QUOTE_IMAGES_HEIGHT_MM` (default 35)
  - `QUOTE_IMAGES_USE_THUMBS` (default True)

Tareas
- [ ] Agregar settings con defaults en `api/app/settings.py`.
- [ ] `api/service/pdf.py`: helper `_get_ingreso_images(ingreso_id)` para fetch + paths preferentes.
- [ ] `api/service/pdf.py`: helper `_draw_images_grid(c, x, y, width, images)` que calcula columnas, alto (mm→pt) y dibuja con `ImageReader` devolviendo nuevo `y`.
- [ ] Invocar `_draw_images_grid` entre el bloque de diagnóstico/trabajos y la sección de totales.
- [ ] Manejo de errores por imagen (no interrumpe el render completo).
- [ ] QA manual: 0 imágenes (sin cambios), 1–6 imágenes (distintos ratios), thumbs faltantes (usa original), solo PDFs/videos (no inserta sección), tamaño de PDF razonable.

Decisiones abiertas
- Orden de imágenes: recientes primero (default) vs antiguas primero.
- Pie de foto (nombre/comentario): por ahora NO.
- Toggle “incluir imágenes” al emitir presupuesto: por ahora SIEMPRE incluir si hay.

Riesgos / mitigaciones
- Aumento tamaño del PDF → usar thumbnails por default y límite de cantidad.
- Faltan miniaturas → fallback a `storage_path` y manejo de excepciones.

