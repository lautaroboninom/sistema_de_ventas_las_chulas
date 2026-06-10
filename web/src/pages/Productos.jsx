import { useEffect, useRef, useState } from 'react';
import {
  deleteRetailAtributo,
  deleteRetailVariante,
  getRetailAtributos,
  getRetailAtributoValores,
  getRetailComprasProveedores,
  getRetailOnlineFailedJobsSummary,
  getRetailProductos,
  getRetailVarianteBarcodeLabelsUrl,
  getRetailVarianteBarcodes,
  getRetailVariantes,
  patchRetailAtributo,
  patchRetailProducto,
  patchRetailVariante,
  postRetailAtributo,
  postRetailProducto,
  postRetailVarianteBarcodeAssociate,
  postRetailVarianteBarcodeGenerate,
  postRetailVarianteBarcodePrimary,
  postRetailVariante,
} from '../lib/api';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { can, PERMISSION_CODES } from '../lib/permissions';
import { attrCode, normalizeValueError } from '../lib/variantAttributes';
import InfoHint from '../components/InfoHint';
import { VariantAttributeRows } from '../components/VariantAttributeRows';
import VariantBatchCreator from '../components/VariantBatchCreator';

function errMsg(error) {
  return error?.message || 'Ocurrio un error inesperado';
}

function explainVariantCombinationError(error) {
  const detail = String(error?.data?.detail || error?.message || '').toLowerCase();
  if (!detail.includes('ya existe una variante con esa combinacion')) return errMsg(error);
  if (detail.includes('inactiva')) {
    return 'Ya existe una variante inactiva de este producto con esos mismos atributos. Reactiva o edita la existente en lugar de crear otra.';
  }
  return 'Ya existe otra variante de este producto con esos mismos atributos. Ejemplo: si ya existe Color Negro + Talle M, no se puede crear otra igual.';
}

function duplicateVariantConflict(error) {
  const data = error?.data || {};
  if (error?.status !== 409 || data?.code !== 'variant_combination_conflict') return null;
  const variant = data?.conflict?.variant;
  if (!variant?.id) return null;
  return { detail: data?.detail || '', variant };
}

function variantLabel(row) {
  if (!row) return 'la variante existente';
  const product = row.producto || row.display_name || 'Variante existente';
  const signature = row.option_signature ? ` (${row.option_signature})` : '';
  const sku = row.sku ? ` [SKU ${row.sku}]` : '';
  return `${product}${signature}${sku}`;
}

const moneyFmt = new Intl.NumberFormat('es-AR', {
  style: 'currency',
  currency: 'ARS',
  maximumFractionDigits: 2,
});

function money(v) {
  const n = Number(v || 0);
  return moneyFmt.format(Number.isFinite(n) ? n : 0);
}

function variantBarcodes(row) {
  return Array.isArray(row?.barcodes) ? row.barcodes : [];
}

function fmtDate(value) {
  if (!value) return '-';
  try {
    return new Date(`${String(value).slice(0, 10)}T00:00:00`).toLocaleDateString('es-AR');
  } catch (_error) {
    return String(value).slice(0, 10);
  }
}

function fmtDateTime(value) {
  if (!value) return '-';
  return String(value).slice(0, 16).replace('T', ' ');
}

function primaryBarcode(row) {
  const barcodes = variantBarcodes(row);
  return barcodes.find((barcode) => barcode?.is_primary) || barcodes[0] || (row?.barcode_internal ? {
    barcode: row.barcode_internal,
    is_primary: true,
    supplier_name: '',
    supplier_item_code: '',
    supplier_ean_code: '',
  } : null);
}

function variantOptionsText(row) {
  const values = Array.isArray(row?.option_values) ? row.option_values : [];
  const labels = values
    .map((opt) => {
      const attr = opt?.attribute_name || opt?.attribute_code || '';
      const value = opt?.option_value || '';
      if (attr && value) return `${attr}: ${value}`;
      return value || attr;
    })
    .filter(Boolean);
  return labels.length ? labels.join(' / ') : (row?.option_signature || '-');
}

function variantSupplierSummary(row) {
  const barcodes = variantBarcodes(row);
  const primary = primaryBarcode(row);
  if (primary?.supplier_name) {
    return {
      name: primary.supplier_name,
      source: 'Barcode principal',
      barcode: primary.barcode || '',
      article: primary.supplier_item_code || '',
      ean: primary.supplier_ean_code || '',
    };
  }
  if (row?.last_purchase_supplier_name) {
    return {
      name: row.last_purchase_supplier_name,
      source: 'Ultima compra',
      barcode: primary?.barcode || row?.barcode_internal || '',
      article: row.last_purchase_supplier_product_name || '',
      ean: row.last_purchase_supplier_ean_code || '',
      date: row.last_purchase_date || '',
    };
  }
  const linked = barcodes.find((barcode) => barcode?.supplier_name);
  if (linked) {
    return {
      name: linked.supplier_name,
      source: linked.is_primary ? 'Barcode principal' : 'Barcode asociado',
      barcode: linked.barcode || '',
      article: linked.supplier_item_code || '',
      ean: linked.supplier_ean_code || '',
    };
  }
  return {
    name: 'Sin proveedor vinculado',
    source: primary?.barcode ? 'Barcode principal sin proveedor' : 'Sin vinculo',
    barcode: primary?.barcode || row?.barcode_internal || '',
    article: primary?.supplier_item_code || '',
    ean: primary?.supplier_ean_code || '',
  };
}

function detailValue(value, fallback = '-') {
  const txt = String(value ?? '').trim();
  return txt || fallback;
}

function inputMoney(v, fallback = '') {
  if (v === null || v === undefined || v === '') return fallback;
  return String(v);
}

function sameMoney(a, b) {
  return Number(a || 0) === Number(b || 0);
}

function HelpTitle({ as: Tag = 'h3', className = '', children, help }) {
  return (
    <Tag className={`inline-flex items-center gap-2 ${className}`}>
      <span>{children}</span>
      <InfoHint text={help} />
    </Tag>
  );
}

function buildOptionValues(rows) {
  const list = Array.isArray(rows) ? rows : [];
  const out = [];
  const seen = new Set();

  list.forEach((row, idx) => {
    const code = attrCode(row?.attribute_code);
    const value = String(row?.value || '').trim();

    if (!code && !value) return;
    if (!code || !value) {
      throw new Error(`Completa atributo y valor en la fila ${idx + 1}`);
    }
    if (seen.has(code)) {
      throw new Error(`No se puede repetir atributo en la fila ${idx + 1}`);
    }

    seen.add(code);
    out.push({
      attribute_code: code,
      value,
      attribute_value_id: row?.attribute_value_id || undefined,
      confirm_new_value: !!row?.confirm_new_value,
    });
  });

  if (!out.length) {
    throw new Error('Debes cargar al menos un atributo con valor');
  }

  return out;
}

function buildOptionalOptionValues(rows) {
  const list = Array.isArray(rows) ? rows : [];
  const hasAnyValue = list.some((row) => attrCode(row?.attribute_code) || String(row?.value || '').trim());
  if (!hasAnyValue) return null;
  return buildOptionValues(list);
}

const BARCODE_PRINT_PREFS_KEY = 'las_chulas_barcode_print_prefs_v1';
const PRINT_LAYOUTS = {
  A4: 'a4_grid',
  THERMAL: 'thermal_custom',
};
const DEFAULT_PRINT_PREFS = {
  layout: PRINT_LAYOUTS.THERMAL,
  labelWidthMm: '50',
  labelHeightMm: '30',
};

function clampNumber(value, min, max, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, n));
}

function normalizePrintLayout(value) {
  return value === PRINT_LAYOUTS.A4 ? PRINT_LAYOUTS.A4 : PRINT_LAYOUTS.THERMAL;
}

function normalizePrintMm(value, fallback) {
  const n = clampNumber(value, 10, 200, Number(fallback));
  return String(Math.round((n + Number.EPSILON) * 100) / 100);
}

function normalizeBarcodePrintPrefs(raw) {
  const source = raw || {};
  return {
    layout: normalizePrintLayout(source.layout),
    labelWidthMm: normalizePrintMm(source.labelWidthMm, DEFAULT_PRINT_PREFS.labelWidthMm),
    labelHeightMm: normalizePrintMm(source.labelHeightMm, DEFAULT_PRINT_PREFS.labelHeightMm),
  };
}

function loadBarcodePrintPrefs() {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return { ...DEFAULT_PRINT_PREFS };
    const raw = window.localStorage.getItem(BARCODE_PRINT_PREFS_KEY);
    if (!raw) return { ...DEFAULT_PRINT_PREFS };
    return normalizeBarcodePrintPrefs(JSON.parse(raw));
  } catch (_error) {
    return { ...DEFAULT_PRINT_PREFS };
  }
}

function saveBarcodePrintPrefs(raw) {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return;
    const normalized = normalizeBarcodePrintPrefs(raw);
    window.localStorage.setItem(BARCODE_PRINT_PREFS_KEY, JSON.stringify(normalized));
  } catch (_error) {
    // no-op: guardar preferencia no debe romper el flujo de impresion
  }
}

const EMPTY_PRODUCT = { name: '', sku_prefix: '', default_price_store_ars: '', default_price_online_ars: '' };
const EMPTY_ATTR = { name: '', code: '' };
const EMPTY_VARIANT = {
  product_id: '',
  option_rows: [{ attribute_code: '', value: '' }],
  sku: '',
  barcode_internal: '',
  supplier_id: '',
  price_store_ars: '',
  price_online_ars: '',
  cost_avg_ars: '',
  stock_on_hand: '0',
  stock_min: '0',
};

const EMPTY_EDIT_PRODUCT = {
  id: null,
  name: '',
  sku_prefix: '',
  default_cost_ars: '0',
  default_price_store_ars: '0',
  default_price_online_ars: '0',
  original_default_price_store_ars: '0',
  original_default_price_online_ars: '0',
  active: true,
};

const EMPTY_EDIT_ATTR = {
  id: null,
  name: '',
  code: '',
  sort_order: '100',
  active: true,
};

const EMPTY_EDIT_VARIANT = {
  id: null,
  display_name: '',
  sku: '',
  barcode_internal: '',
  original_barcode_internal: '',
  price_store_ars: '0',
  price_online_ars: '0',
  cost_avg_ars: '0',
  stock_min: '0',
  active: true,
  option_rows: [],
};

const EMPTY_BARCODE_MODAL = {
  open: false,
  variant: null,
  rows: [],
  loading: false,
  saving: false,
  err: '',
  msg: '',
  associateCode: '',
  supplierId: '',
  forceMove: false,
  printScope: 'primary',
  printCode: '',
  printCopies: '1',
  printLayout: DEFAULT_PRINT_PREFS.layout,
  printLabelWidthMm: DEFAULT_PRINT_PREFS.labelWidthMm,
  printLabelHeightMm: DEFAULT_PRINT_PREFS.labelHeightMm,
};

const EMPTY_DETAIL_MODAL = {
  open: false,
  variant: null,
};

const EMPTY_ONLINE_SYNC_SUMMARY = {
  failed_total: 0,
  by_type: {
    import_catalogo: 0,
    sync_catalogo: 0,
    sync_stock: 0,
  },
  loading: false,
  statusAvailable: false,
  lastUpdated: '',
};

function barcodeConflictDetail(error) {
  const payload = error?.data || {};
  if (error?.status !== 409 || payload?.code !== 'barcode_conflict') {
    return errMsg(error);
  }
  const owner = payload?.conflict?.current_owner?.variant;
  const ownerTxt = owner
    ? `${owner.producto || 'Variante'} ${owner.option_signature ? `(${owner.option_signature})` : ''} [SKU ${owner.sku || '-'}]`
    : 'otra variante';
  return `${payload?.detail || 'Conflicto de barcode'}: actualmente pertenece a ${ownerTxt}. Marca "Forzar mover" para transferirlo.`;
}

export default function ProductosPage() {
  const { user } = useAuth();
  const canEdit = can(user, PERMISSION_CODES.ACTION_CONFIG_EDITAR);
  const canSeeOnlineSyncStatus = can(user, PERMISSION_CODES.ACTION_ONLINE_SYNC);
  const canGoOnline = can(user, PERMISSION_CODES.PAGE_ONLINE);

  const [productos, setProductos] = useState([]);
  const [atributos, setAtributos] = useState([]);
  const [attrValuesByCode, setAttrValuesByCode] = useState({});
  const [variantes, setVariantes] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [q, setQ] = useState('');

  const [prodForm, setProdForm] = useState({ ...EMPTY_PRODUCT });
  const [prodImageFile, setProdImageFile] = useState(null);
  const [attrForm, setAttrForm] = useState({ ...EMPTY_ATTR });
  const [varForm, setVarForm] = useState({ ...EMPTY_VARIANT });
  const [editProductForm, setEditProductForm] = useState({ ...EMPTY_EDIT_PRODUCT });
  const [editAttrForm, setEditAttrForm] = useState({ ...EMPTY_EDIT_ATTR });
  const [editVariantForm, setEditVariantForm] = useState({ ...EMPTY_EDIT_VARIANT });
  const [editVariantOpen, setEditVariantOpen] = useState(false);
  const [createMenuOpen, setCreateMenuOpen] = useState(false);
  const [duplicateStockPrompt, setDuplicateStockPrompt] = useState(null);
  const prodImageInputRef = useRef(null);
  const barcodeInputRef = useRef(null);
  const barcodeModalInputRef = useRef(null);

  const [adjustByVariant, setAdjustByVariant] = useState({});
  const [barcodeModal, setBarcodeModal] = useState({ ...EMPTY_BARCODE_MODAL });
  const [detailModal, setDetailModal] = useState({ ...EMPTY_DETAIL_MODAL });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [onlineSyncSummary, setOnlineSyncSummary] = useState({ ...EMPTY_ONLINE_SYNC_SUMMARY });

  async function refreshOnlineSyncSummary() {
    if (!canSeeOnlineSyncStatus) return;
    setOnlineSyncSummary((prev) => ({ ...prev, loading: true }));
    try {
      const row = await getRetailOnlineFailedJobsSummary({ limit: 20 });
      setOnlineSyncSummary({
        failed_total: Number(row?.failed_total || 0),
        by_type: {
          import_catalogo: Number(row?.by_type?.import_catalogo || 0),
          sync_catalogo: Number(row?.by_type?.sync_catalogo || 0),
          sync_stock: Number(row?.by_type?.sync_stock || 0),
        },
        loading: false,
        statusAvailable: true,
        lastUpdated: new Date().toISOString(),
      });
    } catch (_error) {
      setOnlineSyncSummary((prev) => ({
        ...prev,
        loading: false,
        statusAvailable: false,
        lastUpdated: new Date().toISOString(),
      }));
    }
  }

  async function loadAll(options = {}) {
    const refreshSyncStatus = options.refreshSyncStatus ?? canSeeOnlineSyncStatus;
    setLoading(true);
    setErr('');
    try {
      const [prods, attrs, attrVals, vars, sups] = await Promise.all([
        getRetailProductos({ active: 1 }),
        getRetailAtributos(),
        getRetailAtributoValores({ limit: 500 }),
        getRetailVariantes({ q, active: 1 }),
        getRetailComprasProveedores({ limit: 500 }),
      ]);
      setProductos(Array.isArray(prods) ? prods : []);
      setAtributos(Array.isArray(attrs) ? attrs : []);
      const groupedValues = {};
      const valueItems = Array.isArray(attrVals?.items) ? attrVals.items : Array.isArray(attrVals) ? attrVals : [];
      valueItems.forEach((item) => {
        const code = attrCode(item?.attribute_code);
        if (!code) return;
        groupedValues[code] = [...(groupedValues[code] || []), item];
      });
      setAttrValuesByCode(groupedValues);
      setVariantes(Array.isArray(vars) ? vars : []);
      setSuppliers(Array.isArray(sups) ? sups : []);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoading(false);
    }
    if (refreshSyncStatus) {
      await refreshOnlineSyncSummary();
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    if (!canSeeOnlineSyncStatus) return undefined;
    const timer = window.setInterval(() => {
      refreshOnlineSyncSummary();
    }, 30000);
    return () => window.clearInterval(timer);
  }, [canSeeOnlineSyncStatus]);

  function availableAttrsForRow(idx) {
    const rows = Array.isArray(varForm.option_rows) ? varForm.option_rows : [];
    const current = attrCode(rows[idx]?.attribute_code);
    const selected = new Set(
      rows
        .filter((_, i) => i !== idx)
        .map((row) => attrCode(row.attribute_code))
        .filter(Boolean)
    );

    return atributos.filter((a) => {
      if (a?.active === false) return false;
      const code = attrCode(a.code);
      return !selected.has(code) || code === current;
    });
  }

  function updateOptionRow(idx, patch) {
    setVarForm((prev) => ({
      ...prev,
      option_rows: (prev.option_rows || []).map((row, i) => (i === idx ? { ...row, ...patch } : row)),
    }));
  }

  function addOptionRow() {
    setVarForm((prev) => {
      const used = new Set((prev.option_rows || []).map((row) => attrCode(row.attribute_code)).filter(Boolean));
      const firstFree = atributos.find((a) => a?.active !== false && !used.has(attrCode(a.code)));
      return {
        ...prev,
        option_rows: [
          ...(prev.option_rows || []),
          { attribute_code: firstFree ? firstFree.code : '', value: '' },
        ],
      };
    });
  }

  function removeOptionRow(idx) {
    setVarForm((prev) => {
      const next = (prev.option_rows || []).filter((_, i) => i !== idx);
      return {
        ...prev,
        option_rows: next.length ? next : [{ attribute_code: '', value: '' }],
      };
    });
  }

  function productById(productId) {
    const pid = Number(productId || 0);
    return productos.find((p) => Number(p.id) === pid) || null;
  }

  function productDefaultPrices(productId) {
    const product = productById(productId);
    const store = inputMoney(product?.default_price_store_ars, '');
    const online = inputMoney(product?.default_price_online_ars, store);
    return { store, online };
  }

  function onVariantProductChange(productId) {
    const defaults = productDefaultPrices(productId);
    setVarForm((prev) => ({
      ...prev,
      product_id: productId,
      price_store_ars: defaults.store || prev.price_store_ars,
      price_online_ars: defaults.online || defaults.store || prev.price_online_ars,
    }));
  }

  function openProductEditor(row) {
    if (!row) return;
    const defaultStore = inputMoney(row.default_price_store_ars, '0');
    const defaultOnline = inputMoney(row.default_price_online_ars, defaultStore || '0');
    setEditProductForm({
      id: row.id,
      name: row.name || '',
      sku_prefix: row.sku_prefix || '',
      default_cost_ars: String(row.default_cost_ars ?? 0),
      default_price_store_ars: defaultStore,
      default_price_online_ars: defaultOnline,
      original_default_price_store_ars: defaultStore,
      original_default_price_online_ars: defaultOnline,
      active: !!row.active,
    });
  }

  function closeProductEditor() {
    setEditProductForm({ ...EMPTY_EDIT_PRODUCT });
  }

  async function saveProductEditor() {
    if (!canEdit || !editProductForm?.id) return;
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      const pricesChanged =
        !sameMoney(editProductForm.default_price_store_ars, editProductForm.original_default_price_store_ars) ||
        !sameMoney(editProductForm.default_price_online_ars, editProductForm.original_default_price_online_ars);
      await patchRetailProducto(editProductForm.id, {
        name: editProductForm.name,
        sku_prefix: editProductForm.sku_prefix || undefined,
        default_cost_ars: Number(editProductForm.default_cost_ars || 0),
        default_price_store_ars: Number(editProductForm.default_price_store_ars || 0),
        default_price_online_ars: Number(editProductForm.default_price_online_ars || 0),
        sync_variant_prices: pricesChanged,
        active: !!editProductForm.active,
      });
      setMsg('Producto actualizado');
      closeProductEditor();
      await loadAll();
    } catch (error) {
      const suggestion = normalizeValueError(error);
      if (suggestion) {
        setErr(suggestion.detail || errMsg(error));
      } else {
        setErr(errMsg(error));
      }
    } finally {
      setSaving(false);
    }
  }

  function openAttrEditor(row) {
    if (!row) return;
    setEditAttrForm({
      id: row.id,
      name: row.name || '',
      code: row.code || '',
      sort_order: String(row.sort_order ?? 100),
      active: !!row.active,
    });
  }

  function closeAttrEditor() {
    setEditAttrForm({ ...EMPTY_EDIT_ATTR });
  }

  async function saveAttrEditor() {
    if (!canEdit || !editAttrForm?.id) return;
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await patchRetailAtributo(editAttrForm.id, {
        name: editAttrForm.name,
        code: editAttrForm.code,
        sort_order: Number(editAttrForm.sort_order || 100),
        active: !!editAttrForm.active,
      });
      setMsg('Atributo actualizado');
      closeAttrEditor();
      await loadAll();
    } catch (error) {
      const suggestion = normalizeValueError(error);
      if (suggestion) {
        setErr(suggestion.detail || errMsg(error));
      } else {
        setErr(errMsg(error));
      }
    } finally {
      setSaving(false);
    }
  }

  async function deleteAttr(row) {
    if (!canEdit) return;
    const aid = Number(row?.id || 0);
    if (!aid) return;
    const confirmed = window.confirm(`Eliminar atributo ${row?.name || ''}?`);
    if (!confirmed) return;
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      const resp = await deleteRetailAtributo(aid);
      if (resp?.mode === 'soft') {
        setMsg('Atributo en uso: se aplico baja logica.');
      } else {
        setMsg('Atributo eliminado.');
      }
      if (Number(editAttrForm?.id) === aid) closeAttrEditor();
      await loadAll();
    } catch (error) {
      const suggestion = normalizeValueError(error);
      setErr(suggestion?.detail || errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  function openVariantEditor(row) {
    if (!row) return;
    const rows = Array.isArray(row.option_values) && row.option_values.length
      ? row.option_values.map((opt) => ({
          attribute_code: attrCode(opt.attribute_code),
          value: opt.option_value || '',
          attribute_value_id: opt.attribute_value_id || undefined,
        }))
      : [];
    setEditVariantForm({
      id: row.id,
      display_name: row.display_name || '',
      sku: row.sku || '',
      barcode_internal: row.barcode_internal || '',
      original_barcode_internal: row.barcode_internal || '',
      price_store_ars: String(row.price_store_ars ?? 0),
      price_online_ars: String(row.price_online_ars ?? 0),
      cost_avg_ars: String(row.cost_avg_ars ?? 0),
      stock_min: String(row.stock_min ?? 0),
      active: !!row.active,
      option_rows: rows,
    });
    setEditVariantOpen(true);
  }

  function closeVariantEditor() {
    setEditVariantOpen(false);
    setEditVariantForm({ ...EMPTY_EDIT_VARIANT });
  }

  function availableAttrsForVariantEditRow(idx) {
    const rows = Array.isArray(editVariantForm.option_rows) ? editVariantForm.option_rows : [];
    const current = attrCode(rows[idx]?.attribute_code);
    const selected = new Set(
      rows
        .filter((_, i) => i !== idx)
        .map((row) => attrCode(row.attribute_code))
        .filter(Boolean)
    );

    return atributos.filter((a) => {
      if (a?.active === false) return false;
      const code = attrCode(a.code);
      return !selected.has(code) || code === current;
    });
  }

  function updateEditVariantOptionRow(idx, patch) {
    setEditVariantForm((prev) => ({
      ...prev,
      option_rows: (prev.option_rows || []).map((row, i) => (i === idx ? { ...row, ...patch } : row)),
    }));
  }

  function addEditVariantOptionRow() {
    setEditVariantForm((prev) => {
      const used = new Set((prev.option_rows || []).map((row) => attrCode(row.attribute_code)).filter(Boolean));
      const firstFree = atributos.find((a) => a?.active !== false && !used.has(attrCode(a.code)));
      return {
        ...prev,
        option_rows: [...(prev.option_rows || []), { attribute_code: firstFree ? firstFree.code : '', value: '' }],
      };
    });
  }

  function removeEditVariantOptionRow(idx) {
    setEditVariantForm((prev) => {
      const next = (prev.option_rows || []).filter((_, i) => i !== idx);
      return {
        ...prev,
        option_rows: next,
      };
    });
  }

  async function saveVariantEditor(e) {
    e.preventDefault();
    if (!canEdit || !editVariantForm?.id) return;
    setErr('');
    setMsg('');

    let option_values = null;
    try {
      option_values = buildOptionalOptionValues(editVariantForm.option_rows);
    } catch (error) {
      setErr(error?.message || errMsg(error));
      return;
    }

    setSaving(true);
    try {
      const payload = {
        display_name: editVariantForm.display_name || undefined,
        sku: editVariantForm.sku,
        price_store_ars: Number(editVariantForm.price_store_ars || 0),
        price_online_ars: Number(editVariantForm.price_online_ars || 0),
        cost_avg_ars: Number(editVariantForm.cost_avg_ars || 0),
        stock_min: Number(editVariantForm.stock_min || 0),
        active: !!editVariantForm.active,
      };
      if (option_values) {
        payload.option_values = option_values;
      }
      await patchRetailVariante(editVariantForm.id, payload);
      setMsg('Variante actualizada');
      closeVariantEditor();
      await loadAll();
    } catch (error) {
      const suggestion = normalizeValueError(error);
      setErr(suggestion?.detail || barcodeConflictDetail(error));
    } finally {
      setSaving(false);
    }
  }

  async function openBarcodeModalFromVariantEditor() {
    if (!editVariantForm?.id) return;
    const optionSignature = (editVariantForm.option_rows || [])
      .map((row) => {
        const attr = atributos.find((a) => attrCode(a.code) === attrCode(row.attribute_code));
        const attrName = attr?.name || row.attribute_code;
        const value = String(row.value || '').trim();
        if (attrName && value) return `${attrName}: ${value}`;
        return value || attrName || '';
      })
      .filter(Boolean)
      .join(' / ');
    const variant = {
      id: editVariantForm.id,
      producto: editVariantForm.display_name || 'Variante',
      option_signature: optionSignature,
      sku: editVariantForm.sku || '',
      barcode_internal: editVariantForm.original_barcode_internal || editVariantForm.barcode_internal || '',
    };
    closeVariantEditor();
    await openBarcodeModal(variant);
  }

  async function createProducto(e) {
    e.preventDefault();
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      if (prodImageFile) {
        const formData = new FormData();
        formData.append('name', prodForm.name);
        if (prodForm.sku_prefix) formData.append('sku_prefix', prodForm.sku_prefix);
        formData.append('default_price_store_ars', Number(prodForm.default_price_store_ars || 0));
        formData.append(
          'default_price_online_ars',
          Number(prodForm.default_price_online_ars || prodForm.default_price_store_ars || 0),
        );
        formData.append('image', prodImageFile);
        await postRetailProducto(formData);
      } else {
        await postRetailProducto({
          name: prodForm.name,
          sku_prefix: prodForm.sku_prefix || undefined,
          default_price_store_ars: Number(prodForm.default_price_store_ars || 0),
          default_price_online_ars: Number(prodForm.default_price_online_ars || prodForm.default_price_store_ars || 0),
        });
      }
      setProdForm({ ...EMPTY_PRODUCT });
      setProdImageFile(null);
      if (prodImageInputRef.current) prodImageInputRef.current.value = '';
      setMsg('Producto creado');
      await loadAll();
    } catch (error) {
      const suggestion = normalizeValueError(error);
      setErr(suggestion?.detail || errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function createAtributo(e) {
    e.preventDefault();
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await postRetailAtributo({ name: attrForm.name, code: attrForm.code });
      setAttrForm({ ...EMPTY_ATTR });
      setMsg('Atributo creado');
      await loadAll();
    } catch (error) {
      const suggestion = normalizeValueError(error);
      setErr(suggestion?.detail || errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function createVariante(e) {
    e.preventDefault();
    setSaving(true);
    setErr('');
    setMsg('');
    setDuplicateStockPrompt(null);
    try {
      const barcode = String(varForm.barcode_internal || '').trim();
      const supplierId = String(varForm.supplier_id || '').trim();
      const option_values = buildOptionValues(varForm.option_rows);
      const stockQty = Math.trunc(Number(varForm.stock_on_hand || 0));
      await postRetailVariante({
        product_id: Number(varForm.product_id),
        option_values,
        sku: varForm.sku || undefined,
        barcode_internal: barcode || undefined,
        supplier_id: supplierId ? Number(supplierId) : undefined,
        price_store_ars: Number(varForm.price_store_ars || 0),
        price_online_ars: Number(varForm.price_online_ars || 0),
        cost_avg_ars: Number(varForm.cost_avg_ars || 0),
        stock_on_hand: stockQty,
        stock_min: Number(varForm.stock_min || 0),
      });
      setVarForm({ ...EMPTY_VARIANT });
      setMsg(barcode ? 'Variante creada con barcode manual' : 'Variante creada con barcode EAN-13 generado');
      await loadAll();
    } catch (error) {
      const conflict = duplicateVariantConflict(error);
      const stockQty = Math.trunc(Number(varForm.stock_on_hand || 0));
      if (conflict && conflict.variant?.active !== false && Number.isFinite(stockQty) && stockQty > 0) {
        setDuplicateStockPrompt({
          detail: explainVariantCombinationError(error),
          variant: conflict.variant,
          qty: stockQty,
        });
      } else {
        setErr(explainVariantCombinationError(error));
      }
    } finally {
      setSaving(false);
    }
  }

  async function acceptDuplicateStockPrompt() {
    if (!canEdit || !duplicateStockPrompt?.variant?.id) return;
    const prompt = duplicateStockPrompt;
    const variantId = Number(prompt.variant.id);
    const qty = Math.trunc(Number(prompt.qty || 0));
    if (!Number.isInteger(variantId) || variantId <= 0 || !Number.isFinite(qty) || qty <= 0) {
      setDuplicateStockPrompt(null);
      return;
    }
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await patchRetailVariante(variantId, {
        stock_adjust_qty: qty,
        stock_adjust_note: 'Stock sumado desde alta de variante duplicada',
      });
      setDuplicateStockPrompt(null);
      setVarForm({ ...EMPTY_VARIANT });
      setMsg(`Se sumaron ${qty} unidad(es) al stock de ${variantLabel(prompt.variant)}.`);
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  function rejectDuplicateStockPrompt() {
    setDuplicateStockPrompt(null);
    setErr('');
    setMsg('No se modifico el stock.');
  }

  async function onBatchCreated(rows) {
    const createdCount = Array.isArray(rows) ? rows.length : 0;
    if (createdCount > 0) {
      setMsg(`Lote de variantes finalizado. Creadas: ${createdCount}.`);
      await loadAll();
    }
  }

  async function applyAdjust(variantId) {
    if (!canEdit) return;
    const qty = Number(adjustByVariant[variantId] || 0);
    if (!Number.isFinite(qty) || qty === 0) return;
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await patchRetailVariante(variantId, {
        stock_adjust_qty: Math.trunc(qty),
        stock_adjust_note: 'Ajuste manual desde productos',
      });
      setAdjustByVariant((prev) => ({ ...prev, [variantId]: '' }));
      setMsg('Stock ajustado');
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function deactivateVariant(row) {
    if (!canEdit) return;
    const variantId = Number(row?.id || 0);
    if (!variantId) return;
    const label = `${row?.producto || 'Variante'}${row?.option_signature ? ` (${row.option_signature})` : ''}`;
    if (!window.confirm(`Eliminar variante en RH y Tienda Nube?\n\n${label}`)) return;

    setSaving(true);
    setErr('');
    setMsg('');
    try {
      const resp = await deleteRetailVariante(variantId);
      if (resp?.mode === 'soft') {
        setMsg('Variante con historial: se aplico baja logica.');
      } else {
        setMsg('Variante eliminada.');
      }
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function hideVariant(row) {
    if (!canEdit) return;
    const variantId = Number(row?.id || 0);
    if (!variantId) return;
    const label = `${row?.producto || 'Variante'}${row?.option_signature ? ` (${row.option_signature})` : ''}`;
    if (!window.confirm(`Ocultar variante?\n\n${label}\n\nSe marcara como inactiva y dejara de verse en las pantallas normales.`)) return;

    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await patchRetailVariante(variantId, { active: false });
      setMsg('Variante oculta');
      if (Number(editVariantForm?.id) === variantId) closeVariantEditor();
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function hideProduct(row) {
    if (!canEdit) return;
    const productId = Number(row?.id || 0);
    if (!productId) return;
    const label = String(row?.name || 'Producto').trim() || `Producto #${productId}`;
    if (!window.confirm(`Ocultar producto?\n\n${label}\n\nSe marcara como inactivo y sus variantes activas tambien quedaran ocultas.`)) return;

    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await patchRetailProducto(productId, { active: false });
      setMsg('Producto oculto junto con sus variantes activas');
      if (Number(editProductForm?.id) === productId) closeProductEditor();
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function loadBarcodeRows(variantId, options = {}) {
    const keepState = Boolean(options.keepState);
    if (!variantId) return;
    setBarcodeModal((prev) => ({
      ...prev,
      loading: true,
      err: keepState ? prev.err : '',
      msg: keepState ? prev.msg : '',
    }));
    try {
      const resp = await getRetailVarianteBarcodes(variantId);
      setBarcodeModal((prev) => ({
        ...prev,
        rows: Array.isArray(resp?.barcodes) ? resp.barcodes : [],
        variant: resp?.variant || prev.variant,
        loading: false,
        err: '',
      }));
    } catch (error) {
      setBarcodeModal((prev) => ({
        ...prev,
        loading: false,
        err: errMsg(error),
      }));
    }
  }

  async function openBarcodeModal(row) {
    const prefs = loadBarcodePrintPrefs();
    setBarcodeModal({
      ...EMPTY_BARCODE_MODAL,
      printLayout: prefs.layout,
      printLabelWidthMm: prefs.labelWidthMm,
      printLabelHeightMm: prefs.labelHeightMm,
      open: true,
      variant: row,
    });
    await loadBarcodeRows(row?.id);
    if (canEdit) {
      setTimeout(() => barcodeModalInputRef.current?.focus(), 0);
    }
  }

  function closeBarcodeModal() {
    setBarcodeModal({ ...EMPTY_BARCODE_MODAL });
  }

  function openVariantDetails(row) {
    if (!row) return;
    setDetailModal({ open: true, variant: row });
  }

  function closeVariantDetails() {
    setDetailModal({ ...EMPTY_DETAIL_MODAL });
  }

  async function generateBarcodeFromModal() {
    if (!canEdit) return;
    const variantId = barcodeModal?.variant?.id;
    if (!variantId) return;
    setBarcodeModal((prev) => ({ ...prev, saving: true, err: '', msg: '' }));
    try {
      const supplierId = String(barcodeModal.supplierId || '').trim();
      const resp = await postRetailVarianteBarcodeGenerate(variantId, {
        supplier_id: supplierId ? Number(supplierId) : undefined,
        make_primary: true,
      });
      setBarcodeModal((prev) => ({
        ...prev,
        rows: Array.isArray(resp?.barcodes) ? resp.barcodes : prev.rows,
        saving: false,
        msg: 'EAN-13 generado',
      }));
      await loadAll();
    } catch (error) {
      setBarcodeModal((prev) => ({ ...prev, saving: false, err: errMsg(error) }));
    }
  }

  async function associateBarcodeFromModal(e) {
    e.preventDefault();
    if (!canEdit) return;
    const variantId = barcodeModal?.variant?.id;
    const code = String(barcodeModal.associateCode || '').trim();
    if (!variantId || !code) return;
    setBarcodeModal((prev) => ({ ...prev, saving: true, err: '', msg: '' }));
    try {
      const supplierId = String(barcodeModal.supplierId || '').trim();
      const resp = await postRetailVarianteBarcodeAssociate(variantId, {
        code,
        make_primary: true,
        force_move: Boolean(barcodeModal.forceMove),
        supplier_id: supplierId ? Number(supplierId) : undefined,
      });
      setBarcodeModal((prev) => ({
        ...prev,
        rows: Array.isArray(resp?.barcodes) ? resp.barcodes : prev.rows,
        associateCode: '',
        forceMove: false,
        saving: false,
        msg: 'Barcode asociado como principal',
      }));
      await loadAll();
      setTimeout(() => barcodeModalInputRef.current?.focus(), 0);
    } catch (error) {
      setBarcodeModal((prev) => ({ ...prev, saving: false, err: barcodeConflictDetail(error) }));
    }
  }

  async function setPrimaryBarcodeFromModal(barcodeId) {
    if (!canEdit) return;
    const variantId = barcodeModal?.variant?.id;
    if (!variantId || !barcodeId) return;
    setBarcodeModal((prev) => ({ ...prev, saving: true, err: '', msg: '' }));
    try {
      const resp = await postRetailVarianteBarcodePrimary(variantId, { barcode_id: barcodeId });
      setBarcodeModal((prev) => ({
        ...prev,
        rows: Array.isArray(resp?.barcodes) ? resp.barcodes : prev.rows,
        saving: false,
        msg: 'Barcode principal actualizado',
      }));
      await loadAll();
    } catch (error) {
      setBarcodeModal((prev) => ({ ...prev, saving: false, err: errMsg(error) }));
    }
  }

  function openBarcodeLabelsPdf(scope = 'primary', code = '') {
    const variantId = barcodeModal?.variant?.id;
    if (!variantId) return;
    const copies = Math.max(1, Math.min(200, Number(barcodeModal.printCopies || 1)));
    const layout = normalizePrintLayout(barcodeModal.printLayout);
    const widthMm = normalizePrintMm(barcodeModal.printLabelWidthMm, DEFAULT_PRINT_PREFS.labelWidthMm);
    const heightMm = normalizePrintMm(barcodeModal.printLabelHeightMm, DEFAULT_PRINT_PREFS.labelHeightMm);
    saveBarcodePrintPrefs({
      layout,
      labelWidthMm: widthMm,
      labelHeightMm: heightMm,
    });

    const params = {
      scope,
      copies,
      code: code || undefined,
      layout,
    };
    if (layout === PRINT_LAYOUTS.THERMAL) {
      params.label_width_mm = widthMm;
      params.label_height_mm = heightMm;
    }
    const url = getRetailVarianteBarcodeLabelsUrl(variantId, {
      ...params,
    });
    const win = window.open(url, '_blank', 'noopener,noreferrer');
    if (!win) {
      setBarcodeModal((prev) => ({ ...prev, err: 'No se pudo abrir la ventana de impresion (bloqueada por el navegador)' }));
    }
  }

  const usedAttrs = new Set((varForm.option_rows || []).map((row) => attrCode(row.attribute_code)).filter(Boolean));
  const activeAttrCount = atributos.filter((a) => a?.active !== false).length;
  const canAddOptionRow = activeAttrCount === 0 || usedAttrs.size < activeAttrCount;
  const usedEditAttrs = new Set((editVariantForm.option_rows || []).map((row) => attrCode(row.attribute_code)).filter(Boolean));
  const canAddEditOptionRow = activeAttrCount === 0 || usedEditAttrs.size < activeAttrCount;
  const totalProductos = productos.length;
  const totalVariantes = variantes.length;
  const failedSyncTotal = Number(onlineSyncSummary?.failed_total || 0);
  const syncStatusAvailable = Boolean(onlineSyncSummary?.statusAvailable);
  const hasFailedSync = syncStatusAvailable && failedSyncTotal > 0;
  const detailVariant = detailModal.open
    ? (variantes.find((row) => Number(row.id) === Number(detailModal.variant?.id)) || detailModal.variant)
    : null;
  const detailSupplier = detailVariant ? variantSupplierSummary(detailVariant) : null;
  const detailRelatedVariants = detailVariant
    ? variantes.filter((row) => Number(row.product_id) === Number(detailVariant.product_id) && Number(row.id) !== Number(detailVariant.id))
    : [];

  return (
    <div className="space-y-4">
      <div className="card">
        <HelpTitle
          as="h1"
          className="h1"
          help="Aca se administra el catalogo interno. Un producto agrupa las variantes; cada variante tiene SKU, stock, precio, barcode y atributos para vender localmente y sincronizar con Tienda Nube."
        >
          Productos y variantes
        </HelpTitle>
        <p className="text-sm text-gray-600">
          Catalogo retail unificado. Variantes con atributos configurables y stock global por SKU/barcode.
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-neutral-700">
            Productos activos RH: {totalProductos}
          </span>
          <span className="rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-neutral-700">
            Variantes activas RH: {totalVariantes}
          </span>
          {canSeeOnlineSyncStatus ? (
            <span
              className={`rounded-full border px-3 py-1 ${
                hasFailedSync
                  ? 'border-red-300 bg-red-50 text-red-700 font-semibold'
                  : 'border-neutral-200 bg-neutral-50 text-neutral-700'
              }`}
            >
              {syncStatusAvailable ? (hasFailedSync ? `Sync TN fallidos: ${failedSyncTotal}` : 'Sync TN: OK') : 'Sync TN: sin estado'}
            </span>
          ) : null}
          {canSeeOnlineSyncStatus && canGoOnline ? (
            <Link
              to="/online"
              className="rounded-full border border-neutral-200 bg-white px-3 py-1 text-neutral-700 hover:bg-neutral-100"
            >
              Ver Online
            </Link>
          ) : null}
          {canSeeOnlineSyncStatus && onlineSyncSummary.loading ? (
            <span className="rounded-full border border-neutral-200 bg-neutral-50 px-3 py-1 text-neutral-500">
              Sync TN: actualizando...
            </span>
          ) : null}
        </div>
      </div>

      {canEdit ? (
        <div className="card space-y-3">
          <div className="flex items-center justify-between gap-3">
            <HelpTitle
              as="h2"
              className="text-lg font-semibold"
              help="Desde este bloque se cargan las piezas basicas del catalogo: primero producto, luego atributos si faltan, y finalmente variantes vendibles."
            >
              Altas
            </HelpTitle>
            <button
              type="button"
              className="btn"
              aria-expanded={createMenuOpen}
              aria-controls="productos-create-panel"
              onClick={() => setCreateMenuOpen((prev) => !prev)}
            >
              Nuevo
            </button>
          </div>

          {createMenuOpen ? (
            <div id="productos-create-panel" className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <form className="rounded-xl border border-neutral-200 bg-white p-4 space-y-3" onSubmit={createProducto}>
                  <HelpTitle
                    as="h3"
                    className="text-lg font-semibold"
                    help="Crea el item base, por ejemplo Remera Basica. No representa un talle o color puntual: sirve para agrupar todas sus variantes bajo el mismo producto."
                  >
                    Nuevo producto
                  </HelpTitle>
                  <input
                    className="input"
                    placeholder="Nombre interno"
                    value={prodForm.name}
                    onChange={(e) => setProdForm((v) => ({ ...v, name: e.target.value }))}
                    required
                  />
                  <input
                    className="input"
                    placeholder="Prefijo SKU (ej CHU-BLU)"
                    value={prodForm.sku_prefix}
                    onChange={(e) => setProdForm((v) => ({ ...v, sku_prefix: e.target.value }))}
                  />
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <input
                      className="input"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Precio local"
                      value={prodForm.default_price_store_ars}
                      onChange={(e) => {
                        const value = e.target.value;
                        setProdForm((v) => ({
                          ...v,
                          default_price_store_ars: value,
                          default_price_online_ars: v.default_price_online_ars || value,
                        }));
                      }}
                    />
                    <input
                      className="input"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Precio online"
                      value={prodForm.default_price_online_ars}
                      onChange={(e) => setProdForm((v) => ({ ...v, default_price_online_ars: e.target.value }))}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Imagen del producto (opcional)</label>
                    <input
                      ref={prodImageInputRef}
                      className="input"
                      type="file"
                      accept="image/png,image/jpeg,image/webp,image/gif"
                      onChange={(e) => setProdImageFile(e.target.files?.[0] || null)}
                    />
                  </div>
                  <button className="btn" disabled={saving} type="submit">Crear producto</button>
                </form>

                <form className="rounded-xl border border-neutral-200 bg-white p-4 space-y-3" onSubmit={createAtributo}>
                  <HelpTitle
                    as="h3"
                    className="text-lg font-semibold"
                    help="Crea una caracteristica reutilizable, como Talle o Color. Luego cada variante recibe un valor de ese atributo, por ejemplo Talle M o Color Negro."
                  >
                    Nuevo atributo
                  </HelpTitle>
                  <input
                    className="input"
                    placeholder="Nombre (ej Talle)"
                    value={attrForm.name}
                    onChange={(e) => setAttrForm((v) => ({ ...v, name: e.target.value }))}
                    required
                  />
                  <input
                    className="input"
                    placeholder="Code (ej talle)"
                    value={attrForm.code}
                    onChange={(e) => setAttrForm((v) => ({ ...v, code: e.target.value }))}
                    required
                  />
                  <button className="btn" disabled={saving} type="submit">Crear atributo</button>
                </form>
              </div>

              <form className="rounded-xl border border-neutral-200 bg-white p-4 space-y-3" onSubmit={createVariante}>
                <HelpTitle
                  as="h3"
                  className="text-lg font-semibold"
                  help="Crea una unidad vendible concreta del producto. Esta variante tiene SKU, barcode, stock, precios y valores de atributos; por ejemplo Remera Basica, Color Negro, Talle M."
                >
                  Nueva variante
                </HelpTitle>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  <div className="space-y-1">
                    <label className="block text-xs text-gray-500">Producto</label>
                    <select
                      className="input"
                      value={varForm.product_id}
                      onChange={(e) => onVariantProductChange(e.target.value)}
                      required
                    >
                      <option value="">Seleccionar producto</option>
                      {productos.map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="block text-xs text-gray-500">SKU (opcional)</label>
                    <input
                      className="input"
                      placeholder="Ej: CHU-NEG-S"
                      value={varForm.sku}
                      onChange={(e) => setVarForm((v) => ({ ...v, sku: e.target.value }))}
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="block text-xs text-gray-500">Codigo de barras (opcional)</label>
                    <div className="flex items-center gap-2">
                      <input
                        ref={barcodeInputRef}
                        className="input flex-1"
                        placeholder="Escanear o escribir EAN-13 (si lo dejas vacio, se genera)"
                        value={varForm.barcode_internal}
                        onChange={(e) => setVarForm((v) => ({ ...v, barcode_internal: e.target.value }))}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') e.preventDefault();
                        }}
                      />
                      <button
                        type="button"
                        className="px-3 py-2 rounded border whitespace-nowrap"
                        onClick={() => barcodeInputRef.current?.focus()}
                      >
                        Escanear
                      </button>
                    </div>
                    <p className="text-xs text-gray-500">Solo EAN-13 para nuevos codigos. Si queda vacio, el sistema genera automaticamente.</p>
                  </div>

                  <div className="space-y-1">
                    <label className="block text-xs text-gray-500">Proveedor para autogenerar (opcional)</label>
                    <select
                      className="input"
                      value={varForm.supplier_id || ''}
                      onChange={(e) => setVarForm((v) => ({ ...v, supplier_id: e.target.value }))}
                    >
                      <option value="">Sin especificar (codigo proveedor generico)</option>
                      {suppliers.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}{s.ean_supplier_code ? ` - EAN Prov ${s.ean_supplier_code}` : ' - sin codigo EAN'}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="block text-xs text-gray-500">Precio local</label>
                    <input
                      className="input"
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="0.00"
                      value={varForm.price_store_ars}
                      onChange={(e) => setVarForm((v) => ({ ...v, price_store_ars: e.target.value }))}
                      required
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="block text-xs text-gray-500">Precio online</label>
                    <input
                      className="input"
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="0.00"
                      value={varForm.price_online_ars}
                      onChange={(e) => setVarForm((v) => ({ ...v, price_online_ars: e.target.value }))}
                      required
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="block text-xs text-gray-500">Costo promedio</label>
                    <input
                      className="input"
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="0.00"
                      value={varForm.cost_avg_ars}
                      onChange={(e) => setVarForm((v) => ({ ...v, cost_avg_ars: e.target.value }))}
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="block text-xs text-gray-500">Stock inicial</label>
                    <input
                      className="input"
                      type="number"
                      min="0"
                      placeholder="0"
                      value={varForm.stock_on_hand}
                      onChange={(e) => setVarForm((v) => ({ ...v, stock_on_hand: e.target.value }))}
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="block text-xs text-gray-500">Stock minimo</label>
                    <input
                      className="input"
                      type="number"
                      min="0"
                      placeholder="0"
                      value={varForm.stock_min}
                      onChange={(e) => setVarForm((v) => ({ ...v, stock_min: e.target.value }))}
                    />
                  </div>
                </div>

                <VariantAttributeRows
                  rows={varForm.option_rows || []}
                  attributes={atributos}
                  attributeValuesByCode={attrValuesByCode}
                  getAvailableAttributesForRow={availableAttrsForRow}
                  onUpdateRow={updateOptionRow}
                  onRemoveRow={removeOptionRow}
                  onAddRow={addOptionRow}
                  canAddRow={canAddOptionRow}
                  disabled={saving}
                  title="Atributos de la variante"
                  help="Define que valores distinguen esta variante dentro del producto. Elegir valores ya existentes evita duplicados como Negro, negro o NEGRO."
                  listIdPrefix="product-create-variant-attr-values"
                />

                {duplicateStockPrompt ? (
                  <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
                    <p className="font-semibold">{duplicateStockPrompt.detail}</p>
                    <p className="mt-1">
                      Desea sumar {duplicateStockPrompt.qty} unidad(es) al stock de {variantLabel(duplicateStockPrompt.variant)}?
                    </p>
                    <p className="mt-1 text-xs text-amber-800">
                      Stock actual: {Number(duplicateStockPrompt.variant?.stock_on_hand || 0)}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button type="button" className="btn" onClick={acceptDuplicateStockPrompt} disabled={saving}>
                        Aceptar
                      </button>
                      <button type="button" className="px-3 py-2 rounded border bg-white" onClick={rejectDuplicateStockPrompt} disabled={saving}>
                        Rechazar
                      </button>
                    </div>
                  </div>
                ) : null}

                <button className="btn" disabled={saving} type="submit">Crear variante</button>
              </form>

              <VariantBatchCreator
                title="Alta masiva por combinaciones"
                products={productos}
                attributes={atributos}
                attributeValuesByCode={attrValuesByCode}
                suppliers={suppliers}
                canEdit={canEdit}
                onBatchFinished={onBatchCreated}
              />
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="card grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <div className="md:col-span-3">
          <label className="block text-xs text-gray-500 mb-1">Buscar variante</label>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="SKU, barcode o nombre producto" />
        </div>
        <button className="px-3 py-2 rounded border" type="button" onClick={loadAll} disabled={loading}>Filtrar</button>
      </div>

      {canEdit ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="card space-y-3">
            <HelpTitle
              as="h2"
              className="text-lg font-semibold"
              help="Lista de productos base. Cada fila puede tener una o varias variantes asociadas para talles, colores u otras opciones."
            >
              Productos
            </HelpTitle>
            <div className="overflow-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left border-b">
                    <th className="py-2 pr-3">Nombre interno</th>
                    <th className="py-2 pr-3">SKU prefix</th>
                    <th className="py-2 pr-3">Precio base</th>
                    <th className="py-2 pr-3">Variantes</th>
                    <th className="py-2 pr-3">Accion</th>
                  </tr>
                </thead>
                <tbody>
                  {productos.map((row) => (
                    <tr key={row.id} className="border-b last:border-b-0">
                      <td className="py-2 pr-3">{row.name}</td>
                      <td className="py-2 pr-3">{row.sku_prefix || '-'}</td>
                      <td className="py-2 pr-3">
                        <div>Local: {money(row.default_price_store_ars)}</div>
                        <div className="text-xs text-gray-500">Online: {money(row.default_price_online_ars)}</div>
                      </td>
                      <td className="py-2 pr-3">{Number(row.variantes || 0)}</td>
                      <td className="py-2 pr-3">
                        <div className="flex flex-wrap gap-2">
                          <button type="button" className="px-2 py-1 rounded border text-xs" onClick={() => openProductEditor(row)}>
                            Editar
                          </button>
                          <button
                            type="button"
                            className="px-2 py-1 rounded border text-xs text-amber-700 border-amber-300 hover:bg-amber-50"
                            onClick={() => hideProduct(row)}
                            disabled={saving}
                          >
                            Ocultar
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!productos.length ? (
                    <tr>
                      <td colSpan={5} className="py-3 text-gray-500">Sin productos para mostrar.</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>

            {editProductForm?.id ? (
              <div className="rounded-xl border border-neutral-200 p-3 space-y-2">
                <HelpTitle
                  as="h3"
                  className="text-sm font-semibold"
                  help="Modifica los datos generales del producto base. Los cambios de precios por defecto pueden propagarse a variantes cuando corresponda."
                >
                  Editar producto #{editProductForm.id}
                </HelpTitle>
                <input
                  className="input"
                  value={editProductForm.name}
                  onChange={(e) => setEditProductForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="Nombre interno"
                />
                <input
                  className="input"
                  value={editProductForm.sku_prefix}
                  onChange={(e) => setEditProductForm((prev) => ({ ...prev, sku_prefix: e.target.value }))}
                  placeholder="Prefijo SKU"
                />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  <input
                    className="input"
                    type="number"
                    min="0"
                    step="0.01"
                    value={editProductForm.default_price_store_ars}
                    onChange={(e) => {
                      const value = e.target.value;
                      setEditProductForm((prev) => ({
                        ...prev,
                        default_price_store_ars: value,
                        default_price_online_ars: prev.default_price_online_ars || value,
                      }));
                    }}
                    placeholder="Precio base local"
                  />
                  <input
                    className="input"
                    type="number"
                    min="0"
                    step="0.01"
                    value={editProductForm.default_price_online_ars}
                    onChange={(e) => setEditProductForm((prev) => ({ ...prev, default_price_online_ars: e.target.value }))}
                    placeholder="Precio base online"
                  />
                </div>
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.01"
                  value={editProductForm.default_cost_ars}
                  onChange={(e) => setEditProductForm((prev) => ({ ...prev, default_cost_ars: e.target.value }))}
                  placeholder="Costo default"
                />
                <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
                  <input
                    type="checkbox"
                    checked={!!editProductForm.active}
                    onChange={(e) => setEditProductForm((prev) => ({ ...prev, active: e.target.checked }))}
                  />
                  Activo
                </label>
                <div className="flex gap-2">
                  <button type="button" className="btn" onClick={saveProductEditor} disabled={saving}>Guardar</button>
                  <button
                    type="button"
                    className="px-3 py-2 rounded border text-amber-700 border-amber-300 hover:bg-amber-50"
                    onClick={() => hideProduct(editProductForm)}
                    disabled={saving}
                  >
                    Ocultar producto
                  </button>
                  <button type="button" className="px-3 py-2 rounded border" onClick={closeProductEditor}>Cancelar</button>
                </div>
              </div>
            ) : null}
          </div>

          <div className="card space-y-3">
            <HelpTitle
              as="h2"
              className="text-lg font-semibold"
              help="Catalogo de atributos reutilizables para variantes. Mantenerlo ordenado ayuda a que RetailHub y Tienda Nube hablen el mismo idioma."
            >
              Atributos
            </HelpTitle>
            <div className="overflow-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left border-b">
                    <th className="py-2 pr-3">Nombre</th>
                    <th className="py-2 pr-3">Code</th>
                    <th className="py-2 pr-3">Orden</th>
                    <th className="py-2 pr-3">Activo</th>
                    <th className="py-2 pr-3">Accion</th>
                  </tr>
                </thead>
                <tbody>
                  {atributos.map((row) => (
                    <tr key={row.id} className="border-b last:border-b-0">
                      <td className="py-2 pr-3">{row.name}</td>
                      <td className="py-2 pr-3">{row.code}</td>
                      <td className="py-2 pr-3">{row.sort_order}</td>
                      <td className="py-2 pr-3">{row.active ? 'Si' : 'No'}</td>
                      <td className="py-2 pr-3">
                        <div className="flex gap-2">
                          <button type="button" className="px-2 py-1 rounded border text-xs" onClick={() => openAttrEditor(row)}>
                            Editar
                          </button>
                          <button
                            type="button"
                            className="px-2 py-1 rounded border text-xs text-red-700 border-red-300 hover:bg-red-50"
                            onClick={() => deleteAttr(row)}
                            disabled={saving}
                          >
                            Eliminar
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!atributos.length ? (
                    <tr>
                      <td colSpan={5} className="py-3 text-gray-500">Sin atributos para mostrar.</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>

            {editAttrForm?.id ? (
              <div className="rounded-xl border border-neutral-200 p-3 space-y-2">
                <HelpTitle
                  as="h3"
                  className="text-sm font-semibold"
                  help="Ajusta el nombre visible o estado del atributo. El codigo no se puede cambiar cuando ya esta usado para evitar romper variantes existentes."
                >
                  Editar atributo #{editAttrForm.id}
                </HelpTitle>
                <input
                  className="input"
                  value={editAttrForm.name}
                  onChange={(e) => setEditAttrForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="Nombre"
                />
                <input
                  className="input"
                  value={editAttrForm.code}
                  onChange={(e) => setEditAttrForm((prev) => ({ ...prev, code: e.target.value }))}
                  placeholder="Code"
                />
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="1"
                  value={editAttrForm.sort_order}
                  onChange={(e) => setEditAttrForm((prev) => ({ ...prev, sort_order: e.target.value }))}
                  placeholder="Sort order"
                />
                <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
                  <input
                    type="checkbox"
                    checked={!!editAttrForm.active}
                    onChange={(e) => setEditAttrForm((prev) => ({ ...prev, active: e.target.checked }))}
                  />
                  Activo
                </label>
                <div className="flex gap-2">
                  <button type="button" className="btn" onClick={saveAttrEditor} disabled={saving}>Guardar</button>
                  <button type="button" className="px-3 py-2 rounded border" onClick={closeAttrEditor}>Cancelar</button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="card">
        <div className="flex items-center justify-between mb-2">
          <HelpTitle
            as="h2"
            className="text-lg font-semibold"
            help="Lista de variantes vendibles. Cada variante descuenta stock, puede tener barcode propio y se sincroniza como una variante del producto en Tienda Nube."
          >
            Variantes
          </HelpTitle>
          <span className="text-xs text-gray-500">Atributos cargados: {atributos.length}</span>
        </div>
        {loading ? <p className="text-sm text-gray-500">Cargando...</p> : null}
        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="py-2 pr-3">Img</th>
                <th className="py-2 pr-3">SKU</th>
                <th className="py-2 pr-3">Producto</th>
                <th className="py-2 pr-3">Proveedor / articulo</th>
                <th className="py-2 pr-3">Precios</th>
                <th className="py-2 pr-3">Stock</th>
                <th className="py-2 pr-3">Ajuste</th>
                <th className="py-2 pr-3">Barcodes</th>
                <th className="py-2 pr-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {variantes.map((row) => {
                const supplier = variantSupplierSummary(row);
                const primary = primaryBarcode(row);
                return (
                  <tr key={row.id} className="border-b last:border-b-0 align-top">
                  <td className="py-2 pr-3">
                    {row.product_image_url ? (
                      <img
                        src={row.product_image_url}
                        alt={row.producto || 'Producto'}
                        className="h-10 w-10 rounded object-cover border border-neutral-200"
                        loading="lazy"
                      />
                    ) : (
                      <div className="h-10 w-10 rounded border border-neutral-200 bg-neutral-50 text-[10px] text-neutral-400 flex items-center justify-center">
                        -
                      </div>
                    )}
                  </td>
                  <td className="py-2 pr-3">
                    {row.sku}
                  </td>
                  <td className="py-2 pr-3">
                    {row.producto}
                    <div className="text-xs text-gray-500">{row.option_signature}</div>
                  </td>
                  <td className="py-2 pr-3">
                    <div className="min-w-[210px] max-w-[280px] space-y-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-medium text-gray-800">{supplier.name}</span>
                        <span className="rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[10px] font-semibold uppercase text-neutral-500">
                          {supplier.source}
                        </span>
                      </div>
                      <div className="text-[11px] text-gray-500">
                        {supplier.article ? `Articulo: ${supplier.article}` : 'Articulo: -'}
                        {supplier.barcode ? ` - Codigo: ${supplier.barcode}` : ''}
                      </div>
                      {row.last_purchase_supplier_product_name ? (
                        <div className="text-[11px] text-gray-400">
                          Ultima compra: {row.last_purchase_supplier_product_name}
                          {row.last_purchase_date ? ` (${fmtDate(row.last_purchase_date)})` : ''}
                        </div>
                      ) : null}
                      {!row.last_purchase_supplier_product_name && primary?.barcode && !supplier.article ? (
                        <div className="text-[11px] text-gray-400">Barcode principal sin articulo de proveedor</div>
                      ) : null}
                    </div>
                  </td>
                  <td className="py-2 pr-3">
                    <div>Local: {money(row.price_store_ars)}</div>
                    <div>Online: {money(row.price_online_ars)}</div>
                  </td>
                  <td className={`py-2 pr-3 ${Number(row.stock_on_hand) <= Number(row.stock_min) ? 'text-red-700 font-semibold' : ''}`}>
                    {row.stock_on_hand} (min {row.stock_min})
                  </td>
                  <td className="py-2 pr-3">
                    <div className="flex items-center gap-2">
                      <input
                        className="input w-24"
                        placeholder="+/-"
                        value={adjustByVariant[row.id] || ''}
                        onChange={(e) => setAdjustByVariant((prev) => ({ ...prev, [row.id]: e.target.value }))}
                        disabled={!canEdit}
                      />
                      {canEdit ? (
                        <button type="button" className="px-2 py-1 rounded border" onClick={() => applyAdjust(row.id)} disabled={saving}>
                          Aplicar
                        </button>
                      ) : null}
                    </div>
                  </td>
                  <td className="py-2 pr-3">
                    <div className="space-y-2 min-w-[220px]">
                      <div>
                        <div className="text-xs text-gray-700">{row.barcode_internal || 'Sin barcode principal'}</div>
                        <div className="text-[11px] text-gray-400">
                          {Math.max(Number(row.barcode_count || 0), row.barcode_internal ? 1 : 0)} codigos vinculados
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          className="px-2 py-1 rounded border text-xs"
                          onClick={() => openBarcodeModal(row)}
                          disabled={saving}
                        >
                          {canEdit ? 'Gestionar' : 'Ver'}
                        </button>
                        <button
                          type="button"
                          className="px-2 py-1 rounded border text-xs"
                          onClick={() => {
                            const prefs = loadBarcodePrintPrefs();
                            const layout = normalizePrintLayout(prefs.layout);
                            const params = {
                              scope: 'primary',
                              copies: 1,
                              layout,
                            };
                            if (layout === PRINT_LAYOUTS.THERMAL) {
                              params.label_width_mm = normalizePrintMm(prefs.labelWidthMm, DEFAULT_PRINT_PREFS.labelWidthMm);
                              params.label_height_mm = normalizePrintMm(prefs.labelHeightMm, DEFAULT_PRINT_PREFS.labelHeightMm);
                            }
                            const url = getRetailVarianteBarcodeLabelsUrl(row.id, params);
                            window.open(url, '_blank', 'noopener,noreferrer');
                          }}
                        >
                          Imprimir
                        </button>
                      </div>
                    </div>
                  </td>
                  <td className="py-2 pr-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        className="px-2 py-1 rounded border text-xs"
                        onClick={() => openVariantDetails(row)}
                        disabled={saving}
                      >
                        Detalles
                      </button>
                      <button
                        type="button"
                        className="px-2 py-1 rounded border text-xs"
                        onClick={() => openVariantEditor(row)}
                        disabled={saving || !canEdit}
                      >
                        Editar variante
                      </button>
                      {canEdit ? (
                        <button
                          type="button"
                          className="px-2 py-1 rounded border text-xs text-amber-700 border-amber-300 hover:bg-amber-50"
                          onClick={() => hideVariant(row)}
                          disabled={saving}
                        >
                          Ocultar
                        </button>
                      ) : null}
                      {canEdit ? (
                        <button
                          type="button"
                          className="px-2 py-1 rounded border text-xs text-red-700 border-red-300 hover:bg-red-50"
                          onClick={() => deactivateVariant(row)}
                          disabled={saving}
                        >
                          Eliminar
                        </button>
                      ) : null}
                    </div>
                  </td>
                  </tr>
                );
              })}
              {!variantes.length && !loading ? (
                <tr>
                  <td className="py-3 text-gray-500" colSpan={9}>Sin variantes para mostrar.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {detailVariant ? (
        <div className="fixed inset-0 z-50 bg-black/40 p-3 md:p-6 overflow-auto">
          <div className="mx-auto w-full max-w-6xl rounded-xl border border-neutral-200 bg-white p-4 space-y-4">
            <div className="flex items-start justify-between gap-3 border-b border-neutral-100 pb-3">
              <div className="flex min-w-0 gap-3">
                {detailVariant.product_image_url ? (
                  <img
                    src={detailVariant.product_image_url}
                    alt={detailVariant.producto || 'Producto'}
                    className="h-16 w-16 rounded object-cover border border-neutral-200"
                    loading="lazy"
                  />
                ) : (
                  <div className="h-16 w-16 shrink-0 rounded border border-neutral-200 bg-neutral-50 text-xs text-neutral-400 flex items-center justify-center">
                    -
                  </div>
                )}
                <div className="min-w-0">
                  <h3 className="text-lg font-semibold leading-tight">{detailVariant.producto || 'Variante'}</h3>
                  <p className="text-sm text-gray-600">{variantOptionsText(detailVariant)}</p>
                  <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
                    <span>SKU: {detailValue(detailVariant.sku)}</span>
                    <span>ID variante: {detailValue(detailVariant.id)}</span>
                    <span className={detailVariant.active ? 'text-green-700' : 'text-amber-700'}>
                      {detailVariant.active ? 'Activa' : 'Oculta'}
                    </span>
                  </div>
                </div>
              </div>
              <button type="button" className="px-3 py-2 rounded border" onClick={closeVariantDetails}>
                Cerrar
              </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div className="rounded-xl border border-neutral-200 p-3">
                <h4 className="text-sm font-semibold mb-2">Proveedor destacado</h4>
                <div className="space-y-1 text-sm">
                  <div className="font-medium text-gray-900">{detailSupplier?.name || 'Sin proveedor vinculado'}</div>
                  <div className="text-xs text-gray-500">Fuente: {detailSupplier?.source || '-'}</div>
                  <div className="text-xs text-gray-500">Articulo: {detailValue(detailSupplier?.article)}</div>
                  <div className="text-xs text-gray-500">Codigo: {detailValue(detailSupplier?.barcode)}</div>
                  <div className="text-xs text-gray-500">EAN proveedor: {detailValue(detailSupplier?.ean)}</div>
                </div>
              </div>

              <div className="rounded-xl border border-neutral-200 p-3">
                <h4 className="text-sm font-semibold mb-2">Precios y stock</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div><div className="text-xs text-gray-500">Precio local</div><div className="font-medium">{money(detailVariant.price_store_ars)}</div></div>
                  <div><div className="text-xs text-gray-500">Precio online</div><div className="font-medium">{money(detailVariant.price_online_ars)}</div></div>
                  <div><div className="text-xs text-gray-500">Stock actual</div><div className="font-medium">{detailValue(detailVariant.stock_on_hand)}</div></div>
                  <div><div className="text-xs text-gray-500">Stock minimo</div><div className="font-medium">{detailValue(detailVariant.stock_min)}</div></div>
                  <div><div className="text-xs text-gray-500">Reservado</div><div className="font-medium">{detailValue(detailVariant.stock_reserved)}</div></div>
                  <div><div className="text-xs text-gray-500">Costo promedio</div><div className="font-medium">{detailVariant.cost_avg_ars === null ? '-' : money(detailVariant.cost_avg_ars)}</div></div>
                </div>
              </div>

              <div className="rounded-xl border border-neutral-200 p-3">
                <h4 className="text-sm font-semibold mb-2">Catalogo online</h4>
                <div className="space-y-1 text-sm">
                  <div className="text-xs text-gray-500">Producto Tienda Nube: {detailValue(detailVariant.tiendanube_product_id)}</div>
                  <div className="text-xs text-gray-500">Variante Tienda Nube: {detailValue(detailVariant.tiendanube_variant_id)}</div>
                  <div className="text-xs text-gray-500">Creada: {fmtDateTime(detailVariant.created_at)}</div>
                  <div className="text-xs text-gray-500">Actualizada: {fmtDateTime(detailVariant.updated_at)}</div>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-neutral-200 p-3">
              <h4 className="text-sm font-semibold mb-2">Ultima compra</h4>
              {detailVariant.last_purchase_date || detailVariant.last_purchase_supplier_name || detailVariant.last_purchase_supplier_product_name ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
                  <div>
                    <div className="text-xs text-gray-500">Proveedor</div>
                    <div className="font-medium">{detailValue(detailVariant.last_purchase_supplier_name)}</div>
                    <div className="text-xs text-gray-500">EAN proveedor: {detailValue(detailVariant.last_purchase_supplier_ean_code)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Fecha / comprobante</div>
                    <div className="font-medium">{fmtDate(detailVariant.last_purchase_date)}</div>
                    <div className="text-xs text-gray-500">Comprobante: {detailValue(detailVariant.last_purchase_invoice_number)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Articulo proveedor</div>
                    <div className="font-medium">{detailValue(detailVariant.last_purchase_supplier_product_name)}</div>
                    <div className="text-xs text-gray-500">Cantidad: {detailValue(detailVariant.last_purchase_quantity)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Costo unitario</div>
                    <div className="font-medium">{detailVariant.last_purchase_unit_cost_currency === null ? '-' : money(detailVariant.last_purchase_unit_cost_currency)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Markup sugerido</div>
                    <div className="font-medium">{detailVariant.last_purchase_suggested_markup_pct === null || detailVariant.last_purchase_suggested_markup_pct === undefined ? '-' : `${detailVariant.last_purchase_suggested_markup_pct}%`}</div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-500">No hay compras registradas para esta variante.</p>
              )}
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
              <div className="rounded-xl border border-neutral-200 p-3">
                <h4 className="text-sm font-semibold mb-2">Codigos asociados</h4>
                {variantBarcodes(detailVariant).length ? (
                  <div className="overflow-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="text-left border-b">
                          <th className="py-2 pr-3">Codigo</th>
                          <th className="py-2 pr-3">Proveedor</th>
                          <th className="py-2 pr-3">Articulo</th>
                          <th className="py-2 pr-3">Origen</th>
                        </tr>
                      </thead>
                      <tbody>
                        {variantBarcodes(detailVariant).map((barcode) => (
                          <tr key={barcode.id || barcode.barcode} className="border-b last:border-b-0">
                            <td className="py-2 pr-3">
                              <span className={barcode.is_primary ? 'font-semibold text-green-700' : ''}>{barcode.barcode}</span>
                              {barcode.is_primary ? <div className="text-[11px] text-green-700">Principal</div> : null}
                            </td>
                            <td className="py-2 pr-3">
                              {barcode.supplier_name || 'Sin especificar'}
                              {barcode.supplier_ean_code ? <div className="text-[11px] text-gray-500">EAN Prov {barcode.supplier_ean_code}</div> : null}
                            </td>
                            <td className="py-2 pr-3">{barcode.supplier_item_code || '-'}</td>
                            <td className="py-2 pr-3">{barcode.source || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">La variante no tiene codigos asociados.</p>
                )}
              </div>

              <div className="rounded-xl border border-neutral-200 p-3">
                <h4 className="text-sm font-semibold mb-2">Otras variantes del producto</h4>
                {detailRelatedVariants.length ? (
                  <div className="overflow-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="text-left border-b">
                          <th className="py-2 pr-3">SKU</th>
                          <th className="py-2 pr-3">Atributos</th>
                          <th className="py-2 pr-3">Proveedor</th>
                          <th className="py-2 pr-3">Stock</th>
                          <th className="py-2 pr-3">Precio</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detailRelatedVariants.map((related) => {
                          const relatedSupplier = variantSupplierSummary(related);
                          return (
                            <tr key={related.id} className="border-b last:border-b-0">
                              <td className="py-2 pr-3">{detailValue(related.sku)}</td>
                              <td className="py-2 pr-3">{variantOptionsText(related)}</td>
                              <td className="py-2 pr-3">{relatedSupplier.name}<div className="text-[11px] text-gray-500">{relatedSupplier.source}</div></td>
                              <td className="py-2 pr-3">{detailValue(related.stock_on_hand)} (min {detailValue(related.stock_min)})</td>
                              <td className="py-2 pr-3">{money(related.price_store_ars)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No hay otras variantes activas para este producto.</p>
                )}
              </div>
            </div>

            <div className="flex flex-wrap justify-end gap-2 border-t border-neutral-100 pt-3">
              <button type="button" className="px-3 py-2 rounded border" onClick={() => { closeVariantDetails(); openBarcodeModal(detailVariant); }} disabled={saving}>
                Gestionar codigos
              </button>
              {canEdit ? (
                <button type="button" className="btn" onClick={() => { closeVariantDetails(); openVariantEditor(detailVariant); }} disabled={saving}>
                  Editar variante
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {editVariantOpen ? (
        <div className="fixed inset-0 z-50 bg-black/40 p-3 md:p-6 overflow-auto">
          <div className="mx-auto w-full max-w-4xl rounded-xl border border-neutral-200 bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <HelpTitle
                as="h3"
                className="text-lg font-semibold"
                help="Actualiza la variante vendible: SKU, precios, stock minimo, estado y valores de atributos. El barcode se administra aparte para no bloquear estos cambios."
              >
                Editar variante #{editVariantForm?.id || ''}
              </HelpTitle>
              <button type="button" className="px-3 py-2 rounded border" onClick={closeVariantEditor} disabled={saving}>
                Cerrar
              </button>
            </div>

            <form className="space-y-3" onSubmit={saveVariantEditor}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <input
                  className="input"
                  value={editVariantForm.display_name}
                  onChange={(e) => setEditVariantForm((prev) => ({ ...prev, display_name: e.target.value }))}
                  placeholder="Display name"
                />
                <input
                  className="input"
                  value={editVariantForm.sku}
                  onChange={(e) => setEditVariantForm((prev) => ({ ...prev, sku: e.target.value }))}
                  placeholder="SKU"
                  required
                />
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.01"
                  value={editVariantForm.price_store_ars}
                  onChange={(e) => setEditVariantForm((prev) => ({ ...prev, price_store_ars: e.target.value }))}
                  placeholder="Precio local"
                />
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.01"
                  value={editVariantForm.price_online_ars}
                  onChange={(e) => setEditVariantForm((prev) => ({ ...prev, price_online_ars: e.target.value }))}
                  placeholder="Precio online"
                />
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.01"
                  value={editVariantForm.cost_avg_ars}
                  onChange={(e) => setEditVariantForm((prev) => ({ ...prev, cost_avg_ars: e.target.value }))}
                  placeholder="Costo promedio"
                />
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="1"
                  value={editVariantForm.stock_min}
                  onChange={(e) => setEditVariantForm((prev) => ({ ...prev, stock_min: e.target.value }))}
                  placeholder="Stock minimo"
                />
              </div>

              <div className="flex flex-col gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-600 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="font-semibold text-neutral-800">Barcode principal</div>
                  <div className="mt-0.5 font-mono text-sm text-neutral-700">
                    {editVariantForm.original_barcode_internal || editVariantForm.barcode_internal || 'Sin barcode principal'}
                  </div>
                  <div className="mt-1">
                    Guardar esta variante no cambia ni revalida el barcode. Si hay que moverlo, reemplazarlo o crear uno nuevo, se hace desde Gestionar barcode.
                  </div>
                </div>
                {canEdit ? (
                  <button
                    type="button"
                    className="self-start rounded border border-neutral-300 bg-white px-3 py-2 text-xs font-semibold text-neutral-800 hover:bg-neutral-100 md:self-center"
                    onClick={openBarcodeModalFromVariantEditor}
                    disabled={saving}
                  >
                    Gestionar barcode
                  </button>
                ) : null}
              </div>

              <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
                <input
                  type="checkbox"
                  checked={!!editVariantForm.active}
                  onChange={(e) => setEditVariantForm((prev) => ({ ...prev, active: e.target.checked }))}
                />
                Activa
              </label>

              <VariantAttributeRows
                rows={editVariantForm.option_rows || []}
                attributes={atributos}
                attributeValuesByCode={attrValuesByCode}
                getAvailableAttributesForRow={availableAttrsForVariantEditRow}
                onUpdateRow={updateEditVariantOptionRow}
                onRemoveRow={removeEditVariantOptionRow}
                onAddRow={addEditVariantOptionRow}
                canAddRow={canAddEditOptionRow}
                disabled={saving}
                title="Atributos"
                help="Estos valores identifican la variante dentro del producto. Cambiarlos puede modificar la combinacion que ve Tienda Nube."
                emptyMessage="Esta variante no tiene atributos cargados. Puedes guardar otros cambios igual, o agregar atributos si corresponde."
                listIdPrefix="product-edit-variant-attr-values"
              />

              {err ? <p className="text-sm text-red-700">{err}</p> : null}
              {msg ? <p className="text-sm text-green-700">{msg}</p> : null}

              <div className="flex gap-2">
                <button className="btn" type="submit" disabled={saving}>
                  Guardar cambios
                </button>
                <button type="button" className="px-3 py-2 rounded border" onClick={closeVariantEditor}>
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {barcodeModal.open ? (
        <div className="fixed inset-0 z-50 bg-black/40 p-3 md:p-6 overflow-auto">
          <div className="mx-auto w-full max-w-5xl rounded-xl border border-neutral-200 bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <HelpTitle
                  as="h3"
                  className="text-lg font-semibold"
                  help="Administra los codigos que identifican esta variante al escanear, vender o imprimir etiquetas. La variante siempre debe tener un codigo principal."
                >
                  Gestion de barcodes
                </HelpTitle>
                <p className="text-xs text-gray-500">
                  {barcodeModal?.variant?.producto || 'Variante'} {barcodeModal?.variant?.option_signature ? `(${barcodeModal.variant.option_signature})` : ''}
                </p>
                {!canEdit ? (
                  <p className="text-xs text-amber-700 mt-1">Modo lectura: puedes consultar e imprimir, sin editar codigos.</p>
                ) : null}
              </div>
              <button type="button" className="px-3 py-2 rounded border" onClick={closeBarcodeModal}>
                Cerrar
              </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {canEdit ? (
                <form className="rounded-xl border border-neutral-200 p-3 space-y-2" onSubmit={associateBarcodeFromModal}>
                  <HelpTitle
                    as="h4"
                    className="text-sm font-semibold"
                    help="Vincula un EAN-13 ya existente a esta variante. Sirve cuando el producto ya trae etiqueta o cuando se quiere usar un codigo escaneado."
                  >
                    Asociar barcode (teclado o escaner)
                  </HelpTitle>
                  <input
                    ref={barcodeModalInputRef}
                    className="input"
                    placeholder="EAN-13 (13 digitos)"
                    value={barcodeModal.associateCode}
                    onChange={(e) => setBarcodeModal((prev) => ({ ...prev, associateCode: e.target.value }))}
                    required
                  />
                  <select
                    className="input"
                    value={barcodeModal.supplierId}
                    onChange={(e) => setBarcodeModal((prev) => ({ ...prev, supplierId: e.target.value }))}
                  >
                    <option value="">Sin especificar (codigo proveedor generico)</option>
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}{s.ean_supplier_code ? ` - EAN Prov ${s.ean_supplier_code}` : ' - sin codigo EAN'}
                      </option>
                    ))}
                  </select>
                  <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
                    <input
                      type="checkbox"
                      checked={!!barcodeModal.forceMove}
                      onChange={(e) => setBarcodeModal((prev) => ({ ...prev, forceMove: e.target.checked }))}
                    />
                    Forzar mover si el codigo esta en otra variante
                  </label>
                  <button className="btn" type="submit" disabled={barcodeModal.saving}>
                    {barcodeModal.saving ? 'Guardando...' : 'Asociar como principal'}
                  </button>
                </form>
              ) : (
                <div className="rounded-xl border border-neutral-200 p-3 text-sm text-neutral-600">
                  Edicion de barcode deshabilitada para este rol.
                </div>
              )}

              <div className="rounded-xl border border-neutral-200 p-3 space-y-2">
                {canEdit ? (
                  <>
                    <HelpTitle
                      as="h4"
                      className="text-sm font-semibold"
                      help="Crea un codigo EAN-13 interno para esta variante cuando no tiene uno propio. Usa el codigo de proveedor si esta configurado."
                    >
                      Generar EAN-13
                    </HelpTitle>
                    <select
                      className="input"
                      value={barcodeModal.supplierId}
                      onChange={(e) => setBarcodeModal((prev) => ({ ...prev, supplierId: e.target.value }))}
                    >
                      <option value="">Sin especificar (codigo proveedor generico)</option>
                      {suppliers.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}{s.ean_supplier_code ? ` - EAN Prov ${s.ean_supplier_code}` : ' - sin codigo EAN'}
                        </option>
                      ))}
                    </select>
                    <button className="btn" type="button" onClick={generateBarcodeFromModal} disabled={barcodeModal.saving}>
                      {barcodeModal.saving ? 'Generando...' : 'Generar y asignar principal'}
                    </button>
                    <div className="h-px bg-neutral-200 my-1" />
                  </>
                ) : null}
                <HelpTitle
                  as="h4"
                  className="text-sm font-semibold"
                  help="Abre el PDF para imprimir etiquetas de barcodes. Puede imprimir el codigo principal, todos los codigos o uno puntual."
                >
                  Impresion
                </HelpTitle>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 items-end">
                  <select
                    className="input"
                    value={barcodeModal.printScope}
                    onChange={(e) => setBarcodeModal((prev) => ({ ...prev, printScope: e.target.value }))}
                  >
                    <option value="primary">Solo principal</option>
                    <option value="all">Todos</option>
                    <option value="code">Un codigo</option>
                  </select>
                  {barcodeModal.printScope === 'code' ? (
                    <select
                      className="input"
                      value={barcodeModal.printCode}
                      onChange={(e) => setBarcodeModal((prev) => ({ ...prev, printCode: e.target.value }))}
                    >
                      <option value="">Seleccionar codigo</option>
                      {barcodeModal.rows.map((r) => (
                        <option key={r.id} value={r.barcode}>{r.barcode}</option>
                      ))}
                    </select>
                  ) : (
                    <div />
                  )}
                  <input
                    className="input"
                    type="number"
                    min="1"
                    max="200"
                    value={barcodeModal.printCopies}
                    onChange={(e) => setBarcodeModal((prev) => ({ ...prev, printCopies: e.target.value }))}
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 items-end">
                  <select
                    className="input"
                    value={barcodeModal.printLayout}
                    onChange={(e) => setBarcodeModal((prev) => ({ ...prev, printLayout: e.target.value }))}
                  >
                    <option value={PRINT_LAYOUTS.THERMAL}>Termica personalizada</option>
                    <option value={PRINT_LAYOUTS.A4}>A4 (grilla 3x8)</option>
                  </select>
                  {barcodeModal.printLayout === PRINT_LAYOUTS.THERMAL ? (
                    <>
                      <input
                        className="input"
                        type="number"
                        min="10"
                        max="200"
                        step="0.1"
                        value={barcodeModal.printLabelWidthMm}
                        onChange={(e) => setBarcodeModal((prev) => ({ ...prev, printLabelWidthMm: e.target.value }))}
                        placeholder="Ancho mm"
                      />
                      <input
                        className="input"
                        type="number"
                        min="10"
                        max="200"
                        step="0.1"
                        value={barcodeModal.printLabelHeightMm}
                        onChange={(e) => setBarcodeModal((prev) => ({ ...prev, printLabelHeightMm: e.target.value }))}
                        placeholder="Alto mm"
                      />
                    </>
                  ) : (
                    <>
                      <div />
                      <div />
                    </>
                  )}
                </div>
                <button
                  className="px-3 py-2 rounded border"
                  type="button"
                  onClick={() => openBarcodeLabelsPdf(barcodeModal.printScope, barcodeModal.printScope === 'code' ? barcodeModal.printCode : '')}
                >
                  Abrir PDF de etiquetas
                </button>
              </div>
            </div>

            <div className="rounded-xl border border-neutral-200 p-3">
              <div className="flex items-center justify-between mb-2">
                <HelpTitle
                  as="h4"
                  className="text-sm font-semibold"
                  help="Muestra todos los codigos vinculados a la variante y cual es el principal para busquedas, ventas e impresion."
                >
                  Codigos asociados
                </HelpTitle>
                <button
                  type="button"
                  className="px-2 py-1 rounded border text-xs"
                  onClick={() => loadBarcodeRows(barcodeModal?.variant?.id, { keepState: true })}
                  disabled={barcodeModal.loading}
                >
                  Recargar
                </button>
              </div>
              {barcodeModal.loading ? <p className="text-sm text-gray-500">Cargando codigos...</p> : null}
              {!barcodeModal.loading && barcodeModal.rows.length ? (
                <div className="overflow-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="text-left border-b">
                        <th className="py-2 pr-3">Codigo</th>
                        <th className="py-2 pr-3">Proveedor</th>
                        <th className="py-2 pr-3">Articulo</th>
                        <th className="py-2 pr-3">Origen</th>
                        <th className="py-2 pr-3">Accion</th>
                      </tr>
                    </thead>
                    <tbody>
                      {barcodeModal.rows.map((r) => (
                        <tr key={r.id} className="border-b last:border-b-0">
                          <td className="py-2 pr-3">
                            <span className={r.is_primary ? 'font-semibold text-green-700' : ''}>{r.barcode}</span>
                            {r.is_primary ? <div className="text-[11px] text-green-700">Principal</div> : null}
                          </td>
                          <td className="py-2 pr-3">
                            {r.supplier_name || 'Sin especificar'}
                            {r.supplier_ean_code ? <div className="text-[11px] text-gray-500">EAN Prov {r.supplier_ean_code}</div> : null}
                          </td>
                          <td className="py-2 pr-3">{r.supplier_item_code || '-'}</td>
                          <td className="py-2 pr-3">{r.source || '-'}</td>
                          <td className="py-2 pr-3">
                            <div className="flex flex-wrap gap-2">
                              {canEdit && !r.is_primary ? (
                                <button
                                  type="button"
                                  className="px-2 py-1 rounded border text-xs"
                                  onClick={() => setPrimaryBarcodeFromModal(r.id)}
                                  disabled={barcodeModal.saving}
                                >
                                  Hacer principal
                                </button>
                              ) : null}
                              <button
                                type="button"
                                className="px-2 py-1 rounded border text-xs"
                                onClick={() => openBarcodeLabelsPdf('code', r.barcode)}
                              >
                                Imprimir
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              {!barcodeModal.loading && !barcodeModal.rows.length ? (
                <p className="text-sm text-gray-500">La variante aun no tiene barcodes cargados.</p>
              ) : null}
            </div>

            {barcodeModal.err ? <p className="text-sm text-red-700">{barcodeModal.err}</p> : null}
            {barcodeModal.msg ? <p className="text-sm text-green-700">{barcodeModal.msg}</p> : null}
          </div>
        </div>
      ) : null}

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {msg ? <p className="text-sm text-green-700">{msg}</p> : null}
    </div>
  );
}

