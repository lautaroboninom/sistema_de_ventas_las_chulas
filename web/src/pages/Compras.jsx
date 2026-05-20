import { useEffect, useMemo, useState } from 'react';
import {
  getRetailAtributos,
  getRetailAtributoValores,
  getRetailComprasConfig,
  getRetailComprasProveedores,
  getRetailProductos,
  getRetailVarianteBarcodeLabelsUrl,
  getRetailVariantes,
  patchRetailProducto,
  patchRetailVariante,
  postRetailCompra,
  postRetailProducto,
  postRetailVariante,
} from '../lib/api';
import { attrCode, dedupValues, normalizeValueError, splitValues } from '../lib/variantAttributes';
import { VariantAttributeMultiRows, VariantAttributeRows } from '../components/VariantAttributeRows';
import VariantBatchCreator from '../components/VariantBatchCreator';

function errMsg(error) {
  return error?.message || 'Ocurrio un error inesperado';
}

function parseNum(value) {
  if (value == null) return null;
  if (typeof value === 'string' && value.trim() === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function inputMoney(v, fallback = '') {
  if (v === null || v === undefined || v === '') return fallback;
  return String(v);
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

function makeEmptyItem(markupPct = '') {
  return {
    variant_id: '',
    variant_query: '',
    variant_name: '',
    supplier_product_name: '',
    barcode_internal: '',
    quantity: '1',
    unit_cost_currency: '',
    suggested_markup_pct: markupPct === '' ? '' : String(markupPct),
    unit_price_final_ars: '',
  };
}

const EMPTY_CREATE_PRODUCT = {
  name: '',
  sku_prefix: '',
  default_price_store_ars: '',
  default_price_online_ars: '',
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

const EMPTY_CREATE_PRODUCT_EDIT = {
  id: '',
  name: '',
  sku_prefix: '',
  default_price_store_ars: '0',
  default_price_online_ars: '0',
  active: true,
};

const EMPTY_CREATE_VARIANT_EDIT = {
  id: '',
  sku: '',
  barcode_internal: '',
  price_store_ars: '0',
  price_online_ars: '0',
  stock_min: '0',
  active: true,
};

const EMPTY_QUICK_ATTR_ROW = {
  attribute_code: '',
  values_text: '',
};

function variantName(row) {
  const producto = String(row?.producto || row?.display_name || '').trim();
  const firma = String(row?.option_signature || '').trim();
  const sku = String(row?.sku || '').trim();
  const base = firma ? `${producto} (${firma})` : producto;
  return sku ? `${base} - SKU ${sku}` : base;
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

function normalizeOptionSignature(optionValues) {
  const normalized = (Array.isArray(optionValues) ? optionValues : [])
    .map((option) => ({
      attribute_code: attrCode(option?.attribute_code),
      value: String(option?.value ?? option?.option_value ?? '')
        .trim()
        .toLowerCase(),
    }))
    .filter((option) => option.attribute_code && option.value);

  normalized.sort((a, b) =>
    a.attribute_code.localeCompare(b.attribute_code) || a.value.localeCompare(b.value)
  );
  return normalized.map((option) => `${option.attribute_code}=${option.value}`).join('|');
}

function parseOptionSignature(rawSignature) {
  const text = String(rawSignature || '').trim();
  if (!text) return '';
  const pairs = text
    .split('|')
    .map((token) => token.trim())
    .filter(Boolean)
    .map((token) => {
      const [left, ...rest] = token.split('=');
      return {
        attribute_code: left,
        value: rest.join('='),
      };
    });
  return normalizeOptionSignature(pairs);
}

function signatureFromVariantRow(row) {
  const fromOptions = normalizeOptionSignature(row?.option_values || []);
  if (fromOptions) return fromOptions;
  return parseOptionSignature(row?.option_signature);
}

function variantMatchScore(row, queryText) {
  const q = String(queryText || '').trim().toLowerCase();
  if (!q) return 9;
  const sku = String(row?.sku || '').trim().toLowerCase();
  const barcode = String(row?.barcode_internal || '').trim().toLowerCase();
  const product = String(row?.producto || '').trim().toLowerCase();
  const sig = String(row?.option_signature || '').trim().toLowerCase();
  if (sku === q || barcode === q) return 0;
  if (sku.startsWith(q) || barcode.startsWith(q)) return 1;
  if (sku.includes(q) || barcode.includes(q)) return 2;
  if (product.startsWith(q) || sig.startsWith(q)) return 3;
  if (product.includes(q) || sig.includes(q)) return 4;
  return 8;
}

function productMatchScore(row, queryText) {
  const q = String(queryText || '').trim().toLowerCase();
  if (!q) return 10;
  const name = String(row?.name || '').trim().toLowerCase();
  if (name === q) return 0;
  if (name.startsWith(q)) return 1;
  if (name.includes(q)) return 2;
  return 8;
}

function buildLookupItems(variantRows, productRows, queryText = '') {
  const variants = (Array.isArray(variantRows) ? variantRows : [])
    .map((row) => ({ kind: 'variant', key: `v-${row.id}`, score: variantMatchScore(row, queryText), row }))
    .sort((a, b) => a.score - b.score || Number(a.row?.id || 0) - Number(b.row?.id || 0));

  const products = (Array.isArray(productRows) ? productRows : [])
    .map((row) => ({ kind: 'product', key: `p-${row.id}`, score: productMatchScore(row, queryText), row }))
    .sort((a, b) => a.score - b.score || Number(a.row?.id || 0) - Number(b.row?.id || 0));

  return [...variants.slice(0, 25), ...products.slice(0, 15)];
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
    const finalPrice = Number(it.unit_price_final_ars);
    if (!Number.isFinite(finalPrice) || finalPrice < 0) {
      throw new Error(`Precio final invalido en la fila ${idx + 1}`);
    }
    const suggestedMarkupPct = parseNum(it.suggested_markup_pct);
    if (suggestedMarkupPct == null) {
      throw new Error(`Margen objetivo invalido en la fila ${idx + 1}`);
    }
    if (suggestedMarkupPct < 0) {
      throw new Error(`Margen objetivo no puede ser negativo en la fila ${idx + 1}`);
    }

    return {
      variant_id: variantId,
      supplier_product_name: String(it.supplier_product_name || '').trim() || undefined,
      quantity,
      unit_cost_currency: unitCost,
      suggested_markup_pct: suggestedMarkupPct,
      unit_price_final_ars: finalPrice,
    };
  });
}

export default function ComprasPage() {
  const [supplierName, setSupplierName] = useState('');
  const [purchaseDate, setPurchaseDate] = useState('');
  const [currencyCode, setCurrencyCode] = useState('ARS');
  const [fxRate, setFxRate] = useState('');
  const [defaultMarkupPct, setDefaultMarkupPct] = useState(100);
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [notes, setNotes] = useState('');

  const [items, setItems] = useState([makeEmptyItem()]);

  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [result, setResult] = useState(null);
  const [suppliersRows, setSuppliersRows] = useState([]);
  const [suppliersLoading, setSuppliersLoading] = useState(false);
  const [suppliersErr, setSuppliersErr] = useState('');
  const [suppliersQuery, setSuppliersQuery] = useState('');

  const [lookupIndex, setLookupIndex] = useState(null);
  const [lookupRows, setLookupRows] = useState([]);
  const [lookupLoading, setLookupLoading] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [createTargetIndex, setCreateTargetIndex] = useState(null);
  const [createProducts, setCreateProducts] = useState([]);
  const [createAttributes, setCreateAttributes] = useState([]);
  const [createAttrValuesByCode, setCreateAttrValuesByCode] = useState({});
  const [createProductForm, setCreateProductForm] = useState({ ...EMPTY_CREATE_PRODUCT });
  const [createVariantForm, setCreateVariantForm] = useState({ ...EMPTY_CREATE_VARIANT });
  const [createLoadingData, setCreateLoadingData] = useState(false);
  const [createProductSaving, setCreateProductSaving] = useState(false);
  const [createVariantSaving, setCreateVariantSaving] = useState(false);
  const [createProductEditForm, setCreateProductEditForm] = useState({ ...EMPTY_CREATE_PRODUCT_EDIT });
  const [createProductEditSaving, setCreateProductEditSaving] = useState(false);
  const [createProductVariants, setCreateProductVariants] = useState([]);
  const [createProductVariantsLoading, setCreateProductVariantsLoading] = useState(false);
  const [createVariantEditForm, setCreateVariantEditForm] = useState({ ...EMPTY_CREATE_VARIANT_EDIT });
  const [createVariantEditSaving, setCreateVariantEditSaving] = useState(false);
  const [createErr, setCreateErr] = useState('');
  const [createMsg, setCreateMsg] = useState('');
  const [quickOpen, setQuickOpen] = useState(false);
  const [quickTargetIndex, setQuickTargetIndex] = useState(null);
  const [quickProduct, setQuickProduct] = useState(null);
  const [quickAttrRows, setQuickAttrRows] = useState([{ ...EMPTY_QUICK_ATTR_ROW }]);
  const [quickApplying, setQuickApplying] = useState(false);
  const [quickErr, setQuickErr] = useState('');
  const [quickMsg, setQuickMsg] = useState('');
  const [itemsFlowMsg, setItemsFlowMsg] = useState('');
  const [itemsFlowMsgTone, setItemsFlowMsgTone] = useState('ok');

  const moneyFmt = useMemo(
    () =>
      new Intl.NumberFormat('es-AR', {
        style: 'currency',
        currency: 'ARS',
        maximumFractionDigits: 2,
      }),
    [],
  );

  const activeLookupQuery = useMemo(() => {
    if (lookupIndex == null) return '';
    return String(items[lookupIndex]?.variant_query || '').trim();
  }, [items, lookupIndex]);

  const createBusy =
    createLoadingData ||
    createProductSaving ||
    createVariantSaving ||
    createProductEditSaving ||
    createVariantEditSaving ||
    createProductVariantsLoading;

  async function fetchSuppliers(queryText = '') {
    setSuppliersLoading(true);
    setSuppliersErr('');
    try {
      const rows = await getRetailComprasProveedores({
        q: queryText || undefined,
        limit: 200,
      });
      setSuppliersRows(Array.isArray(rows) ? rows : []);
    } catch (error) {
      setSuppliersErr(errMsg(error));
      setSuppliersRows([]);
    } finally {
      setSuppliersLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cfg = await getRetailComprasConfig();
        if (cancelled) return;
        const pct = Number(cfg?.purchase_default_markup_pct);
        const nextDefaultPct = Number.isFinite(pct) && pct >= 0 ? pct : 100;
        setDefaultMarkupPct(nextDefaultPct);
        setItems((prev) => {
          const markupTxt = nextDefaultPct.toFixed(2);
          let changed = false;
          const next = prev.map((row) => {
            if (String(row?.suggested_markup_pct ?? '').trim() !== '') return row;
            changed = true;
            return {
              ...row,
              suggested_markup_pct: markupTxt,
              unit_price_final_ars: row.unit_price_final_ars || '0.00',
            };
          });
          return changed ? next : prev;
        });
      } catch {
        if (cancelled) return;
        setDefaultMarkupPct(100);
        setItems((prev) => {
          let changed = false;
          const next = prev.map((row) => {
            if (String(row?.suggested_markup_pct ?? '').trim() !== '') return row;
            changed = true;
            return {
              ...row,
              suggested_markup_pct: '100.00',
              unit_price_final_ars: row.unit_price_final_ars || '0.00',
            };
          });
          return changed ? next : prev;
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    fetchSuppliers('');
  }, []);

  useEffect(() => {
    if (lookupIndex == null) {
      setLookupRows([]);
      return;
    }

    const query = activeLookupQuery;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setLookupLoading(true);
      try {
        const [variantRows, productRows] = await Promise.all([
          query
            ? getRetailVariantes({ q: query, active: 1, limit: 25 })
            : getRetailVariantes({ active: 1, limit: 25 }),
          query
            ? getRetailProductos({ q: query, active: 1, limit: 15 })
            : getRetailProductos({ active: 1, limit: 15 }),
        ]);
        if (cancelled) return;
        setLookupRows(buildLookupItems(variantRows, productRows, query));
      } catch {
        if (!cancelled) setLookupRows([]);
      } finally {
        if (!cancelled) setLookupLoading(false);
      }
    }, query ? 220 : 0);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [activeLookupQuery, lookupIndex]);

  useEffect(() => {
    if (!createOpen && !quickOpen) return;
    let cancelled = false;

    (async () => {
      setCreateLoadingData(true);
      try {
        const [prods, attrs, attrVals] = await Promise.all([
          getRetailProductos({ active: 1 }),
          getRetailAtributos(),
          getRetailAtributoValores({ limit: 500 }),
        ]);
        if (cancelled) return;
        setCreateProducts(Array.isArray(prods) ? prods : []);
        setCreateAttributes(Array.isArray(attrs) ? attrs : []);
        const groupedValues = {};
        const valueItems = Array.isArray(attrVals?.items) ? attrVals.items : Array.isArray(attrVals) ? attrVals : [];
        valueItems.forEach((item) => {
          const code = attrCode(item?.attribute_code);
          if (!code) return;
          groupedValues[code] = [...(groupedValues[code] || []), item];
        });
        setCreateAttrValuesByCode(groupedValues);
      } catch (error) {
        if (cancelled) return;
        setCreateErr(errMsg(error));
        setCreateProducts([]);
        setCreateAttributes([]);
        setCreateAttrValuesByCode({});
      } finally {
        if (!cancelled) setCreateLoadingData(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [createOpen, quickOpen]);

  useEffect(() => {
    if (!createOpen) return;
    const pid = Number(createVariantForm.product_id || 0);
    if (!Number.isInteger(pid) || pid <= 0) {
      setCreateProductVariants([]);
      setCreateVariantEditForm({ ...EMPTY_CREATE_VARIANT_EDIT });
      return;
    }

    const selectedProduct = (createProducts || []).find((p) => Number(p.id) === pid);
    if (selectedProduct) {
      const defaultStore = inputMoney(selectedProduct.default_price_store_ars, '0');
      const defaultOnline = inputMoney(selectedProduct.default_price_online_ars, defaultStore || '0');
      setCreateProductEditForm({
        id: selectedProduct.id,
        name: selectedProduct.name || '',
        sku_prefix: selectedProduct.sku_prefix || '',
        default_price_store_ars: defaultStore,
        default_price_online_ars: defaultOnline,
        active: !!selectedProduct.active,
      });
      setCreateVariantForm((prev) => ({
        ...prev,
        price_store_ars: prev.price_store_ars || defaultStore,
        price_online_ars: prev.price_online_ars || defaultOnline || defaultStore,
      }));
    }

    let cancelled = false;
    (async () => {
      setCreateProductVariantsLoading(true);
      try {
        const rows = await getRetailVariantes({ product_id: pid, active: 1, limit: 300 });
        if (cancelled) return;
        setCreateProductVariants(Array.isArray(rows) ? rows : []);
      } catch {
        if (!cancelled) setCreateProductVariants([]);
      } finally {
        if (!cancelled) setCreateProductVariantsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [createOpen, createVariantForm.product_id, createProducts]);

  function updateItem(idx, patch) {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  }

  function newItemFromGeneralMarkup() {
    return {
      ...makeEmptyItem(toNum(defaultMarkupPct).toFixed(2)),
      unit_price_final_ars: '0.00',
    };
  }

  function addItem() {
    setItems((prev) => [...prev, newItemFromGeneralMarkup()]);
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

    if (quickTargetIndex === idx) {
      closeQuickModal();
    }
    if (quickTargetIndex != null && idx < quickTargetIndex) {
      setQuickTargetIndex((current) => (current == null ? current : current - 1));
    }
  }

  function toNum(value) {
    const n = parseNum(value);
    return n == null ? 0 : n;
  }

  function toFixed2(value) {
    return toNum(value).toFixed(2);
  }

  function fmtMoney(value) {
    return moneyFmt.format(toNum(value));
  }

  function fmtDate(value) {
    if (!value) return '-';
    try {
      return new Date(`${value}T00:00:00`).toLocaleDateString('es-AR');
    } catch {
      return value;
    }
  }

  function itemUnitCostArs(item, ctx = {}) {
    const base = toNum(item?.unit_cost_currency);
    const effectiveCurrency = ctx.currencyCode || currencyCode;
    if (effectiveCurrency === 'USD') {
      return base * toNum(ctx.fxRate ?? fxRate);
    }
    return base;
  }

  function itemSuggestedMarkupPct(item) {
    const pct = parseNum(item?.suggested_markup_pct);
    if (pct != null) return pct;
    return toNum(defaultMarkupPct);
  }

  function calcFinalFromMarkup(item, ctx = {}) {
    const unitCostArs = itemUnitCostArs(item, ctx);
    const markupPct = itemSuggestedMarkupPct(item);
    return (unitCostArs * (1 + (markupPct / 100)));
  }

  function recalcFinalPriceKeepingMarkup(item, ctx = {}) {
    const nextPrice = toFixed2(calcFinalFromMarkup(item, ctx));
    if (String(item?.unit_price_final_ars || '') === nextPrice) {
      return item;
    }
    return {
      ...item,
      unit_price_final_ars: nextPrice,
    };
  }

  function itemSuggestedPrice(item) {
    return calcFinalFromMarkup(item);
  }

  function itemMarginPct(item) {
    const unitCostArs = itemUnitCostArs(item);
    if (unitCostArs <= 0) return null;
    const finalPrice = toNum(item?.unit_price_final_ars);
    return ((finalPrice - unitCostArs) / unitCostArs) * 100;
  }

  function applyGeneralMarkupToAll() {
    const generalMarkupTxt = toFixed2(defaultMarkupPct);
    setItems((prev) =>
      prev.map((item) =>
        recalcFinalPriceKeepingMarkup(
          {
            ...item,
            suggested_markup_pct: generalMarkupTxt,
          },
        )
      )
    );
  }

  function onItemCostChange(idx, value) {
    setItems((prev) =>
      prev.map((item, i) => {
        if (i !== idx) return item;
        return recalcFinalPriceKeepingMarkup({
          ...item,
          unit_cost_currency: value,
        });
      })
    );
  }

  function onItemMarkupChange(idx, value) {
    setItems((prev) =>
      prev.map((item, i) => {
        if (i !== idx) return item;
        return recalcFinalPriceKeepingMarkup({
          ...item,
          suggested_markup_pct: value,
        });
      })
    );
  }

  function onItemFinalPriceChange(idx, value) {
    setItems((prev) =>
      prev.map((item, i) => {
        if (i !== idx) return item;
        const next = {
          ...item,
          unit_price_final_ars: value,
        };
        const finalPrice = parseNum(value);
        if (finalPrice == null) {
          return next;
        }
        const unitCostArs = itemUnitCostArs(next);
        const nextMarkupPct = unitCostArs > 0 ? ((finalPrice - unitCostArs) / unitCostArs) * 100 : 0;
        return {
          ...next,
          suggested_markup_pct: toFixed2(nextMarkupPct),
        };
      })
    );
  }

  function itemPrintCopies(item) {
    const qtyRaw = parseNum(item?.quantity);
    if (qtyRaw == null) return null;
    const qtyInt = Math.trunc(qtyRaw);
    if (!Number.isFinite(qtyInt) || qtyInt <= 0) return null;
    return Math.min(qtyInt, 200);
  }

  function canPrintItemLabel(item) {
    const variantId = Number(item?.variant_id);
    return Number.isInteger(variantId) && variantId > 0 && itemPrintCopies(item) != null;
  }

  function onPrintItemLabel(idx) {
    setErr('');
    const item = items[idx] || {};
    const variantId = Number(item?.variant_id);
    if (!Number.isInteger(variantId) || variantId <= 0) {
      setErr(`Selecciona una variante valida en la fila ${idx + 1} para imprimir etiqueta.`);
      return;
    }
    const copies = itemPrintCopies(item);
    if (copies == null) {
      setErr(`Cantidad invalida en la fila ${idx + 1} para imprimir etiqueta.`);
      return;
    }
    const prefs = loadBarcodePrintPrefs();
    const layout = normalizePrintLayout(prefs.layout);
    const params = {
      scope: 'primary',
      copies,
      layout,
    };
    if (layout === PRINT_LAYOUTS.THERMAL) {
      params.label_width_mm = normalizePrintMm(prefs.labelWidthMm, DEFAULT_PRINT_PREFS.labelWidthMm);
      params.label_height_mm = normalizePrintMm(prefs.labelHeightMm, DEFAULT_PRINT_PREFS.labelHeightMm);
    }
    const url = getRetailVarianteBarcodeLabelsUrl(variantId, {
      ...params,
    });
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  useEffect(() => {
    setItems((prev) => {
      let changed = false;
      const next = prev.map((item) => {
        const updated = recalcFinalPriceKeepingMarkup(item, { currencyCode, fxRate });
        if (updated !== item) changed = true;
        return updated;
      });
      return changed ? next : prev;
    });
  }, [currencyCode, fxRate]);

  function onVariantQueryChange(idx, value) {
    updateItem(idx, {
      variant_query: value,
      variant_id: '',
      variant_name: '',
      barcode_internal: '',
    });
    setItemsFlowMsg('');
    setLookupIndex(idx);
  }

  function applyVariantHistoryDefaults(baseItem, variantRow) {
    let next = { ...(baseItem || {}) };
    let touchedPricing = false;

    const lastQty = parseNum(variantRow?.last_purchase_quantity);
    if (lastQty != null && lastQty > 0) {
      next.quantity = String(Math.max(1, Math.trunc(lastQty)));
    }

    const rawCost = String(variantRow?.last_purchase_unit_cost_currency ?? '').trim();
    const parsedCost = parseNum(rawCost);
    if (rawCost !== '' && parsedCost != null && parsedCost >= 0) {
      next.unit_cost_currency = rawCost;
      touchedPricing = true;
    }

    const rawMarkup = String(variantRow?.last_purchase_suggested_markup_pct ?? '').trim();
    const parsedMarkup = parseNum(rawMarkup);
    if (rawMarkup !== '' && parsedMarkup != null && parsedMarkup >= 0) {
      next.suggested_markup_pct = rawMarkup;
      touchedPricing = true;
    }

    const supplierProductName = String(variantRow?.last_purchase_supplier_product_name || '').trim();
    if (supplierProductName && !String(next.supplier_product_name || '').trim()) {
      next.supplier_product_name = supplierProductName;
    }

    return touchedPricing ? recalcFinalPriceKeepingMarkup(next) : next;
  }

  function describeDefaultsApplied(row) {
    const chunks = [];
    const qty = parseNum(row?.last_purchase_quantity);
    if (qty != null && qty > 0) chunks.push(`Cantidad ${Math.max(1, Math.trunc(qty))}`);
    const cost = String(row?.last_purchase_unit_cost_currency ?? '').trim();
    if (cost) chunks.push(`Costo ${cost}`);
    const markup = String(row?.last_purchase_suggested_markup_pct ?? '').trim();
    if (markup) chunks.push(`Margen ${markup}%`);
    const supplierProductName = String(row?.last_purchase_supplier_product_name || '').trim();
    if (supplierProductName) chunks.push(`Nombre proveedor ${supplierProductName}`);
    return chunks.join(' | ');
  }

  function onSelectVariant(idx, row) {
    const name = variantName(row);
    setItems((prev) =>
      prev.map((item, i) => {
        if (i !== idx) return item;
        return applyVariantHistoryDefaults(
          {
            ...item,
            variant_id: String(row.id),
            variant_name: name,
            variant_query: name,
            barcode_internal: String(row?.barcode_internal || '').trim(),
          },
          row,
        );
      })
    );
    const defaultsText = describeDefaultsApplied(row);
    if (defaultsText) {
      setItemsFlowMsg(`Defaults aplicados desde ultima compra. ${defaultsText}.`);
      setItemsFlowMsgTone('ok');
    } else {
      setItemsFlowMsg('');
    }
    setLookupRows([]);
    setLookupIndex(null);
  }

  function buildItemFromVariant(baseItem, variantRow) {
    const name = variantName(variantRow);
    return applyVariantHistoryDefaults(
      {
        ...(baseItem || newItemFromGeneralMarkup()),
        variant_id: String(variantRow?.id || ''),
        variant_name: name,
        variant_query: name,
        barcode_internal: String(variantRow?.barcode_internal || '').trim(),
      },
      variantRow,
    );
  }

  function productDefaultPrices(product) {
    const store = inputMoney(product?.default_price_store_ars, '');
    const online = inputMoney(product?.default_price_online_ars, store);
    return { store, online: online || store };
  }

  function pricesPayloadFromProduct(product) {
    const prices = productDefaultPrices(product);
    const store = Number(prices.store || 0);
    const online = Number(prices.online || prices.store || 0);
    return {
      price_store_ars: Number.isFinite(store) ? store : 0,
      price_online_ars: Number.isFinite(online) ? online : Number.isFinite(store) ? store : 0,
    };
  }

  function createProductById(productId) {
    const pid = Number(productId || 0);
    return (createProducts || []).find((p) => Number(p.id) === pid) || null;
  }

  function onCreateVariantProductChange(productId) {
    const product = createProductById(productId);
    const prices = productDefaultPrices(product);
    setCreateVariantForm((prev) => ({
      ...prev,
      product_id: productId,
      price_store_ars: prices.store || prev.price_store_ars,
      price_online_ars: prices.online || prices.store || prev.price_online_ars,
    }));
  }

  function openQuickModal(idx, product) {
    if (!product?.id) return;
    setQuickErr('');
    setQuickMsg('');
    setCreateErr('');
    setCreateMsg('');
    setItemsFlowMsg('');
    setQuickTargetIndex(idx);
    setQuickProduct(product);
    setQuickAttrRows([{ ...EMPTY_QUICK_ATTR_ROW }]);
    setQuickOpen(true);
    setLookupRows([]);
    setLookupIndex(null);
  }

  function closeQuickModal() {
    setQuickOpen(false);
    setQuickTargetIndex(null);
    setQuickProduct(null);
    setQuickAttrRows([{ ...EMPTY_QUICK_ATTR_ROW }]);
    setQuickErr('');
    setQuickMsg('');
    setQuickApplying(false);
  }

  function availableQuickAttrsForRow(idx) {
    const rows = Array.isArray(quickAttrRows) ? quickAttrRows : [];
    const current = attrCode(rows[idx]?.attribute_code);
    const selected = new Set(
      rows
        .filter((_, i) => i !== idx)
        .map((row) => attrCode(row.attribute_code))
        .filter(Boolean)
    );

    return (createAttributes || []).filter((a) => {
      if (a?.active === false) return false;
      const code = attrCode(a.code);
      return !selected.has(code) || code === current;
    });
  }

  function updateQuickAttrRow(idx, patch) {
    setQuickAttrRows((prev) => (prev || []).map((row, i) => (i === idx ? { ...row, ...patch } : row)));
  }

  function addQuickAttrRow() {
    setQuickAttrRows((prev) => {
      const list = prev || [];
      const used = new Set(list.map((row) => attrCode(row.attribute_code)).filter(Boolean));
      const firstFree = (createAttributes || []).find((a) => a?.active !== false && !used.has(attrCode(a.code)));
      return [...list, { attribute_code: firstFree ? firstFree.code : '', values_text: '' }];
    });
  }

  function removeQuickAttrRow(idx) {
    setQuickAttrRows((prev) => {
      const next = (prev || []).filter((_, i) => i !== idx);
      return next.length ? next : [{ ...EMPTY_QUICK_ATTR_ROW }];
    });
  }

  function buildQuickCombinations() {
    const parsedGroups = [];
    const seenCodes = new Set();

    for (let i = 0; i < quickAttrRows.length; i += 1) {
      const row = quickAttrRows[i] || {};
      const code = attrCode(row.attribute_code);
      const values = dedupValues(splitValues(row.values_text));
      if (!code && !values.length) continue;
      if (!code || !values.length) {
        throw new Error(`Completa atributo y valores en la fila ${i + 1}.`);
      }
      if (seenCodes.has(code)) {
        throw new Error(`No se puede repetir atributo en la fila ${i + 1}.`);
      }
      seenCodes.add(code);
      parsedGroups.push({ attribute_code: code, values });
    }

    if (!parsedGroups.length) {
      throw new Error('Carga al menos un atributo con valores.');
    }

    const rawCombos = cartesianProduct(parsedGroups);
    if (!rawCombos.length) {
      throw new Error('No se pudieron generar combinaciones.');
    }
    if (rawCombos.length > 250) {
      throw new Error('Demasiadas combinaciones. Reduce valores por atributo (max 250 por lote).');
    }

    const unique = [];
    const seenSignatures = new Set();
    rawCombos.forEach((optionValues) => {
      const signature = normalizeOptionSignature(optionValues);
      if (!signature || seenSignatures.has(signature)) return;
      seenSignatures.add(signature);
      unique.push({ option_values: optionValues, signature });
    });
    return unique;
  }

  async function applyQuickCombinations() {
    if (quickApplying) return;
    setQuickErr('');
    setQuickMsg('');
    setErr('');

    const productId = Number(quickProduct?.id || 0);
    if (!Number.isInteger(productId) || productId <= 0) {
      setQuickErr('Producto invalido para generar combinaciones.');
      return;
    }
    if (quickTargetIndex == null || quickTargetIndex < 0 || quickTargetIndex >= items.length) {
      setQuickErr('La fila de destino ya no existe. Vuelve a seleccionar el producto.');
      return;
    }

    let combos = [];
    try {
      combos = buildQuickCombinations();
    } catch (error) {
      setQuickErr(errMsg(error));
      return;
    }

    setQuickApplying(true);
    try {
      const existing = await getRetailVariantes({ product_id: productId, limit: 500 });
      const bySignature = new Map();
      (Array.isArray(existing) ? existing : []).forEach((row) => {
        const signature = signatureFromVariantRow(row);
        if (!signature) return;
        const prev = bySignature.get(signature);
        if (!prev || (!prev.active && row.active)) {
          bySignature.set(signature, row);
        }
      });

      const resolved = [];
      let createdCount = 0;
      let reusedCount = 0;
      let errorCount = 0;

      for (const combo of combos) {
        const reused = bySignature.get(combo.signature);
        if (reused) {
          resolved.push(reused);
          reusedCount += 1;
          continue;
        }

        try {
          const created = await postRetailVariante({
            product_id: productId,
            option_values: combo.option_values,
            ...pricesPayloadFromProduct(quickProduct),
          });
          bySignature.set(combo.signature, created);
          resolved.push(created);
          createdCount += 1;
        } catch (_error) {
          errorCount += 1;
        }
      }

      if (!resolved.length) {
        setQuickErr('No se pudo aplicar ninguna combinacion. Revisa valores e intenta nuevamente.');
        setQuickMsg(`Creadas: ${createdCount}. Reusadas: ${reusedCount}. Con error: ${errorCount}.`);
        return;
      }

      const targetIndex = quickTargetIndex;
      setItems((prev) => {
        if (targetIndex == null || targetIndex < 0 || targetIndex >= prev.length) return prev;
        const source = prev[targetIndex] || newItemFromGeneralMarkup();
        const nextRows = resolved.map((row) => buildItemFromVariant(source, row));
        return [...prev.slice(0, targetIndex), ...nextRows, ...prev.slice(targetIndex + 1)];
      });

      setItemsFlowMsg(`Combinaciones aplicadas. Creadas: ${createdCount}. Reusadas: ${reusedCount}. Con error: ${errorCount}.`);
      setItemsFlowMsgTone(errorCount ? 'warn' : 'ok');
      closeQuickModal();
    } catch (error) {
      setQuickErr(errMsg(error));
    } finally {
      setQuickApplying(false);
    }
  }

  function openCreateModal(idx, options = {}) {
    const seed = String(items[idx]?.variant_query || '').trim();
    const selectedProduct = options?.product || null;
    const selectedPrices = productDefaultPrices(selectedProduct);

    setCreateErr('');
    setCreateMsg('');
    setItemsFlowMsg('');
    setCreateTargetIndex(idx);
    setCreateProductForm({
      ...EMPTY_CREATE_PRODUCT,
      name: selectedProduct?.name ? String(selectedProduct.name).slice(0, 80) : seed.slice(0, 80),
      default_price_store_ars: selectedPrices.store || '',
      default_price_online_ars: selectedPrices.online || selectedPrices.store || '',
    });
    setCreateVariantForm({
      ...EMPTY_CREATE_VARIANT,
      product_id: selectedProduct?.id ? String(selectedProduct.id) : '',
      price_store_ars: selectedPrices.store || '',
      price_online_ars: selectedPrices.online || selectedPrices.store || '',
    });
    setCreateProductEditForm(selectedProduct
      ? {
          id: selectedProduct.id,
          name: selectedProduct.name || '',
          sku_prefix: selectedProduct.sku_prefix || '',
          default_price_store_ars: selectedPrices.store || '0',
          default_price_online_ars: selectedPrices.online || selectedPrices.store || '0',
          active: !!selectedProduct.active,
        }
      : { ...EMPTY_CREATE_PRODUCT_EDIT });
    setCreateProductVariants([]);
    setCreateVariantEditForm({ ...EMPTY_CREATE_VARIANT_EDIT });
    setCreateOpen(true);
  }

  function closeCreateModal() {
    setCreateOpen(false);
    setCreateTargetIndex(null);
    setCreateErr('');
    setCreateMsg('');
    setCreateProductForm({ ...EMPTY_CREATE_PRODUCT });
    setCreateVariantForm({ ...EMPTY_CREATE_VARIANT });
    setCreateProductEditForm({ ...EMPTY_CREATE_PRODUCT_EDIT });
    setCreateProductVariants([]);
    setCreateVariantEditForm({ ...EMPTY_CREATE_VARIANT_EDIT });
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
      if (a?.active === false) return false;
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
      const firstFree = createAttributes.find((a) => a?.active !== false && !used.has(attrCode(a.code)));
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
        default_price_store_ars: Number(createProductForm.default_price_store_ars || 0),
        default_price_online_ars: Number(createProductForm.default_price_online_ars || createProductForm.default_price_store_ars || 0),
      });
      const createdPrices = productDefaultPrices(created);

      const nextProducts = [created, ...createProducts].filter(Boolean);
      setCreateProducts(nextProducts);
      setCreateVariantForm((prev) => ({
        ...prev,
        product_id: String(created?.id || ''),
        price_store_ars: prev.price_store_ars || createdPrices.store,
        price_online_ars: prev.price_online_ars || createdPrices.online || createdPrices.store,
      }));
      setCreateProductEditForm({
        id: created?.id || '',
        name: created?.name || '',
        sku_prefix: created?.sku_prefix || '',
        default_price_store_ars: createdPrices.store || '0',
        default_price_online_ars: createdPrices.online || createdPrices.store || '0',
        active: true,
      });
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
      const suggestion = normalizeValueError(error);
      setCreateErr(suggestion?.detail || errMsg(error));
    } finally {
      setCreateVariantSaving(false);
    }
  }

  async function saveCreateProductEdit(e) {
    e.preventDefault();
    if (!createProductEditForm?.id) return;
    setCreateErr('');
    setCreateMsg('');
    setCreateProductEditSaving(true);
    try {
      const updated = await patchRetailProducto(createProductEditForm.id, {
        name: createProductEditForm.name,
        sku_prefix: createProductEditForm.sku_prefix || undefined,
        default_price_store_ars: Number(createProductEditForm.default_price_store_ars || 0),
        default_price_online_ars: Number(createProductEditForm.default_price_online_ars || createProductEditForm.default_price_store_ars || 0),
        sync_variant_prices:
          Number(createProductEditForm.default_price_store_ars || 0) > 0 ||
          Number(createProductEditForm.default_price_online_ars || 0) > 0,
        active: !!createProductEditForm.active,
      });
      setCreateProducts((prev) =>
        (prev || []).map((p) => (Number(p.id) === Number(updated?.id) ? { ...p, ...updated } : p))
      );
      const updatedPrices = productDefaultPrices(updated);
      setCreateVariantForm((prev) => ({
        ...prev,
        price_store_ars: updatedPrices.store || prev.price_store_ars,
        price_online_ars: updatedPrices.online || updatedPrices.store || prev.price_online_ars,
      }));
      setCreateMsg('Producto actualizado.');
    } catch (error) {
      setCreateErr(errMsg(error));
    } finally {
      setCreateProductEditSaving(false);
    }
  }

  function startEditCreateVariant(row) {
    if (!row?.id) return;
    setCreateVariantEditForm({
      id: row.id,
      sku: row.sku || '',
      barcode_internal: row.barcode_internal || '',
      price_store_ars: String(row.price_store_ars ?? 0),
      price_online_ars: String(row.price_online_ars ?? 0),
      stock_min: String(row.stock_min ?? 0),
      active: !!row.active,
    });
  }

  async function saveCreateVariantEdit(e) {
    e.preventDefault();
    if (!createVariantEditForm?.id) return;
    setCreateErr('');
    setCreateMsg('');
    setCreateVariantEditSaving(true);
    try {
      await patchRetailVariante(createVariantEditForm.id, {
        sku: createVariantEditForm.sku,
        barcode_internal: createVariantEditForm.barcode_internal || undefined,
        price_store_ars: Number(createVariantEditForm.price_store_ars || 0),
        price_online_ars: Number(createVariantEditForm.price_online_ars || 0),
        stock_min: Number(createVariantEditForm.stock_min || 0),
        active: !!createVariantEditForm.active,
      });
      const pid = Number(createVariantForm.product_id || 0);
      if (Number.isInteger(pid) && pid > 0) {
        const rows = await getRetailVariantes({ product_id: pid, active: 1, limit: 300 });
        setCreateProductVariants(Array.isArray(rows) ? rows : []);
      }
      setCreateVariantEditForm({ ...EMPTY_CREATE_VARIANT_EDIT });
      setCreateMsg('Variante actualizada.');
    } catch (error) {
      setCreateErr(errMsg(error));
    } finally {
      setCreateVariantEditSaving(false);
    }
  }

  function useVariantFromCreateList(row) {
    if (!row?.id || createTargetIndex == null) return;
    onSelectVariant(createTargetIndex, row);
    closeCreateModal();
  }

  async function onCreateBatchFinished(rows) {
    const created = Array.isArray(rows) ? rows : [];
    if (!created.length) return;
    const pid = Number(createVariantForm.product_id || 0);
    if (Number.isInteger(pid) && pid > 0) {
      try {
        const refreshed = await getRetailVariantes({ product_id: pid, active: 1, limit: 300 });
        setCreateProductVariants(Array.isArray(refreshed) ? refreshed : []);
      } catch {
        // no-op
      }
    }
    if (createTargetIndex != null) {
      onSelectVariant(createTargetIndex, created[0]);
    }
  }

  function onSelectLookupItem(idx, item) {
    if (!item) return;
    if (item.kind === 'variant') {
      onSelectVariant(idx, item.row);
      return;
    }
    if (item.kind === 'product') {
      openQuickModal(idx, item.row);
    }
  }

  async function onSubmit(e) {
    e.preventDefault();
    setErr('');
    setResult(null);
    setItemsFlowMsg('');
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
      setItems([newItemFromGeneralMarkup()]);
      setLookupIndex(null);
      setLookupRows([]);
      setItemsFlowMsg('');
      fetchSuppliers(suppliersQuery);
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
  const quickAvailableAttributes = (createAttributes || []).filter((a) => a?.active !== false);
  const usedQuickAttrs = new Set(
    (quickAttrRows || []).map((row) => attrCode(row.attribute_code)).filter(Boolean)
  );
  const canAddQuickAttrRow =
    quickAvailableAttributes.length === 0 || usedQuickAttrs.size < quickAvailableAttributes.length;

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">Compras / Proveedores</h1>
        <p className="text-sm text-gray-600">
          Ingreso de mercaderia con trazabilidad de costos y actualizacion de costo promedio por variante.
        </p>
      </div>

      <form className="card relative z-30 isolate space-y-4" onSubmit={onSubmit}>
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
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Margen general (%)</label>
              <input
                className="input"
                type="number"
                min="0"
                step="0.01"
                value={defaultMarkupPct}
                onChange={(e) => setDefaultMarkupPct(toNum(e.target.value))}
              />
            </div>
            <button
              type="button"
              className="px-3 py-2 rounded border"
              onClick={applyGeneralMarkupToAll}
            >
              Aplicar margen general a todos
            </button>
            <p className="text-xs text-gray-500">
              El margen general es local a esta pantalla y no cambia la configuracion global.
            </p>
          </div>
          <h2 className="text-lg font-semibold">Items</h2>
          {items.map((it, idx) => {
            const marginPct = itemMarginPct(it);
            const printCopies = itemPrintCopies(it);
            return (
            <div
              key={idx}
              className="grid grid-cols-1 md:grid-cols-12 gap-2 items-start rounded border border-gray-200 p-2"
            >
              <div className="md:col-span-1">
                <label className="block text-xs text-gray-500 mb-1">Variante ID</label>
                <input
                  className="input bg-gray-100 text-gray-500 cursor-not-allowed"
                  value={it.variant_id || ''}
                  readOnly
                  disabled
                />
              </div>

              <div className="md:col-span-3 relative">
                <label className="block text-xs text-gray-500 mb-1">Nombre interno</label>
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
                  <div className="absolute z-[70] mt-1 w-full rounded border bg-white shadow-lg overflow-hidden">
                    <div className="grid grid-cols-[100px_1fr_90px] gap-2 border-b bg-gray-50 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-gray-600">
                      <span>ID</span>
                      <span>Nombre</span>
                      <span>Tipo</span>
                    </div>
                    <div className="max-h-80 min-h-[240px] flex flex-col">
                      <div className="min-h-0 flex-1 overflow-auto">
                        {lookupLoading ? (
                          <div className="px-2 py-2 text-xs text-gray-500">Buscando...</div>
                        ) : lookupRows.length ? (
                          lookupRows.map((item) => (
                            <button
                              key={item.key}
                              type="button"
                              className="grid w-full grid-cols-[100px_1fr_90px] gap-2 border-b px-2 py-2 text-left text-sm hover:bg-gray-50"
                              onMouseDown={(e) => e.preventDefault()}
                              onClick={() => onSelectLookupItem(idx, item)}
                            >
                              <span className="font-semibold text-gray-700">{item.row?.id}</span>
                              <span className="text-gray-700">
                                {item.kind === 'variant' ? variantName(item.row) : (item.row?.name || 'Producto')}
                              </span>
                              <span className="text-gray-500">{item.kind === 'variant' ? 'Variante' : 'Producto'}</span>
                            </button>
                          ))
                        ) : (
                          <div className="px-2 py-2 text-xs text-gray-600">
                            <p>
                              {activeLookupQuery
                                ? `Sin resultados para "${activeLookupQuery}".`
                                : 'Sin resultados iniciales para mostrar.'}
                            </p>
                          </div>
                        )}
                      </div>
                      <div className="border-t bg-white px-2 py-2">
                        <button
                          type="button"
                          className="w-full px-2 py-2 rounded border text-xs font-semibold hover:bg-gray-50"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => openCreateModal(idx)}
                        >
                          Agregar producto y variante
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="md:col-span-3">
                <label className="block text-xs text-gray-500 mb-1">Nombre proveedor</label>
                <input
                  className="input"
                  placeholder="Ej: Jean Wideleg FIA ceniza"
                  value={it.supplier_product_name || ''}
                  onChange={(e) => updateItem(idx, { supplier_product_name: e.target.value })}
                />
              </div>

              <div className="md:col-span-1">
                <label className="block text-xs text-gray-500 mb-1">Codigo de barras</label>
                <input
                  className="input bg-gray-100 text-gray-500"
                  value={it.barcode_internal || '-'}
                  readOnly
                  disabled
                />
                <button
                  type="button"
                  className="mt-1 w-full px-2 py-1 rounded border text-xs font-semibold hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={() => onPrintItemLabel(idx)}
                  disabled={!canPrintItemLabel(it)}
                >
                  {printCopies ? `Imprimir etiqueta (${printCopies})` : 'Imprimir etiqueta'}
                </button>
              </div>

              <div className="md:col-span-1">
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

              <div className="md:col-span-1">
                <label className="block text-xs text-gray-500 mb-1">Costo unitario</label>
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.0001"
                  placeholder="Costo en moneda"
                  value={it.unit_cost_currency}
                  onChange={(e) => onItemCostChange(idx, e.target.value)}
                  required
                />
              </div>

              <div className="md:col-span-1">
                <label className="block text-xs text-gray-500 mb-1">Costo ARS</label>
                <input className="input bg-gray-100 text-gray-500" value={fmtMoney(itemUnitCostArs(it))} readOnly disabled />
              </div>

              <div className="md:col-span-1">
                <label className="block text-xs text-gray-500 mb-1">Margen objetivo</label>
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.01"
                  value={it.suggested_markup_pct}
                  onChange={(e) => onItemMarkupChange(idx, e.target.value)}
                  required
                />
              </div>

              <div className="md:col-span-1">
                <label className="block text-xs text-gray-500 mb-1">Precio sugerido</label>
                <input className="input bg-gray-100 text-gray-500" value={fmtMoney(itemSuggestedPrice(it))} readOnly disabled />
              </div>

              <div className="md:col-span-1">
                <label className="block text-xs text-gray-500 mb-1">Precio final</label>
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="ARS"
                  value={it.unit_price_final_ars}
                  onChange={(e) => onItemFinalPriceChange(idx, e.target.value)}
                  required
                />
              </div>

              <div className="md:col-span-1">
                <label className="block text-xs text-gray-500 mb-1">Margen real</label>
                <input
                  className={`input bg-gray-100 ${marginPct != null && marginPct < 0 ? 'text-red-700 font-semibold' : 'text-gray-500'}`}
                  value={marginPct == null ? '-' : `${marginPct.toFixed(2)}%`}
                  readOnly
                  disabled
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
            );
          })}

          <button type="button" className="px-3 py-2 rounded border" onClick={addItem}>
            Agregar item
          </button>
        </div>

        <button className="btn" type="submit" disabled={saving}>
          Registrar compra
        </button>
      </form>

      {itemsFlowMsg ? (
        <p className={`text-sm ${itemsFlowMsgTone === 'warn' ? 'text-amber-700' : 'text-green-700'}`}>{itemsFlowMsg}</p>
      ) : null}
      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {result ? (
        <div className="card">
          <p className="text-sm text-green-700">
            Compra registrada: <strong>#{result.id}</strong> ({result.items?.length || 0} items)
          </p>
        </div>
      ) : null}

      <div className="card relative z-0 space-y-3">
        <div className="flex flex-wrap gap-2 items-end justify-between">
          <div>
            <h2 className="text-lg font-semibold">Lista de proveedores</h2>
            <p className="text-xs text-gray-500">Selecciona uno para autocompletar el campo Proveedor del formulario.</p>
          </div>
          <div className="flex flex-wrap gap-2 items-end">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Buscar proveedor</label>
              <input
                className="input"
                placeholder="Nombre proveedor"
                value={suppliersQuery}
                onChange={(e) => setSuppliersQuery(e.target.value)}
              />
            </div>
            <button
              type="button"
              className="px-3 py-2 rounded border"
              onClick={() => fetchSuppliers(suppliersQuery)}
              disabled={suppliersLoading}
            >
              {suppliersLoading ? 'Buscando...' : 'Buscar'}
            </button>
            <button
              type="button"
              className="px-3 py-2 rounded border"
              onClick={() => {
                setSuppliersQuery('');
                fetchSuppliers('');
              }}
              disabled={suppliersLoading}
            >
              Limpiar
            </button>
          </div>
        </div>

        {suppliersErr ? <p className="text-sm text-red-700">{suppliersErr}</p> : null}
        {suppliersLoading ? <p className="text-sm text-gray-500">Cargando proveedores...</p> : null}

        {!suppliersLoading && !suppliersErr ? (
          suppliersRows.length ? (
            <div className="overflow-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left border-b">
                    <th className="py-2 pr-3">Proveedor</th>
                    <th className="py-2 pr-3">Compras</th>
                    <th className="py-2 pr-3">Ultima compra</th>
                    <th className="py-2 pr-3">Accion</th>
                  </tr>
                </thead>
                <tbody>
                  {suppliersRows.map((row) => (
                    <tr key={row.id} className="border-b last:border-b-0">
                      <td className="py-2 pr-3">{row.name || '-'}</td>
                      <td className="py-2 pr-3">{Number(row.purchases_count || 0)}</td>
                      <td className="py-2 pr-3">{fmtDate(row.last_purchase_date)}</td>
                      <td className="py-2 pr-3">
                        <button
                          type="button"
                          className="px-2 py-1 rounded border text-xs font-semibold hover:bg-gray-50"
                          onClick={() => setSupplierName(String(row.name || ''))}
                        >
                          Usar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-gray-500">No hay proveedores para mostrar.</p>
          )
        ) : null}
      </div>

      {quickOpen ? (
        <div className="fixed inset-0 z-[55] bg-black/40 p-3 md:p-6" onClick={closeQuickModal}>
          <div
            className="mx-auto max-w-3xl rounded-xl border border-gray-200 bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="border-b bg-white px-4 py-3 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Alta masiva por combinaciones</h2>
                <p className="text-xs text-gray-500">
                  Producto: <strong>{quickProduct?.name || `#${quickProduct?.id || ''}`}</strong>
                </p>
              </div>
              <button
                type="button"
                className="px-3 py-2 rounded border"
                onClick={closeQuickModal}
                disabled={quickApplying}
              >
                Cerrar
              </button>
            </div>

            <div className="p-4 space-y-3">
              {quickErr ? <p className="text-sm text-red-700">{quickErr}</p> : null}
              {quickMsg ? <p className="text-sm text-gray-700">{quickMsg}</p> : null}
              {!createLoadingData && createErr ? <p className="text-sm text-red-700">{createErr}</p> : null}
              {createLoadingData ? <p className="text-sm text-gray-500">Cargando atributos...</p> : null}

              <VariantAttributeMultiRows
                rows={quickAttrRows || []}
                attributes={createAttributes}
                attributeValuesByCode={createAttrValuesByCode}
                getAvailableAttributesForRow={availableQuickAttrsForRow}
                onUpdateRow={updateQuickAttrRow}
                onRemoveRow={removeQuickAttrRow}
                onAddRow={addQuickAttrRow}
                canAddRow={canAddQuickAttrRow}
                disabled={quickApplying || createLoadingData}
                title="Atributos multivalor"
                help="Carga un atributo y varios valores separados por coma, punto y coma o salto de linea. El sistema combina esos valores para armar variantes o reaprovechar las que ya existen."
                listIdPrefix="purchase-quick-attr-values"
                valuePlaceholder="Ej: Azul, Violeta, Negro"
              />

              <div className="flex flex-wrap justify-end gap-2 pt-2 border-t">
                <button
                  type="button"
                  className="px-3 py-2 rounded border"
                  onClick={closeQuickModal}
                  disabled={quickApplying}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={applyQuickCombinations}
                  disabled={quickApplying || createLoadingData}
                >
                  {quickApplying ? 'Aplicando...' : 'Aplicar combinaciones'}
                </button>
              </div>
            </div>
          </div>
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
                    placeholder="Nombre interno"
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
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <input
                      className="input"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Precio local"
                      value={createProductForm.default_price_store_ars}
                      onChange={(e) => {
                        const value = e.target.value;
                        setCreateProductForm((prev) => ({
                          ...prev,
                          default_price_store_ars: value,
                          default_price_online_ars: prev.default_price_online_ars || value,
                        }));
                      }}
                    />
                    <input
                      className="input"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="Precio online"
                      value={createProductForm.default_price_online_ars}
                      onChange={(e) => setCreateProductForm((prev) => ({ ...prev, default_price_online_ars: e.target.value }))}
                    />
                  </div>
                  <button className="btn" type="submit" disabled={createProductSaving}>
                    {createProductSaving ? 'Guardando...' : 'Crear producto'}
                  </button>
                </form>

                <form className="card space-y-3" onSubmit={createVariantFromModal}>
                  <h3 className="text-base font-semibold">Nueva variante</h3>

                  <select
                    className="input"
                    value={createVariantForm.product_id}
                    onChange={(e) => onCreateVariantProductChange(e.target.value)}
                    required
                    disabled={createLoadingData}
                  >
                    <option value="">Seleccionar producto</option>
                    {createProducts.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>

                  <VariantAttributeRows
                    rows={createVariantForm.option_rows || []}
                    attributes={createAttributes}
                    attributeValuesByCode={createAttrValuesByCode}
                    getAvailableAttributesForRow={availableCreateAttrsForRow}
                    onUpdateRow={updateCreateOptionRow}
                    onRemoveRow={removeCreateOptionRow}
                    onAddRow={addCreateOptionRow}
                    canAddRow={canAddCreateOptionRow}
                    disabled={createBusy}
                    title="Atributos"
                    help="Usa valores ya conocidos cuando existan para evitar duplicados como Negro, negro o NEGRO, igual que en Nueva variante de Productos."
                    listIdPrefix="purchase-create-variant-attr-values"
                  />

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

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <form className="card space-y-3" onSubmit={saveCreateProductEdit}>
                  <h3 className="text-base font-semibold">Editar producto seleccionado</h3>
                  {createProductEditForm?.id ? (
                    <>
                      <input
                        className="input"
                        value={createProductEditForm.name}
                        onChange={(e) => setCreateProductEditForm((prev) => ({ ...prev, name: e.target.value }))}
                        placeholder="Nombre interno"
                        required
                      />
                      <input
                        className="input"
                        value={createProductEditForm.sku_prefix}
                        onChange={(e) => setCreateProductEditForm((prev) => ({ ...prev, sku_prefix: e.target.value }))}
                        placeholder="Prefijo SKU"
                      />
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        <input
                          className="input"
                          type="number"
                          min="0"
                          step="0.01"
                          value={createProductEditForm.default_price_store_ars}
                          onChange={(e) => {
                            const value = e.target.value;
                            setCreateProductEditForm((prev) => ({
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
                          value={createProductEditForm.default_price_online_ars}
                          onChange={(e) => setCreateProductEditForm((prev) => ({ ...prev, default_price_online_ars: e.target.value }))}
                          placeholder="Precio base online"
                        />
                      </div>
                      <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
                        <input
                          type="checkbox"
                          checked={!!createProductEditForm.active}
                          onChange={(e) => setCreateProductEditForm((prev) => ({ ...prev, active: e.target.checked }))}
                        />
                        Activo
                      </label>
                      <button className="btn" type="submit" disabled={createProductEditSaving}>
                        {createProductEditSaving ? 'Guardando...' : 'Guardar producto'}
                      </button>
                    </>
                  ) : (
                    <p className="text-sm text-gray-500">Selecciona un producto en la forma de variante para editarlo.</p>
                  )}
                </form>

                <div className="card space-y-3">
                  <h3 className="text-base font-semibold">Variantes del producto seleccionado</h3>
                  {createProductVariantsLoading ? <p className="text-sm text-gray-500">Cargando variantes...</p> : null}
                  {!createProductVariantsLoading ? (
                    createProductVariants.length ? (
                      <div className="overflow-auto">
                        <table className="min-w-full text-sm">
                          <thead>
                            <tr className="text-left border-b">
                              <th className="py-2 pr-3">ID</th>
                              <th className="py-2 pr-3">SKU</th>
                              <th className="py-2 pr-3">Firma</th>
                              <th className="py-2 pr-3">Accion</th>
                            </tr>
                          </thead>
                          <tbody>
                            {createProductVariants.map((row) => (
                              <tr key={row.id} className="border-b last:border-b-0">
                                <td className="py-2 pr-3">{row.id}</td>
                                <td className="py-2 pr-3">{row.sku}</td>
                                <td className="py-2 pr-3">{row.option_signature || '-'}</td>
                                <td className="py-2 pr-3">
                                  <div className="flex gap-2">
                                    <button
                                      type="button"
                                      className="px-2 py-1 rounded border text-xs font-semibold hover:bg-gray-50"
                                      onClick={() => useVariantFromCreateList(row)}
                                    >
                                      Usar
                                    </button>
                                    <button
                                      type="button"
                                      className="px-2 py-1 rounded border text-xs font-semibold hover:bg-gray-50"
                                      onClick={() => startEditCreateVariant(row)}
                                    >
                                      Editar
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500">No hay variantes para este producto.</p>
                    )
                  ) : null}

                  {createVariantEditForm?.id ? (
                    <form className="rounded-xl border border-neutral-200 p-3 space-y-2" onSubmit={saveCreateVariantEdit}>
                      <h4 className="text-sm font-semibold">Editar variante #{createVariantEditForm.id}</h4>
                      <input
                        className="input"
                        value={createVariantEditForm.sku}
                        onChange={(e) => setCreateVariantEditForm((prev) => ({ ...prev, sku: e.target.value }))}
                        placeholder="SKU"
                        required
                      />
                      <input
                        className="input"
                        value={createVariantEditForm.barcode_internal}
                        onChange={(e) => setCreateVariantEditForm((prev) => ({ ...prev, barcode_internal: e.target.value }))}
                        placeholder="Barcode interno"
                      />
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        <input
                          className="input"
                          type="number"
                          min="0"
                          step="0.01"
                          value={createVariantEditForm.price_store_ars}
                          onChange={(e) => setCreateVariantEditForm((prev) => ({ ...prev, price_store_ars: e.target.value }))}
                          placeholder="Precio local"
                        />
                        <input
                          className="input"
                          type="number"
                          min="0"
                          step="0.01"
                          value={createVariantEditForm.price_online_ars}
                          onChange={(e) => setCreateVariantEditForm((prev) => ({ ...prev, price_online_ars: e.target.value }))}
                          placeholder="Precio online"
                        />
                        <input
                          className="input"
                          type="number"
                          min="0"
                          step="1"
                          value={createVariantEditForm.stock_min}
                          onChange={(e) => setCreateVariantEditForm((prev) => ({ ...prev, stock_min: e.target.value }))}
                          placeholder="Stock minimo"
                        />
                      </div>
                      <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
                        <input
                          type="checkbox"
                          checked={!!createVariantEditForm.active}
                          onChange={(e) => setCreateVariantEditForm((prev) => ({ ...prev, active: e.target.checked }))}
                        />
                        Activa
                      </label>
                      <div className="flex gap-2">
                        <button className="btn" type="submit" disabled={createVariantEditSaving}>
                          {createVariantEditSaving ? 'Guardando...' : 'Guardar variante'}
                        </button>
                        <button
                          type="button"
                          className="px-3 py-2 rounded border"
                          onClick={() => setCreateVariantEditForm({ ...EMPTY_CREATE_VARIANT_EDIT })}
                        >
                          Cancelar
                        </button>
                      </div>
                    </form>
                  ) : null}
                </div>
              </div>

              <VariantBatchCreator
                title="Alta masiva por combinaciones"
                products={createProducts}
                attributes={createAttributes}
                attributeValuesByCode={createAttrValuesByCode}
                suppliers={suppliersRows}
                canEdit={!createBusy}
                initialProductId={createVariantForm.product_id}
                onBatchFinished={onCreateBatchFinished}
              />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
