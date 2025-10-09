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
    AprobadosParaRepararView,
    AprobadosYReparadosView,
    AprobadosCombinadosView,
    LiberadosView,
    GeneralEquiposView,
    GeneralPorClienteView,
    MarcarReparadoView,
    EntregarIngresoView,
    GarantiaReparacionCheckView,
    GarantiaFabricaCheckView,
    NuevoIngresoView,
    IngresoDetalleView,
    IngresoAsignarTecnicoView,
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

from .proveedores_views import (
    ProveedoresExternosView,
)

from .clientes_views import (
    CustomersListView,
    ClientesView,
    ClienteDeleteView,
)

from .reportes_views import (
    RemitoSalidaPdfView,
    RemitoDerivacionPdfView,
)

# Motivos catálogo (propio de views/)
from .motivos_view import CatalogoMotivosView

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
    "MetricasCalibracionView",
    "FeriadosView",
    "MetricasConfigView",
    # catalogo (tipos)
    "TiposEquipoView",
    # ingresos
    "MisPendientesView",
    "PendientesPresupuestoView",
    "PresupuestadosView",
    "AprobadosParaRepararView",
    "AprobadosYReparadosView",
    "AprobadosCombinadosView",
    "LiberadosView",
    "GeneralEquiposView",
    "GeneralPorClienteView",
    "MarcarReparadoView",
    "EntregarIngresoView",
    "GarantiaReparacionCheckView",
    "GarantiaFabricaCheckView",
    "NuevoIngresoView",
    "IngresoDetalleView",
    "IngresoAsignarTecnicoView",
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
    # media
    "IngresoMediaListCreateView",
    "IngresoMediaDetailView",
    "IngresoMediaFileView",
    "IngresoMediaThumbnailView",
    # accesorios
    "CatalogoAccesoriosView",
    "IngresoAccesoriosView",
    "IngresoAccesorioDetailView",
    "BuscarAccesorioPorReferenciaView",
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
    # proveedores
    "ProveedoresExternosView",
    # clientes
    "CustomersListView",
    "ClientesView",
    "ClienteDeleteView",
    # reportes
    "RemitoSalidaPdfView",
    "RemitoDerivacionPdfView",
    # motivos (catálogo ENUM ingreso.motivo)
    "CatalogoMotivosView",
]
