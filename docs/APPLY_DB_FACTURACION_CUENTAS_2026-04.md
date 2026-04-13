# Apply DB - Facturacion por cuenta (2026-04)

## Alcance del cambio
Este apply corresponde a los cambios de:
- `retail_payment_accounts.price_modifier_pct`
- `retail_payment_accounts.default_arca_account_id`
- backfill inicial de `%` y cuenta ARCA default
- logica nueva de facturacion por cuenta de cobro (sin round-robin para ventas nuevas)

Migracion involucrada:
- `service.0012_payment_account_invoice_rules`

## Regla importante
En ambientes existentes, aplicar por **migraciones Django**.  
No ejecutar `sql/schema.sql` completo sobre una base en uso.

## Pre-checks (produccion)
1. Confirmar backup reciente de Postgres.
2. Confirmar que no haya despliegue paralelo de otra version.
3. Verificar que el contenedor `postgres` este sano.

## Paso a paso (Docker prod)
Parado en raiz del repo:

```powershell
docker compose -f docker-compose.prod.yml ps
```

### 1) Backup antes del apply
```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
docker compose -f docker-compose.prod.yml exec -T postgres sh -lc `
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' `
  > ".\\output\\backup_pre_0012_$ts.sql"
```

### 2) Ver migraciones pendientes
```powershell
docker compose -f docker-compose.prod.yml exec api python manage.py showmigrations service
```

### 3) Aplicar migracion
```powershell
docker compose -f docker-compose.prod.yml exec api `
  python manage.py migrate service 0012_payment_account_invoice_rules --noinput
```

Si queres dejar todo al dia:
```powershell
docker compose -f docker-compose.prod.yml exec api python manage.py migrate --noinput
```

## Verificacion tecnica post-apply
```powershell
docker compose -f docker-compose.prod.yml exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name='retail_payment_accounts'
  AND column_name IN ('price_modifier_pct','default_arca_account_id')
ORDER BY column_name;
"'
```

```powershell
docker compose -f docker-compose.prod.yml exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT code, payment_method, price_modifier_pct, default_arca_account_id
FROM retail_payment_accounts
ORDER BY sort_order, id;
"'
```

Esperado:
- `cash` con `price_modifier_pct = -10`
- `credit` con `price_modifier_pct = 10`
- resto en `0` (salvo cambios manuales)
- `debit/transfer/credit` con `default_arca_account_id` seteado si existe cuenta ARCA activa

## Verificacion funcional minima
1. Ir a `Config > Cuentas de cobro` y confirmar que aparecen:
- `% recargo/descuento`
- `Cuenta ARCA por defecto`
2. Cotizar una venta simple y una mixta en POS.
3. Validar que el desglose de pagos muestre `base`, `%` y `final`.
4. Confirmar que usuario no admin no pueda override de facturacion.
5. Confirmar que admin si pueda forzar `Cuenta A / Cuenta B / No facturar`.

## Contingencia
Este cambio es aditivo en esquema (nuevas columnas + datos).  
Si hay incidente funcional:
1. Mantener esquema aplicado.
2. Ajustar configuracion desde `Config > Cuentas de cobro`:
- poner `%` en `0`
- dejar `default_arca_account_id = NULL` para no facturar por default
3. Si fuera necesario rollback de codigo, volver a la version anterior de app sin revertir columnas.

## Checklist de cierre
- [ ] Backup pre-migracion generado
- [ ] `migrate` ejecutado sin error
- [ ] Columnas nuevas visibles
- [ ] Backfill validado
- [ ] Prueba POS simple OK
- [ ] Prueba POS mixta OK
- [ ] Override admin/no-admin validado
