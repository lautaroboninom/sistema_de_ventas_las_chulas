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
    'RetailAtributoValoresView': {'GET': 'page.productos'},
    'RetailAtributoDetailView': {'PATCH': 'action.config.editar', 'DELETE': 'action.config.editar'},
    'RetailVariantesView': {'GET': 'page.productos', 'POST': 'action.config.editar'},
    'RetailVarianteDetailView': {'PATCH': 'action.config.editar', 'DELETE': 'action.config.editar'},
    'RetailVarianteEscanearView': {'GET': 'page.pos'},
    'RetailVarianteBarcodesView': {'GET': 'page.productos'},
    'RetailVarianteBarcodeGenerateView': {'POST': 'action.config.editar'},
    'RetailVarianteBarcodeAssociateView': {'POST': 'action.config.editar'},
    'RetailVarianteBarcodePrimaryView': {'POST': 'action.config.editar'},
    'RetailVarianteBarcodeLabelsPdfView': {'GET': ['page.productos', 'page.compras']},

    # Compras / caja
    'RetailComprasConfigView': {'GET': 'page.compras'},
    'RetailComprasProveedoresView': {'GET': 'page.compras'},
    'RetailComprasView': {'POST': 'page.compras'},
    'RetailCompraDetailView': {'GET': 'page.compras'},
    'RetailCajaAperturaView': {'POST': 'page.pos'},
    'RetailCajaCierreView': {'POST': 'page.pos'},
    'RetailCajaCierreAsistidoView': {'POST': 'action.caja.cierre_asistido'},
    'RetailCajaActualView': {'GET': 'page.pos'},
    'RetailCajaCuentasView': {'GET': 'page.pos'},
    'RetailCajaDetailView': {'GET': 'page.pos'},
    'RetailOperacionPendientesView': {'GET': 'page.pos'},
    'RetailOperacionIncidenciaResolverView': {'POST': 'action.caja.cierre_asistido'},
    'RetailVentasView': {'GET': 'page.ventas'},
    'RetailVentaDetailView': {'GET': 'page.ventas'},
    'RetailPromocionesView': {'GET': 'page.promociones', 'POST': 'action.promociones.editar'},
    'RetailPromocionDetailView': {'GET': 'page.promociones', 'PATCH': 'action.promociones.editar', 'PUT': 'action.promociones.editar'},

    # Ventas / devoluciones / facturacion
    'RetailVentasCotizarView': {'POST': 'page.pos'},
    'RetailVentasConfirmarView': {'POST': 'page.pos'},
    'RetailVentaAnularView': {'POST': 'action.ventas.anular'},
    'RetailVentaDevolverView': {'POST': 'action.ventas.devolver'},
    'RetailVentaCambiarView': {'POST': 'action.ventas.cambiar'},
    'RetailVentaOperacionSolicitudView': {'POST': 'page.ventas'},
    'RetailStoreCreditsView': {'GET': 'page.pos'},
    'RetailStoreCreditConsumeView': {'POST': 'page.pos'},
    'RetailGarantiaTicketView': {'GET': 'page.ventas'},
    'RetailGarantiasActivasView': {'GET': 'page.ventas'},
    'RetailInventarioConteosView': {'GET': 'action.inventario.conteo', 'POST': 'action.inventario.conteo'},
    'RetailInventarioConteoDetailView': {'GET': 'action.inventario.conteo'},
    'RetailInventarioConteoCerrarView': {'POST': 'action.inventario.conteo'},
    'RetailReposicionSugeridaView': {'GET': 'page.compras'},
    'RetailFacturacionEmitirView': {'POST': 'action.facturacion.emitir'},
    'RetailFacturacionDetailView': {'GET': 'page.ventas'},
    'RetailFacturacionNotaCreditoView': {'POST': 'action.facturacion.nota_credito'},
    'RetailConfigSettingsView': {
        'GET': 'page.config',
        'PUT': ['action.config.editar', 'action.config.online_credentials'],
    },
    'RetailConfigPageSettingsView': {'GET': 'page.pos', 'PUT': 'action.config.editar'},
    'RetailConfigPaymentAccountsView': {'GET': 'page.config', 'PUT': 'action.config.editar'},

    # Online
    'RetailOnlineSyncCatalogoView': {'POST': 'action.online.sync'},
    'RetailOnlineSyncStockView': {'POST': 'action.online.sync'},
    'RetailOnlineFailedJobsSummaryView': {'GET': 'action.online.sync'},
    'RetailOnlineRetryFailedJobsView': {'POST': 'action.online.sync'},
    'RetailOnlineJobsProcessView': {'POST': 'action.online.sync'},
    'RetailOnlineOAuthReauthorizeUrlView': {'POST': 'action.config.online_credentials'},
    'RetailOnlineOAuthApplyTokenView': {'POST': 'action.config.online_credentials'},

    # Reportes
    'RetailReporteResumenComercialView': {'GET': 'page.reportes'},
    'RetailReporteAnalisisProductosView': {'GET': 'action.reportes.ver_costos'},
    'RetailReporteAnalisisProveedoresView': {'GET': 'action.reportes.ver_costos'},
    'RetailReporteMasVendidosView': {'GET': 'page.reportes'},
    'RetailReporteTallesColoresView': {'GET': 'page.reportes'},
    'RetailReporteBajoStockView': {'GET': 'page.reportes'},
    'RetailReporteRentabilidadView': {'GET': 'action.reportes.ver_costos'},
    'RetailReporteVentasPorMedioView': {'GET': 'page.reportes'},
    'RetailReporteCierreCajaView': {'GET': 'page.reportes'},
    'RetailReporteDevolucionesView': {'GET': 'page.reportes'},
    'RetailDashboardOperativoView': {'GET': 'page.reportes'},
    'RetailAlertasView': {'GET': 'page.reportes'},
    'RetailAlertaAckView': {'POST': 'action.alertas.gestionar'},
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




