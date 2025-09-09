// web/src/lib/ui-helpers.js

export const ingresoIdOf = (row) => row?.ingreso_id ?? row?.id;

export const formatOS = (rowOrId, prefix = "OS ") => {
  // Acepta objeto row o un id suelto
  if (rowOrId && typeof rowOrId === "object") {
    const id = ingresoIdOf(rowOrId) ?? 0;
    return rowOrId?.os ?? `${prefix}${String(id).padStart(6, "0")}`;
  }
  const id = Number(rowOrId ?? 0);
  return `${prefix}${String(id).padStart(6, "0")}`;
};

export const formatDateTime = (s, locale = "es-AR") =>
  s ? new Date(s).toLocaleString(locale, { dateStyle: "short", timeStyle: "short" }) : "-";

export const norm = (v) => (v ?? "").toString().toLowerCase().trim();

export const formatMoney = (amount, currency = "ARS", locale = "es-AR") => {
  if (amount == null || isNaN(Number(amount))) return "-";
  try {
    return new Intl.NumberFormat(locale, { style: "currency", currency }).format(Number(amount));
  } catch {
    return new Intl.NumberFormat(locale).format(Number(amount));
  }
};

export const toNum = (v) => (v === "" || v === null || v === undefined ? null : Number(v));
