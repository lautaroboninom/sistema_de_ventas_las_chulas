CREATE OR REPLACE FUNCTION retail_normalized_option_key(raw TEXT)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
  txt TEXT;
BEGIN
  txt := COALESCE(raw, '');
  txt := regexp_replace(trim(txt), '\s+', ' ', 'g');
  txt := lower(txt);
  txt := translate(
    txt,
    'áàäâãéèëêíìïîóòöôõúùüûñçÁÀÄÂÃÉÈËÊÍÌÏÎÓÒÖÔÕÚÙÜÛÑÇ',
    'aaaaaeeeeiiiiooooouuuuncAAAAAEEEEIIIIOOOOOUUUUNC'
  );
  RETURN NULLIF(txt, '');
END $$;

CREATE TABLE IF NOT EXISTS retail_variant_attribute_values (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  attribute_id   BIGINT NOT NULL REFERENCES retail_variant_attributes(id) ON DELETE CASCADE,
  value_label    TEXT NOT NULL,
  value_key      TEXT NOT NULL,
  active         BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_variant_attribute_values_key UNIQUE (attribute_id, value_key)
);

DROP TRIGGER IF EXISTS trg_retail_variant_attribute_values_updated_at ON retail_variant_attribute_values;
CREATE TRIGGER trg_retail_variant_attribute_values_updated_at
BEFORE UPDATE ON retail_variant_attribute_values
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE retail_variant_option_values
  ADD COLUMN IF NOT EXISTS attribute_value_id BIGINT REFERENCES retail_variant_attribute_values(id) ON DELETE SET NULL;

ALTER TABLE retail_variant_option_values
  ADD COLUMN IF NOT EXISTS option_value_key TEXT;

WITH attr_rank AS (
  SELECT id,
         retail_normalized_option_key(COALESCE(code, name)) AS attr_key,
         ROW_NUMBER() OVER (
           PARTITION BY retail_normalized_option_key(COALESCE(code, name))
           ORDER BY active DESC, id
         ) AS rn
  FROM retail_variant_attributes
  WHERE retail_normalized_option_key(COALESCE(code, name)) IS NOT NULL
)
UPDATE retail_variant_attributes a
SET active = FALSE
FROM attr_rank r
WHERE a.id = r.id
  AND r.rn > 1;

WITH value_counts AS (
  SELECT attribute_id,
         retail_normalized_option_key(option_value) AS value_key,
         option_value AS value_label,
         COUNT(*)::int AS usage_count
  FROM retail_variant_option_values
  WHERE retail_normalized_option_key(option_value) IS NOT NULL
  GROUP BY attribute_id, retail_normalized_option_key(option_value), option_value
),
value_rank AS (
  SELECT attribute_id,
         value_key,
         value_label,
         ROW_NUMBER() OVER (
           PARTITION BY attribute_id, value_key
           ORDER BY usage_count DESC, length(value_label), value_label
         ) AS rn
  FROM value_counts
)
INSERT INTO retail_variant_attribute_values(attribute_id, value_label, value_key, active)
SELECT attribute_id, value_label, value_key, TRUE
FROM value_rank
WHERE rn = 1
ON CONFLICT (attribute_id, value_key) DO NOTHING;

UPDATE retail_variant_option_values ov
SET option_value_key = retail_normalized_option_key(ov.option_value),
    attribute_value_id = av.id,
    option_value = COALESCE(av.value_label, ov.option_value)
FROM retail_variant_attribute_values av
WHERE av.attribute_id = ov.attribute_id
  AND av.value_key = retail_normalized_option_key(ov.option_value);

CREATE INDEX IF NOT EXISTS idx_retail_variant_attribute_values_attr_active
ON retail_variant_attribute_values(attribute_id, active, value_label);

CREATE INDEX IF NOT EXISTS idx_retail_variant_option_values_value_id
ON retail_variant_option_values(attribute_value_id);

CREATE INDEX IF NOT EXISTS idx_retail_variant_option_values_key
ON retail_variant_option_values(attribute_id, option_value_key);
