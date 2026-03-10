import { normalizeRole } from './authz';

export const PERMISSION_CODES = {
  PAGE_POS: 'page.pos',
  PAGE_PRODUCTOS: 'page.productos',
  PAGE_COMPRAS: 'page.compras',
  PAGE_VENTAS: 'page.ventas',
  PAGE_PROMOCIONES: 'page.promociones',
  PAGE_REPORTES: 'page.reportes',
  PAGE_ONLINE: 'page.online',
  PAGE_CONFIG: 'page.config',
  ACTION_PROMOCIONES_EDITAR: 'action.promociones.editar',
  ACTION_VENTAS_OVERRIDE_PRECIO: 'action.ventas.override_precio',
  ACTION_VENTAS_ANULAR: 'action.ventas.anular',
  ACTION_VENTAS_DEVOLVER: 'action.ventas.devolver',
  ACTION_VENTAS_CAMBIAR: 'action.ventas.cambiar',
  ACTION_VENTAS_DEVOLVER_OVERRIDE_GARANTIA: 'action.ventas.devolver.override_garantia',
  ACTION_FACTURACION_EMITIR: 'action.facturacion.emitir',
  ACTION_FACTURACION_NOTA_CREDITO: 'action.facturacion.nota_credito',
  ACTION_ONLINE_SYNC: 'action.online.sync',
  ACTION_REPORTES_VER_COSTOS: 'action.reportes.ver_costos',
  ACTION_CONFIG_EDITAR: 'action.config.editar',
};

const ROLE_DEFAULT_PERMISSIONS = {
  admin: new Set(Object.values(PERMISSION_CODES)),
  empleado: new Set([
    PERMISSION_CODES.PAGE_POS,
    PERMISSION_CODES.PAGE_PRODUCTOS,
    PERMISSION_CODES.PAGE_VENTAS,
    PERMISSION_CODES.ACTION_VENTAS_ANULAR,
    PERMISSION_CODES.ACTION_VENTAS_DEVOLVER,
    PERMISSION_CODES.ACTION_VENTAS_CAMBIAR,
    PERMISSION_CODES.ACTION_FACTURACION_EMITIR,
  ]),
};

export function normalizePermissionsMap(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
  const out = {};
  Object.entries(raw).forEach(([code, value]) => {
    out[String(code)] = !!value;
  });
  return out;
}

function hasRoleFallbackPermission(user, code) {
  const role = normalizeRole(user?.rol);
  const set = ROLE_DEFAULT_PERMISSIONS[role];
  if (!set) return false;
  return set.has(code);
}

export function can(user, permissionCode) {
  if (!permissionCode) return true;
  if (!user) return false;
  const map = normalizePermissionsMap(user.permissions);
  if (Object.prototype.hasOwnProperty.call(map, permissionCode)) {
    return !!map[permissionCode];
  }
  return hasRoleFallbackPermission(user, permissionCode);
}

export function canAny(user, permissionCodes) {
  const list = Array.isArray(permissionCodes) ? permissionCodes : [permissionCodes];
  if (!list.length) return true;
  return list.some((code) => can(user, code));
}

export function canAll(user, permissionCodes) {
  const list = Array.isArray(permissionCodes) ? permissionCodes : [permissionCodes];
  if (!list.length) return true;
  return list.every((code) => can(user, code));
}
