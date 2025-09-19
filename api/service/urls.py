# service/urls.py
from django.urls import path, include
from .views import (
    # salud / login
    ping, LoginView, LogoutView, SessionView, ForgotPasswordView, ResetPasswordView,

    # flujo ingresos / tÃ©cnico
    MisPendientesView,
    EmitirPresupuestoView, AprobarPresupuestoView, QuotePdfView,
    PendientesPresupuestoView, PresupuestadosView,
    MarcarReparadoView, EntregarIngresoView, GarantiaReparacionCheckView,
    ListosParaRetiroView,

    # listados / generales
    CustomersListView, PendientesGeneralView,
    AprobadosParaRepararView, AprobadosYReparadosView, LiberadosView,
    GeneralEquiposView, GeneralPorClienteView,

    # ingresos nuevos + derivaciÃ³n
    NuevoIngresoView, DerivarIngresoView, DerivacionesPorIngresoView, DevolverDerivacionView,
    

    # catÃ¡logos
    CatalogoMarcasView, CatalogoModelosView, CatalogoUbicacionesView, CatalogoMotivosView,
    CatalogoAccesoriosView, IngresoAccesoriosView, IngresoAccesorioDetailView,
    BuscarAccesorioPorReferenciaView,
    CatalogoMarcasSimpleView, CatalogoTiposEquipoV2View, CatalogoSeriesView, CatalogoVariantesView, CatalogoComposeView, CatalogoMarcaTreeView,

    # administraciÃ³n de usuarios
    UsuariosView, UsuarioActivoView, UsuarioResetPassView, UsuarioRolePermView, UsuarioDeleteView,
    CatalogoRolesView, CerrarReparacionView,

    # clientes / marcas-modelos / proveedores externos
    ClientesView, ClienteDeleteView,
    MarcaDeleteView, ModelosPorMarcaView, ModeloDeleteView,
    ProveedoresExternosView, 

    # detalle de ingreso
    IngresoDetalleView, IngresoAsignarTecnicoView, CatalogoTecnicosView,
    MarcaTecnicoView,MarcaAplicarTecnicoAModelosView,ModeloTecnicoView,
    EquiposDerivadosView,
    IngresoMediaListCreateView, IngresoMediaDetailView, IngresoMediaFileView, IngresoMediaThumbnailView,

    QuoteDetailView, QuoteItemsView, QuoteItemDetailView, QuoteResumenView, AnularPresupuestoView,
    RemitoSalidaPdfView, TiposEquipoView, ModeloTipoEquipoView, IngresoHistorialView,
)

urlpatterns = [
    # salud y login

    path("ping/", ping),
    path("auth/login/", LoginView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("auth/session/", SessionView.as_view()),
    path("auth/forgot/", ForgotPasswordView.as_view()),
    path("auth/reset/", ResetPasswordView.as_view()),

    # tÃ©cnico / ingresos (acciones)
    path("tecnico/mis-pendientes/", MisPendientesView.as_view()),
    path("ingresos/<int:ingreso_id>/reparado/", MarcarReparadoView.as_view()),
    path("ingresos/<int:ingreso_id>/entregar/", EntregarIngresoView.as_view()),

    # presupuestos
    path("quotes/<int:ingreso_id>/emitir/", EmitirPresupuestoView.as_view()),
    path("quotes/<int:ingreso_id>/aprobar/", AprobarPresupuestoView.as_view()),
    path("presupuestos/pendientes/", PendientesPresupuestoView.as_view()),
    path("ingresos/presupuestados/", PresupuestadosView.as_view()),

    # listados operativos
    path("clientes/", CustomersListView.as_view()),
    path("ingresos/pendientes/", PendientesGeneralView.as_view()),
    path("ingresos/aprobados-para-reparar/", AprobadosParaRepararView.as_view()),
    path("ingresos/aprobados-reparados/", AprobadosYReparadosView.as_view()),
    path("ingresos/liberados/", LiberadosView.as_view()),
    path("listos-para-retiro/", ListosParaRetiroView.as_view()),  # alias de compat

    # ALIAS de compatibilidad con el front (si existÃ­an)
    path("ingresos/aprobados/", AprobadosParaRepararView.as_view()),
    path("ingresos/reparados/", AprobadosYReparadosView.as_view()),
    path("ingresos/pendientes-presupuesto/", PendientesPresupuestoView.as_view()),

    # -------- Tabs superiores --------
    path("equipos/", GeneralEquiposView.as_view()),
    path("ingresos/", GeneralEquiposView.as_view()),
    path("clientes/<int:customer_id>/general/", GeneralPorClienteView.as_view()),
    # utilidades
    path("equipos/garantia-reparacion/", GarantiaReparacionCheckView.as_view()),

    # ingresos nuevos / derivaciÃ³n
    path("ingresos/nuevo/", NuevoIngresoView.as_view()),
    path("ingresos/<int:ingreso_id>/derivar/", DerivarIngresoView.as_view()),
    path("ingresos/<int:ingreso_id>/derivaciones/", DerivacionesPorIngresoView.as_view()),
    path("ingresos/<int:ingreso_id>/derivaciones/<int:deriv_id>/devolver/", DevolverDerivacionView.as_view()),

    # catÃ¡logos
    path("catalogos/marcas/", CatalogoMarcasView.as_view()),
    path("catalogos/modelos/", CatalogoModelosView.as_view()),                   # ?marca_id=#
    path("catalogos/ubicaciones/", CatalogoUbicacionesView.as_view()),
    path("catalogos/motivos/", CatalogoMotivosView.as_view()),
    path("catalogos/accesorios/", CatalogoAccesoriosView.as_view()),
    path("catalogos/proveedores-externos/", ProveedoresExternosView.as_view()),
    path("catalogos/proveedores-externos/<int:pid>/", ProveedoresExternosView.as_view()),
    path("catalogo/marcas/", CatalogoMarcasSimpleView.as_view()),
    path("catalogo/tipos/", CatalogoTiposEquipoV2View.as_view()),
    path("catalogo/modelos/", CatalogoSeriesView.as_view()),
    path("catalogo/variantes/", CatalogoVariantesView.as_view()),
    path("catalogo/compose/", CatalogoComposeView.as_view()),
    path("catalogo/marcas/<int:marca_id>/arbol/", CatalogoMarcaTreeView.as_view()),
    path("catalogo/tipos/<int:tipo_id>/", CatalogoTiposEquipoV2View.as_view()),
    path("catalogo/modelos/<int:serie_id>/", CatalogoSeriesView.as_view()),
    path("catalogo/variantes/<int:variante_id>/", CatalogoVariantesView.as_view()),



    # administraciÃ³n de clientes / marcas / modelos
    path("catalogos/clientes/", ClientesView.as_view()),                         # GET/POST
    path("catalogos/clientes/<int:cid>/", ClienteDeleteView.as_view()),          # DELETE
    path("catalogos/marcas/<int:bid>/", MarcaDeleteView.as_view()),              # DELETE
    path("catalogos/marcas/<int:bid>/modelos/", ModelosPorMarcaView.as_view()), # GET/POST
    path("catalogos/modelos/<int:mid>/", ModeloDeleteView.as_view()),            # DELETE

    # detalle de ingreso (GET, PATCH)
    path("ingresos/<int:ingreso_id>/", IngresoDetalleView.as_view()),
    # accesorios por ingreso
    path("ingresos/<int:ingreso_id>/accesorios/", IngresoAccesoriosView.as_view()),
    path("ingresos/<int:ingreso_id>/accesorios/<int:item_id>/", IngresoAccesorioDetailView.as_view()),
    path("accesorios/buscar/", BuscarAccesorioPorReferenciaView.as_view()),
    path("ingresos/<int:ingreso_id>/fotos/", IngresoMediaListCreateView.as_view()),
    path("ingresos/<int:ingreso_id>/fotos/<int:media_id>/", IngresoMediaDetailView.as_view()),
    path("ingresos/<int:ingreso_id>/fotos/<int:media_id>/archivo/", IngresoMediaFileView.as_view()),
    path("ingresos/<int:ingreso_id>/fotos/<int:media_id>/miniatura/", IngresoMediaThumbnailView.as_view()),


    # usuarios (class-based)
    path("usuarios/", UsuariosView.as_view()),                                   # GET lista, POST upsert
    path("usuarios/<int:uid>/activar/", UsuarioActivoView.as_view()),            # PATCH {activo}
    path("usuarios/<int:uid>/reset-pass/", UsuarioResetPassView.as_view()),      # PATCH {password}
    path("usuarios/<int:uid>/roleperm/", UsuarioRolePermView.as_view()),         # PATCH {rol, perm_ingresar}
    path("usuarios/<int:uid>/", UsuarioDeleteView.as_view()),                    # DELETE
    path("catalogos/roles/", CatalogoRolesView.as_view()),
    path("ingresos/<int:ingreso_id>/asignar-tecnico/", IngresoAsignarTecnicoView.as_view()),
    path("catalogos/tecnicos/", CatalogoTecnicosView.as_view()),



    # (si usÃ¡s los endpoints para asignar tÃ©cnico y setear tÃ©cnico de marca/modelo)
    path('catalogos/marcas/<int:bid>/tecnico/', MarcaTecnicoView.as_view()),
    path('catalogos/marcas/<int:bid>/tecnico/aplicar-a-modelos/', MarcaAplicarTecnicoAModelosView.as_view()),
    path('catalogos/marcas/<int:bid>/modelos/<int:mid>/tecnico/', ModeloTecnicoView.as_view()),

    path("ingresos/derivados/", EquiposDerivadosView.as_view()),

    path("quotes/<int:ingreso_id>/", QuoteDetailView.as_view()),  # GET
    path("quotes/<int:ingreso_id>/items/", QuoteItemsView.as_view()),  # POST
    path("quotes/<int:ingreso_id>/items/<int:item_id>/", QuoteItemDetailView.as_view()),  # PATCH/DELETE
    path("quotes/<int:ingreso_id>/resumen/", QuoteResumenView.as_view()),  # PATCH {mano_obra}
    path("quotes/<int:ingreso_id>/pdf/", QuotePdfView.as_view()),
    path("quotes/<int:ingreso_id>/anular/", AnularPresupuestoView.as_view()),

    # tÃ©cnico / ingresos (acciones)


    path("ingresos/<int:ingreso_id>/remito/", RemitoSalidaPdfView.as_view()),   # ðŸ‘ˆ nuevo
    path("ingresos/<int:ingreso_id>/cerrar/", CerrarReparacionView.as_view()),

    # tipos de equipo (alias singular/plural por compat)
    path("catalogos/tipos-equipo/", TiposEquipoView.as_view()),
    path("catalogo/tipos-equipo/", TiposEquipoView.as_view()),
    # asignaciÃ³n de tipo de equipo al modelo (alias singular/plural por compat)
    path("catalogos/marcas/<int:marca_id>/modelos/<int:modelo_id>/tipo-equipo/", ModeloTipoEquipoView.as_view()),
    path("catalogo/marcas/<int:marca_id>/modelos/<int:modelo_id>/tipo-equipo/", ModeloTipoEquipoView.as_view()),



    # historial de cambios por ingreso
    path("ingresos/<int:ingreso_id>/historial/", IngresoHistorialView.as_view()),
]


