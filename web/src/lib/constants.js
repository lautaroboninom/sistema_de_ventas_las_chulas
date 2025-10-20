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
};

export const RESOLUCION_LABELS = {
  [RESOLUCION.REPARADO]: "Reparado",
  [RESOLUCION.NO_REPARADO]: "No reparado",
  [RESOLUCION.NO_SE_ENCONTRO_FALLA]: "No se encontr falla",
  [RESOLUCION.PRESUPUESTO_RECHAZADO]: "Presupuesto rechazado",
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


