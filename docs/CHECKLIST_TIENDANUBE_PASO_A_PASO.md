# Checklist Tienda Nube (Prueba ahora + Cambio a PC cliente)

## 1) Enlace inicial en esta PC (prueba)

### 1.1 Desde el panel de Tienda Nube
- En el menú lateral del admin de la tienda, entrar en `Aplicaciones`.
- Verificar si la app de integración ya está instalada (sección tipo `Mis aplicaciones`).
- Si no está instalada, instalarla desde el flujo de la app (autorización OAuth).

Nota:
- Las credenciales `client_id` y `client_secret` se obtienen del panel de socios/dev de Tienda Nube.
- El `access_token` y `store_id` salen del flujo de autorización (el `user_id` es el `store_id`).

### 1.2 Cargar credenciales en RetailHub
- Entrar a `Config > Config general`.
- Completar:
  - `tiendanube_store_id`
  - `tiendanube_client_id`
  - `tiendanube_client_secret`
  - `tiendanube_access_token`
  - `tiendanube_webhook_secret` (puede ser el mismo `client_secret`)
- Guardar.

### 1.3 Configurar webhooks (URL pública actual)
- `order/paid` -> `https://retailhub.tailcee59c.ts.net/api/retail/online/webhooks/orden-pagada/`
- `order/cancelled` -> `https://retailhub.tailcee59c.ts.net/api/retail/online/webhooks/orden-cancelada/`
- `store/redact` -> `https://retailhub.tailcee59c.ts.net/api/retail/online/webhooks/store-redact/`

### 1.4 Validación mínima
- Crear una orden de prueba pagada en Tienda Nube.
- Confirmar que se cree la venta en RetailHub (canal `online`).
- Cancelar una orden de prueba y validar reversión de stock/estado.

---

## 2) Cambio a la PC del cliente (cutover)

### 2.1 Preparación
- Definir ventana de corte (sin ventas online durante el cambio).
- Backup completo de base en PC actual.
- Exportar `.env.prod` y verificar secretos.

### 2.2 Instalación en PC cliente
- Copiar proyecto y `.env.prod`.
- Levantar `prod` en la PC cliente.
- Configurar Tailscale + Funnel en la PC cliente.
- Obtener nueva URL pública `https://<host>.ts.net`.

### 2.3 Reconfiguración de webhooks (obligatorio)
- Actualizar en Tienda Nube las 3 URLs de webhook a la nueva URL pública de la PC cliente.
- No dejar webhooks apuntando a dos PCs a la vez.

### 2.4 Corte
- Detener stack `prod` en la PC de prueba anterior.
- Dejar activa sólo la PC cliente.

### 2.5 Verificación post-corte
- `GET /api/ping/` responde `200` por URL pública nueva.
- Login admin OK.
- Webhook de orden pagada entra y crea venta online.
- Webhook de cancelación entra y revierte correctamente.

---

## 3) Regla de oro para evitar problemas
- Nunca operar dos entornos productivos con webhooks activos en paralelo para la misma tienda.

