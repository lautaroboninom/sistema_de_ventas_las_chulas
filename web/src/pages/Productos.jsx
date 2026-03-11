import { useEffect, useRef, useState } from 'react';
import {
  getRetailAtributos,
  getRetailComprasProveedores,
  getRetailProductos,
  getRetailVarianteBarcodeLabelsUrl,
  getRetailVarianteBarcodes,
  getRetailVariantes,
  patchRetailVariante,
  postRetailAtributo,
  postRetailProducto,
  postRetailVarianteBarcodeAssociate,
  postRetailVarianteBarcodeGenerate,
  postRetailVarianteBarcodePrimary,
  postRetailVariante,
} from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { can, PERMISSION_CODES } from '../lib/permissions';

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
};

export default function ProductosPage() {
  const { user } = useAuth();
  const canEdit = can(user, PERMISSION_CODES.ACTION_CONFIG_EDITAR);

  const [productos, setProductos] = useState([]);
  const [atributos, setAtributos] = useState([]);
  const [variantes, setVariantes] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [q, setQ] = useState('');

  const [prodForm, setProdForm] = useState({ ...EMPTY_PRODUCT });
  const [prodImageFile, setProdImageFile] = useState(null);
  const [attrForm, setAttrForm] = useState({ ...EMPTY_ATTR });
  const [varForm, setVarForm] = useState({ ...EMPTY_VARIANT });
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

  async function loadAll() {
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
  }

  useEffect(() => {
    loadAll();
  }, []);

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

  async function applyAdjust(variantId) {
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
    setBarcodeModal({
      ...EMPTY_BARCODE_MODAL,
      open: true,
      variant: row,
    });
    await loadBarcodeRows(row?.id);
    setTimeout(() => barcodeModalInputRef.current?.focus(), 0);
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
    const url = getRetailVarianteBarcodeLabelsUrl(variantId, {
      scope,
      copies,
      code: code || undefined,
    });
    const win = window.open(url, '_blank', 'noopener,noreferrer');
    if (!win) {
      setBarcodeModal((prev) => ({ ...prev, err: 'No se pudo abrir la ventana de impresion (bloqueada por el navegador)' }));
    }
  }

  const usedAttrs = new Set((varForm.option_rows || []).map((row) => attrCode(row.attribute_code)).filter(Boolean));
  const canAddOptionRow = atributos.length === 0 || usedAttrs.size < atributos.length;

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">Productos y variantes</h1>
        <p className="text-sm text-gray-600">
          Catalogo retail unificado. Variantes con atributos configurables y stock global por SKU/barcode.
        </p>
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
                      <button
                        type="button"
                        className="px-2 py-1 rounded border text-xs"
                        onClick={() => quickGenerateBarcode(row.id)}
                        disabled={saving}
                      >
                        Generar
                      </button>
                      <button
                        type="button"
                        className="px-2 py-1 rounded border text-xs"
                        onClick={() => openBarcodeModal(row)}
                        disabled={saving}
                      >
                        Asociar
                      </button>
                      <button
                        type="button"
                        className="px-2 py-1 rounded border text-xs"
                        onClick={() => {
                          const url = getRetailVarianteBarcodeLabelsUrl(row.id, { scope: 'primary', copies: 1 });
                          window.open(url, '_blank', 'noopener,noreferrer');
                        }}
                      >
                        Imprimir
                      </button>
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

      {barcodeModal.open ? (
        <div className="fixed inset-0 z-50 bg-black/40 p-3 md:p-6 overflow-auto">
          <div className="mx-auto w-full max-w-5xl rounded-xl border border-neutral-200 bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold">Gestion de barcodes</h3>
                <p className="text-xs text-gray-500">
                  {barcodeModal?.variant?.producto || 'Variante'} {barcodeModal?.variant?.option_signature ? `(${barcodeModal.variant.option_signature})` : ''}
                </p>
              </div>
              <button type="button" className="px-3 py-2 rounded border" onClick={closeBarcodeModal}>
                Cerrar
              </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
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

              <div className="rounded-xl border border-neutral-200 p-3 space-y-2">
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
                              {!r.is_primary ? (
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

