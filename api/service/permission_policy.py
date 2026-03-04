"""Request -> permission policy matrix for retail cutover."""


VIEW_PERMISSION_MATRIX = {
    # Usuarios / permisos
    'UsuariosView': {'GET': 'page.config', 'POST': 'action.config.editar'},
    'UsuarioActivoView': {'PATCH': 'action.config.editar'},
    'UsuarioResetPassView': {'PATCH': 'action.config.editar'},
    'UsuarioRolePermView': {'PATCH': 'action.config.editar'},
    'UsuarioDeleteView': {'DELETE': 'action.config.editar'},
    'CatalogoPermisosView': {'GET': 'page.config'},
    'UsuarioPermisosView': {'GET': 'page.config', 'PUT': 'action.config.editar'},
    'UsuarioPermisosResetView': {'POST': 'action.config.editar'},

    # Catalogo retail
    'RetailProductosView': {'GET': 'page.productos', 'POST': 'action.config.editar'},
    'RetailProductoDetailView': {'PATCH': 'action.config.editar'},
    'RetailAtributosView': {'GET': 'page.productos', 'POST': 'action.config.editar'},
    'RetailVariantesView': {'GET': 'page.productos', 'POST': 'action.config.editar'},
    'RetailVarianteDetailView': {'PATCH': 'action.config.editar'},
    'RetailVarianteEscanearView': {'GET': 'page.pos'},

    # Compras / caja
    'RetailComprasView': {'POST': 'page.compras'},
    'RetailCompraDetailView': {'GET': 'page.compras'},
    'RetailCajaAperturaView': {'POST': 'page.pos'},
    'RetailCajaCierreView': {'POST': 'page.pos'},
    'RetailCajaActualView': {'GET': 'page.pos'},
    'RetailCajaCuentasView': {'GET': 'page.pos'},
    'RetailCajaDetailView': {'GET': 'page.pos'},
    'RetailVentasView': {'GET': 'page.ventas'},
    'RetailVentaDetailView': {'GET': 'page.ventas'},

    # Ventas / devoluciones / facturacion
    'RetailVentasCotizarView': {'POST': 'page.pos'},
    'RetailVentasConfirmarView': {'POST': 'page.pos'},
    'RetailVentaAnularView': {'POST': 'action.ventas.anular'},
    'RetailVentaDevolverView': {'POST': 'action.ventas.devolver'},
    'RetailGarantiaTicketView': {'GET': 'page.ventas'},
    'RetailGarantiasActivasView': {'GET': 'page.ventas'},
    'RetailFacturacionEmitirView': {'POST': 'action.facturacion.emitir'},
    'RetailFacturacionDetailView': {'GET': 'page.ventas'},
    'RetailFacturacionNotaCreditoView': {'POST': 'action.facturacion.nota_credito'},
    'RetailConfigSettingsView': {'GET': 'page.config', 'PUT': 'action.config.editar'},
    'RetailConfigPageSettingsView': {'GET': 'page.pos', 'PUT': 'action.config.editar'},
    'RetailConfigPaymentAccountsView': {'GET': 'page.config', 'PUT': 'action.config.editar'},

    # Online
    'RetailOnlineSyncCatalogoView': {'POST': 'action.online.sync'},
    'RetailOnlineSyncStockView': {'POST': 'action.online.sync'},

    # Reportes
    'RetailReporteMasVendidosView': {'GET': 'page.reportes'},
    'RetailReporteTallesColoresView': {'GET': 'page.reportes'},
    'RetailReporteBajoStockView': {'GET': 'page.reportes'},
    'RetailReporteRentabilidadView': {'GET': 'action.reportes.ver_costos'},
    'RetailReporteVentasPorMedioView': {'GET': 'page.reportes'},
    'RetailReporteCierreCajaView': {'GET': 'page.reportes'},
    'RetailReporteDevolucionesView': {'GET': 'page.reportes'},
}


def resolve_permission_code_for_request(request):
    rm = getattr(request, 'resolver_match', None)
    func = getattr(rm, 'func', None)
    view_class = getattr(func, 'view_class', None)
    if view_class is None:
        return None
    class_name = getattr(view_class, '__name__', None)
    if not class_name:
        return None
    method = (getattr(request, 'method', '') or '').upper()
    class_map = VIEW_PERMISSION_MATRIX.get(class_name, {})
    return class_map.get(method)




