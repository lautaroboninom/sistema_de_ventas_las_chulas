import { useEffect, useRef, useState } from 'react';
import {
  deleteRetailAtributo,
  deleteRetailVariante,
  getRetailAtributos,
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
import VariantBatchCreator from '../components/VariantBatchCreator';

function errMsg(error) {
  return error?.message || 'Ocurrio un error inesperado';
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

function attrCode(v) {
  return String(v || '').trim().toLowerCase();
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
    out.push({ attribute_code: code, value });
  });

  if (!out.length) {
    throw new Error('Debes cargar al menos un atributo con valor');
  }

  return out;
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

const EMPTY_PRODUCT = { name: '', sku_prefix: '' };
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
  price_store_ars: '0',
  price_online_ars: '0',
  cost_avg_ars: '0',
  stock_min: '0',
  active: true,
  option_rows: [{ attribute_code: '', value: '' }],
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

export default function ProductosPage() {
  const { user } = useAuth();
  const canEdit = can(user, PERMISSION_CODES.ACTION_CONFIG_EDITAR);
  const canSeeOnlineSyncStatus = can(user, PERMISSION_CODES.ACTION_ONLINE_SYNC);
  const canGoOnline = can(user, PERMISSION_CODES.PAGE_ONLINE);

  const [productos, setProductos] = useState([]);
  const [atributos, setAtributos] = useState([]);
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
  const prodImageInputRef = useRef(null);
  const barcodeInputRef = useRef(null);
  const barcodeModalInputRef = useRef(null);

  const [adjustByVariant, setAdjustByVariant] = useState({});
  const [barcodeModal, setBarcodeModal] = useState({ ...EMPTY_BARCODE_MODAL });
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
      const [prods, attrs, vars, sups] = await Promise.all([
        getRetailProductos({ active: 1 }),
        getRetailAtributos(),
        getRetailVariantes({ q, active: 1 }),
        getRetailComprasProveedores({ limit: 500 }),
      ]);
      setProductos(Array.isArray(prods) ? prods : []);
      setAtributos(Array.isArray(attrs) ? attrs : []);
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
      const firstFree = atributos.find((a) => !used.has(attrCode(a.code)));
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

  function openProductEditor(row) {
    if (!row) return;
    setEditProductForm({
      id: row.id,
      name: row.name || '',
      sku_prefix: row.sku_prefix || '',
      default_cost_ars: String(row.default_cost_ars ?? 0),
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
      await patchRetailProducto(editProductForm.id, {
        name: editProductForm.name,
        sku_prefix: editProductForm.sku_prefix || undefined,
        default_cost_ars: Number(editProductForm.default_cost_ars || 0),
        active: !!editProductForm.active,
      });
      setMsg('Producto actualizado');
      closeProductEditor();
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
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
      setErr(errMsg(error));
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
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  function openVariantEditor(row) {
    if (!row) return;
    const rows = Array.isArray(row.option_values) && row.option_values.length
      ? row.option_values.map((opt) => ({ attribute_code: attrCode(opt.attribute_code), value: opt.option_value || '' }))
      : [{ attribute_code: '', value: '' }];
    setEditVariantForm({
      id: row.id,
      display_name: row.display_name || '',
      sku: row.sku || '',
      barcode_internal: row.barcode_internal || '',
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
      const firstFree = atributos.find((a) => !used.has(attrCode(a.code)));
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
        option_rows: next.length ? next : [{ attribute_code: '', value: '' }],
      };
    });
  }

  async function saveVariantEditor(e) {
    e.preventDefault();
    if (!canEdit || !editVariantForm?.id) return;
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      const option_values = buildOptionValues(editVariantForm.option_rows);
      await patchRetailVariante(editVariantForm.id, {
        display_name: editVariantForm.display_name || undefined,
        sku: editVariantForm.sku,
        barcode_internal: editVariantForm.barcode_internal || undefined,
        price_store_ars: Number(editVariantForm.price_store_ars || 0),
        price_online_ars: Number(editVariantForm.price_online_ars || 0),
        cost_avg_ars: Number(editVariantForm.cost_avg_ars || 0),
        stock_min: Number(editVariantForm.stock_min || 0),
        active: !!editVariantForm.active,
        option_values,
      });
      setMsg('Variante actualizada');
      closeVariantEditor();
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
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
        formData.append('image', prodImageFile);
        await postRetailProducto(formData);
      } else {
        await postRetailProducto({
          name: prodForm.name,
          sku_prefix: prodForm.sku_prefix || undefined,
        });
      }
      setProdForm({ ...EMPTY_PRODUCT });
      setProdImageFile(null);
      if (prodImageInputRef.current) prodImageInputRef.current.value = '';
      setMsg('Producto creado');
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
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
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  async function createVariante(e) {
    e.preventDefault();
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      const barcode = String(varForm.barcode_internal || '').trim();
      const supplierId = String(varForm.supplier_id || '').trim();
      const option_values = buildOptionValues(varForm.option_rows);
      await postRetailVariante({
        product_id: Number(varForm.product_id),
        option_values,
        sku: varForm.sku || undefined,
        barcode_internal: barcode || undefined,
        supplier_id: supplierId ? Number(supplierId) : undefined,
        price_store_ars: Number(varForm.price_store_ars || 0),
        price_online_ars: Number(varForm.price_online_ars || 0),
        cost_avg_ars: Number(varForm.cost_avg_ars || 0),
        stock_on_hand: Number(varForm.stock_on_hand || 0),
        stock_min: Number(varForm.stock_min || 0),
      });
      setVarForm({ ...EMPTY_VARIANT });
      setMsg(barcode ? 'Variante creada con barcode manual' : 'Variante creada con barcode EAN-13 generado');
      await loadAll();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
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

  function conflictDetail(error) {
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

  async function quickGenerateBarcode(variantId) {
    if (!canEdit) return;
    if (!variantId) return;
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      await postRetailVarianteBarcodeGenerate(variantId, {});
      setMsg('EAN-13 generado y asignado como principal');
      await loadAll();
      if (barcodeModal.open && Number(barcodeModal?.variant?.id) === Number(variantId)) {
        await loadBarcodeRows(variantId, { keepState: true });
      }
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
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
      setBarcodeModal((prev) => ({ ...prev, saving: false, err: conflictDetail(error) }));
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
  const canAddOptionRow = atributos.length === 0 || usedAttrs.size < atributos.length;
  const usedEditAttrs = new Set((editVariantForm.option_rows || []).map((row) => attrCode(row.attribute_code)).filter(Boolean));
  const canAddEditOptionRow = atributos.length === 0 || usedEditAttrs.size < atributos.length;
  const totalProductos = productos.length;
  const totalVariantes = variantes.length;
  const failedSyncTotal = Number(onlineSyncSummary?.failed_total || 0);
  const syncStatusAvailable = Boolean(onlineSyncSummary?.statusAvailable);
  const hasFailedSync = syncStatusAvailable && failedSyncTotal > 0;

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">Productos y variantes</h1>
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
            <h2 className="text-lg font-semibold">Altas</h2>
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
                  <h3 className="text-lg font-semibold">Nuevo producto</h3>
                  <input
                    className="input"
                    placeholder="Nombre"
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
                  <h3 className="text-lg font-semibold">Nuevo atributo</h3>
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
                <h3 className="text-lg font-semibold">Nueva variante</h3>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  <div className="space-y-1">
                    <label className="block text-xs text-gray-500">Producto</label>
                    <select
                      className="input"
                      value={varForm.product_id}
                      onChange={(e) => setVarForm((v) => ({ ...v, product_id: e.target.value }))}
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

                <div className="space-y-2">
                  <h4 className="text-sm font-semibold">Atributos de la variante</h4>
                  {(varForm.option_rows || []).map((row, idx) => {
                    const options = availableAttrsForRow(idx);
                    return (
                      <div key={idx} className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
                        <div className="md:col-span-5">
                          <label className="block text-xs text-gray-500 mb-1">Atributo</label>
                          <select
                            className="input"
                            value={row.attribute_code || ''}
                            onChange={(e) => updateOptionRow(idx, { attribute_code: e.target.value })}
                            required
                          >
                            <option value="">Seleccionar atributo</option>
                            {options.map((a) => (
                              <option key={a.id} value={a.code}>{a.name}</option>
                            ))}
                          </select>
                        </div>

                        <div className="md:col-span-5">
                          <label className="block text-xs text-gray-500 mb-1">Valor</label>
                          <input
                            className="input"
                            placeholder="Ej: S, Negro, 36"
                            value={row.value || ''}
                            onChange={(e) => updateOptionRow(idx, { value: e.target.value })}
                            required
                          />
                        </div>

                        <div className="md:col-span-2">
                          <button
                            type="button"
                            className="px-3 py-2 rounded border w-full"
                            onClick={() => removeOptionRow(idx)}
                            disabled={(varForm.option_rows || []).length <= 1}
                          >
                            Quitar
                          </button>
                        </div>
                      </div>
                    );
                  })}

                  <button
                    type="button"
                    className="px-3 py-2 rounded border"
                    onClick={addOptionRow}
                    disabled={!canAddOptionRow}
                  >
                    Agregar atributo
                  </button>
                </div>

                <button className="btn" disabled={saving} type="submit">Crear variante</button>
              </form>

              <VariantBatchCreator
                title="Alta masiva por combinaciones"
                products={productos}
                attributes={atributos}
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
            <h2 className="text-lg font-semibold">Productos</h2>
            <div className="overflow-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left border-b">
                    <th className="py-2 pr-3">Nombre</th>
                    <th className="py-2 pr-3">SKU prefix</th>
                    <th className="py-2 pr-3">Variantes</th>
                    <th className="py-2 pr-3">Accion</th>
                  </tr>
                </thead>
                <tbody>
                  {productos.map((row) => (
                    <tr key={row.id} className="border-b last:border-b-0">
                      <td className="py-2 pr-3">{row.name}</td>
                      <td className="py-2 pr-3">{row.sku_prefix || '-'}</td>
                      <td className="py-2 pr-3">{Number(row.variantes || 0)}</td>
                      <td className="py-2 pr-3">
                        <button type="button" className="px-2 py-1 rounded border text-xs" onClick={() => openProductEditor(row)}>
                          Editar
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!productos.length ? (
                    <tr>
                      <td colSpan={4} className="py-3 text-gray-500">Sin productos para mostrar.</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>

            {editProductForm?.id ? (
              <div className="rounded-xl border border-neutral-200 p-3 space-y-2">
                <h3 className="text-sm font-semibold">Editar producto #{editProductForm.id}</h3>
                <input
                  className="input"
                  value={editProductForm.name}
                  onChange={(e) => setEditProductForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="Nombre"
                />
                <input
                  className="input"
                  value={editProductForm.sku_prefix}
                  onChange={(e) => setEditProductForm((prev) => ({ ...prev, sku_prefix: e.target.value }))}
                  placeholder="Prefijo SKU"
                />
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
                  <button type="button" className="px-3 py-2 rounded border" onClick={closeProductEditor}>Cancelar</button>
                </div>
              </div>
            ) : null}
          </div>

          <div className="card space-y-3">
            <h2 className="text-lg font-semibold">Atributos</h2>
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
                <h3 className="text-sm font-semibold">Editar atributo #{editAttrForm.id}</h3>
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
          <h2 className="text-lg font-semibold">Variantes</h2>
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
                <th className="py-2 pr-3">Precios</th>
                <th className="py-2 pr-3">Stock</th>
                <th className="py-2 pr-3">Ajuste</th>
                <th className="py-2 pr-3">Barcodes</th>
              </tr>
            </thead>
            <tbody>
              {variantes.map((row) => (
                <tr key={row.id} className="border-b last:border-b-0">
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
                    <div className="text-xs text-gray-500">{row.barcode_internal}</div>
                    <div className="text-[11px] text-gray-400">
                      {Math.max(Number(row.barcode_count || 0), row.barcode_internal ? 1 : 0)} codigos
                    </div>
                  </td>
                  <td className="py-2 pr-3">
                    {row.producto}
                    <div className="text-xs text-gray-500">{row.option_signature}</div>
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
                    <div className="flex flex-wrap items-center gap-2">
                      {canEdit ? (
                        <button
                          type="button"
                          className="px-2 py-1 rounded border text-xs"
                          onClick={() => quickGenerateBarcode(row.id)}
                          disabled={saving}
                        >
                          Generar
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="px-2 py-1 rounded border text-xs"
                        onClick={() => openBarcodeModal(row)}
                        disabled={saving}
                      >
                        {canEdit ? 'Asociar' : 'Ver'}
                      </button>
                      <button
                        type="button"
                        className="px-2 py-1 rounded border text-xs"
                        onClick={() => openVariantEditor(row)}
                        disabled={saving || !canEdit}
                      >
                        Editar
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
              ))}
              {!variantes.length && !loading ? (
                <tr>
                  <td className="py-3 text-gray-500" colSpan={7}>Sin variantes para mostrar.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {editVariantOpen ? (
        <div className="fixed inset-0 z-50 bg-black/40 p-3 md:p-6 overflow-auto">
          <div className="mx-auto w-full max-w-4xl rounded-xl border border-neutral-200 bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold">Editar variante #{editVariantForm?.id || ''}</h3>
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
                  value={editVariantForm.barcode_internal}
                  onChange={(e) => setEditVariantForm((prev) => ({ ...prev, barcode_internal: e.target.value }))}
                  placeholder="Barcode interno"
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

              <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
                <input
                  type="checkbox"
                  checked={!!editVariantForm.active}
                  onChange={(e) => setEditVariantForm((prev) => ({ ...prev, active: e.target.checked }))}
                />
                Activa
              </label>

              <div className="space-y-2">
                <h4 className="text-sm font-semibold">Atributos</h4>
                {(editVariantForm.option_rows || []).map((row, idx) => (
                  <div key={idx} className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
                    <div className="md:col-span-5">
                      <select
                        className="input"
                        value={row.attribute_code || ''}
                        onChange={(e) => updateEditVariantOptionRow(idx, { attribute_code: e.target.value })}
                        required
                      >
                        <option value="">Seleccionar atributo</option>
                        {availableAttrsForVariantEditRow(idx).map((a) => (
                          <option key={a.id} value={a.code}>{a.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="md:col-span-5">
                      <input
                        className="input"
                        value={row.value || ''}
                        onChange={(e) => updateEditVariantOptionRow(idx, { value: e.target.value })}
                        placeholder="Valor"
                        required
                      />
                    </div>
                    <div className="md:col-span-2">
                      <button
                        type="button"
                        className="px-3 py-2 rounded border w-full"
                        onClick={() => removeEditVariantOptionRow(idx)}
                        disabled={(editVariantForm.option_rows || []).length <= 1}
                      >
                        Quitar
                      </button>
                    </div>
                  </div>
                ))}

                <button
                  type="button"
                  className="px-3 py-2 rounded border"
                  onClick={addEditVariantOptionRow}
                  disabled={!canAddEditOptionRow}
                >
                  Agregar atributo
                </button>
              </div>

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
                <h3 className="text-lg font-semibold">Gestion de barcodes</h3>
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
                  <h4 className="text-sm font-semibold">Asociar barcode (teclado o escaner)</h4>
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
                    <h4 className="text-sm font-semibold">Generar EAN-13</h4>
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
                <h4 className="text-sm font-semibold">Impresion</h4>
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
                <h4 className="text-sm font-semibold">Codigos asociados</h4>
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

