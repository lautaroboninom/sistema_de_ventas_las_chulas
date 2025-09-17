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

export const tipoEquipoOf = (row, fallback = "-") => {
  if (!row) return fallback;
  const candidates = [
    row?.tipo_equipo,
    row?.equipo?.tipo_equipo,
    row?.tipo_equipo_nombre,
    row?.equipo?.tipo_equipo_nombre,
    row?.tipo,
    row?.equipo?.tipo,
    row?.tipoEquipo,
    row?.equipo?.tipoEquipo,
    row?.modelo_tipo,
    row?.equipo?.modelo_tipo,
  ];
  for (const raw of candidates) {
    if (typeof raw === "string") {
      const value = raw.trim();
      if (value) return value;
    }
  }
  return fallback;
};

export const norm = (v) => {
  const s = (v ?? "").toString().toLowerCase().trim();
  try {
    // Remover acentos/diacríticos para comparaciones robustas
    return s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  } catch {
    return s;
  }
};

export const formatMoney = (amount, currency = "ARS", locale = "es-AR") => {
  if (amount == null || isNaN(Number(amount))) return "-";
  try {
    return new Intl.NumberFormat(locale, { style: "currency", currency }).format(Number(amount));
  } catch {
    return new Intl.NumberFormat(locale).format(Number(amount));
  }
};

export const toNum = (v) => (v === "" || v === null || v === undefined ? null : Number(v));
