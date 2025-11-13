// web/src/lib/constants.js
// Catlogos/constantes de dominio (nica fuente de verdad).

// =========================
// Resolucin de reparacin
// =========================
export const RESOLUCION = {
  REPARADO: "reparado",
  NO_REPARADO: "no_reparado",
  NO_SE_ENCONTRO_FALLA: "no_se_encontro_falla",
  PRESUPUESTO_RECHAZADO: "presupuesto_rechazado",
  CAMBIO: "cambio",
};

export const RESOLUCION_LABELS = {
  [RESOLUCION.REPARADO]: "Reparado",
  [RESOLUCION.NO_REPARADO]: "No reparado",
  [RESOLUCION.NO_SE_ENCONTRO_FALLA]: "No se encontró falla",
  [RESOLUCION.PRESUPUESTO_RECHAZADO]: "Presupuesto rechazado",
  [RESOLUCION.CAMBIO]: "Cambio",
};

// til para armar selects sin repetir arrays en cada pantalla
export const RESOLUCION_OPTIONS = Object.entries(RESOLUCION_LABELS).map(
  ([value, label]) => ({ value, label })
);

export const resolutionLabel = (value) =>
  RESOLUCION_LABELS[value] ?? String(value ?? "");

// Estados operativos (flujo de trabajo)
export const ESTADO = {
  DIAGNOSTICADO: "diagnosticado",
  REPARAR: "reparar",
  REPARADO: "reparado",
  LIBERADO: "liberado",
  ENTREGADO: "entregado",
  ALQUILADO: "alquilado",
};

export const ESTADO_LABELS = {
  [ESTADO.DIAGNOSTICADO]: "Diagnosticado",
  [ESTADO.REPARAR]: "Reparar",
  [ESTADO.REPARADO]: "Reparado",
  [ESTADO.LIBERADO]: "Liberado",
  [ESTADO.ENTREGADO]: "Entregado",
  [ESTADO.ALQUILADO]: "Alquilado",
};

export const ESTADO_OPTIONS = Object.entries(ESTADO_LABELS).map(
  ([value, label]) => ({ value, label })
);

// (opcional) por si quers habilitar siguiente paso en UI
export const NEXT_STATE = {
  [ESTADO.DIAGNOSTICADO]: ESTADO.REPARAR,
  [ESTADO.REPARAR]: ESTADO.REPARADO,
  [ESTADO.REPARADO]: ESTADO.LIBERADO,
  [ESTADO.LIBERADO]: ESTADO.ENTREGADO,
};


// =========================
// Motivos de ingreso
// =========================
export const MOTIVO = {
  REPARACION: "reparación",
  BAJA_ALQUILER: "baja alquiler",
  REPARACION_ALQUILER: "reparación alquiler",
  SERVICE_PREVENTIVO: "service preventivo",
  URGENTE_CONTROL: "urgente control",
  DEVOLUCION_DEMO: "devolución demo",
  OTROS: "otros",
};

export const MOTIVO_LABELS = {
  [MOTIVO.REPARACION]: "Reparación",
  [MOTIVO.BAJA_ALQUILER]: "Baja alquiler",
  [MOTIVO.REPARACION_ALQUILER]: "Reparación alquiler",
  [MOTIVO.SERVICE_PREVENTIVO]: "Service preventivo",
  [MOTIVO.URGENTE_CONTROL]: "Urgente control",
  [MOTIVO.DEVOLUCION_DEMO]: "Devolución demo",
  [MOTIVO.OTROS]: "Otros",
};

export const MOTIVO_OPTIONS = Object.entries(MOTIVO_LABELS).map(
  ([value, label]) => ({ value, label })
);

export const motivoLabel = (value) =>
  MOTIVO_LABELS[value] ?? String(value ?? "");

// =========================
// Métricas - Fecha mínima de corte (unificada)
// =========================
// Solo considerar ingresos con fecha_ingreso >= METRICAS_DESDE_MIN (inclusive)
export const METRICAS_DESDE_MIN = '2025-06-26';
export const clampDesdeMin = (s) => {
  if (!s) return METRICAS_DESDE_MIN;
  return s < METRICAS_DESDE_MIN ? METRICAS_DESDE_MIN : s;
};
