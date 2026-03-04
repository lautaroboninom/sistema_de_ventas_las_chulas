// web/src/lib/api.js

const devApiPort = window.location.port === '5175' ? '18100' : '8000';
const isDevVite = window.location.port === '5173' || window.location.port === '5175';
const BASE =
  import.meta.env.VITE_API_URL?.replace(/\/+$/, '') ||
  (isDevVite ? `${window.location.protocol}//${window.location.hostname}:${devApiPort}` : '');

let token = null;
export const setToken = (t) => {
  token = t;
};

async function http(path, { method = 'GET', body, headers } = {}) {
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
  const requestHeaders = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(headers || {}),
  };
  if (isFormData && requestHeaders['Content-Type']) {
    delete requestHeaders['Content-Type'];
  }

  let requestBody;
  if (body !== undefined && body !== null) {
    requestBody = isFormData ? body : JSON.stringify(body);
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    credentials: 'include',
    headers: requestHeaders,
    body: requestBody,
  });

  const ct = res.headers.get('content-type') || '';
  const data = ct.includes('application/json') ? await res.json() : await res.text();

  if (!res.ok) {
    const msg = typeof data === 'string' ? data : data?.detail || JSON.stringify(data);
    const err = new Error(`${res.status} ${res.statusText}: ${msg}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  get: (p, opts) => http(p, { ...opts, method: 'GET' }),
  post: (p, body, opts) => http(p, { ...opts, method: 'POST', body }),
  put: (p, body, opts) => http(p, { ...opts, method: 'PUT', body }),
  patch: (p, body, opts) => http(p, { ...opts, method: 'PATCH', body }),
  del: (p, opts) => http(p, { ...opts, method: 'DELETE' }),
};

export default api;

// Auth
export const postLogin = (email, password) => api.post('/api/auth/login/', { email, password });
export const postAuthForgot = (email) => api.post('/api/auth/forgot/', { email });
export const postAuthReset = (tokenValue, password) => api.post('/api/auth/reset/', { token: tokenValue, password });
export const getAuthSession = () => api.get('/api/auth/session/');
export const postAuthLogout = () => api.post('/api/auth/logout/', {});

// Usuarios y permisos
export const getUsuarios = () => api.get('/api/usuarios/');
export const postUsuario = (payload) => api.post('/api/usuarios/', payload);
export const patchUsuarioActivo = (id, activo) => api.patch(`/api/usuarios/${id}/activar/`, { activo });
export const patchUsuarioReset = (id) => api.patch(`/api/usuarios/${id}/reset-pass/`, {});
export const patchUsuarioRolePerm = (id, payload) => api.patch(`/api/usuarios/${id}/roleperm/`, payload);
export const deleteUsuario = (id) => api.del(`/api/usuarios/${id}/`);
export const getPermisosCatalogo = () => api.get('/api/permisos/catalogo/');
export const getUsuarioPermisos = (id) => api.get(`/api/usuarios/${id}/permisos/`);
export const putUsuarioPermisos = (id, payload) => api.put(`/api/usuarios/${id}/permisos/`, payload);
export const postUsuarioPermisosReset = (id) => api.post(`/api/usuarios/${id}/permisos/reset/`, {});

// Retail catalogo
export const getRetailProductos = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.active !== undefined) qs.set('active', String(params.active));
  return api.get(`/api/retail/productos/${qs.toString() ? `?${qs}` : ''}`);
};
export const postRetailProducto = (payload) => api.post('/api/retail/productos/', payload);
export const patchRetailProducto = (id, payload) => api.patch(`/api/retail/productos/${id}/`, payload);

export const getRetailAtributos = () => api.get('/api/retail/atributos/');
export const postRetailAtributo = (payload) => api.post('/api/retail/atributos/', payload);

export const getRetailVariantes = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.active !== undefined) qs.set('active', String(params.active));
  return api.get(`/api/retail/variantes/${qs.toString() ? `?${qs}` : ''}`);
};
export const postRetailVariante = (payload) => api.post('/api/retail/variantes/', payload);
export const patchRetailVariante = (id, payload) => api.patch(`/api/retail/variantes/${id}/`, payload);
export const getRetailVarianteByScan = (codigo) => api.get(`/api/retail/variantes/escanear/${encodeURIComponent(codigo)}/`);

// Compras
export const postRetailCompra = (payload) => api.post('/api/retail/compras/', payload);
export const getRetailCompra = (id) => api.get(`/api/retail/compras/${id}/`);

// Caja
export const postRetailCajaApertura = (payload) => api.post('/api/retail/caja/apertura/', payload || {});
export const postRetailCajaCierre = (payload) => api.post('/api/retail/caja/cierre/', payload || {});
export const getRetailCajaActual = () => api.get('/api/retail/caja/actual/');
export const getRetailCajaCuentas = () => api.get('/api/retail/caja/cuentas/');
export const getRetailCaja = (id) => api.get(`/api/retail/caja/${id}/`);

// Ventas/facturacion
export const getRetailVentas = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.desde) qs.set('desde', params.desde);
  if (params.hasta) qs.set('hasta', params.hasta);
  if (params.q) qs.set('q', params.q);
  if (params.channel) qs.set('channel', params.channel);
  if (params.payment_method) qs.set('payment_method', params.payment_method);
  if (params.status) qs.set('status', params.status);
  if (params.limit) qs.set('limit', String(params.limit));
  if (params.offset) qs.set('offset', String(params.offset));
  return api.get(`/api/retail/ventas/${qs.toString() ? `?${qs}` : ''}`);
};
export const getRetailVentaDetail = (id) => api.get(`/api/retail/ventas/${id}/`);
export const postRetailVentaCotizar = (payload) => api.post('/api/retail/ventas/cotizar/', payload);
export const postRetailVentaConfirmar = (payload) => api.post('/api/retail/ventas/confirmar/', payload);
export const postRetailVentaAnular = (id, payload) => api.post(`/api/retail/ventas/${id}/anular/`, payload || {});
export const postRetailVentaDevolver = (id, payload) => api.post(`/api/retail/ventas/${id}/devolver/`, payload || {});
export const getRetailGarantiaTicket = (codigo) =>
  api.get(`/api/retail/garantias/ticket/${encodeURIComponent(codigo)}/`);
export const getRetailGarantiasActivas = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.tipo) qs.set('tipo', params.tipo);
  if (params.limit) qs.set('limit', String(params.limit));
  if (params.offset) qs.set('offset', String(params.offset));
  return api.get(`/api/retail/garantias/activas/${qs.toString() ? `?${qs}` : ''}`);
};

export const postRetailFacturaEmitir = (ventaId) => api.post(`/api/retail/facturacion/${ventaId}/emitir/`, {});
export const getRetailFactura = (ventaId) => api.get(`/api/retail/facturacion/${ventaId}/`);
export const postRetailNotaCredito = (ventaId, payload) => api.post(`/api/retail/facturacion/${ventaId}/nota-credito/`, payload || {});

// Config
export const getRetailConfigSettings = () => api.get('/api/retail/config/settings/');
export const getRetailConfigPageSettings = () => api.get('/api/retail/config/page-settings/');
export const putRetailConfigSettings = (payload) => api.put('/api/retail/config/settings/', payload || {});
export const putRetailConfigPageSettings = (payload) => api.put('/api/retail/config/page-settings/', payload || {});
export const getRetailConfigPaymentAccounts = () => api.get('/api/retail/config/payment-accounts/');
export const putRetailConfigPaymentAccounts = (payload) =>
  api.put('/api/retail/config/payment-accounts/', payload || {});

// Online
export const postRetailOnlineSyncCatalogo = (payload) => api.post('/api/retail/online/sync/catalogo/', payload || {});
export const postRetailOnlineSyncStock = (payload) => api.post('/api/retail/online/sync/stock/', payload || {});

// Reportes
export const getRetailReporteMasVendidos = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.desde) qs.set('desde', params.desde);
  if (params.hasta) qs.set('hasta', params.hasta);
  if (params.limit) qs.set('limit', params.limit);
  return api.get(`/api/retail/reportes/mas-vendidos/${qs.toString() ? `?${qs}` : ''}`);
};
export const getRetailReporteTallesColores = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.desde) qs.set('desde', params.desde);
  if (params.hasta) qs.set('hasta', params.hasta);
  return api.get(`/api/retail/reportes/talles-colores/${qs.toString() ? `?${qs}` : ''}`);
};
export const getRetailReporteBajoStock = () => api.get('/api/retail/reportes/bajo-stock/');
export const getRetailReporteRentabilidad = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.desde) qs.set('desde', params.desde);
  if (params.hasta) qs.set('hasta', params.hasta);
  return api.get(`/api/retail/reportes/rentabilidad/${qs.toString() ? `?${qs}` : ''}`);
};
export const getRetailReporteVentasPorMedio = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.desde) qs.set('desde', params.desde);
  if (params.hasta) qs.set('hasta', params.hasta);
  return api.get(`/api/retail/reportes/ventas-por-medio/${qs.toString() ? `?${qs}` : ''}`);
};
export const getRetailReporteCierreCaja = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.desde) qs.set('desde', params.desde);
  if (params.hasta) qs.set('hasta', params.hasta);
  return api.get(`/api/retail/reportes/cierre-caja/${qs.toString() ? `?${qs}` : ''}`);
};
export const getRetailReporteDevoluciones = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.desde) qs.set('desde', params.desde);
  if (params.hasta) qs.set('hasta', params.hasta);
  return api.get(`/api/retail/reportes/devoluciones/${qs.toString() ? `?${qs}` : ''}`);
};



