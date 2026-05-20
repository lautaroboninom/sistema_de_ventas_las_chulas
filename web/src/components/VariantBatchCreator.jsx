import { useEffect, useMemo, useState } from 'react';
import { getRetailVarianteBarcodeLabelsUrl, postRetailVariante } from '../lib/api';
import { attrCode, dedupValues, normalizeValueError, splitValues } from '../lib/variantAttributes';
import InfoHint from './InfoHint';
import { VariantAttributeMultiRows } from './VariantAttributeRows';

function errMsg(error) {
  return error?.message || 'Ocurrio un error inesperado';
}

function explainVariantCombinationError(error) {
  const detail = String(error?.data?.detail || error?.message || '').toLowerCase();
  if (!detail.includes('ya existe una variante con esa combinacion')) return errMsg(error);
  if (detail.includes('inactiva')) {
    return 'Ya existe una variante inactiva de este producto con esos mismos atributos.';
  }
  return 'Ya existe otra variante de este producto con esos mismos atributos.';
}

function HelpTitle({ as: Tag = 'h3', className = '', children, help }) {
  return (
    <Tag className={`inline-flex items-center gap-2 ${className}`}>
      <span>{children}</span>
      <InfoHint text={help} />
    </Tag>
  );
}

function cartesianProduct(groups) {
  if (!groups.length) return [];
  return groups.reduce(
    (acc, group) => {
      const out = [];
      acc.forEach((partial) => {
        group.values.forEach((value) => {
          out.push([...partial, { attribute_code: group.attribute_code, value }]);
        });
      });
      return out;
    },
    [[]],
  );
}

function rowLabel(optionValues) {
  return (optionValues || [])
    .map((opt) => `${opt.attribute_code}=${opt.value}`)
    .join(' | ');
}

function toNum(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function inputMoney(value, fallback = '') {
  if (value === null || value === undefined || value === '') return fallback;
  return String(value);
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

const EMPTY_ATTR_ROW = { attribute_code: '', values_text: '' };

export default function VariantBatchCreator({
  products = [],
  attributes = [],
  attributeValuesByCode = {},
  suppliers = [],
  canEdit = true,
  initialProductId = '',
  title = 'Generador masivo de variantes',
  onBatchFinished,
}) {
  const [productId, setProductId] = useState(initialProductId ? String(initialProductId) : '');
  const [supplierId, setSupplierId] = useState('');
  const [batchPriceStore, setBatchPriceStore] = useState('');
  const [batchPriceOnline, setBatchPriceOnline] = useState('');
  const [attrRows, setAttrRows] = useState([{ ...EMPTY_ATTR_ROW }]);
  const [generatedRows, setGeneratedRows] = useState([]);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [visibleGeneratedBarcodes, setVisibleGeneratedBarcodes] = useState({});

  useEffect(() => {
    setProductId(initialProductId ? String(initialProductId) : '');
    setGeneratedRows([]);
  }, [initialProductId]);

  const selectedProduct = useMemo(
    () => (products || []).find((p) => String(p?.id || '') === String(productId || '')) || null,
    [products, productId],
  );

  useEffect(() => {
    const store = inputMoney(selectedProduct?.default_price_store_ars, '');
    const online = inputMoney(selectedProduct?.default_price_online_ars, store);
    setBatchPriceStore(store);
    setBatchPriceOnline(online || store);
  }, [selectedProduct]);

  const usedAttrCodes = useMemo(
    () =>
      new Set(
        (attrRows || [])
          .map((row) => attrCode(row.attribute_code))
          .filter(Boolean),
      ),
    [attrRows],
  );

  const activeAttrCount = attributes.filter((a) => a?.active !== false).length;
  const canAddAttrRow = activeAttrCount === 0 || usedAttrCodes.size < activeAttrCount;

  function availableAttrsForRow(idx) {
    const rows = Array.isArray(attrRows) ? attrRows : [];
    const current = attrCode(rows[idx]?.attribute_code);
    const selected = new Set(
      rows
        .filter((_, i) => i !== idx)
        .map((row) => attrCode(row.attribute_code))
        .filter(Boolean),
    );

    return attributes.filter((a) => {
      if (a?.active === false) return false;
      const code = attrCode(a.code);
      return !selected.has(code) || code === current;
    });
  }

  function updateAttrRow(idx, patch) {
    setAttrRows((prev) => prev.map((row, i) => (i === idx ? { ...row, ...patch } : row)));
  }

  function addAttrRow() {
    setAttrRows((prev) => {
      const used = new Set((prev || []).map((row) => attrCode(row.attribute_code)).filter(Boolean));
      const firstFree = attributes.find((a) => a?.active !== false && !used.has(attrCode(a.code)));
      return [...prev, { attribute_code: firstFree ? firstFree.code : '', values_text: '' }];
    });
  }

  function removeAttrRow(idx) {
    setAttrRows((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      return next.length ? next : [{ ...EMPTY_ATTR_ROW }];
    });
  }

  function buildCombinations() {
    setErr('');
    setMsg('');
    const parsedGroups = [];
    const seenCodes = new Set();

    for (let i = 0; i < attrRows.length; i += 1) {
      const row = attrRows[i] || {};
      const code = attrCode(row.attribute_code);
      const values = dedupValues(splitValues(row.values_text));
      if (!code && values.length === 0) continue;
      if (!code || values.length === 0) {
        setErr(`Completa atributo y lista de valores en la fila ${i + 1}.`);
        return;
      }
      if (seenCodes.has(code)) {
        setErr(`No se puede repetir atributo en la fila ${i + 1}.`);
        return;
      }
      seenCodes.add(code);
      parsedGroups.push({ attribute_code: code, values });
    }

    if (!productId) {
      setErr('Selecciona producto base.');
      return;
    }
    if (!parsedGroups.length) {
      setErr('Carga al menos un atributo con valores.');
      return;
    }

    const combos = cartesianProduct(parsedGroups);
    if (!combos.length) {
      setErr('No se pudieron generar combinaciones.');
      return;
    }
    if (combos.length > 250) {
      setErr('Demasiadas combinaciones. Reduce valores por atributo (max 250 por lote).');
      return;
    }

    setGeneratedRows(
      combos.map((optionValues, idx) => ({
        row_key: `${idx + 1}-${rowLabel(optionValues)}`,
        option_values: optionValues,
        row_label: rowLabel(optionValues),
        sku: '',
        barcode_internal: '',
        price_store_ars: batchPriceStore || '0',
        price_online_ars: batchPriceOnline || batchPriceStore || '0',
        cost_avg_ars: '0',
        stock_on_hand: '0',
        stock_min: '0',
        status: 'idle',
        detail: '',
        created: null,
      })),
    );
    setMsg(`Se generaron ${combos.length} combinaciones.`);
  }

  function updateGeneratedRow(idx, patch) {
    setGeneratedRows((prev) => prev.map((row, i) => (i === idx ? { ...row, ...patch } : row)));
  }

  function removeGeneratedRow(idx) {
    setGeneratedRows((prev) => prev.filter((_, i) => i !== idx));
  }

  async function saveBatch() {
    if (!canEdit) return;
    if (!productId) {
      setErr('Selecciona producto base.');
      return;
    }
    if (!generatedRows.length) {
      setErr('No hay combinaciones para guardar.');
      return;
    }

    setSaving(true);
    setErr('');
    setMsg('');
    const createdRows = [];
    let okCount = 0;
    let failCount = 0;

    for (let i = 0; i < generatedRows.length; i += 1) {
      const row = generatedRows[i];
      const payload = {
        product_id: Number(productId),
        option_values: row.option_values,
        sku: String(row.sku || '').trim() || undefined,
        barcode_internal: String(row.barcode_internal || '').trim() || undefined,
        supplier_id: supplierId ? Number(supplierId) : undefined,
        price_store_ars: toNum(row.price_store_ars, 0),
        price_online_ars: toNum(row.price_online_ars, 0),
        cost_avg_ars: toNum(row.cost_avg_ars, 0),
        stock_on_hand: Math.trunc(toNum(row.stock_on_hand, 0)),
        stock_min: Math.max(0, Math.trunc(toNum(row.stock_min, 0))),
      };

      try {
        const created = await postRetailVariante(payload);
        createdRows.push(created);
        okCount += 1;
        setGeneratedRows((prev) =>
          prev.map((curr, idx) =>
            idx === i
              ? {
                  ...curr,
                  status: 'ok',
                  detail: `Creada #${created?.id || ''}`,
                  created,
                }
              : curr,
          ),
        );
      } catch (error) {
        const suggestion = normalizeValueError(error);
        failCount += 1;
        setGeneratedRows((prev) =>
          prev.map((curr, idx) =>
            idx === i
              ? {
                  ...curr,
                  status: 'err',
                  detail: suggestion?.detail || explainVariantCombinationError(error),
                  created: null,
                }
              : curr,
          ),
        );
      }
    }

    setSaving(false);
    setMsg(`Lote finalizado. Exitosas: ${okCount}. Con error: ${failCount}.`);
    if (typeof onBatchFinished === 'function') {
      onBatchFinished(createdRows);
    }
  }

  function toggleGeneratedBarcode(rowKey) {
    setVisibleGeneratedBarcodes((prev) => ({ ...prev, [rowKey]: !prev[rowKey] }));
  }

  function resolveGeneratedBarcode(row) {
    const direct = String(row?.created?.barcode_internal || '').trim();
    if (direct) return direct;
    const list = Array.isArray(row?.created?.barcodes) ? row.created.barcodes : [];
    const primary = list.find((item) => item?.is_primary) || list[0];
    return String(primary?.barcode || '').trim();
  }

  async function copyBarcode(code) {
    const text = String(code || '').trim();
    if (!text) return;
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        setMsg(`Barcode copiado: ${text}`);
      }
    } catch (_error) {
      setErr('No se pudo copiar el barcode al portapapeles.');
    }
  }

  function printGeneratedBarcode(row) {
    const variantId = Number(row?.created?.id || 0);
    if (!Number.isInteger(variantId) || variantId <= 0) return;
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
    const url = getRetailVarianteBarcodeLabelsUrl(variantId, params);
    if (typeof window !== 'undefined') {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  }

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <HelpTitle
          as="h3"
          className="text-base font-semibold"
          help="Genera varias variantes de un producto en un solo paso combinando valores de atributos, por ejemplo todos los talles con un color."
        >
          {title}
        </HelpTitle>
        <button
          type="button"
          className="px-4 py-2.5 rounded border text-sm font-semibold bg-neutral-50 hover:bg-neutral-100 disabled:opacity-50"
          onClick={buildCombinations}
          disabled={!canEdit || saving}
        >
          Generar combinaciones
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
        <select
          className="input"
          value={productId}
          onChange={(e) => setProductId(e.target.value)}
          disabled={!canEdit || saving}
        >
          <option value="">Seleccionar producto base</option>
          {(products || []).map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>

        <input
          className="input"
          type="number"
          min="0"
          step="0.01"
          placeholder="Precio local del lote"
          value={batchPriceStore}
          onChange={(e) => {
            const value = e.target.value;
            setBatchPriceStore(value);
            setBatchPriceOnline((prev) => prev || value);
            setGeneratedRows((prev) =>
              prev.map((row) => ({
                ...row,
                price_store_ars: value,
                price_online_ars: row.price_online_ars || value,
              }))
            );
          }}
          disabled={!canEdit || saving}
        />

        <input
          className="input"
          type="number"
          min="0"
          step="0.01"
          placeholder="Precio online del lote"
          value={batchPriceOnline}
          onChange={(e) => {
            const value = e.target.value;
            setBatchPriceOnline(value);
            setGeneratedRows((prev) => prev.map((row) => ({ ...row, price_online_ars: value })));
          }}
          disabled={!canEdit || saving}
        />

        <select
          className="input"
          value={supplierId}
          onChange={(e) => setSupplierId(e.target.value)}
          disabled={!canEdit || saving}
        >
          <option value="">Proveedor EAN (opcional)</option>
          {(suppliers || []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}{s.ean_supplier_code ? ` - EAN ${s.ean_supplier_code}` : ''}
            </option>
          ))}
        </select>
      </div>

      <VariantAttributeMultiRows
        rows={attrRows}
        attributes={attributes}
        attributeValuesByCode={attributeValuesByCode}
        getAvailableAttributesForRow={availableAttrsForRow}
        onUpdateRow={updateAttrRow}
        onRemoveRow={removeAttrRow}
        onAddRow={addAttrRow}
        canAddRow={canAddAttrRow}
        disabled={!canEdit || saving}
        title="Atributos multivalor"
        help="Carga un atributo y varios valores separados por coma, punto y coma o salto de linea. El sistema combina esos valores para armar variantes."
        listIdPrefix="batch-attr-values"
      />

      {generatedRows.length ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <HelpTitle
              as="h4"
              className="text-sm font-semibold"
              help="Estas son las variantes que se van a crear. Antes de guardar puedes ajustar SKU, barcode, precio, costo, stock y quitar combinaciones que no existan."
            >
              Combinaciones generadas ({generatedRows.length})
            </HelpTitle>
            <button className="btn" type="button" onClick={saveBatch} disabled={!canEdit || saving}>
              {saving ? 'Guardando lote...' : 'Guardar lote'}
            </button>
          </div>

          <div className="overflow-auto border border-neutral-200 rounded">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="text-left border-b bg-neutral-50">
                  <th className="py-2 px-2">Combinacion</th>
                  <th className="py-2 px-2">SKU</th>
                  <th className="py-2 px-2">Barcode</th>
                  <th className="py-2 px-2">P. local</th>
                  <th className="py-2 px-2">P. online</th>
                  <th className="py-2 px-2">Costo</th>
                  <th className="py-2 px-2">Stock</th>
                  <th className="py-2 px-2">Min</th>
                  <th className="py-2 px-2">Estado</th>
                  <th className="py-2 px-2">Accion</th>
                </tr>
              </thead>
              <tbody>
                {generatedRows.map((row, idx) => (
                  <tr key={row.row_key} className="border-b last:border-b-0 align-top">
                    <td className="py-2 px-2 whitespace-nowrap">{row.row_label}</td>
                    <td className="py-2 px-2">
                      <input
                        className="input"
                        value={row.sku}
                        onChange={(e) => updateGeneratedRow(idx, { sku: e.target.value })}
                        disabled={!canEdit || saving}
                      />
                    </td>
                    <td className="py-2 px-2">
                      <input
                        className="input"
                        value={row.barcode_internal}
                        onChange={(e) => updateGeneratedRow(idx, { barcode_internal: e.target.value })}
                        disabled={!canEdit || saving}
                        placeholder="vacío = autogenerar"
                      />
                      {!String(row.barcode_internal || '').trim() && row.status === 'ok' ? (
                        <div className="mt-1 flex flex-wrap gap-1">
                          <button
                            type="button"
                            className="px-2 py-1 rounded border text-[11px] font-semibold hover:bg-gray-50"
                            onClick={() => toggleGeneratedBarcode(row.row_key)}
                            disabled={!resolveGeneratedBarcode(row)}
                          >
                            {visibleGeneratedBarcodes[row.row_key] ? 'Ocultar autogenerado' : 'Ver autogenerado'}
                          </button>
                          <button
                            type="button"
                            className="px-2 py-1 rounded border text-[11px] font-semibold hover:bg-gray-50"
                            onClick={() => copyBarcode(resolveGeneratedBarcode(row))}
                            disabled={!resolveGeneratedBarcode(row)}
                          >
                            Copiar
                          </button>
                          <button
                            type="button"
                            className="px-2 py-1 rounded border text-[11px] font-semibold hover:bg-gray-50"
                            onClick={() => printGeneratedBarcode(row)}
                            disabled={!resolveGeneratedBarcode(row)}
                          >
                            Imprimir
                          </button>
                        </div>
                      ) : null}
                      {!String(row.barcode_internal || '').trim() &&
                      row.status === 'ok' &&
                      visibleGeneratedBarcodes[row.row_key] &&
                      resolveGeneratedBarcode(row) ? (
                        <p className="mt-1 text-[11px] font-semibold text-green-700">
                          Barcode autogenerado: {resolveGeneratedBarcode(row)}
                        </p>
                      ) : null}
                    </td>
                    <td className="py-2 px-2">
                      <input
                        className="input"
                        type="number"
                        min="0"
                        step="0.01"
                        value={row.price_store_ars}
                        onChange={(e) => updateGeneratedRow(idx, { price_store_ars: e.target.value })}
                        disabled={!canEdit || saving}
                      />
                    </td>
                    <td className="py-2 px-2">
                      <input
                        className="input"
                        type="number"
                        min="0"
                        step="0.01"
                        value={row.price_online_ars}
                        onChange={(e) => updateGeneratedRow(idx, { price_online_ars: e.target.value })}
                        disabled={!canEdit || saving}
                      />
                    </td>
                    <td className="py-2 px-2">
                      <input
                        className="input"
                        type="number"
                        min="0"
                        step="0.01"
                        value={row.cost_avg_ars}
                        onChange={(e) => updateGeneratedRow(idx, { cost_avg_ars: e.target.value })}
                        disabled={!canEdit || saving}
                      />
                    </td>
                    <td className="py-2 px-2">
                      <input
                        className="input"
                        type="number"
                        step="1"
                        value={row.stock_on_hand}
                        onChange={(e) => updateGeneratedRow(idx, { stock_on_hand: e.target.value })}
                        disabled={!canEdit || saving}
                      />
                    </td>
                    <td className="py-2 px-2">
                      <input
                        className="input"
                        type="number"
                        min="0"
                        step="1"
                        value={row.stock_min}
                        onChange={(e) => updateGeneratedRow(idx, { stock_min: e.target.value })}
                        disabled={!canEdit || saving}
                      />
                    </td>
                    <td className="py-2 px-2">
                      {row.status === 'ok' ? <span className="text-green-700 font-semibold">{row.detail || 'OK'}</span> : null}
                      {row.status === 'err' ? <span className="text-red-700 font-semibold">{row.detail || 'Error'}</span> : null}
                      {row.status === 'idle' ? <span className="text-gray-500">Pendiente</span> : null}
                    </td>
                    <td className="py-2 px-2">
                      <button
                        type="button"
                        className="px-2 py-1 rounded border text-xs"
                        onClick={() => removeGeneratedRow(idx)}
                        disabled={!canEdit || saving}
                      >
                        Quitar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {msg ? <p className="text-sm text-green-700">{msg}</p> : null}
    </div>
  );
}
