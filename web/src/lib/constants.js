// web/src/lib/constants.js
// Catálogos/constantes de dominio (única fuente de verdad).

// =========================
// Resolución de reparación
// =========================
export const RESOLUCION = {
  REPARADO: "reparado",
  NO_REPARADO: "no_reparado",
  NO_SE_ENCONTRO_FALLA: "no_se_encontro_falla",
  PRESUPUESTO_RECHAZADO: "presupuesto_rechazado",
};

export const RESOLUCION_LABELS = {
  [RESOLUCION.REPARADO]: "Reparado",
  [RESOLUCION.NO_REPARADO]: "No reparado",
  [RESOLUCION.NO_SE_ENCONTRO_FALLA]: "No se encontró falla",
  [RESOLUCION.PRESUPUESTO_RECHAZADO]: "Presupuesto rechazado",
};

// Útil para armar selects sin repetir arrays en cada pantalla
export const RESOLUCION_OPTIONS = Object.entries(RESOLUCION_LABELS).map(
  ([value, label]) => ({ value, label })
);

export const resolutionLabel = (value) =>
  RESOLUCION_LABELS[value] ?? String(value ?? "");

// Estados operativos (flujo de trabajo)
export const ESTADO = {
  DIAGNOSTICADO: "diagnosticado",
  EMITIDO: "emitido",
  APROBADO: "aprobado",
  REPARAR: "reparar",
  REPARADO: "reparado",
  LISTO_RETIRO: "listo_retiro",
  ENTREGADO: "entregado",
};

export const ESTADO_LABELS = {
  [ESTADO.DIAGNOSTICADO]: "Diagnosticado",
  [ESTADO.EMITIDO]: "Emitido",
  [ESTADO.APROBADO]: "Aprobado",
  [ESTADO.REPARAR]: "Reparar",
  [ESTADO.REPARADO]: "Reparado",
  [ESTADO.LISTO_RETIRO]: "Listo para retiro",
  [ESTADO.ENTREGADO]: "Entregado",
};

export const ESTADO_OPTIONS = Object.entries(ESTADO_LABELS).map(
  ([value, label]) => ({ value, label })
);

// (opcional) por si querés habilitar “siguiente paso” en UI
export const NEXT_STATE = {
  [ESTADO.DIAGNOSTICADO]: ESTADO.EMITIDO,
  [ESTADO.EMITIDO]: ESTADO.APROBADO,
  [ESTADO.APROBADO]: ESTADO.REPARAR,
  [ESTADO.REPARAR]: ESTADO.REPARADO,
  [ESTADO.REPARADO]: ESTADO.LISTO_RETIRO,
  [ESTADO.LISTO_RETIRO]: ESTADO.ENTREGADO,
};
