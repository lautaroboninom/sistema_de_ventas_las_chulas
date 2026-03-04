export const ROLES = {
  ADMIN: 'admin',
  EMPLEADO: 'empleado',
};

export const normalizeRole = (r) => (r ?? '').toString().trim().toLowerCase();
export const hasAnyRole = (user, roles) => roles.includes(normalizeRole(user?.rol));

export const isAdmin = (u) => normalizeRole(u?.rol) === ROLES.ADMIN;
export const isEmpleado = (u) => normalizeRole(u?.rol) === ROLES.EMPLEADO;
