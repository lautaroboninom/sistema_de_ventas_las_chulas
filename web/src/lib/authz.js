// web/src/lib/authz.js
// Helpers de autorizacin (RBAC) centralizados.


export const ROLES = {
  JEFE: "jefe",
  JEFE_VEEDOR: "jefe_veedor",
  ADMIN: "admin",
  RECEPCION: "recepcion",
  TECNICO: "tecnico",
};

export const normalizeRole = (r) => (r ?? "").toString().trim().toLowerCase();
export const hasAnyRole = (user, roles) => roles.includes(normalizeRole(user?.rol));

// Jefe/Jefe_veedor pueden actuar como tcnico
export const canActAsTech = (user) =>
  [ROLES.TECNICO, ROLES.JEFE, ROLES.JEFE_VEEDOR].includes(normalizeRole(user?.rol));

// Quines pueden liberar (imprimir orden de salida)
export const canRelease = (user) =>
  [ROLES.JEFE, ROLES.JEFE_VEEDOR, ROLES.ADMIN].includes(normalizeRole(user?.rol));

// (Opcional) helpers por rol, por si los quers en otras pantallas
export const isJefe        = (u) => normalizeRole(u?.rol) === ROLES.JEFE;
export const isJefeVeedor  = (u) => normalizeRole(u?.rol) === ROLES.JEFE_VEEDOR;
export const isAdmin       = (u) => normalizeRole(u?.rol) === ROLES.ADMIN;
export const isRecepcion   = (u) => normalizeRole(u?.rol) === ROLES.RECEPCION;
export const isTecnico     = (u) => normalizeRole(u?.rol) === ROLES.TECNICO;

