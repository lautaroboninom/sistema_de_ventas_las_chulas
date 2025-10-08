# TODO Garantías (políticas y verificación)

Objetivo
- Robustecer el cálculo/visualización de garantías de fábrica y de reparación.
- Exponer una página de administración/consulta de políticas.

Alcance v1 (mínimo viable)
- Mantener lector de Excel de trazabilidad como fuente para fecha de venta.
- Auto-tildar garantía de fábrica (≤365 días) por N/S en Nuevo ingreso y Hoja de servicio.
- Endpoint auxiliar para verificar por N/S (ya implementado): `GET /api/equipos/garantia-fabrica/?numero_serie=...&marca=...`.

Alcance v2 (políticas por marca/modelo)
- Tabla `warranty_rules`:
  - `id`, `brand_id` (nullable), `model_id` (nullable), `serial_prefix` (nullable), `serial_range` (nullable), `days` (int), `notas` (text), `activo` (bool), `created_by`, `created_at`, `updated_by`, `updated_at`.
  - Índices por `brand_id`, `model_id`, `serial_prefix`.
- Defaults en existencia:
  - `marcas.warranty_days_default` (nullable)
  - `models.warranty_days_default` (nullable)
- Servicio de cálculo unificado:
  - Input: `{marca, modelo, numero_serie, fecha_venta?}`
  - Origen de `fecha_venta`: primero reglas explícitas (si exigen venta), luego trazabilidad Excel.
  - Salida: `{days, vence_el, fuente: (excel|regla_modelo|regla_marca|default_modelo|default_marca|ninguna)}`
- API ABM:
  - `GET /api/garantias/politicas/` (filtros por marca/modelo/prefijo)
  - `POST /api/garantias/politicas/` crear
  - `PATCH /api/garantias/politicas/:id/` editar
  - `DELETE /api/garantias/politicas/:id/` (soft delete → `activo=false`)

Alcance v3 (excepciones por N/S)
- Tabla `warranty_overrides` con `{serial_exact, days, vence_el?, motivo}` que prevalece sobre cualquier regla.

Front-end
- Página `/garantias`:
  - Buscador por marca/modelo/serie.
  - Muestra política aplicada y vencimiento estimado.
  - Enlace para ABM (según rol).
- Integración existente:
  - Mostrar en UI la fuente de la garantía cuando se autocompleta (excel vs regla).

Notas técnicas
- `TRAZABILIDAD_ROOT` apunta al share UNC con Excels.
- Lector robusto: detecta encabezados aunque haya títulos y prioriza columnas exactas:
  - Serie: "Ítem - Artículo - Partida - Cód."
  - Fecha: "Comp. - F. Emisión"
- Cache simple en memoria (TTL configurable: `TRAZABILIDAD_CACHE_TTL_SEC`).

Tareas pendientes
- [ ] Modelo y migraciones para `warranty_rules` y `warranty_overrides`.
- [ ] Views/API DRF para ABM de políticas.
- [ ] Servicio de cálculo de garantía unificado.
- [ ] Página `/garantias` con filtros y detalle.
- [ ] Mostrar fuente de garantía en Nuevo ingreso/Hoja de servicio.

