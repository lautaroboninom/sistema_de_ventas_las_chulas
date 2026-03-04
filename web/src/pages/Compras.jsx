import { useEffect, useMemo, useState } from 'react';
import {
  getRetailAtributos,
  getRetailProductos,
  getRetailVariantes,
  postRetailCompra,
  postRetailProducto,
  postRetailVariante,
} from '../lib/api';

function errMsg(error) {
  return error?.message || 'Ocurrio un error inesperado';
}

const EMPTY_ITEM = {
  variant_id: '',
  variant_query: '',
  variant_name: '',
  quantity: '1',
  unit_cost_currency: '',
};

const EMPTY_CREATE_PRODUCT = {
  name: '',
  sku_prefix: '',
};

const EMPTY_CREATE_VARIANT = {
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

function variantName(row) {
  const producto = String(row?.producto || row?.display_name || '').trim();
  const firma = String(row?.option_signature || '').trim();
  const sku = String(row?.sku || '').trim();
  const base = firma ? `${producto} (${firma})` : producto;
  return sku ? `${base} - SKU ${sku}` : base;
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

function payloadItems(items) {
  return items.map((it, idx) => {
    const variantId = Number(it.variant_id);
    if (!Number.isInteger(variantId) || variantId <= 0) {
      throw new Error(`Selecciona una variante valida en la fila ${idx + 1}`);
    }

    const quantity = Number(it.quantity || 0);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      throw new Error(`Cantidad invalida en la fila ${idx + 1}`);
    }

    const unitCost = Number(it.unit_cost_currency || 0);
    if (!Number.isFinite(unitCost) || unitCost < 0) {
      throw new Error(`Costo unitario invalido en la fila ${idx + 1}`);
    }

    return {
      variant_id: variantId,
      quantity,
      unit_cost_currency: unitCost,
    };
  });
}

export default function ComprasPage() {
  const [supplierName, setSupplierName] = useState('');
  const [purchaseDate, setPurchaseDate] = useState('');
  const [currencyCode, setCurrencyCode] = useState('ARS');
  const [fxRate, setFxRate] = useState('');
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [notes, setNotes] = useState('');

  const [items, setItems] = useState([{ ...EMPTY_ITEM }]);

  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [result, setResult] = useState(null);

  const [lookupIndex, setLookupIndex] = useState(null);
  const [lookupRows, setLookupRows] = useState([]);
  const [lookupLoading, setLookupLoading] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [createTargetIndex, setCreateTargetIndex] = useState(null);
  const [createProducts, setCreateProducts] = useState([]);
  const [createAttributes, setCreateAttributes] = useState([]);
  const [createProductForm, setCreateProductForm] = useState({ ...EMPTY_CREATE_PRODUCT });
  const [createVariantForm, setCreateVariantForm] = useState({ ...EMPTY_CREATE_VARIANT });
  const [createLoadingData, setCreateLoadingData] = useState(false);
  const [createProductSaving, setCreateProductSaving] = useState(false);
  const [createVariantSaving, setCreateVariantSaving] = useState(false);
  const [createErr, setCreateErr] = useState('');
  const [createMsg, setCreateMsg] = useState('');

  const activeLookupQuery = useMemo(() => {
    if (lookupIndex == null) return '';
    return String(items[lookupIndex]?.variant_query || '').trim();
  }, [items, lookupIndex]);

  const createBusy = createLoadingData || createProductSaving || createVariantSaving;

  useEffect(() => {
    if (lookupIndex == null) {
      setLookupRows([]);
      return;
    }

    const query = activeLookupQuery;
    if (!query) {
      setLookupRows([]);
      return;
    }

    let cancelled = false;
    const timer = setTimeout(async () => {
      setLookupLoading(true);
      try {
        const rows = await getRetailVariantes({ q: query, active: 1 });
        if (cancelled) return;
        setLookupRows(Array.isArray(rows) ? rows.slice(0, 25) : []);
      } catch {
        if (!cancelled) setLookupRows([]);
      } finally {
        if (!cancelled) setLookupLoading(false);
      }
    }, 220);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [activeLookupQuery, lookupIndex]);

  useEffect(() => {
    if (!createOpen) return;
    let cancelled = false;

    (async () => {
      setCreateLoadingData(true);
      try {
        const [prods, attrs] = await Promise.all([
          getRetailProductos({ active: 1 }),
          getRetailAtributos(),
        ]);
        if (cancelled) return;
        setCreateProducts(Array.isArray(prods) ? prods : []);
        setCreateAttributes(Array.isArray(attrs) ? attrs : []);
      } catch (error) {
        if (cancelled) return;
        setCreateErr(errMsg(error));
        setCreateProducts([]);
        setCreateAttributes([]);
      } finally {
        if (!cancelled) setCreateLoadingData(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [createOpen]);

  function updateItem(idx, patch) {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  }

  function addItem() {
    setItems((prev) => [...prev, { ...EMPTY_ITEM }]);
  }

  function removeItem(idx) {
    setItems((prev) => prev.filter((_, i) => i !== idx));

    if (lookupIndex === idx) {
      setLookupIndex(null);
      setLookupRows([]);
    }
    if (lookupIndex != null && idx < lookupIndex) {
      setLookupIndex((current) => (current == null ? current : current - 1));
    }

    if (createTargetIndex === idx) {
      closeCreateModal();
    }
    if (createTargetIndex != null && idx < createTargetIndex) {
      setCreateTargetIndex((current) => (current == null ? current : current - 1));
    }
  }

  function onVariantQueryChange(idx, value) {
    updateItem(idx, {
      variant_query: value,
      variant_id: '',
      variant_name: '',
    });
    setLookupIndex(idx);
  }

  function onSelectVariant(idx, row) {
    const name = variantName(row);
    updateItem(idx, {
      variant_id: String(row.id),
      variant_name: name,
      variant_query: name,
    });
    setLookupRows([]);
    setLookupIndex(null);
  }

  function openCreateModal(idx) {
    const seed = String(items[idx]?.variant_query || '').trim();

    setCreateErr('');
    setCreateMsg('');
    setCreateTargetIndex(idx);
    setCreateProductForm({
      ...EMPTY_CREATE_PRODUCT,
      name: seed.slice(0, 80),
    });
    setCreateVariantForm({ ...EMPTY_CREATE_VARIANT });
    setCreateOpen(true);
  }

  function closeCreateModal() {
    setCreateOpen(false);
    setCreateTargetIndex(null);
    setCreateErr('');
    setCreateMsg('');
    setCreateProductForm({ ...EMPTY_CREATE_PRODUCT });
    setCreateVariantForm({ ...EMPTY_CREATE_VARIANT });
  }

  function availableCreateAttrsForRow(idx) {
    const rows = Array.isArray(createVariantForm.option_rows) ? createVariantForm.option_rows : [];
    const current = attrCode(rows[idx]?.attribute_code);
    const selected = new Set(
      rows
        .filter((_, i) => i !== idx)
        .map((row) => attrCode(row.attribute_code))
        .filter(Boolean)
    );

    return createAttributes.filter((a) => {
      const code = attrCode(a.code);
      return !selected.has(code) || code === current;
    });
  }

  function updateCreateOptionRow(idx, patch) {
    setCreateVariantForm((prev) => ({
      ...prev,
      option_rows: (prev.option_rows || []).map((row, i) => (i === idx ? { ...row, ...patch } : row)),
    }));
  }

  function addCreateOptionRow() {
    setCreateVariantForm((prev) => {
      const used = new Set((prev.option_rows || []).map((row) => attrCode(row.attribute_code)).filter(Boolean));
      const firstFree = createAttributes.find((a) => !used.has(attrCode(a.code)));
      return {
        ...prev,
        option_rows: [
          ...(prev.option_rows || []),
          { attribute_code: firstFree ? firstFree.code : '', value: '' },
        ],
      };
    });
  }

  function removeCreateOptionRow(idx) {
    setCreateVariantForm((prev) => {
      const next = (prev.option_rows || []).filter((_, i) => i !== idx);
      return {
        ...prev,
        option_rows: next.length ? next : [{ attribute_code: '', value: '' }],
      };
    });
  }

  async function createProductFromModal(e) {
    e.preventDefault();
    setCreateErr('');
    setCreateMsg('');
    setCreateProductSaving(true);

    try {
      const created = await postRetailProducto({
        name: createProductForm.name,
        sku_prefix: createProductForm.sku_prefix || undefined,
      });

      const nextProducts = [created, ...createProducts].filter(Boolean);
      setCreateProducts(nextProducts);
      setCreateVariantForm((prev) => ({
        ...prev,
        product_id: String(created?.id || ''),
      }));
      setCreateMsg(`Producto creado (#${created?.id || ''}).`);
    } catch (error) {
      setCreateErr(errMsg(error));
    } finally {
      setCreateProductSaving(false);
    }
  }

  async function createVariantFromModal(e) {
    e.preventDefault();
    setCreateErr('');
    setCreateMsg('');
    setCreateVariantSaving(true);

    try {
      const optionValues = buildOptionValues(createVariantForm.option_rows);
      const created = await postRetailVariante({
        product_id: Number(createVariantForm.product_id),
        option_values: optionValues,
        sku: createVariantForm.sku || undefined,
        barcode_internal: createVariantForm.barcode_internal || undefined,
        price_store_ars: Number(createVariantForm.price_store_ars || 0),
        price_online_ars: Number(createVariantForm.price_online_ars || 0),
        cost_avg_ars: Number(createVariantForm.cost_avg_ars || 0),
        stock_on_hand: Number(createVariantForm.stock_on_hand || 0),
        stock_min: Number(createVariantForm.stock_min || 0),
      });

      if (createTargetIndex != null) {
        onSelectVariant(createTargetIndex, created);
      }

      closeCreateModal();
    } catch (error) {
      setCreateErr(errMsg(error));
    } finally {
      setCreateVariantSaving(false);
    }
  }

  async function onSubmit(e) {
    e.preventDefault();
    setErr('');
    setResult(null);
    setSaving(true);

    try {
      const payload = {
        supplier_name: supplierName,
        purchase_date: purchaseDate || undefined,
        currency_code: currencyCode,
        fx_rate_ars: currencyCode === 'USD' ? Number(fxRate || 0) : undefined,
        invoice_number: invoiceNumber || undefined,
        notes: notes || undefined,
        items: payloadItems(items),
      };

      const created = await postRetailCompra(payload);
      setResult(created);
      setSupplierName('');
      setPurchaseDate('');
      setCurrencyCode('ARS');
      setFxRate('');
      setInvoiceNumber('');
      setNotes('');
      setItems([{ ...EMPTY_ITEM }]);
      setLookupIndex(null);
      setLookupRows([]);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setSaving(false);
    }
  }

  const usedCreateAttrs = new Set(
    (createVariantForm.option_rows || []).map((row) => attrCode(row.attribute_code)).filter(Boolean)
  );
  const canAddCreateOptionRow = createAttributes.length === 0 || usedCreateAttrs.size < createAttributes.length;

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">Compras</h1>
        <p className="text-sm text-gray-600">
          Ingreso de mercaderia con trazabilidad de costos y actualizacion de costo promedio por variante.
        </p>
      </div>

      <form className="card space-y-4" onSubmit={onSubmit}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Proveedor</label>
            <input className="input" value={supplierName} onChange={(e) => setSupplierName(e.target.value)} required />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Fecha compra</label>
            <input type="date" className="input" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Moneda</label>
            <select className="input" value={currencyCode} onChange={(e) => setCurrencyCode(e.target.value)}>
              <option value="ARS">ARS</option>
              <option value="USD">USD</option>
            </select>
          </div>
          {currencyCode === 'USD' ? (
            <div>
              <label className="block text-xs text-gray-500 mb-1">Tipo de cambio ARS</label>
              <input className="input" type="number" step="0.0001" min="0" value={fxRate} onChange={(e) => setFxRate(e.target.value)} required />
            </div>
          ) : null}
          <div>
            <label className="block text-xs text-gray-500 mb-1">Comprobante proveedor</label>
            <input className="input" value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} />
          </div>
          <div className="md:col-span-3">
            <label className="block text-xs text-gray-500 mb-1">Notas</label>
            <textarea className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>

        <div className="space-y-2">
          <h2 className="text-lg font-semibold">Items</h2>
          {items.map((it, idx) => (
            <div key={idx} className="grid grid-cols-1 md:grid-cols-12 gap-2 items-start">
              <div className="md:col-span-2">
                <label className="block text-xs text-gray-500 mb-1">Variante ID</label>
                <input
                  className="input bg-gray-100 text-gray-500 cursor-not-allowed"
                  value={it.variant_id || ''}
                  readOnly
                  disabled
                />
              </div>

              <div className="md:col-span-5 relative">
                <label className="block text-xs text-gray-500 mb-1">Nombre variante</label>
                <input
                  className="input"
                  placeholder="Buscar por nombre, SKU o barcode"
                  value={it.variant_query || ''}
                  onFocus={() => setLookupIndex(idx)}
                  onBlur={() => {
                    setTimeout(() => {
                      setLookupIndex((current) => (current === idx ? null : current));
                    }, 120);
                  }}
                  onChange={(e) => onVariantQueryChange(idx, e.target.value)}
                  required
                />
                {it.variant_name && it.variant_id ? (
                  <p className="mt-1 text-xs text-gray-500">{it.variant_name}</p>
                ) : null}

                {lookupIndex === idx ? (
                  <div className="absolute z-20 mt-1 w-full rounded border bg-white shadow-lg">
                    <div className="grid grid-cols-[120px_1fr] gap-2 border-b bg-gray-50 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-gray-600">
                      <span>Variante ID</span>
                      <span>Nombre</span>
                    </div>

                    {lookupLoading ? (
                      <div className="px-2 py-2 text-xs text-gray-500">Buscando...</div>
                    ) : lookupRows.length ? (
                      <div className="max-h-56 overflow-auto">
                        {lookupRows.map((row) => (
                          <button
                            key={row.id}
                            type="button"
                            className="grid w-full grid-cols-[120px_1fr] gap-2 border-b px-2 py-2 text-left text-sm hover:bg-gray-50"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => onSelectVariant(idx, row)}
                          >
                            <span className="font-semibold text-gray-700">{row.id}</span>
                            <span className="text-gray-700">{variantName(row)}</span>
                          </button>
                        ))}
                      </div>
                    ) : activeLookupQuery ? (
                      <div className="px-2 py-2 text-xs text-gray-600 space-y-2">
                        <p>No encontramos variantes para "{activeLookupQuery}".</p>
                        <button
                          type="button"
                          className="px-2 py-1 rounded border text-xs font-semibold hover:bg-gray-50"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => openCreateModal(idx)}
                        >
                          Agregar producto y variante
                        </button>
                      </div>
                    ) : (
                      <div className="px-2 py-2 text-xs text-gray-500">Escribe para buscar variantes.</div>
                    )}
                  </div>
                ) : null}
              </div>

              <div className="md:col-span-2">
                <label className="block text-xs text-gray-500 mb-1">Cantidad</label>
                <input
                  className="input"
                  type="number"
                  min="1"
                  placeholder="Cantidad"
                  value={it.quantity}
                  onChange={(e) => updateItem(idx, { quantity: e.target.value })}
                  required
                />
              </div>

              <div className="md:col-span-2">
                <label className="block text-xs text-gray-500 mb-1">Costo unitario</label>
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.0001"
                  placeholder="Costo en moneda"
                  value={it.unit_cost_currency}
                  onChange={(e) => updateItem(idx, { unit_cost_currency: e.target.value })}
                  required
                />
              </div>

              <button
                type="button"
                className="md:col-span-1 mt-6 px-3 py-2 rounded border"
                onClick={() => removeItem(idx)}
                disabled={items.length <= 1}
              >
                Quitar
              </button>
            </div>
          ))}

          <button type="button" className="px-3 py-2 rounded border" onClick={addItem}>
            Agregar item
          </button>
        </div>

        <button className="btn" type="submit" disabled={saving}>
          Registrar compra
        </button>
      </form>

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {result ? (
        <div className="card">
          <p className="text-sm text-green-700">
            Compra registrada: <strong>#{result.id}</strong> ({result.items?.length || 0} items)
          </p>
        </div>
      ) : null}

      {createOpen ? (
        <div className="fixed inset-0 z-50 bg-black/40 p-3 md:p-6" onClick={closeCreateModal}>
          <div
            className="mx-auto max-w-6xl rounded-xl border border-gray-200 bg-white shadow-2xl max-h-[92vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 z-10 border-b bg-white px-4 py-3 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Agregar producto y variante</h2>
                <p className="text-xs text-gray-500">Alta rapida sin salir de Compras.</p>
              </div>
              <button
                type="button"
                className="px-3 py-2 rounded border"
                onClick={closeCreateModal}
                disabled={createBusy}
              >
                Cerrar
              </button>
            </div>

            <div className="p-4 space-y-4">
              {createErr ? <p className="text-sm text-red-700">{createErr}</p> : null}
              {createMsg ? <p className="text-sm text-green-700">{createMsg}</p> : null}

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <form className="card space-y-3" onSubmit={createProductFromModal}>
                  <h3 className="text-base font-semibold">Nuevo producto</h3>
                  <input
                    className="input"
                    placeholder="Nombre"
                    value={createProductForm.name}
                    onChange={(e) => setCreateProductForm((prev) => ({ ...prev, name: e.target.value }))}
                    required
                  />
                  <input
                    className="input"
                    placeholder="Prefijo SKU (ej CHU-BLU)"
                    value={createProductForm.sku_prefix}
                    onChange={(e) => setCreateProductForm((prev) => ({ ...prev, sku_prefix: e.target.value }))}
                  />
                  <button className="btn" type="submit" disabled={createProductSaving}>
                    {createProductSaving ? 'Guardando...' : 'Crear producto'}
                  </button>
                </form>

                <form className="card space-y-3" onSubmit={createVariantFromModal}>
                  <h3 className="text-base font-semibold">Nueva variante</h3>

                  <select
                    className="input"
                    value={createVariantForm.product_id}
                    onChange={(e) => setCreateVariantForm((prev) => ({ ...prev, product_id: e.target.value }))}
                    required
                    disabled={createLoadingData}
                  >
                    <option value="">Seleccionar producto</option>
                    {createProducts.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>

                  <div className="space-y-2">
                    <h4 className="text-sm font-semibold">Atributos</h4>
                    {(createVariantForm.option_rows || []).map((row, idx) => {
                      const options = availableCreateAttrsForRow(idx);
                      return (
                        <div key={idx} className="grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
                          <div className="md:col-span-5">
                            <label className="block text-xs text-gray-500 mb-1">Atributo</label>
                            <select
                              className="input"
                              value={row.attribute_code || ''}
                              onChange={(e) => updateCreateOptionRow(idx, { attribute_code: e.target.value })}
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
                              onChange={(e) => updateCreateOptionRow(idx, { value: e.target.value })}
                              required
                            />
                          </div>

                          <div className="md:col-span-2">
                            <button
                              type="button"
                              className="px-3 py-2 rounded border w-full"
                              onClick={() => removeCreateOptionRow(idx)}
                              disabled={(createVariantForm.option_rows || []).length <= 1}
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
                      onClick={addCreateOptionRow}
                      disabled={!canAddCreateOptionRow}
                    >
                      Agregar atributo
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <input
                      className="input"
                      placeholder="SKU (opcional)"
                      value={createVariantForm.sku}
                      onChange={(e) => setCreateVariantForm((prev) => ({ ...prev, sku: e.target.value }))}
                    />
                    <input
                      className="input"
                      placeholder="Barcode interno (opcional)"
                      value={createVariantForm.barcode_internal}
                      onChange={(e) => setCreateVariantForm((prev) => ({ ...prev, barcode_internal: e.target.value }))}
                    />
                    <input
                      className="input"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Precio local"
                      value={createVariantForm.price_store_ars}
                      onChange={(e) => setCreateVariantForm((prev) => ({ ...prev, price_store_ars: e.target.value }))}
                      required
                    />
                    <input
                      className="input"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Precio online"
                      value={createVariantForm.price_online_ars}
                      onChange={(e) => setCreateVariantForm((prev) => ({ ...prev, price_online_ars: e.target.value }))}
                      required
                    />
                    <input
                      className="input"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Costo promedio"
                      value={createVariantForm.cost_avg_ars}
                      onChange={(e) => setCreateVariantForm((prev) => ({ ...prev, cost_avg_ars: e.target.value }))}
                    />
                    <input
                      className="input"
                      type="number"
                      min="0"
                      placeholder="Stock inicial"
                      value={createVariantForm.stock_on_hand}
                      onChange={(e) => setCreateVariantForm((prev) => ({ ...prev, stock_on_hand: e.target.value }))}
                    />
                    <input
                      className="input"
                      type="number"
                      min="0"
                      placeholder="Stock minimo"
                      value={createVariantForm.stock_min}
                      onChange={(e) => setCreateVariantForm((prev) => ({ ...prev, stock_min: e.target.value }))}
                    />
                  </div>

                  <button className="btn" type="submit" disabled={createVariantSaving}>
                    {createVariantSaving ? 'Guardando...' : 'Crear variante y seleccionar'}
                  </button>
                </form>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
