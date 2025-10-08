-- One-off merge for duplicated customer "OXICASTHOMECARE".
-- Keep customer id = 157, move references from id = 1591, then delete 1591.
-- Safe to run multiple times: updates are idempotent; DELETE will be a no-op if 1591 no longer exists.

BEGIN;

-- Optional: basic sanity checks (uncomment to inspect before running updates)
-- SELECT id, cod_empresa, razon_social, telefono, telefono_2, email
--   FROM customers WHERE id IN (157, 1591);
-- SELECT COUNT(*) AS dev_157 FROM devices WHERE customer_id = 157;
-- SELECT COUNT(*) AS dev_1591 FROM devices WHERE customer_id = 1591;

-- Lock minimally to avoid concurrent writes while moving refs
LOCK TABLE devices IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE customers IN ROW EXCLUSIVE MODE;

-- If the kept record (157) has empty/null fields, complete them with data from 1591
UPDATE customers t
SET
  cod_empresa = COALESCE(NULLIF(t.cod_empresa, ''), NULLIF(s.cod_empresa, '')),
  telefono    = COALESCE(NULLIF(t.telefono, ''),    NULLIF(s.telefono, '')),
  telefono_2  = COALESCE(NULLIF(t.telefono_2, ''),  NULLIF(s.telefono_2, '')),
  email       = COALESCE(NULLIF(t.email, ''),       NULLIF(s.email, ''))
FROM customers s
WHERE t.id = 157 AND s.id = 1591;

-- Repoint all devices to the kept customer id
UPDATE devices
   SET customer_id = 157
 WHERE customer_id = 1591;

-- Finally remove the duplicate customer (will fail only if some other FK appears)
DELETE FROM customers WHERE id = 1591;

COMMIT;

