"""Permission catalog and role defaults for retail cutover."""

from copy import deepcopy


PERMISSION_CATALOG = [
    {'code': 'page.pos', 'label': 'Ver POS', 'type': 'page', 'group': 'Paginas'},
    {'code': 'page.productos', 'label': 'Ver productos y variantes', 'type': 'page', 'group': 'Paginas'},
    {'code': 'page.compras', 'label': 'Ver compras', 'type': 'page', 'group': 'Paginas'},
    {'code': 'page.ventas', 'label': 'Ver ventas y devoluciones', 'type': 'page', 'group': 'Paginas'},
    {'code': 'page.reportes', 'label': 'Ver reportes', 'type': 'page', 'group': 'Paginas'},
    {'code': 'page.online', 'label': 'Ver integracion online', 'type': 'page', 'group': 'Paginas'},
    {'code': 'page.config', 'label': 'Ver configuracion', 'type': 'page', 'group': 'Paginas'},
    {'code': 'action.ventas.override_precio', 'label': 'Override manual de precio', 'type': 'action', 'group': 'Ventas'},
    {'code': 'action.ventas.anular', 'label': 'Anular venta', 'type': 'action', 'group': 'Ventas'},
    {'code': 'action.ventas.devolver', 'label': 'Registrar devolucion', 'type': 'action', 'group': 'Ventas'},
    {'code': 'action.ventas.devolver.override_garantia', 'label': 'Override devolucion fuera de garantia', 'type': 'action', 'group': 'Ventas'},
    {'code': 'action.facturacion.emitir', 'label': 'Emitir factura', 'type': 'action', 'group': 'Facturacion'},
    {'code': 'action.facturacion.nota_credito', 'label': 'Emitir nota de credito', 'type': 'action', 'group': 'Facturacion'},
    {'code': 'action.online.sync', 'label': 'Sincronizar Tienda Nube', 'type': 'action', 'group': 'Online'},
    {'code': 'action.reportes.ver_costos', 'label': 'Ver costos y rentabilidad', 'type': 'action', 'group': 'Reportes'},
    {'code': 'action.config.editar', 'label': 'Editar configuracion y permisos', 'type': 'action', 'group': 'Configuracion'},
]

PERMISSION_CODES = [item['code'] for item in PERMISSION_CATALOG]
PERMISSION_CODES_SET = set(PERMISSION_CODES)


ROLE_DEFAULTS = {
    'admin': {code: True for code in PERMISSION_CODES},
    'empleado': {
        'page.pos': True,
        'page.productos': True,
        'page.compras': False,
        'page.ventas': True,
        'page.reportes': False,
        'page.online': False,
        'page.config': False,
        'action.ventas.override_precio': False,
        'action.ventas.anular': True,
        'action.ventas.devolver': True,
        'action.ventas.devolver.override_garantia': False,
        'action.facturacion.emitir': True,
        'action.facturacion.nota_credito': False,
        'action.online.sync': False,
        'action.reportes.ver_costos': False,
        'action.config.editar': False,
    },
}


def normalize_role(role):
    return (role or '').strip().lower()


def get_catalog():
    return deepcopy(PERMISSION_CATALOG)


def get_role_defaults(role):
    role_key = normalize_role(role)
    base = ROLE_DEFAULTS.get(role_key)
    if base is None:
        return {code: False for code in PERMISSION_CODES}
    return deepcopy(base)
