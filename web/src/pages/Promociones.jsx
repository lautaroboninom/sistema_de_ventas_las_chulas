import { useEffect, useMemo, useState } from 'react';
import {
  getRetailProductos,
  getRetailVariantes,
  getRetailPromocionDetail,
  getRetailPromociones,
  patchRetailPromocion,
  postRetailPromocion,
} from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { can, PERMISSION_CODES } from '../lib/permissions';

function errMsg(error) {
  return error?.message || 'Ocurrio un error inesperado';
}

function toInputDateTime(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return '';
  const offset = parsed.getTimezoneOffset();
  const local = new Date(parsed.getTime() - offset * 60000);
  return local.toISOString().slice(0, 16);
}

function fromInputDateTime(value) {
  const txt = String(value || '').trim();
  if (!txt) return undefined;
  const parsed = new Date(txt);
  if (Number.isNaN(parsed.getTime())) return undefined;
  return parsed.toISOString();
}

function blankForm() {
  return {
    id: null,
    name: '',
    promo_type: 'percent_off',
    active: true,
    channel_scope: 'both',
    activation_mode: 'automatic',
    coupon_code: '',
    priority: 100,
    combinable: true,
    bogo_mode: 'sku',
    buy_qty: 2,
    pay_qty: 1,
    discount_pct: 10,
    applies_to_all_products: true,
    product_ids: [],
    variant_ids: [],
    valid_from: '',
    valid_until: '',
  };
}

function normalizeForm(row) {
  const base = blankForm();
  if (!row) return base;
  return {
    ...base,
    id: row.id ?? null,
    name: row.name || '',
    promo_type: row.promo_type || 'percent_off',
    active: row.active !== false,
    channel_scope: row.channel_scope || 'both',
    activation_mode: row.activation_mode || 'automatic',
    coupon_code: row.coupon_code || '',
    priority: Number(row.priority ?? 100),
    combinable: row.combinable !== false,
    bogo_mode: row.bogo_mode || 'sku',
    buy_qty: Number(row.buy_qty ?? 2),
    pay_qty: Number(row.pay_qty ?? 1),
    discount_pct: Number(row.discount_pct ?? 10),
    applies_to_all_products: row.applies_to_all_products !== false,
    product_ids: Array.isArray(row.product_ids) ? row.product_ids.map((v) => Number(v)).filter(Number.isFinite) : [],
    variant_ids: Array.isArray(row.variant_ids) ? row.variant_ids.map((v) => Number(v)).filter(Number.isFinite) : [],
    valid_from: toInputDateTime(row.valid_from),
    valid_until: toInputDateTime(row.valid_until),
  };
}

export default function PromocionesPage() {
  const { user } = useAuth();
  const canEdit = can(user, PERMISSION_CODES.ACTION_PROMOCIONES_EDITAR);

  const [rows, setRows] = useState([]);
  const [products, setProducts] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [form, setForm] = useState(blankForm());
  const [selectedVariants, setSelectedVariants] = useState([]);
  const [skuQuery, setSkuQuery] = useState('');
  const [skuResults, setSkuResults] = useState([]);
  const [skuLoading, setSkuLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [onlyActive, setOnlyActive] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const productMap = useMemo(() => {
    const map = new Map();
    products.forEach((p) => map.set(Number(p.id), p));
    return map;
  }, [products]);
  const selectedVariantIds = useMemo(
    () => new Set((form.variant_ids || []).map((id) => Number(id)).filter(Number.isFinite)),
    [form.variant_ids],
  );
  const isXForYSku = form.promo_type === 'x_for_y' && form.bogo_mode === 'sku';
  const isXForYMix = form.promo_type === 'x_for_y' && form.bogo_mode === 'mix';

  function resetForm() {
    setSelectedId(null);
    setForm(blankForm());
    setSelectedVariants([]);
    setSkuQuery('');
    setSkuResults([]);
  }

  function addVariant(row) {
    const vid = Number(row?.id || 0);
    if (!vid) return;
    setForm((prev) => {
      if ((prev.variant_ids || []).includes(vid)) return prev;
      return { ...prev, variant_ids: [...(prev.variant_ids || []), vid] };
    });
    setSelectedVariants((prev) => {
      if (prev.some((item) => Number(item.id) === vid)) return prev;
      return [
        ...prev,
        {
          id: vid,
          sku: row?.sku || `#${vid}`,
          producto: row?.producto || row?.product_name || '',
        },
      ];
    });
    setSkuQuery('');
    setSkuResults([]);
  }

  function removeVariant(variantId) {
    const vid = Number(variantId || 0);
    if (!vid) return;
    setForm((prev) => ({ ...prev, variant_ids: (prev.variant_ids || []).filter((id) => Number(id) !== vid) }));
    setSelectedVariants((prev) => prev.filter((item) => Number(item.id) !== vid));
  }

  async function loadList() {
    setLoading(true);
    setErr('');
    try {
      const [promos, catalog] = await Promise.all([
        getRetailPromociones({
          q: search || undefined,
          active: onlyActive ? true : undefined,
        }),
        getRetailProductos({ active: true }),
      ]);
      setRows(Array.isArray(promos) ? promos : []);
      setProducts(Array.isArray(catalog) ? catalog : []);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadList();
  }, []);

  useEffect(() => {
    if (!isXForYSku) {
      setSkuResults([]);
      setSkuLoading(false);
      return undefined;
    }
    const term = String(skuQuery || '').trim();
    if (term.length < 2) {
      setSkuResults([]);
      setSkuLoading(false);
      return undefined;
    }
    let active = true;
    setSkuLoading(true);
    const timer = setTimeout(async () => {
      try {
        const rows = await getRetailVariantes({ q: term, active: true });
        if (!active) return;
        const mapped = (Array.isArray(rows) ? rows : [])
          .map((row) => ({
            id: Number(row.id),
            sku: row.sku || '',
            producto: row.producto || '',
          }))
          .filter((row) => Number.isFinite(row.id))
          .slice(0, 20);
        setSkuResults(mapped);
      } catch {
        if (active) setSkuResults([]);
      } finally {
        if (active) setSkuLoading(false);
      }
    }, 220);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [isXForYSku, skuQuery]);

  async function selectPromo(id) {
    if (!id) {
      resetForm();
      return;
    }
    setLoading(true);
    setErr('');
    try {
      const row = await getRetailPromocionDetail(Number(id));
      setSelectedId(Number(id));
      setForm(normalizeForm(row));
      const variants = Array.isArray(row?.variants)
        ? row.variants
            .map((item) => ({
              id: Number(item.id),
              sku: item.sku || '',
              producto: item.producto || item.product_name || '',
            }))
            .filter((item) => Number.isFinite(item.id))
        : [];
      setSelectedVariants(variants);
      setSkuQuery('');
      setSkuResults([]);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoading(false);
    }
  }

  function toggleProduct(productId) {
    const pid = Number(productId);
    if (!Number.isFinite(pid)) return;
    setForm((prev) => {
      const exists = prev.product_ids.includes(pid);
      const next = exists ? prev.product_ids.filter((x) => x !== pid) : [...prev.product_ids, pid];
      return { ...prev, product_ids: next };
    });
  }

  async function submitForm(e) {
    e.preventDefault();
    if (!canEdit) return;
    setSaving(true);
    setErr('');
    setMsg('');
    try {
      if (form.promo_type === 'x_for_y' && form.bogo_mode === 'sku' && !(form.variant_ids || []).length) {
        throw new Error('Debes agregar al menos un SKU para modo X por Y por SKU');
      }
      const payload = {
        name: form.name || undefined,
        promo_type: form.promo_type,
        active: !!form.active,
        channel_scope: form.channel_scope,
        activation_mode: form.activation_mode,
        coupon_code: form.coupon_code || undefined,
        priority: Number(form.priority || 0),
        combinable: !!form.combinable,
        valid_from: fromInputDateTime(form.valid_from),
        valid_until: fromInputDateTime(form.valid_until),
      };
      if (form.promo_type === 'percent_off') {
        payload.discount_pct = Number(form.discount_pct || 0);
        payload.applies_to_all_products = !!form.applies_to_all_products;
        payload.product_ids = form.applies_to_all_products ? [] : form.product_ids;
        payload.variant_ids = [];
      } else {
        payload.bogo_mode = form.bogo_mode;
        payload.buy_qty = Number(form.buy_qty || 0);
        payload.pay_qty = Number(form.pay_qty || 0);
        payload.applies_to_all_products = true;
        payload.product_ids = [];
        payload.variant_ids = form.bogo_mode === 'sku' ? (form.variant_ids || []) : [];
      }

      let saved;
      if (form.id) {
        saved = await patchRetailPromocion(form.id, payload);
        setMsg('Promocion actualizada');
      } else {
        saved = await postRetailPromocion(payload);
        setMsg('Promocion creada');
      }
      setForm(normalizeForm(saved));
      setSelectedId(saved?.id || null);
      const variants = Array.isArray(saved?.variants)
        ? saved.variants
            .map((item) => ({
              id: Number(item.id),
              sku: item.sku || '',
              producto: item.producto || item.product_name || '',
            }))
            .filter((item) => Number.isFinite(item.id))
        : [];
      setSelectedVariants(variants);
      await loadList();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">Promociones</h1>
        <p className="text-sm text-gray-600">
          Motor de promociones retail: porcentaje, 2x1/3x2, combinables por prioridad, automaticas y por cupon.
        </p>
      </div>

      <div className="card grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <div className="md:col-span-2">
          <label className="block text-xs text-gray-500 mb-1">Buscar</label>
          <input
            className="input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Nombre o cupon"
          />
        </div>
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" checked={onlyActive} onChange={(e) => setOnlyActive(e.target.checked)} />
          Solo activas
        </label>
        <button type="button" className="btn" onClick={loadList} disabled={loading}>
          Buscar
        </button>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold">Listado</h2>
          <button
            type="button"
            className="px-3 py-2 rounded border"
            onClick={resetForm}
            disabled={!canEdit}
          >
            Nueva promocion
          </button>
        </div>
        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="py-2 pr-3">Nombre</th>
                <th className="py-2 pr-3">Tipo</th>
                <th className="py-2 pr-3">Canal</th>
                <th className="py-2 pr-3">Modo</th>
                <th className="py-2 pr-3">Prioridad</th>
                <th className="py-2 pr-3">Activa</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.id}
                  className={`border-b last:border-b-0 cursor-pointer ${Number(selectedId) === Number(row.id) ? 'bg-gray-50' : ''}`}
                  onClick={() => selectPromo(row.id)}
                >
                  <td className="py-2 pr-3">
                    {row.name}
                    <div className="text-xs text-gray-500">{row.coupon_code || '-'}</div>
                  </td>
                  <td className="py-2 pr-3">{row.promo_type}</td>
                  <td className="py-2 pr-3">{row.channel_scope}</td>
                  <td className="py-2 pr-3">{row.activation_mode}</td>
                  <td className="py-2 pr-3">{row.priority}</td>
                  <td className="py-2 pr-3">{row.active ? 'Si' : 'No'}</td>
                </tr>
              ))}
              {!rows.length ? (
                <tr>
                  <td className="py-3 text-gray-500" colSpan={6}>
                    Sin promociones para el filtro actual.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <form className="card space-y-3" onSubmit={submitForm}>
        <h2 className="text-lg font-semibold">{form.id ? `Editar promocion #${form.id}` : 'Nueva promocion'}</h2>
        <p className="text-xs text-gray-600">
          Completa cada campo segun el objetivo comercial. Menor prioridad se aplica primero.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="space-y-1 md:col-span-2">
            <label className="block text-xs text-gray-500">Nombre</label>
            <input
              className="input"
              placeholder="Ej: 3x2 Remeras fin de semana"
              value={form.name}
              onChange={(e) => setForm((v) => ({ ...v, name: e.target.value }))}
              disabled={!canEdit}
            />
            <p className="text-xs text-gray-500">Nombre interno para identificar la promocion en caja y reportes.</p>
          </div>

          <div className="space-y-1">
            <label className="block text-xs text-gray-500">Tipo de promocion</label>
            <select
              className="input"
              value={form.promo_type}
              onChange={(e) => setForm((v) => ({ ...v, promo_type: e.target.value }))}
              disabled={!canEdit}
            >
              <option value="percent_off">% descuento</option>
              <option value="x_for_y">X por Y (2x1/3x2)</option>
            </select>
            <p className="text-xs text-gray-500">Define si baja porcentaje o bonifica unidades por bloque.</p>
          </div>

          <div className="space-y-1">
            <label className="block text-xs text-gray-500">Prioridad</label>
            <input
              className="input"
              type="number"
              min="0"
              placeholder="100"
              value={form.priority}
              onChange={(e) => setForm((v) => ({ ...v, priority: e.target.value }))}
              disabled={!canEdit}
            />
            <p className="text-xs text-gray-500">Menor numero = se aplica antes.</p>
          </div>

          <div className="space-y-1">
            <label className="block text-xs text-gray-500">Canal</label>
            <select
              className="input"
              value={form.channel_scope}
              onChange={(e) => setForm((v) => ({ ...v, channel_scope: e.target.value }))}
              disabled={!canEdit}
            >
              <option value="both">Local + online</option>
              <option value="local">Solo local</option>
              <option value="online">Solo online</option>
            </select>
            <p className="text-xs text-gray-500">Indica donde puede activarse la promo.</p>
          </div>

          <div className="space-y-1">
            <label className="block text-xs text-gray-500">Modo de activacion</label>
            <select
              className="input"
              value={form.activation_mode}
              onChange={(e) => setForm((v) => ({ ...v, activation_mode: e.target.value }))}
              disabled={!canEdit}
            >
              <option value="automatic">Automatica</option>
              <option value="coupon">Solo cupon</option>
              <option value="both">Automatica + cupon</option>
            </select>
            <p className="text-xs text-gray-500">Automatico la aplica sola. Cupon exige codigo.</p>
          </div>

          <div className="space-y-1">
            <label className="block text-xs text-gray-500">Codigo cupon</label>
            <input
              className="input"
              placeholder="Ej: OTONO20"
              value={form.coupon_code}
              onChange={(e) => setForm((v) => ({ ...v, coupon_code: e.target.value }))}
              disabled={!canEdit}
            />
            <p className="text-xs text-gray-500">Obligatorio si el modo incluye cupon.</p>
          </div>

          <div className="space-y-1">
            <label className="block text-xs text-gray-500">Estado y combinacion</label>
            <div className="grid grid-cols-2 gap-2">
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) => setForm((v) => ({ ...v, active: e.target.checked }))}
                  disabled={!canEdit}
                />
                Activa
              </label>
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.combinable}
                  onChange={(e) => setForm((v) => ({ ...v, combinable: e.target.checked }))}
                  disabled={!canEdit}
                />
                Combinable
              </label>
            </div>
            <p className="text-xs text-gray-500">Si no es combinable, bloquea esas unidades para promos siguientes.</p>
          </div>

          <div className="space-y-1">
            <label className="block text-xs text-gray-500">Vigencia desde</label>
            <input
              className="input"
              type="datetime-local"
              value={form.valid_from}
              onChange={(e) => setForm((v) => ({ ...v, valid_from: e.target.value }))}
              disabled={!canEdit}
            />
            <p className="text-xs text-gray-500">Fecha/hora inicial de activacion.</p>
          </div>

          <div className="space-y-1">
            <label className="block text-xs text-gray-500">Vigencia hasta</label>
            <input
              className="input"
              type="datetime-local"
              value={form.valid_until}
              onChange={(e) => setForm((v) => ({ ...v, valid_until: e.target.value }))}
              disabled={!canEdit}
            />
            <p className="text-xs text-gray-500">Fecha/hora limite. Vacio = sin fin.</p>
          </div>
        </div>

        {form.promo_type === 'percent_off' ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div className="space-y-1">
                <label className="block text-xs text-gray-500">% de descuento</label>
                <input
                  className="input"
                  type="number"
                  min="0.01"
                  max="100"
                  step="0.01"
                  value={form.discount_pct}
                  onChange={(e) => setForm((v) => ({ ...v, discount_pct: e.target.value }))}
                  disabled={!canEdit}
                />
                <p className="text-xs text-gray-500">Porcentaje que se descuenta sobre lineas elegibles.</p>
              </div>
            </div>

            <div className="space-y-2">
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.applies_to_all_products}
                  onChange={(e) => setForm((v) => ({ ...v, applies_to_all_products: e.target.checked }))}
                  disabled={!canEdit}
                />
                Aplica a todos los productos
              </label>
              <p className="text-xs text-gray-500">
                Marcado: no limita por producto. Desmarcado: elige manualmente que productos participan.
              </p>
              {!form.applies_to_all_products ? (
                <div className="border rounded p-2 max-h-52 overflow-auto grid grid-cols-1 md:grid-cols-2 gap-1">
                  {products.map((p) => (
                    <label key={p.id} className="inline-flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={form.product_ids.includes(Number(p.id))}
                        onChange={() => toggleProduct(p.id)}
                        disabled={!canEdit}
                      />
                      {p.name}
                    </label>
                  ))}
                </div>
              ) : null}
              {!form.applies_to_all_products && form.product_ids.length ? (
                <p className="text-xs text-gray-500">
                  Seleccionados: {form.product_ids.map((id) => productMap.get(Number(id))?.name || `#${id}`).join(', ')}
                </p>
              ) : null}
            </div>
          </>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div className="space-y-1">
                <label className="block text-xs text-gray-500">Modo X por Y</label>
                <select
                  className="input"
                  value={form.bogo_mode}
                  onChange={(e) => setForm((v) => ({ ...v, bogo_mode: e.target.value }))}
                  disabled={!canEdit}
                >
                  <option value="sku">Por SKU</option>
                  <option value="mix">Mix productos</option>
                </select>
                <p className="text-xs text-gray-500">SKU: seleccion explicita de variantes. Mix: todo el ticket.</p>
              </div>
              <div className="space-y-1">
                <label className="block text-xs text-gray-500">Lleva (buy_qty)</label>
                <input
                  className="input"
                  type="number"
                  min="1"
                  value={form.buy_qty}
                  onChange={(e) => setForm((v) => ({ ...v, buy_qty: e.target.value }))}
                  disabled={!canEdit}
                />
                <p className="text-xs text-gray-500">Cantidad minima de unidades por bloque.</p>
              </div>
              <div className="space-y-1">
                <label className="block text-xs text-gray-500">Paga (pay_qty)</label>
                <input
                  className="input"
                  type="number"
                  min="0"
                  value={form.pay_qty}
                  onChange={(e) => setForm((v) => ({ ...v, pay_qty: e.target.value }))}
                  disabled={!canEdit}
                />
                <p className="text-xs text-gray-500">Unidades cobradas por bloque (el resto se bonifica).</p>
              </div>
            </div>

            {isXForYSku ? (
              <div className="space-y-2">
                <label className="block text-xs text-gray-500">SKUs incluidos</label>
                <input
                  className="input"
                  value={skuQuery}
                  onChange={(e) => setSkuQuery(e.target.value)}
                  placeholder="Buscar SKU, barcode o producto"
                  disabled={!canEdit}
                />
                {skuLoading ? <p className="text-xs text-gray-500">Buscando SKUs...</p> : null}
                {String(skuQuery || '').trim().length >= 2 && !skuLoading ? (
                  <div className="border rounded p-2 max-h-44 overflow-auto space-y-1">
                    {skuResults.length ? (
                      skuResults.map((row) => {
                        const alreadyAdded = selectedVariantIds.has(Number(row.id));
                        return (
                          <div key={row.id} className="flex items-center justify-between gap-2 text-sm">
                            <div>
                              <strong>{row.sku || `#${row.id}`}</strong>
                              <span className="text-gray-500"> {row.producto || '-'}</span>
                            </div>
                            <button
                              type="button"
                              className="px-2 py-1 rounded border"
                              onClick={() => addVariant(row)}
                              disabled={!canEdit || alreadyAdded}
                            >
                              {alreadyAdded ? 'Agregado' : 'Agregar'}
                            </button>
                          </div>
                        );
                      })
                    ) : (
                      <p className="text-xs text-gray-500">Sin coincidencias.</p>
                    )}
                  </div>
                ) : null}

                <div className="border rounded p-2 max-h-52 overflow-auto space-y-1">
                  {selectedVariants.length ? (
                    selectedVariants.map((row) => (
                      <div key={row.id} className="flex items-center justify-between gap-2 text-sm">
                        <div>
                          <strong>{row.sku || `#${row.id}`}</strong>
                          <span className="text-gray-500"> {row.producto || '-'}</span>
                        </div>
                        <button
                          type="button"
                          className="px-2 py-1 rounded border"
                          onClick={() => removeVariant(row.id)}
                          disabled={!canEdit}
                        >
                          Quitar
                        </button>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-gray-500">No hay SKUs seleccionados.</p>
                  )}
                </div>
              </div>
            ) : null}

            {isXForYMix ? (
              <p className="text-xs text-gray-500">
                En modo mix entran todos los productos del ticket y se bonifican las unidades mas baratas.
              </p>
            ) : null}
          </>
        )}

        <div className="flex gap-2">
          <button className="btn" type="submit" disabled={saving || loading || !canEdit}>
            {form.id ? 'Guardar cambios' : 'Crear promocion'}
          </button>
          <button
            className="px-3 py-2 rounded border"
            type="button"
            onClick={resetForm}
            disabled={saving}
          >
            Limpiar
          </button>
        </div>
      </form>

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {msg ? <p className="text-sm text-green-700">{msg}</p> : null}
    </div>
  );
}
