  // web/src/lib/api.js
import { MOTIVO_OPTIONS } from "./constants";

  // === BASE del API robusto ===
  // 1) Si est definida VITE_API_URL, la usamos.
  // 2) Si no, caemos al host actual pero en puerto 8000 (til en LAN).
  const API_FALLBACK = `${window.location.protocol}//${window.location.hostname}:8000`;
  const isDevVite = window.location.port === "5173";
  const BASE =
    import.meta.env.VITE_API_URL?.replace(/\/+$/, "") ||
    (isDevVite
      ? `${window.location.protocol}//${window.location.hostname}:8000`
      : ""); // produccin: mismo origen + rutas /api/ relativas

  /* ===== Token en memoria (compatibilidad) ===== */
  let token = null;
  export const setToken = (t) => {
    token = t;
  };

  /* ===== Logout forzado ante 401 ===== */
  let forcingLogout = false;
  function forceLogout() {
    if (forcingLogout) return;
    forcingLogout = true;
    try {
      setToken(null);
    } finally {
      const path = window.location.pathname || "";
      const search = window.location.search || "";
      const hash = window.location.hash || "";
      const current = `${path}${search}${hash}` || "/";
      // No redirigir si estamos en rutas pblicas de auth
      const safePaths = new Set(["/login", "/restablecer", "/recuperar"]);
      if (!safePaths.has(path)) {
        const next = encodeURIComponent(current);
        window.location.replace(`/login?next=${next}`);
        return;
      }
      // Mantenernos en la ruta pblica actual
      forcingLogout = false;
    }
  }

  /* ===== Wrapper HTTP ===== */
  async function http(path, { method = "GET", body, headers } = {}) {
    const res = await fetch(`${BASE}${path}`, {
      method,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(headers || {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    const ct = res.headers.get("content-type") || "";
    const isJSON = ct.includes("application/json");
    const data = isJSON ? await res.json() : await res.text();
    

    if (res.status === 401) {
      // Evitar redirigir desde pginas pblicas de auth
      const p = window.location.pathname || "";
      const publicAuth = p.startsWith("/restablecer") || p.startsWith("/recuperar") || p === "/login";
      if (!publicAuth) forceLogout();
    }

    // Algunos despliegues pueden responder 403 con mensajes de no autenticado.
    if (res.status === 403) {
      const msg = (typeof data === "string" ? data : (data?.detail || ""))?.toString().toLowerCase();
      const looksUnauth =
        msg.includes("credentials were not provided") ||
        msg.includes("not authenticated") ||
        msg.includes("no autenticado") ||
        msg.includes("token expirado") ||
        msg.includes("token inválido") ||
        msg.includes("token invalido");
      if (looksUnauth) {
        const p = window.location.pathname || "";
        const publicAuth = p.startsWith("/restablecer") || p.startsWith("/recuperar") || p === "/login";
        if (!publicAuth) forceLogout();
      }
    }

    if (!res.ok) {
      const msg =
        typeof data === "string" ? data : data.detail || JSON.stringify(data);
      throw new Error(`${res.status} ${res.statusText}: ${msg}`);
    }
    return data;
  }

  /* API cruda para quien prefiera */
  export const api = {
    get: (p, opts) => http(p, { ...opts, method: "GET" }),
    post: (p, body, opts) => http(p, { ...opts, method: "POST", body }),
    patch: (p, body, opts) => http(p, { ...opts, method: "PATCH", body }),
    del: (p, opts) => http(p, { ...opts, method: "DELETE" }),
  };
  export default api;

  /* ================== AUTH ================== */
  export const postLogin = (email, password) =>
    api.post("/api/auth/login/", { email, password });
  export const postAuthForgot = (email) =>
    api.post("/api/auth/forgot/", { email });
  export const postAuthReset = (token, password) =>
    api.post("/api/auth/reset/", { token, password });
  export const getAuthSession = () => api.get("/api/auth/session/");
  export const postAuthLogout = () => api.post("/api/auth/logout/");


  /* =============== USUARIOS ================= */
  export const getUsuarios = () => api.get("/api/usuarios/");
  export const postUsuario = (payload) => api.post("/api/usuarios/", payload);
  export const patchUsuarioActivo = (id, activo) =>
    api.patch(`/api/usuarios/${id}/activar/`, { activo });
  // Enviar enlace de restablecimiento/invitacin por email
  export const patchUsuarioReset = (id) =>
    api.patch(`/api/usuarios/${id}/reset-pass/`, {});
  export const patchUsuarioRolePerm = (id, payload) =>
    api.patch(`/api/usuarios/${id}/roleperm/`, payload);
  export const deleteUsuario = (id) => api.del(`/api/usuarios/${id}/`);

  /* =============== catalogos =============== */


const catalogCache = {
  marcas: null,
  tipos: new Map(),
  modelos: new Map(),
  variantes: new Map(),
};

const catalogCacheKey = (...parts) => parts.filter(part => part !== undefined && part !== null).join(":");

export const clearCatalogCache = () => {
  catalogCache.marcas = null;
  catalogCache.tipos.clear();
  catalogCache.modelos.clear();
  catalogCache.variantes.clear();
};

export async function getCatalogMarcas(force = false) {
  if (!force && catalogCache.marcas) {
    return catalogCache.marcas;
  }
  const data = await api.get("/api/catalogo/marcas/");
  catalogCache.marcas = data;
  return data;
}

export async function getCatalogTipos(marcaId, force = false) {
  const key = String(marcaId ?? "");
  if (!force && catalogCache.tipos.has(key)) {
    return catalogCache.tipos.get(key);
  }
  if (marcaId == null || marcaId === "") {
    catalogCache.tipos.set(key, []);
    return [];
  }
  const data = await api.get(`/api/catalogo/marcas/${encodeURIComponent(marcaId)}/tipos/`);
  catalogCache.tipos.set(key, data);
  return data;
}

export async function getCatalogModelos(marcaId, tipoId, force = false) {
  const key = catalogCacheKey(marcaId, tipoId);
  if (!force && catalogCache.modelos.has(key)) {
    return catalogCache.modelos.get(key);
  }
  if (!marcaId || !tipoId) {
    catalogCache.modelos.set(key, []);
    return [];
  }
  const data = await api.get(
    `/api/catalogo/marcas/${encodeURIComponent(marcaId)}/tipos/${encodeURIComponent(tipoId)}/modelos/`
  );
  catalogCache.modelos.set(key, data);
  return data;
}

export async function getCatalogVariantes(marcaId, tipoId, modeloId, force = false) {
  const key = catalogCacheKey(marcaId, tipoId, modeloId);
  if (!force && catalogCache.variantes.has(key)) {
    return catalogCache.variantes.get(key);
  }
  if (!marcaId || !modeloId) {
    catalogCache.variantes.set(key, []);
    return [];
  }
  const data = await api.get(
    `/api/catalogo/marcas/${encodeURIComponent(marcaId)}/modelos/${encodeURIComponent(modeloId)}/variantes/`
  );
  catalogCache.variantes.set(key, data);
  return data;
}

// Variantes por marca (sugerencias simples)
export async function getVariantesPorMarca(marcaId) {
  if (!marcaId) return [];
  return api.get(`/api/catalogo/marcas/${encodeURIComponent(marcaId)}/variantes/`);
}

// Marcas que soportan un tipo dado (por nombre)
export async function getMarcasPorTipo(tipoNombre) {
  const name = encodeURIComponent(tipoNombre || "");
  if (!name) return [];
  return api.get(`/api/catalogo/tipos/${name}/marcas/`);
}

// Tipos (ABM por marca)
export const postCatalogTipo = (payload) =>
  api.post("/api/catalogo/tipos-equipo/", payload);

export const patchCatalogTipo = (tipoId, payload) =>
  api.patch(`/api/catalogo/tipos-equipo/${tipoId}/`, payload);

export const deleteCatalogTipo = (tipoId) =>
  api.del(`/api/catalogo/tipos-equipo/${tipoId}/`);

export const postCatalogModelo = (payload) =>
  api.post("/api/catalogo/modelos/", payload);

export const patchCatalogModelo = (modeloId, payload) =>
  api.patch(`/api/catalogo/modelos/${modeloId}/`, payload);

export const deleteCatalogModelo = (modeloId) =>
  api.del(`/api/catalogo/modelos/${modeloId}/`);

// Aliases de compat (antes se llamaban 'serie')
export const postCatalogSerie = postCatalogModelo;
export const patchCatalogSerie = patchCatalogModelo;
export const deleteCatalogSerie = deleteCatalogModelo;

export const postCatalogVariante = (payload) =>
  api.post("/api/catalogo/variantes/", payload);

export const patchCatalogVariante = (varianteId, payload) =>
  api.patch(`/api/catalogo/variantes/${varianteId}/`, payload);

export const deleteCatalogVariante = (varianteId) =>
  api.del(`/api/catalogo/variantes/${varianteId}/`);


  export const getClientes = () => api.get("/api/catalogos/clientes/");
  export const postCliente = (payload) =>
    api.post("/api/catalogos/clientes/", payload);
  export const patchCliente = (id, payload) =>
    api.patch(`/api/catalogos/clientes/${id}/`, payload);
  export const deleteCliente = (id) =>
    api.del(`/api/catalogos/clientes/${id}/`);
  export const getRoles = () => api.get("/api/catalogos/roles/");
  export const getMarcas = () => api.get("/api/catalogos/marcas/");
  export const postMarca = (nombre) =>
    api.post("/api/catalogos/marcas/", { nombre });
  export const deleteMarca = (id) =>
    api.del(`/api/catalogos/marcas/${id}/`);
  // Eliminacin en cascada: borra la marca y TODOS sus modelos
  export const deleteMarcaCascade = (id) =>
    api.del(`/api/catalogos/marcas/${id}/eliminar-con-modelos/`);
  export const patchMarca = (id, payload) =>
    api.patch(`/api/catalogos/marcas/${id}/`, payload);

  // Unificar marcas
  export const postMarcaMerge = (sourceId, targetId, opts = {}) =>
    api.post(`/api/catalogos/marcas/merge/`, { source_id: sourceId, target_id: targetId, ...(opts || {}) });

  export const getTiposEquipo = () =>
    api.get("/api/catalogos/tipos-equipo/");

  // ABM Tipos de equipo (catlogo general)
  export const getTiposEquipoAdmin = () =>
    api.get("/api/catalogos/tipos-equipo-admin/");
  export const postTipoEquipo = (nombre) =>
    api.post("/api/catalogos/tipos-equipo-admin/", { nombre });
  export const patchTipoEquipo = (id, payload) =>
    api.patch(`/api/catalogos/tipos-equipo-admin/${id}/`, payload);
  export const deleteTipoEquipo = (id) =>
    api.del(`/api/catalogos/tipos-equipo-admin/${id}/`);

  export const patchModeloTipoEquipo = (marcaId, modeloId, payload) =>
    api.patch(`/api/catalogos/marcas/${marcaId}/modelos/${modeloId}/tipo-equipo/`, payload);

  export const getModelosByBrand = (brandId) =>
    api.get(`/api/catalogos/marcas/${brandId}/modelos/`);
  export const getModelos = getModelosByBrand; // alias por compatibilidad
export const postModelo = (brandId, payloadOrNombre) => {
  const payload = typeof payloadOrNombre === "string"
    ? { nombre: payloadOrNombre }
    : (payloadOrNombre || {});
  return api.post(`/api/catalogos/marcas/${brandId}/modelos/`, payload);
};
  export const deleteModelo = (id) =>
    api.del(`/api/catalogos/modelos/${id}/`);
  export const patchModelo = (id, payload) =>
    api.patch(`/api/catalogos/modelos/${id}/`, payload);

  // Unificar modelos (mueve devices del source al target y elimina el duplicado)
  export const postModelMerge = (sourceId, targetId) =>
    api.post(`/api/catalogos/modelos/merge/`, { source_id: sourceId, target_id: targetId });

  export const getUbicaciones = () => api.get("/api/catalogos/ubicaciones/");
  export const getMotivos = async () => {
    try {
      const res = await api.get("/api/catalogos/motivos/");
      const arr = Array.isArray(res) ? res : [];
      return arr.length ? arr : (MOTIVO_OPTIONS || []);
    } catch (_) {
      return MOTIVO_OPTIONS || [];
    }
  };
  export const getAccesoriosCatalogo = () => api.get("/api/catalogos/accesorios/");

  export const getProveedoresExternos = () =>
    api.get("/api/catalogos/proveedores-externos/");
  export const postProveedorExterno = (payload) =>
    api.post("/api/catalogos/proveedores-externos/", payload);
  export const deleteProveedorExterno = (id) =>
    api.del(`/api/catalogos/proveedores-externos/${id}/`);

  /* =============== INGRESOS ================= */
  export const postNuevoIngreso = (payload) =>
    api.post("/api/ingresos/nuevo/", payload);
  export const postDerivarIngreso = (ingresoId, payload) =>
    api.post(`/api/ingresos/${ingresoId}/derivar/`, payload);
  export const getDerivacionesPorIngreso = (ingresoId) =>
    api.get(`/api/ingresos/${ingresoId}/derivaciones/`);
  export const postDerivacionDevuelto = (ingresoId, derivId, payload) =>
    api.post(`/api/ingresos/${ingresoId}/derivaciones/${derivId}/devolver/`, payload);
  // Accesorios por ingreso
  export const getAccesoriosPorIngreso = (ingresoId) =>
    api.get(`/api/ingresos/${ingresoId}/accesorios/`);
  export const postAccesorioIngreso = (ingresoId, payload) =>
    api.post(`/api/ingresos/${ingresoId}/accesorios/`, payload);
  export const deleteAccesorioIngreso = (ingresoId, itemId) =>
    api.del(`/api/ingresos/${ingresoId}/accesorios/${itemId}/`);

  // Accesorios de alquiler por ingreso
  export const getAccesoriosAlquilerPorIngreso = (ingresoId) =>
    api.get(`/api/ingresos/${ingresoId}/alquiler/accesorios/`);
  export const postAccesorioAlquilerIngreso = (ingresoId, payload) =>
    api.post(`/api/ingresos/${ingresoId}/alquiler/accesorios/`, payload);
  export const deleteAccesorioAlquilerIngreso = (ingresoId, itemId) =>
    api.del(`/api/ingresos/${ingresoId}/alquiler/accesorios/${itemId}/`);

  export const getIngresoFotos = (ingresoId, params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api.get(`/api/ingresos/${ingresoId}/fotos/${qs ? `?${qs}` : ""}`);
  };

  export async function uploadIngresoFotos(ingresoId, files) {
    const form = new FormData();
    (files || []).forEach((file) => {
      if (file) form.append('files', file);
    });
    const res = await fetch(`${BASE}/api/ingresos/${ingresoId}/fotos/`, {
      method: "POST",
      credentials: "include",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: form,
    });
    const ct = res.headers.get("content-type") || "";
    const data = ct.includes("application/json") ? await res.json() : await res.text();
    if (res.status === 401 || res.status === 403) {
      forceLogout();
    }
    if (!res.ok) {
      const detail = typeof data === "string" ? data : data.detail || JSON.stringify(data);
      throw new Error(`${res.status} ${res.statusText}: ${detail}`);
    }
    return data;
  }

  // ---- Descarga/lectura de binarios con autorizacin ----
  function toAbsoluteUrl(pathOrUrl) {
    if (!pathOrUrl) return "";
    if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
    // Acepta paths relativos empezando con '/'
    return `${BASE}${pathOrUrl}`;
  }

  function parseDispositionFilename(header) {
    if (!header) return null;
    // Priorizar filename*=UTF-8''...
    const star = header.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
    if (star && star[1]) {
      try {
        return decodeURIComponent(star[1].trim());
      } catch (_) {
        // fallthrough
      }
    }
    const simple = header.match(/filename\s*=\s*"([^"]+)"/i) || header.match(/filename\s*=\s*([^;]+)/i);
    if (simple && simple[1]) return simple[1].trim().replace(/^"|"$/g, "");
    return null;
  }

  export async function fetchBlobAuth(pathOrUrl) {
    const url = toAbsoluteUrl(pathOrUrl);
    const res = await fetch(url, {
      method: "GET",
      credentials: "include",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (res.status === 401) {
      forceLogout();
    }
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}${text ? `: ${text}` : ""}`);
    }
    const blob = await res.blob();
    return { blob, res };
  }

  export async function downloadAuth(pathOrUrl, fallbackName = "archivo") {
    const { blob, res } = await fetchBlobAuth(pathOrUrl);
    const dispo = res.headers.get("content-disposition") || "";
    const name = parseDispositionFilename(dispo) || fallbackName || "archivo";
    const url = URL.createObjectURL(blob);
    try {
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } finally {
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  }

  export const patchIngresoFoto = (ingresoId, mediaId, payload) =>
    api.patch(`/api/ingresos/${ingresoId}/fotos/${mediaId}/`, payload);

  export const deleteIngresoFoto = (ingresoId, mediaId) =>
    api.del(`/api/ingresos/${ingresoId}/fotos/${mediaId}/`);

  // Bsqueda por referencia de accesorio
  export const buscarAccesorioPorRef = (ref) =>
    api.get(`/api/accesorios/buscar/?ref=${encodeURIComponent(ref||"")}`);
  // Entregar (requiere remito; opcional factura y fecha; si resolucion=cambio: serial_confirm requerido)
  export const postEntregarIngreso = (ingresoId, payload) =>
    api.post(`/api/ingresos/${ingresoId}/entregar/`, payload);
  export const getPendientesGeneral = () => api.get("/api/ingresos/pendientes/");
  export const getPendientesPresupuesto = () =>
    api.get("/api/presupuestos/pendientes/");
  export const getAprobadosParaReparar = () =>
    api.get("/api/ingresos/aprobados-para-reparar/");
  export const getAprobadosYReparados = () =>
    api.get("/api/ingresos/aprobados-reparados/");
  export const getLiberados = () => api.get("/api/ingresos/liberados/");
  export const getTecnicos = () => api.get("/api/catalogos/tecnicos/");
  export const getGeneralEquipos = (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api.get(`/api/equipos/${qs ? `?${qs}` : ""}`);
  };
  // Check garanta de reparacin por N/S
  export const checkGarantiaReparacion = (numero_serie, numero_interno) => {
    const params = new URLSearchParams();
    if (numero_serie) params.set("numero_serie", numero_serie);
    if (numero_interno) params.set("numero_interno", numero_interno);
    const qs = params.toString();
    return api.get(`/api/equipos/garantia-reparacion/${qs ? `?${qs}` : ""}`);
  };

  // TODO: Check garanta de fbrica (por N/S en Excels de trazabilidad)
  export const checkGarantiaFabrica = (numero_serie, marca) => {
    const params = new URLSearchParams();
    if (numero_serie) params.set("numero_serie", numero_serie);
    if (marca) params.set("marca", marca);
    const qs = params.toString();
    return api.get(`/api/equipos/garantia-fabrica/${qs ? `?${qs}` : ""}`);
  };
  // Garantías: políticas (excepciones administrables)
  export const listWarrantyRules = (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api.get(`/api/garantias/politicas/${qs ? `?${qs}` : ""}`);
  };
  export const createWarrantyRule = (payload) =>
    api.post(`/api/garantias/politicas/`, payload);
  export const patchWarrantyRule = (id, payload) =>
    api.patch(`/api/garantias/politicas/${id}/`, payload);
  export const deleteWarrantyRule = (id) =>
    api.delete(`/api/garantias/politicas/${id}/`);
  export const getGeneralPorCliente = (customerId) =>
    api.get(`/api/clientes/${customerId}/general/`);

  export async function getIngreso(id, params = null) {
    const qs = params ? new URLSearchParams(params).toString() : "";
    return api.get(`/api/ingresos/${id}/${qs ? `?${qs}` : ""}`);
  }

  export async function patchIngreso(id, payload) {
    return api.patch(`/api/ingresos/${id}/`, payload);
  }

  export const patchIngresoTecnico = (ingresoId, tecnico_id) =>
    api.patch(`/api/ingresos/${ingresoId}/asignar-tecnico/`, { tecnico_id });

  // Solicitud de asignacin por tcnico
  export const postSolicitarAsignacion = (ingresoId) =>
    api.post(`/api/ingresos/${ingresoId}/solicitar-asignacion/`, {});

  export const patchModeloTecnico = (marcaId, modeloId, tecnico_id) =>
    api.patch(
      `/api/catalogos/marcas/${marcaId}/modelos/${modeloId}/tecnico/`,
      { tecnico_id }
    );

  // Variante simple por modelo (v1)
  export const patchModeloVariante = (marcaId, modeloId, variante) =>
    api.patch(
      `/api/catalogos/marcas/${marcaId}/modelos/${modeloId}/variante/`,
      { variante }
    );

  export const patchMarcaTecnico = (marcaId, tecnico_id) =>
    api.patch(`/api/catalogos/marcas/${marcaId}/tecnico/`, { tecnico_id });

  // Aplica el tcnico de la marca a TODOS los modelos (sobrescribe)
  export const postMarcaAplicarTecnico = (marcaId) =>
    api.post(`/api/catalogos/marcas/${marcaId}/tecnico/aplicar-a-modelos/`);

  /* =============== PRESUPUESTOS =============== */
  export const getQuote = (ingresoId) => api.get(`/api/quotes/${ingresoId}/`);

  export const postQuoteItem = (ingresoId, payload) =>
    api.post(`/api/quotes/${ingresoId}/items/`, payload);

  export const patchQuoteItem = (ingresoId, itemId, payload) =>
    api.patch(`/api/quotes/${ingresoId}/items/${itemId}/`, payload);

  export const deleteQuoteItem = (ingresoId, itemId) =>
    api.del(`/api/quotes/${ingresoId}/items/${itemId}/`);

  export const patchQuoteResumen = (ingresoId, payload /* {mano_obra} */) =>
    api.patch(`/api/quotes/${ingresoId}/resumen/`, payload);

  export const postQuoteEmitir = (ingresoId, payload /* {autorizado_por, forma_pago} */) =>
    api.post(`/api/quotes/${ingresoId}/emitir/`, payload);

  export const postQuoteAprobar = (ingresoId) =>
    api.post(`/api/quotes/${ingresoId}/aprobar/`);

  export const postQuoteNoAplica = (ingresoId) =>
    api.post(`/api/quotes/${ingresoId}/no-aplica/`);

  export const postQuoteQuitarNoAplica = (ingresoId) =>
    api.post(`/api/quotes/${ingresoId}/no-aplica/quitar/`);

  // === GET binario (Blob) con auth y cookies ===
  export async function getBlob(path, opts = {}) {
    const url = path.startsWith("http") ? path : `${BASE}${path}`;
    const authHeader = token ? { Authorization: `Bearer ${token}` } : {};
    const { headers: extraHeaders, ...restOpts } = opts;

    const res = await fetch(url, {
      method: "GET",
      headers: {
        ...authHeader,
        ...(extraHeaders || {}),
      },
      credentials: "include",
      ...restOpts,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(text || `HTTP ${res.status}`);
    }
    return await res.blob();
  }

  export const postQuoteAnular = (ingresoId) =>
    api.post(`/api/quotes/${ingresoId}/anular/`);

  // Cerrar reparacin (setea la resolucin)
  export async function postCerrarReparacion(id, body) {
    // body = { resolucion: "reparado" | "no_reparado" | "no_se_encontro_falla" | "presupuesto_rechazado" | "cambio", serial_cambio?: string }
    return api.post(`/api/ingresos/${id}/cerrar/`, body);
  }

  export async function postMarcarReparado(id) {
    return api.post(`/api/ingresos/${id}/reparado/`);
  }

  // Historial de cambios por ingreso
  export const getIngresoHistorial = (ingresoId) =>
    api.get(`/api/ingresos/${ingresoId}/historial/`);


  /* =============== Mtricas ================= */
  export const getMetricasResumen = (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api.get(`/api/metricas/resumen/${qs ? `?${qs}` : ""}`);
  };
  export const getMetricasSeries = (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api.get(`/api/metricas/series/${qs ? `?${qs}` : ""}`);
  };
  export const getMetricasCalibracion = (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api.get(`/api/metricas/calibracion/${qs ? `?${qs}` : ""}`);
  };
  export const getMetricasConfig = () => api.get(`/api/metricas/config/`);
  export const getFeriados = () => api.get(`/api/metricas/feriados/`);
  export const postFeriado = (fecha, nombre) => api.post(`/api/metricas/feriados/`, { fecha, nombre });
  export const deleteFeriado = (fecha) => api.del(`/api/metricas/feriados/?fecha=${encodeURIComponent(fecha||"")}`);
