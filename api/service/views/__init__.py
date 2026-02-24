"""Domain-split views package.

Temporary re-exports preserve backwards-compat imports like
`from api.service.views import FooView` while we split code by domain.
"""

# Re-export everything public from legacy first, then override with
# domain-specific implementations moved to dedicated modules.
from .legacy import *  # noqa: F401,F403

# Explicitly re-export underscored helpers consumed elsewhere in the repo
# (e.g., motivos_view imports _fix_text_value from .views).
from .helpers import _fix_text_value  # noqa: F401

# Domain-specific views (override legacy exports where applicable)
from .auth_views import (
    ping,
    LoginView,
    LogoutView,
    SessionView,
    ForgotPasswordView,
    ResetPasswordView,
)

from .metricas_views import (
    MetricasResumenView,
    MetricasSeriesView,
    MetricasFinanzasView,
    MetricasFinanzasLiberadosView,
    MetricasCalibracionView,
    FeriadosView,
    MetricasConfigView,
)

from .catalogo_tipos_views import (
    TiposEquipoView,
)

from .ingresos_views import (
    MisPendientesView,
    PendientesPresupuestoView,
    PresupuestadosView,
    PresupuestadosExportView,
    AprobadosParaRepararView,
    AprobadosYReparadosView,
    AprobadosView,
    LiberadosView,
    GeneralEquiposView,
    GeneralPorClienteView,
    GeneralPorClienteExportView,
    MarcarControladoSinDefectoView,
    MarcarParaRepararView,
    MarcarReparadoView,
    EntregarIngresoView,
    DarBajaIngresoView,
    DarAltaIngresoView,
    GarantiaReparacionCheckView,
    GarantiaFabricaCheckView,
    NuevoIngresoView,
    IngresoDetalleView,
    IngresoAsignarTecnicoView,
    IngresoSolicitarAsignacionView,
    IngresoHistorialView,
    PendientesGeneralView,
    ListosParaRetiroView,
    CerrarReparacionView,
)

from .quotes_views import (
    QuoteDetailView,
    QuoteItemsView,
    QuoteItemDetailView,
    QuoteResumenView,
    EmitirPresupuestoView,
    QuotePdfView,
    AprobarPresupuestoView,
    AnularPresupuestoView,
    NoAplicaPresupuestoView,
    QuitarNoAplicaPresupuestoView,
)

from .media_views import (
    IngresoMediaListCreateView,
    IngresoMediaDetailView,
    IngresoMediaFileView,
    IngresoMediaThumbnailView,
)

from .accesorios_views import (
    CatalogoAccesoriosView,
    IngresoAccesoriosView,
    IngresoAccesorioDetailView,
    BuscarAccesorioPorReferenciaView,
    IngresoAlquilerAccesoriosView,
    IngresoAlquilerAccesorioDetailView,
)

from .repuestos_views import (
    RepuestosSubrubrosView,
    RepuestosSubrubroDetailView,
    CatalogoRepuestosView,
    RepuestosView,
    RepuestoDetailView,
    RepuestosConfigView,
    RepuestosCompraMovimientoView,
    RepuestosMovimientosView,
    RepuestosCambiosView,
    RepuestosStockPermisosView,
    RepuestosStockPermisoDetailView,
)

from .catalogo_hierarquia_views import (
    CatalogoTiposView,
    CatalogoModelosDeTipoView,
    CatalogoVariantesView,
    CatalogoMarcasPorTipoView,
    CatalogoTiposCreateView,
    CatalogoTipoDetailView,
    CatalogoModelosCreateView,
    CatalogoModeloDetailView,
    CatalogoVariantesCreateView,
    CatalogoVarianteDetailView,
    ModeloTipoEquipoView,
)

from .marcas_modelos_views import (
    CatalogoMarcasView,
    CatalogoModelosView,
    CatalogoUbicacionesView,
    ModeloVarianteView,
    ModelosPorMarcaView,
    MarcaDeleteView,
    MarcaDeleteCascadeView,
    ModeloDeleteView,
    ModeloTecnicoView,
    MarcaTecnicoView,
    MarcaAplicarTecnicoAModelosView,
    ModelMergeView,
    MarcaMergeView,
)

from .usuarios_views import (
    UsuariosView,
    UsuarioActivoView,
    UsuarioResetPassView,
    UsuarioRolePermView,
    UsuarioDeleteView,
    CatalogoRolesView,
    CatalogoTecnicosView,
)

from .derivaciones_views import (
    DerivarIngresoView,
    DerivacionesPorIngresoView,
    DevolverDerivacionView,
    EquiposDerivadosView,
)

from .devices_views import (
    DeviceIdentificadoresView,
    DevicesListView,
    DevicesMergeView,
)

from .proveedores_views import (
    ProveedoresExternosView,
)

from .clientes_views import (
    CustomersListView,
    ClientesView,
    ClienteDeleteView,
    ClienteMergeView,
)

from .reportes_views import (
    RemitoSalidaPdfView,
    RemitoDerivacionPdfView,
)

from .scan_views import (
    ScanLookupView,
)

# Motivos catálogo (propio de views/)
from .motivos_view import CatalogoMotivosView
from .warranty_views import WarrantyRulesView, WarrantyRuleDetailView

__all__ = [
    # auth
    "ping",
    "LoginView",
    "LogoutView",
    "SessionView",
    "ForgotPasswordView",
    "ResetPasswordView",
    # metricas
    "MetricasResumenView",
    "MetricasSeriesView",
    "MetricasFinanzasView",
    "MetricasFinanzasLiberadosView",
    "MetricasCalibracionView",
    "FeriadosView",
    "MetricasConfigView",
    # catalogo (tipos)
    "TiposEquipoView",
    # ingresos
    "MisPendientesView",
    "PendientesPresupuestoView",
    "PresupuestadosView",
    "PresupuestadosExportView",
    "AprobadosParaRepararView",
    "AprobadosYReparadosView",
    "AprobadosView",
    "LiberadosView",
    "GeneralEquiposView",
    "GeneralPorClienteView",
    "GeneralPorClienteExportView",
    "MarcarControladoSinDefectoView",
    "MarcarParaRepararView",
    "MarcarReparadoView",
    "EntregarIngresoView",
    "DarBajaIngresoView",
    "DarAltaIngresoView",
    "GarantiaReparacionCheckView",
    "GarantiaFabricaCheckView",
    "NuevoIngresoView",
    "IngresoDetalleView",
    "IngresoAsignarTecnicoView",
    "IngresoSolicitarAsignacionView",
    "IngresoHistorialView",
    "PendientesGeneralView",
    "ListosParaRetiroView",
    "CerrarReparacionView",
    # quotes
    "QuoteDetailView",
    "QuoteItemsView",
    "QuoteItemDetailView",
    "QuoteResumenView",
    "EmitirPresupuestoView",
    "QuotePdfView",
    "AprobarPresupuestoView",
    "AnularPresupuestoView",
    "NoAplicaPresupuestoView",
    "QuitarNoAplicaPresupuestoView",
    # media
    "IngresoMediaListCreateView",
    "IngresoMediaDetailView",
    "IngresoMediaFileView",
    "IngresoMediaThumbnailView",
    # accesorios
    "CatalogoAccesoriosView",
    "RepuestosSubrubrosView",
    "RepuestosSubrubroDetailView",
    "CatalogoRepuestosView",
    "RepuestosView",
    "RepuestoDetailView",
    "RepuestosConfigView",
    "RepuestosCompraMovimientoView",
    "RepuestosMovimientosView",
    "RepuestosCambiosView",
    "RepuestosStockPermisosView",
    "RepuestosStockPermisoDetailView",
    "IngresoAccesoriosView",
    "IngresoAccesorioDetailView",
    "BuscarAccesorioPorReferenciaView",
    "IngresoAlquilerAccesoriosView",
    "IngresoAlquilerAccesorioDetailView",
    # catalogo jerarquía
    "CatalogoTiposView",
    "CatalogoModelosDeTipoView",
    "CatalogoVariantesView",
    "CatalogoMarcasPorTipoView",
    "CatalogoTiposCreateView",
    "CatalogoTipoDetailView",
    "CatalogoModelosCreateView",
    "CatalogoModeloDetailView",
    "CatalogoVariantesCreateView",
    "CatalogoVarianteDetailView",
    "ModeloTipoEquipoView",
    # marcas y modelos
    "CatalogoMarcasView",
    "CatalogoModelosView",
    "CatalogoUbicacionesView",
    "ModeloVarianteView",
    "ModelosPorMarcaView",
    "MarcaDeleteView",
    "MarcaDeleteCascadeView",
    "ModeloDeleteView",
    "ModeloTecnicoView",
    "MarcaTecnicoView",
    "MarcaAplicarTecnicoAModelosView",
    "ModelMergeView",
    "MarcaMergeView",
    "CatalogoMotivosView",
    # usuarios
    "UsuariosView",
    "UsuarioActivoView",
    "UsuarioResetPassView",
    "UsuarioRolePermView",
    "UsuarioDeleteView",
    "CatalogoRolesView",
    "CatalogoTecnicosView",
    # derivaciones
    "DerivarIngresoView",
    "DerivacionesPorIngresoView",
    "DevolverDerivacionView",
    "EquiposDerivadosView",
    # devices
    "DeviceIdentificadoresView",
    "DevicesListView",
    "DevicesMergeView",
    # proveedores
    "ProveedoresExternosView",
    # clientes
    "CustomersListView",
    "ClientesView",
    "ClienteDeleteView",
    "ClienteMergeView",
    # reportes
    "RemitoSalidaPdfView",
    "RemitoDerivacionPdfView",
    # scan lookup
    "ScanLookupView",
    # motivos (catálogo ENUM ingreso.motivo)
    "CatalogoMotivosView",
    # warranty rules
    "WarrantyRulesView",
    "WarrantyRuleDetailView",
]
