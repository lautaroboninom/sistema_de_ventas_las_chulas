-- Validación post-migración (PostgreSQL)
-- Objetivo: verificar consistencia entre devices.numero_interno, devices.n_de_control y el snapshot del último ingreso (ingresos.faja_garantia)

\echo '==[1/8] Totales de devices'
SELECT
  COUNT(*) AS devices_total,
  COUNT(NULLIF(TRIM(numero_interno), '')) AS numint_no_vacio,
  COUNT(NULLIF(TRIM(n_de_control), '')) AS ndc_no_vacio
FROM devices;

\echo '==[2/8] Duplicados por numero_interno normalizado (MG|NM|NV|CE ####)'
WITH norm AS (
  SELECT id,
         UPPER(REGEXP_REPLACE(numero_interno,
               '^(MG|NM|NV|CE)\s*(\d{1,4})$', '\\1 ' || LPAD('\\2',4,'0'))) AS num_norm
    FROM devices
   WHERE numero_interno ~* '^(MG|NM|NV|CE)\s*\d{1,4}$'
)
SELECT num_norm, COUNT(*) AS cnt, ARRAY_AGG(id ORDER BY id) AS device_ids
  FROM norm
 GROUP BY 1
HAVING COUNT(*) > 1
 ORDER BY cnt DESC, num_norm
 LIMIT 50;

\echo '==[3/8] Distribución por prefijo de numero_interno'
SELECT prefijo, COUNT(*) AS cant
FROM (
  SELECT CASE
           WHEN numero_interno ~* '^MG' THEN 'MG'
           WHEN numero_interno ~* '^NM' THEN 'NM'
           WHEN numero_interno ~* '^NV' THEN 'NV'
           WHEN numero_interno ~* '^CE' THEN 'CE'
           WHEN NULLIF(TRIM(numero_interno),'') IS NULL THEN 'VACIO'
           ELSE 'OTRO'
         END AS prefijo
    FROM devices
) t
GROUP BY prefijo
ORDER BY prefijo;

\echo '==[4/8] Snapshot esperado de n_de_control (último ingresos.faja_garantia) vs valor en devices'
WITH last_i AS (
  SELECT DISTINCT ON (t.device_id)
         t.device_id,
         NULLIF(t.faja_garantia,'') AS faja
    FROM ingresos t
   ORDER BY t.device_id, COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
)
SELECT COUNT(*) AS mismatches
  FROM devices d
  JOIN last_i li ON li.device_id = d.id
 WHERE COALESCE(NULLIF(d.n_de_control,''), '') <> COALESCE(li.faja, '');

\echo '==[5/8] Muestras de mismatch n_de_control (máx 50)'
WITH last_i AS (
  SELECT DISTINCT ON (t.device_id)
         t.device_id,
         NULLIF(t.faja_garantia,'') AS faja,
         COALESCE(t.fecha_ingreso, t.fecha_creacion) AS fecha_ref,
         t.id AS ingreso_id
    FROM ingresos t
   ORDER BY t.device_id, COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
)
SELECT d.id AS device_id, d.numero_interno, d.n_de_control, li.faja AS faja_last, li.fecha_ref, li.ingreso_id
  FROM devices d
  JOIN last_i li ON li.device_id = d.id
 WHERE COALESCE(NULLIF(d.n_de_control,''), '') <> COALESCE(li.faja, '')
 ORDER BY li.fecha_ref DESC, d.id DESC
 LIMIT 50;

\echo '==[6/8] Devices con ingresos y n_de_control vacío pero faja_garantia del último ingreso no vacía'
WITH last_i AS (
  SELECT DISTINCT ON (t.device_id)
         t.device_id,
         NULLIF(t.faja_garantia,'') AS faja
    FROM ingresos t
   ORDER BY t.device_id, COALESCE(t.fecha_ingreso, t.fecha_creacion) DESC, t.id DESC
)
SELECT COUNT(*) AS faltantes
  FROM devices d
  JOIN last_i li ON li.device_id = d.id
 WHERE NULLIF(TRIM(li.faja),'') IS NOT NULL
   AND NULLIF(TRIM(d.n_de_control),'') IS NULL;

\echo '==[7/8] Devices sin ingresos (para información)'
SELECT COUNT(*) AS sin_ingresos
FROM devices d
LEFT JOIN ingresos t ON t.device_id = d.id
WHERE t.id IS NULL;

\echo '==[8/8] Top 20 numero_interno no normalizados (que parecen MG/NM/NV/CE pero con formato raro)'
SELECT id, numero_interno
FROM devices d
WHERE numero_interno ~* '^(MG|NM|NV|CE)'
  AND NOT (numero_interno ~* '^(MG|NM|NV|CE)\s*\d{1,4}$')
ORDER BY id DESC
LIMIT 20;

