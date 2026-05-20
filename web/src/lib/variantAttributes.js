export function attrCode(value) {
  return String(value || '').trim().toLowerCase();
}

export function optionKey(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase();
}

export function valuesForAttr(valuesByCode, code) {
  return valuesByCode?.[attrCode(code)] || [];
}

export function isKnownAttrValue(valuesByCode, code, value) {
  const key = optionKey(value);
  if (!key) return false;
  return valuesForAttr(valuesByCode, code).some(
    (item) => optionKey(item?.value_label) === key || optionKey(item?.value_key) === key,
  );
}

export function normalizeValueError(error) {
  const data = error?.data || {};
  if (data?.code === 'attribute_value_suggestion_required') return data;
  if (data?.detail?.code === 'attribute_value_suggestion_required') return data.detail;
  return null;
}

export function splitValues(raw) {
  return String(raw || '')
    .split(/[,\n;]+/)
    .map((value) => String(value || '').trim())
    .filter(Boolean);
}

export function dedupValues(values) {
  const out = [];
  const seen = new Set();
  (Array.isArray(values) ? values : []).forEach((value) => {
    const clean = String(value || '').trim();
    const key = optionKey(clean);
    if (!clean || seen.has(key)) return;
    seen.add(key);
    out.push(clean);
  });
  return out;
}

export function appendToken(raw, token) {
  const value = String(token || '').trim();
  if (!value) return raw || '';
  const parts = splitValues(raw);
  if (parts.some((item) => optionKey(item) === optionKey(value))) return raw || '';
  return [...parts, value].join(', ');
}
