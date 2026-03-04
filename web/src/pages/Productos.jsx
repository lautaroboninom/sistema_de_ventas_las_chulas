import { useEffect, useRef, useState } from 'react';
import {
  getRetailAtributos,
  getRetailProductos,
  getRetailVariantes,
  patchRetailVariante,
  postRetailAtributo,
  postRetailProducto,
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
  price_store_ars: '',
  price_online_ars: '',
  cost_avg_ars: '',
  stock_on_hand: '0',
  stock_min: '0',
};

export default function ProductosPage() {
  const { user } = useAuth();
  const canEdit = can(user, PERMISSION_CODES.ACTION_CONFIG_EDITAR);

  const [productos, setProductos] = useState([]);
  const [atributos, setAtributos] = useState([]);
  const [variantes, setVariantes] = useState([]);
  const [q, setQ] = useState('');

  const [prodForm, setProdForm] = useState({ ...EMPTY_PRODUCT });
  const [prodImageFile, setProdImageFile] = useState(null);
  const [attrForm, setAttrForm] = useState({ ...EMPTY_ATTR });
  const [varForm, setVarForm] = useState({ ...EMPTY_VARIANT });
  const [createMenuOpen, setCreateMenuOpen] = useState(false);
  const prodImageInputRef = useRef(null);
  const barcodeInputRef = useRef(null);

  const [adjustByVariant, setAdjustByVariant] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  async function loadAll() {
    setLoading(true);
    setErr('');
    try {
      const [prods, attrs, vars] = await Promise.all([
        getRetailProductos({ active: 1 }),
        getRetailAtributos(),
        getRetailVariantes({ q, active: 1 }),
      ]);
      setProductos(Array.isArray(prods) ? prods : []);
      setAtributos(Array.isArray(attrs) ? attrs : []);
      setVariantes(Array.isArray(vars) ? vars : []);
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
      if (!barcode) {
        throw new Error('Escanea o ingresa el codigo de barras de la variante');
      }
      const option_values = buildOptionValues(varForm.option_rows);
      await postRetailVariante({
        product_id: Number(varForm.product_id),
        option_values,
        sku: varForm.sku || undefined,
        barcode_internal: barcode,
        price_store_ars: Number(varForm.price_store_ars || 0),
        price_online_ars: Number(varForm.price_online_ars || 0),
        cost_avg_ars: Number(varForm.cost_avg_ars || 0),
        stock_on_hand: Number(varForm.stock_on_hand || 0),
        stock_min: Number(varForm.stock_min || 0),
      });
      setVarForm({ ...EMPTY_VARIANT });
      setMsg('Variante creada');
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
                    <label className="block text-xs text-gray-500">Codigo de barras</label>
                    <div className="flex items-center gap-2">
                      <input
                        ref={barcodeInputRef}
                        className="input flex-1"
                        placeholder="Escanear o escribir codigo"
                        value={varForm.barcode_internal}
                        onChange={(e) => setVarForm((v) => ({ ...v, barcode_internal: e.target.value }))}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') e.preventDefault();
                        }}
                        required
                      />
                      <button
                        type="button"
                        className="px-3 py-2 rounded border whitespace-nowrap"
                        onClick={() => barcodeInputRef.current?.focus()}
                      >
                        Escanear
                      </button>
                    </div>
                    <p className="text-xs text-gray-500">Usa el mismo codigo que ya tiene la etiqueta existente.</p>
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
                </tr>
              ))}
              {!variantes.length && !loading ? (
                <tr>
                  <td className="py-3 text-gray-500" colSpan={6}>Sin variantes para mostrar.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {msg ? <p className="text-sm text-green-700">{msg}</p> : null}
    </div>
  );
}

