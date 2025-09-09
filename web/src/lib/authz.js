// web/src/lib/authz.js
// Helpers de autorización (RBAC) centralizados.


export const ROLES = {
  JEFE: "jefe",
  JEFE_VEEDOR: "jefe_veedor",
  ADMIN: "admin",
  RECEPCION: "recepcion",
  TECNICO: "tecnico",
};

export const normalizeRole = (r) => (r ?? "").toString().trim().toLowerCase();
export const hasAnyRole = (user, roles) => roles.includes(normalizeRole(user?.rol));

// Jefe/Jefe_veedor pueden actuar como técnico
export const canActAsTech = (user) =>
  [ROLES.TECNICO, ROLES.JEFE, ROLES.JEFE_VEEDOR].includes(normalizeRole(user?.rol));

// Quiénes pueden liberar (imprimir orden de salida)
export const canRelease = (user) =>
  [ROLES.JEFE, ROLES.JEFE_VEEDOR, ROLES.ADMIN].includes(normalizeRole(user?.rol));

// (Opcional) helpers por rol, por si los querés en otras pantallas
export const isJefe        = (u) => normalizeRole(u?.rol) === ROLES.JEFE;
export const isJefeVeedor  = (u) => normalizeRole(u?.rol) === ROLES.JEFE_VEEDOR;
export const isAdmin       = (u) => normalizeRole(u?.rol) === ROLES.ADMIN;
export const isRecepcion   = (u) => normalizeRole(u?.rol) === ROLES.RECEPCION;
export const isTecnico     = (u) => normalizeRole(u?.rol) === ROLES.TECNICO;
