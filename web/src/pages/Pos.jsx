import { useEffect, useMemo, useRef, useState } from 'react';
import {
  getRetailCajaActual,
  getRetailCajaCuentas,
  getRetailGarantiaTicket,
  getRetailPosDraftDetail,
  getRetailPosDrafts,
  getRetailVarianteByScan,
  getRetailVariantes,
  getRetailVentas,
  patchRetailPosDraft,
  postRetailCajaApertura,
  postRetailCajaCierre,
  postRetailPosDraft,
  postRetailPosDraftConfirm,
  postRetailVentaConfirmar,
  postRetailVentaCotizar,
} from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { can, PERMISSION_CODES } from '../lib/permissions';

const PAYMENT_OPTIONS = [
  { value: 'cash', label: 'Efectivo (-10%)' },
  { value: 'debit', label: 'Debito (lista)' },
  { value: 'transfer', label: 'Transferencia (lista)' },
  { value: 'credit', label: 'Credito (+10%)' },
];

const ACCOUNT_BY_METHOD = {
  cash: 'cash',
  debit: 'payway',
  credit: 'payway',
  transfer: 'transfer_1',
};

const FALLBACK_ACCOUNTS = [
  { code: 'cash', label: 'Caja', payment_method: 'cash', active: true, sort_order: 10 },
  { code: 'bbva', label: 'BBVA', payment_method: 'transfer', active: true, sort_order: 20 },
  { code: 'pbs', label: 'PBS', payment_method: 'transfer', active: true, sort_order: 30 },
  { code: 'payway', label: 'Payway', payment_method: 'credit', active: true, sort_order: 40 },
  { code: 'transfer_1', label: 'Transferencia Cuenta 1', payment_method: 'transfer', active: true, sort_order: 50 },
  { code: 'transfer_2', label: 'Transferencia Cuenta 2', payment_method: 'transfer', active: true, sort_order: 60 },
];

const moneyFmt = new Intl.NumberFormat('es-AR', {
  style: 'currency',
  currency: 'ARS',
  maximumFractionDigits: 2,
});

function money(v) {
  const n = Number(v || 0);
  return moneyFmt.format(Number.isFinite(n) ? n : 0);
}

function errMsg(error) {
  return error?.message || 'Ocurrio un error inesperado';
}

function parseCouponCodes(raw) {
  const txt = String(raw || '').trim();
  if (!txt) return [];
  const out = [];
  const seen = new Set();
  txt.split(',').forEach((token) => {
    const item = token.trim();
    if (!item) return;
    const key = item.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    out.push(item);
  });
  return out;
}

function normalizeAccounts(rows) {
  const list = Array.isArray(rows) && rows.length ? rows : FALLBACK_ACCOUNTS;
  return list
    .filter((row) => !!row && row.active !== false)
    .sort((a, b) => Number(a.sort_order || 100) - Number(b.sort_order || 100));
}

function defaultAccountCode(paymentMethod, accounts) {
  const list = normalizeAccounts(accounts);
  const preferred = ACCOUNT_BY_METHOD[paymentMethod];
  const byCode = list.find((row) => row.code === preferred);
  if (byCode) return byCode.code;
  const byMethod = list.find((row) => row.payment_method === paymentMethod);
  if (byMethod) return byMethod.code;
  return list[0]?.code || preferred || 'cash';
}

function isTextEditableTarget(target) {
  if (!target || typeof target.tagName !== 'string') return false;
  if (target.isContentEditable) return true;
  const tag = String(target.tagName || '').toUpperCase();
  if (tag === 'TEXTAREA') return true;
  if (tag !== 'INPUT') return false;
  const type = String(target.getAttribute('type') || 'text').toLowerCase();
  return ![
    'button',
    'checkbox',
    'color',
    'date',
    'datetime-local',
    'file',
    'hidden',
    'image',
    'month',
    'radio',
    'range',
    'reset',
    'submit',
    'time',
    'week',
  ].includes(type);
}

function normalizeItemPayload(raw) {
  const variantId = Number(raw?.variant_id || raw?.id || 0);
  if (!variantId) return null;
  return {
    variant_id: variantId,
    sku: raw?.sku || '',
    barcode_internal: raw?.barcode_internal || '',
    producto: raw?.producto || raw?.display_name || `Variante #${variantId}`,
    firma: raw?.firma || raw?.option_signature || '',
    precio_local: Number(raw?.precio_local ?? raw?.price_store_ars ?? 0),
    quantity: Math.max(1, Number(raw?.quantity || 1)),
    unit_price_override_ars: raw?.unit_price_override_ars ?? '',
  };
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export default function PosPage() {
  const { user } = useAuth();
  const canOverridePrice = can(user, PERMISSION_CODES.ACTION_VENTAS_OVERRIDE_PRECIO);

  const scanRef = useRef(null);
  const scanBufferRef = useRef('');
  const scanLastKeyAtRef = useRef(0);
  const scanDetectedRef = useRef(false);
  const scanFlushTimerRef = useRef(null);
  const busyRef = useRef(false);
  const submitScanRef = useRef(null);

  const [scan, setScan] = useState('');
  const [manualQuery, setManualQuery] = useState('');
  const [manualRows, setManualRows] = useState([]);
  const [manualLoading, setManualLoading] = useState(false);

  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [paymentAccountCode, setPaymentAccountCode] = useState('cash');
  const [splitPaymentsEnabled, setSplitPaymentsEnabled] = useState(false);
  const [splitPayments, setSplitPayments] = useState([
    { method: 'cash', account_code: 'cash', amount_ars: '' },
  ]);

  const [customerName, setCustomerName] = useState('');
  const [customerDoc, setCustomerDoc] = useState('');
  const [notes, setNotes] = useState('');
  const [couponCodes, setCouponCodes] = useState('');
  const [priceOverrideReason, setPriceOverrideReason] = useState('');
  const [items, setItems] = useState([]);
  const [quote, setQuote] = useState(null);
  const [lastSale, setLastSale] = useState(null);
  const [ticketLookup, setTicketLookup] = useState(null);

  const [cashSession, setCashSession] = useState(null);
  const [accounts, setAccounts] = useState(FALLBACK_ACCOUNTS);
  const [openingCash, setOpeningCash] = useState('0');
  const [closingCash, setClosingCash] = useState('');

  const [drafts, setDrafts] = useState([]);
  const [selectedDraftId, setSelectedDraftId] = useState(null);
  const [draftName, setDraftName] = useState('');
  const [draftsLoading, setDraftsLoading] = useState(false);

  const [recentSales, setRecentSales] = useState([]);
  const [recentLoading, setRecentLoading] = useState(false);

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const totalQty = useMemo(
    () => items.reduce((acc, it) => acc + Number(it.quantity || 0), 0),
    [items]
  );

  const filteredAccounts = useMemo(() => {
    const rows = normalizeAccounts(accounts);
    const byMethod = rows.filter(
      (row) => !row.payment_method || row.payment_method === paymentMethod
    );
    return byMethod.length ? byMethod : rows;
  }, [accounts, paymentMethod]);

  const cashSummaryRows = useMemo(
    () => (Array.isArray(cashSession?.summary?.rows) ? cashSession.summary.rows : []),
    [cashSession]
  );

  const anyOverride = useMemo(
    () =>
      canOverridePrice &&
      items.some((it) => String(it.unit_price_override_ars || '').trim() !== ''),
    [canOverridePrice, items]
  );

  const quoteByVariant = useMemo(() => {
    const map = new Map();
    const lines = Array.isArray(quote?.items) ? quote.items : [];
    lines.forEach((line) => map.set(Number(line.variant_id), line));
    return map;
  }, [quote]);

  const splitTotals = useMemo(() => {
    const expected = Number(quote?.total_ars || 0);
    const current = splitPayments.reduce((acc, row) => {
      const n = Number(row.amount_ars || 0);
      return acc + (Number.isFinite(n) ? n : 0);
    }, 0);
    const diff = current - expected;
    return { expected, current, diff };
  }, [splitPayments, quote]);

  const selectedDraft = useMemo(
    () => drafts.find((row) => Number(row.id) === Number(selectedDraftId)) || null,
    [drafts, selectedDraftId]
  );

  function focusScan(force = false) {
    setTimeout(() => {
      const activeTag = document?.activeElement?.tagName;
      const hasOtherFormFocus = ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(
        activeTag || ''
      );
      if (!force && hasOtherFormFocus) return;
      scanRef.current?.focus();
    }, 0);
  }

  function resetMessages() {
    setErr('');
    setMsg('');
  }

  function addOrIncreaseItem(raw) {
    const row = normalizeItemPayload(raw);
    if (!row) return;
    setItems((prev) => {
      const idx = prev.findIndex((it) => Number(it.variant_id) === Number(row.variant_id));
      if (idx < 0) {
        return [...prev, row];
      }
      const next = [...prev];
      next[idx] = { ...next[idx], quantity: Number(next[idx].quantity || 0) + 1 };
      return next;
    });
    setQuote(null);
    setTicketLookup(null);
  }

  function clearCart() {
    setItems([]);
    setQuote(null);
    setTicketLookup(null);
    setCouponCodes('');
    setPriceOverrideReason('');
  }

  function changeQty(variantId, qty) {
    const parsed = Number(qty);
    if (!Number.isFinite(parsed)) return;
    setItems((prev) =>
      prev
        .map((it) =>
          Number(it.variant_id) === Number(variantId)
            ? { ...it, quantity: Math.max(1, Math.floor(parsed)) }
            : it
        )
        .filter((it) => Number(it.quantity) > 0)
    );
    setQuote(null);
  }

  function stepQty(variantId, delta) {
    setItems((prev) =>
      prev
        .map((it) => {
          if (Number(it.variant_id) !== Number(variantId)) return it;
          const current = Math.max(1, Number(it.quantity || 1));
          return { ...it, quantity: Math.max(1, current + delta) };
        })
        .filter((it) => Number(it.quantity) > 0)
    );
    setQuote(null);
  }

  function changeOverride(variantId, value) {
    setItems((prev) =>
      prev.map((it) =>
        Number(it.variant_id) === Number(variantId)
          ? { ...it, unit_price_override_ars: value }
          : it
      )
    );
    setQuote(null);
  }

  function removeItem(variantId) {
    setItems((prev) => prev.filter((it) => Number(it.variant_id) !== Number(variantId)));
    setQuote(null);
  }

  function buildItemsPayload() {
    return items.map((it) => {
      const line = {
        variant_id: Number(it.variant_id),
        quantity: Number(it.quantity || 1),
      };
      const rawOverride = String(it.unit_price_override_ars || '').trim();
      if (canOverridePrice && rawOverride !== '') {
        const n = Number(rawOverride);
        if (!Number.isFinite(n) || n < 0) {
          throw new Error(`Override invalido en variante ${it.sku || it.variant_id}`);
        }
        line.unit_price_override_ars = n;
      }
      return line;
    });
  }

  function accountsByMethod(method) {
    const rows = normalizeAccounts(accounts);
    const scoped = rows.filter((row) => !row.payment_method || row.payment_method === method);
    return scoped.length ? scoped : rows;
  }

  function buildPaymentsPayload(expectedTotal) {
    if (!splitPaymentsEnabled) return undefined;
    if (!quote) {
      throw new Error('Cotiza antes de confirmar una venta con pago mixto');
    }
    const rows = splitPayments
      .map((row) => ({
        method: String(row.method || '').trim(),
        account_code: String(row.account_code || '').trim(),
        amount_ars: Number(row.amount_ars || 0),
      }))
      .filter((row) => row.method && row.amount_ars > 0);
    if (!rows.length) {
      throw new Error('Debes cargar al menos un tramo de pago');
    }
    rows.forEach((row, idx) => {
      if (!['cash', 'debit', 'transfer', 'credit'].includes(row.method)) {
        throw new Error(`Metodo invalido en pago #${idx + 1}`);
      }
      if (!row.account_code) {
        throw new Error(`Cuenta requerida en pago #${idx + 1}`);
      }
    });
    const sum = rows.reduce((acc, row) => acc + Number(row.amount_ars || 0), 0);
    const expected = Number(expectedTotal || 0);
    const roundedDiff = Math.round((sum - expected) * 100) / 100;
    if (roundedDiff !== 0) {
      throw new Error('La suma de pagos debe coincidir con el total cotizado');
    }
    return rows;
  }

  function buildBaseSalePayload() {
    return {
      channel: 'local',
      payment_method: paymentMethod,
      payment_account_code: paymentAccountCode,
      coupon_codes: parseCouponCodes(couponCodes),
      customer_name: customerName || undefined,
      customer_doc: customerDoc || undefined,
      notes: notes || undefined,
      price_override_reason: anyOverride ? priceOverrideReason.trim() : undefined,
      auto_emit_invoice: true,
      items: buildItemsPayload(),
    };
  }

  function buildDraftPayload() {
    const payload = {
      channel: 'local',
      payment_method: paymentMethod,
      payment_account_code: paymentAccountCode,
      coupon_codes: parseCouponCodes(couponCodes),
      customer_name: customerName || undefined,
      customer_doc: customerDoc || undefined,
      notes: notes || undefined,
      price_override_reason: anyOverride ? priceOverrideReason.trim() : undefined,
      auto_emit_invoice: true,
      items: items.map((it) => ({ ...it })),
    };
    if (splitPaymentsEnabled) {
      payload.payments = splitPayments.map((row) => ({
        method: row.method,
        account_code: row.account_code,
        amount_ars: row.amount_ars,
      }));
    }
    return payload;
  }

  function applyDraftPayload(payload, quoteSnapshot) {
    const data = payload || {};
    const nextItems = Array.isArray(data.items)
      ? data.items.map((row) => normalizeItemPayload(row)).filter(Boolean)
      : [];
    const nextMethod = String(data.payment_method || 'cash');
    const nextAccount = String(
      data.payment_account_code || defaultAccountCode(nextMethod, accounts)
    );

    setItems(nextItems);
    setPaymentMethod(nextMethod);
    setPaymentAccountCode(nextAccount);
    setCouponCodes(Array.isArray(data.coupon_codes) ? data.coupon_codes.join(', ') : '');
    setCustomerName(String(data.customer_name || ''));
    setCustomerDoc(String(data.customer_doc || ''));
    setNotes(String(data.notes || ''));
    setPriceOverrideReason(String(data.price_override_reason || ''));
    setQuote(quoteSnapshot && typeof quoteSnapshot === 'object' ? quoteSnapshot : null);
    setTicketLookup(null);

    const rawPayments = Array.isArray(data.payments) ? data.payments : [];
    const mapped = rawPayments
      .map((row) => ({
        method: String(row.method || row.payment_method || nextMethod),
        account_code: String(
          row.account_code ||
            row.payment_account_code ||
            defaultAccountCode(String(row.method || row.payment_method || nextMethod), accounts)
        ),
        amount_ars: String(row.amount_ars ?? ''),
      }))
      .filter((row) => row.method);

    if (mapped.length > 1) {
      setSplitPaymentsEnabled(true);
      setSplitPayments(mapped);
    } else {
      setSplitPaymentsEnabled(false);
      setSplitPayments([
        {
          method: nextMethod,
          account_code: nextAccount,
          amount_ars: quoteSnapshot?.total_ars != null ? String(quoteSnapshot.total_ars) : '',
        },
      ]);
    }
  }

  async function loadCashSession() {
    try {
      const resp = await getRetailCajaActual();
      setCashSession(resp?.open ? resp?.session : null);
    } catch {
      setCashSession(null);
    }
  }

  async function loadAccounts() {
    try {
      const rows = await getRetailCajaCuentas();
      const normalized = normalizeAccounts(rows);
      setAccounts(normalized.length ? normalized : FALLBACK_ACCOUNTS);
    } catch {
      setAccounts(FALLBACK_ACCOUNTS);
    }
  }

  async function loadDrafts() {
    setDraftsLoading(true);
    try {
      const resp = await getRetailPosDrafts({ status: 'open', limit: 40 });
      const rows = Array.isArray(resp?.rows) ? resp.rows : [];
      setDrafts(rows);
      if (selectedDraftId && !rows.some((row) => Number(row.id) === Number(selectedDraftId))) {
        setSelectedDraftId(null);
      }
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setDraftsLoading(false);
    }
  }

  async function loadRecentSales() {
    setRecentLoading(true);
    try {
      const day = todayIso();
      const resp = await getRetailVentas({
        desde: day,
        hasta: day,
        channel: 'local',
        limit: 8,
        offset: 0,
      });
      setRecentSales(Array.isArray(resp?.rows) ? resp.rows : []);
    } catch {
      setRecentSales([]);
    } finally {
      setRecentLoading(false);
    }
  }

  useEffect(() => {
    loadCashSession();
    loadAccounts();
    loadDrafts();
    loadRecentSales();
  }, []);

  useEffect(() => {
    busyRef.current = busy;
  }, [busy]);

  useEffect(() => {
    submitScanRef.current = submitScanCode;
  });

  useEffect(() => {
    const selectedExists = filteredAccounts.some((row) => row.code === paymentAccountCode);
    if (!selectedExists) {
      setPaymentAccountCode(defaultAccountCode(paymentMethod, filteredAccounts));
    }
  }, [paymentMethod, filteredAccounts, paymentAccountCode]);

  useEffect(() => {
    if (!splitPaymentsEnabled) return;
    setSplitPayments((prev) => {
      if (!prev.length) {
        return [
          {
            method: paymentMethod,
            account_code: paymentAccountCode || defaultAccountCode(paymentMethod, accounts),
            amount_ars: quote?.total_ars != null ? String(quote.total_ars) : '',
          },
        ];
      }
      return prev.map((row) => {
        const method = row.method || paymentMethod;
        const available = accountsByMethod(method);
        const exists = available.some((acc) => acc.code === row.account_code);
        return {
          ...row,
          method,
          account_code: exists ? row.account_code : defaultAccountCode(method, accounts),
        };
      });
    });
  }, [splitPaymentsEnabled, paymentMethod, paymentAccountCode, accounts, quote]);

  useEffect(() => {
    const timer = setTimeout(async () => {
      const qtxt = String(manualQuery || '').trim();
      if (qtxt.length < 2) {
        setManualRows([]);
        setManualLoading(false);
        return;
      }
      setManualLoading(true);
      try {
        const rows = await getRetailVariantes({ q: qtxt, active: 1, limit: 20 });
        setManualRows(Array.isArray(rows) ? rows : []);
      } catch {
        setManualRows([]);
      } finally {
        setManualLoading(false);
      }
    }, 260);
    return () => clearTimeout(timer);
  }, [manualQuery]);

  useEffect(() => {
    const SCAN_RESET_GAP_MS = 90;
    const SCAN_ENTER_GAP_MS = 120;
    const SCAN_MIN_LEN = 3;

    function clearCapture() {
      if (scanFlushTimerRef.current) {
        clearTimeout(scanFlushTimerRef.current);
        scanFlushTimerRef.current = null;
      }
      scanBufferRef.current = '';
      scanLastKeyAtRef.current = 0;
      scanDetectedRef.current = false;
    }

    function scheduleAutoSubmit() {
      if (scanFlushTimerRef.current) {
        clearTimeout(scanFlushTimerRef.current);
      }
      scanFlushTimerRef.current = setTimeout(() => {
        const code = String(scanBufferRef.current || '').trim();
        const canSubmit =
          scanDetectedRef.current && code.length >= SCAN_MIN_LEN && !busyRef.current;
        clearCapture();
        if (!canSubmit) return;
        setScan('');
        void submitScanRef.current?.(code, { variantOnly: true });
      }, SCAN_ENTER_GAP_MS);
    }

    function onWindowKeyDown(event) {
      if (event.defaultPrevented || event.isComposing) return;
      const activeEl = document?.activeElement;
      const hasEditableFocus =
        isTextEditableTarget(activeEl) || Boolean(activeEl?.isContentEditable);
      if (hasEditableFocus) return;

      if (event.ctrlKey || event.altKey || event.metaKey) {
        if (event.ctrlKey && event.key === 'Backspace') {
          event.preventDefault();
          clearCart();
          return;
        }
        clearCapture();
        return;
      }

      if (event.key === 'F2') {
        event.preventDefault();
        focusScan(true);
        return;
      }
      if (event.key === 'F4') {
        event.preventDefault();
        void handleQuote();
        return;
      }
      if (event.key === 'F8') {
        event.preventDefault();
        void quickSaveDraft();
        return;
      }
      if (event.key === 'F9') {
        event.preventDefault();
        void handleConfirm();
        return;
      }

      const now = Date.now();
      const key = String(event.key || '');

      if (key === 'Enter') {
        const code = String(scanBufferRef.current || '').trim();
        const age = scanLastKeyAtRef.current
          ? now - scanLastKeyAtRef.current
          : Number.MAX_SAFE_INTEGER;
        const looksLikeScan =
          scanDetectedRef.current && age <= SCAN_ENTER_GAP_MS && code.length >= SCAN_MIN_LEN;
        clearCapture();
        if (!looksLikeScan || busyRef.current) return;
        event.preventDefault();
        setScan('');
        void submitScanRef.current?.(code, { variantOnly: true });
        return;
      }

      if (key.length !== 1) return;

      if (
        !scanLastKeyAtRef.current ||
        now - scanLastKeyAtRef.current > SCAN_RESET_GAP_MS
      ) {
        scanBufferRef.current = '';
        scanDetectedRef.current = false;
      } else if (scanBufferRef.current.length >= 1) {
        scanDetectedRef.current = true;
      }

      scanBufferRef.current += key;
      scanLastKeyAtRef.current = now;
      event.preventDefault();
      if (scanDetectedRef.current) {
        scheduleAutoSubmit();
      }
    }

    window.addEventListener('keydown', onWindowKeyDown, true);
    return () => {
      window.removeEventListener('keydown', onWindowKeyDown, true);
      clearCapture();
    };
  }, [items, quote, splitPaymentsEnabled, splitPayments, selectedDraftId]);

  async function submitScanCode(rawCode, options = {}) {
    const code = String(rawCode || '').trim();
    if (!code) return;
    if (busyRef.current) return;
    const restoreFocus = Boolean(options.restoreFocus);
    const variantOnly = Boolean(options.variantOnly);
    busyRef.current = true;
    resetMessages();
    setBusy(true);
    try {
      const row = await getRetailVarianteByScan(code);
      addOrIncreaseItem(row);
      setScan('');
    } catch (error) {
      if (error?.status === 404) {
        if (variantOnly) {
          setTicketLookup(null);
          setScan('');
          setErr('No se encontro la variante para el codigo escaneado');
          return;
        }
        try {
          const ticket = await getRetailGarantiaTicket(code);
          setTicketLookup(ticket || null);
          setScan('');
          setErr('');
        } catch (lookupError) {
          setErr(errMsg(lookupError));
        }
      } else {
        setErr(errMsg(error));
      }
    } finally {
      busyRef.current = false;
      setBusy(false);
      if (restoreFocus) {
        focusScan(true);
      }
    }
  }

  async function handleScanSubmit(e) {
    e?.preventDefault?.();
    await submitScanCode(scan, { restoreFocus: true });
  }

  async function handleQuote() {
    if (!items.length) return;
    resetMessages();
    setBusy(true);
    try {
      const resp = await postRetailVentaCotizar({
        channel: 'local',
        payment_method: paymentMethod,
        payment_account_code: paymentAccountCode,
        coupon_codes: parseCouponCodes(couponCodes),
        items: buildItemsPayload(),
      });
      setQuote(resp);
      if (splitPaymentsEnabled && splitPayments.length === 1) {
        setSplitPayments((prev) =>
          prev.map((row, idx) =>
            idx === 0 ? { ...row, amount_ars: String(resp?.total_ars ?? '') } : row
          )
        );
      }
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
      focusScan(true);
    }
  }

  async function quickSaveDraft() {
    if (selectedDraftId) {
      await handleUpdateDraft();
    } else {
      await handleSaveDraft();
    }
  }

  async function handleConfirm() {
    if (!items.length) return;
    if (anyOverride && !String(priceOverrideReason || '').trim()) {
      setErr('Debes indicar motivo de override de precio');
      return;
    }
    resetMessages();
    setBusy(true);
    try {
      const basePayload = buildBaseSalePayload();
      const expectedTotal = quote?.total_ars;
      const paymentsPayload = buildPaymentsPayload(expectedTotal);
      if (paymentsPayload?.length) {
        basePayload.payments = paymentsPayload;
      }

      let sale;
      if (selectedDraftId) {
        const resp = await postRetailPosDraftConfirm(selectedDraftId, {
          payload: { ...buildDraftPayload(), ...basePayload, payments: paymentsPayload },
          quote_snapshot: quote || undefined,
        });
        sale = resp?.sale;
        setSelectedDraftId(null);
      } else {
        sale = await postRetailVentaConfirmar(basePayload);
      }

      setLastSale(sale || null);
      setItems([]);
      setQuote(null);
      setTicketLookup(null);
      setCouponCodes('');
      setPriceOverrideReason('');
      setCustomerName('');
      setCustomerDoc('');
      setNotes('');
      setSplitPaymentsEnabled(false);
      setSplitPayments([
        { method: paymentMethod, account_code: paymentAccountCode, amount_ars: '' },
      ]);
      setMsg('Venta confirmada');
      await Promise.all([loadCashSession(), loadDrafts(), loadRecentSales()]);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
      focusScan(true);
    }
  }

  async function openCashSession() {
    resetMessages();
    setBusy(true);
    try {
      await postRetailCajaApertura({ opening_amount_cash_ars: Number(openingCash || 0) });
      setMsg('Caja abierta');
      await loadCashSession();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
      focusScan(true);
    }
  }

  async function closeCashSession() {
    resetMessages();
    setBusy(true);
    try {
      await postRetailCajaCierre({
        closing_counted_total_ars: closingCash === '' ? undefined : Number(closingCash),
      });
      setClosingCash('');
      setMsg('Caja cerrada');
      await loadCashSession();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
      focusScan(true);
    }
  }

  async function handleSaveDraft() {
    resetMessages();
    setBusy(true);
    try {
      const resp = await postRetailPosDraft({
        name: draftName || undefined,
        payload: buildDraftPayload(),
        quote_snapshot: quote || undefined,
      });
      setSelectedDraftId(resp?.id || null);
      setDraftName(resp?.name || draftName || '');
      setMsg('Draft guardado');
      await loadDrafts();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
    }
  }

  async function handleUpdateDraft() {
    if (!selectedDraftId) {
      await handleSaveDraft();
      return;
    }
    resetMessages();
    setBusy(true);
    try {
      await patchRetailPosDraft(selectedDraftId, {
        name: draftName || undefined,
        payload: buildDraftPayload(),
        quote_snapshot: quote || undefined,
      });
      setMsg('Draft actualizado');
      await loadDrafts();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadDraft(draftId) {
    resetMessages();
    setBusy(true);
    try {
      const row = await getRetailPosDraftDetail(draftId);
      applyDraftPayload(row?.payload || {}, row?.quote_snapshot || null);
      setSelectedDraftId(Number(row?.id));
      setDraftName(row?.name || '');
      setMsg(`Draft ${row?.draft_number || `#${draftId}`} cargado`);
      focusScan(true);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
    }
  }

  function resetDraftContext() {
    setSelectedDraftId(null);
    setDraftName('');
  }

  function changeSplitRow(idx, patch) {
    setSplitPayments((prev) =>
      prev.map((row, i) => {
        if (i !== idx) return row;
        const next = { ...row, ...patch };
        if (patch.method && !patch.account_code) {
          next.account_code = defaultAccountCode(String(patch.method), accounts);
        }
        return next;
      })
    );
  }

  function addSplitRow() {
    setSplitPayments((prev) => [
      ...prev,
      {
        method: paymentMethod,
        account_code: defaultAccountCode(paymentMethod, accounts),
        amount_ars: '',
      },
    ]);
  }

  function removeSplitRow(idx) {
    setSplitPayments((prev) => prev.filter((_, i) => i !== idx));
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="h1">POS operativo</h1>
            <p className="text-sm text-gray-600">
              Consola de mostrador con escaneo rapido, caja diaria y borradores en espera.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span
              className={`rounded-full border px-2.5 py-1 font-semibold ${
                cashSession
                  ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                  : 'border-rose-300 bg-rose-50 text-rose-700'
              }`}
            >
              Caja: {cashSession ? `abierta #${cashSession.id}` : 'sin apertura'}
            </span>
            <span className="rounded-full border border-neutral-300 bg-neutral-50 px-2.5 py-1 font-semibold text-neutral-700">
              Items: {totalQty}
            </span>
            <span className="rounded-full border border-neutral-300 bg-neutral-50 px-2.5 py-1 font-semibold text-neutral-700">
              Draft: {selectedDraft ? selectedDraft.draft_number : 'ninguno'}
            </span>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-neutral-600 md:grid-cols-5">
          <span className="rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1">F2 foco escaner</span>
          <span className="rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1">F4 cotizar</span>
          <span className="rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1">F8 guardar draft</span>
          <span className="rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1">F9 confirmar</span>
          <span className="rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1">Ctrl+Backspace limpia carrito</span>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(340px,1fr)]">
        <div className="space-y-4">
          <form className="card space-y-3" onSubmit={handleScanSubmit}>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
              <div className="md:col-span-3">
                <label className="label">Escanear barcode interno o SKU</label>
                <input
                  ref={scanRef}
                  className="input"
                  value={scan}
                  onChange={(e) => setScan(e.target.value)}
                  placeholder="Ej: CHU-001-NEG-M"
                />
              </div>
              <button type="submit" className="btn md:mt-[1.36rem]" disabled={busy}>
                Agregar
              </button>
              <button type="button" className="btn-secondary md:mt-[1.36rem]" onClick={() => focusScan(true)}>
                Foco scanner
              </button>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              <div className="md:col-span-3">
                <label className="label">Busqueda manual de variantes</label>
                <input
                  className="input"
                  value={manualQuery}
                  onChange={(e) => setManualQuery(e.target.value)}
                  placeholder="Buscar por SKU, barcode o producto"
                />
              </div>
              <button type="button" className="btn-secondary md:mt-[1.36rem]" onClick={() => { setManualQuery(''); setManualRows([]); }}>
                Limpiar busqueda
              </button>
            </div>
            {manualQuery.trim().length >= 2 ? (
              <div className="rounded-xl border border-neutral-200">
                {manualLoading ? (
                  <p className="px-3 py-2 text-sm text-gray-500">Buscando variantes...</p>
                ) : manualRows.length ? (
                  <div className="max-h-72 overflow-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b text-left">
                          <th className="px-3 py-2">SKU</th>
                          <th className="px-3 py-2">Producto</th>
                          <th className="px-3 py-2">Precio</th>
                          <th className="px-3 py-2" />
                        </tr>
                      </thead>
                      <tbody>
                        {manualRows.map((row) => (
                          <tr key={row.id} className="border-b last:border-b-0">
                            <td className="px-3 py-2">{row.sku || '-'}</td>
                            <td className="px-3 py-2">
                              {row.producto}
                              <div className="text-xs text-gray-500">{row.option_signature || '-'}</div>
                            </td>
                            <td className="px-3 py-2">{money(row.price_store_ars)}</td>
                            <td className="px-3 py-2 text-right">
                              <button type="button" className="btn-secondary !px-2.5 !py-1.5 !text-xs" onClick={() => { addOrIncreaseItem(row); setManualQuery(''); setManualRows([]); }}>
                                Agregar
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="px-3 py-2 text-sm text-gray-500">Sin resultados para la busqueda.</p>
                )}
              </div>
            ) : null}
          </form>
          {ticketLookup?.sale ? (
            <div className="card space-y-2">
              <h2 className="text-lg font-semibold">Ticket escaneado</h2>
              <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-4">
                <div>Ticket: <strong>{ticketLookup.sale.sale_number || `#${ticketLookup.sale.id}`}</strong></div>
                <div>Fecha: <strong>{String(ticketLookup.sale.created_at || '').slice(0, 16).replace('T', ' ')}</strong></div>
                <div>Total: <strong>{money(ticketLookup.sale.total_ars)}</strong></div>
                <div>Estado: <strong>{ticketLookup.sale.status}</strong></div>
              </div>
            </div>
          ) : null}
          <div className="card space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Carrito ({totalQty})</h2>
              <div className="flex gap-2">
                <button type="button" className="btn-secondary !px-3 !py-2" onClick={resetDraftContext}>Soltar draft</button>
                <button type="button" className="btn-secondary !px-3 !py-2" onClick={clearCart}>Limpiar</button>
              </div>
            </div>
            {!items.length ? (
              <p className="text-sm text-gray-500">No hay items en la venta.</p>
            ) : (
              <div className="overflow-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b text-left">
                      <th className="py-2 pr-3">SKU</th>
                      <th className="py-2 pr-3">Producto</th>
                      <th className="py-2 pr-3">Precio lista</th>
                      {canOverridePrice ? <th className="py-2 pr-3">Override</th> : null}
                      <th className="py-2 pr-3">Cantidad</th>
                      <th className="py-2 pr-3">Linea</th>
                      <th className="py-2 pr-3" />
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((it) => {
                      const qLine = quoteByVariant.get(Number(it.variant_id));
                      return (
                        <tr key={it.variant_id} className="border-b last:border-b-0">
                          <td className="py-2 pr-3">
                            {it.sku || '-'}
                            <div className="text-xs text-gray-500">{it.barcode_internal || '-'}</div>
                          </td>
                          <td className="py-2 pr-3">
                            {it.producto}
                            <div className="text-xs text-gray-500">{it.firma || '-'}</div>
                          </td>
                          <td className="py-2 pr-3">{money(it.precio_local)}</td>
                          {canOverridePrice ? (
                            <td className="py-2 pr-3">
                              <input className="input w-28" type="number" min="0" step="0.01" value={it.unit_price_override_ars || ''} onChange={(e) => changeOverride(it.variant_id, e.target.value)} />
                            </td>
                          ) : null}
                          <td className="py-2 pr-3">
                            <div className="flex items-center gap-1">
                              <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => stepQty(it.variant_id, -1)}>-</button>
                              <input className="input w-20" type="number" min="1" value={it.quantity} onChange={(e) => changeQty(it.variant_id, e.target.value)} />
                              <button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => stepQty(it.variant_id, 1)}>+</button>
                            </div>
                          </td>
                          <td className="py-2 pr-3">{money(qLine?.line_total_ars || 0)}</td>
                          <td className="py-2 pr-3 text-right">
                            <button type="button" className="rounded border border-red-300 px-2.5 py-1.5 text-xs text-red-700" onClick={() => removeItem(it.variant_id)}>Quitar</button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
        <div className="space-y-4 xl:sticky xl:top-20 xl:self-start">
          <div className="card space-y-3">
            <h2 className="text-lg font-semibold">Caja</h2>
            <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-2 text-sm">
              {cashSession ? (
                <div>
                  <div>
                    Estado: <strong className="text-emerald-700">Abierta #{cashSession.id}</strong>
                  </div>
                  <div>
                    Esperado: <strong>{money(cashSession?.summary?.expected_total_ars)}</strong>
                  </div>
                </div>
              ) : (
                <div>
                  Estado: <strong className="text-rose-700">Sin apertura</strong>
                </div>
              )}
            </div>

            {!cashSession ? (
              <div className="grid grid-cols-1 gap-2">
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.01"
                  value={openingCash}
                  onChange={(e) => setOpeningCash(e.target.value)}
                  placeholder="Apertura efectivo"
                />
                <button type="button" className="btn" onClick={openCashSession} disabled={busy}>
                  Abrir caja
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-2">
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  value={closingCash}
                  onChange={(e) => setClosingCash(e.target.value)}
                  placeholder="Conteo al cierre (opcional)"
                />
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={closeCashSession}
                  disabled={busy || items.length > 0}
                >
                  Cerrar caja
                </button>
              </div>
            )}

            <div className="rounded-lg border border-neutral-200">
              <div className="border-b px-3 py-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Resumen por medio/cuenta
              </div>
              <div className="max-h-48 overflow-auto p-2">
                {cashSummaryRows.length ? (
                  <div className="space-y-1 text-sm">
                    {cashSummaryRows.map((row, idx) => (
                      <div key={`${row.payment_account_code || idx}`} className="flex items-center justify-between gap-2">
                        <span className="truncate text-neutral-700">
                          {row.direction === 'out' ? 'Egreso' : 'Ingreso'} |{' '}
                          {row.payment_account_label || row.payment_account_code || '-'}
                        </span>
                        <strong>{money(row.total_ars)}</strong>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">Sin movimientos en esta caja.</p>
                )}
              </div>
            </div>
          </div>

          <div className="card space-y-3">
            <h2 className="text-lg font-semibold">Cobro</h2>
            <div>
              <label className="label">Medio de pago base (pricing)</label>
              <select
                className="input"
                value={paymentMethod}
                onChange={(e) => {
                  const next = e.target.value;
                  setPaymentMethod(next);
                  setPaymentAccountCode(defaultAccountCode(next, accounts));
                  setQuote(null);
                }}
              >
                {PAYMENT_OPTIONS.map((op) => (
                  <option key={op.value} value={op.value}>
                    {op.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Cuenta / caja base</label>
              <select
                className="input"
                value={paymentAccountCode}
                onChange={(e) => setPaymentAccountCode(e.target.value)}
              >
                {filteredAccounts.map((op) => (
                  <option key={op.code} value={op.code}>
                    {op.label}
                  </option>
                ))}
              </select>
            </div>

            <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
              <input
                type="checkbox"
                checked={splitPaymentsEnabled}
                onChange={(e) => setSplitPaymentsEnabled(e.target.checked)}
              />
              Pago mixto (split tender)
            </label>

            {splitPaymentsEnabled ? (
              <div className="space-y-2 rounded-lg border border-neutral-200 p-2">
                {splitPayments.map((row, idx) => {
                  const scopedAccounts = accountsByMethod(row.method || paymentMethod);
                  return (
                    <div key={`split-${idx}`} className="grid grid-cols-1 gap-2 md:grid-cols-6">
                      <select
                        className="input md:col-span-2"
                        value={row.method}
                        onChange={(e) =>
                          changeSplitRow(idx, {
                            method: e.target.value,
                            account_code: defaultAccountCode(e.target.value, accounts),
                          })
                        }
                      >
                        {PAYMENT_OPTIONS.map((op) => (
                          <option key={op.value} value={op.value}>
                            {op.label}
                          </option>
                        ))}
                      </select>
                      <select
                        className="input md:col-span-2"
                        value={row.account_code}
                        onChange={(e) => changeSplitRow(idx, { account_code: e.target.value })}
                      >
                        {scopedAccounts.map((acc) => (
                          <option key={`${idx}-${acc.code}`} value={acc.code}>
                            {acc.label}
                          </option>
                        ))}
                      </select>
                      <input
                        className="input"
                        type="number"
                        step="0.01"
                        min="0"
                        placeholder="Monto"
                        value={row.amount_ars}
                        onChange={(e) => changeSplitRow(idx, { amount_ars: e.target.value })}
                      />
                      <button
                        type="button"
                        className="rounded border border-neutral-300 px-2 py-1 text-xs"
                        onClick={() => removeSplitRow(idx)}
                        disabled={splitPayments.length <= 1}
                      >
                        Quitar
                      </button>
                    </div>
                  );
                })}
                <button type="button" className="btn-secondary !py-2" onClick={addSplitRow}>
                  Agregar tramo
                </button>
                <div className="rounded border border-dashed px-2 py-1 text-xs">
                  <div>
                    Suma tramos: <strong>{money(splitTotals.current)}</strong>
                  </div>
                  <div>
                    Total cotizado: <strong>{money(splitTotals.expected)}</strong>
                  </div>
                  <div className={splitTotals.diff === 0 ? 'text-emerald-700' : 'text-rose-700'}>
                    Diferencia: <strong>{money(splitTotals.diff)}</strong>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div className="card space-y-3">
            <h2 className="text-lg font-semibold">Cliente y notas</h2>
            {anyOverride ? (
              <input
                className="input"
                value={priceOverrideReason}
                onChange={(e) => setPriceOverrideReason(e.target.value)}
                placeholder="Motivo override precio (obligatorio)"
              />
            ) : null}
            <input
              className="input"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="Cliente (opcional)"
            />
            <input
              className="input"
              value={customerDoc}
              onChange={(e) => setCustomerDoc(e.target.value)}
              placeholder="Documento (opcional)"
            />
            <input
              className="input"
              value={couponCodes}
              onChange={(e) => setCouponCodes(e.target.value)}
              placeholder="Cupon(es), separados por coma"
            />
            <textarea
              className="input"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Notas"
            />
          </div>

          <div className="card space-y-3">
            <h2 className="text-lg font-semibold">Totales y cierre de venta</h2>
            {quote ? (
              <div className="space-y-1 text-sm">
                <div>
                  Subtotal: <strong>{money(quote.subtotal_ars)}</strong>
                </div>
                <div>
                  Promociones: <strong>{money(quote.promotion_discount_total_ars)}</strong>
                </div>
                <div>
                  Subtotal promos: <strong>{money(quote.subtotal_after_promotions_ars)}</strong>
                </div>
                <div>
                  Modificador ({quote.price_modifier_pct}%):{' '}
                  <strong>{money(quote.modifier_amount_ars)}</strong>
                </div>
                <div className="text-base">
                  Total: <strong>{money(quote.total_ars)}</strong>
                </div>
                <div>
                  Factura requerida:{' '}
                  <strong>{quote.invoice_required ? 'Si' : 'No (comprobante interno)'}</strong>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                Cotiza para revisar totales antes de confirmar.
              </p>
            )}

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                className="btn-secondary"
                onClick={handleQuote}
                disabled={!items.length || busy || !cashSession}
              >
                Cotizar
              </button>
              <button
                type="button"
                className="btn"
                onClick={handleConfirm}
                disabled={!items.length || busy || !cashSession}
              >
                Confirmar venta
              </button>
            </div>

            {err ? <p className="rounded border border-rose-300 bg-rose-50 p-2 text-sm text-rose-700">{err}</p> : null}
            {msg ? <p className="rounded border border-emerald-300 bg-emerald-50 p-2 text-sm text-emerald-700">{msg}</p> : null}
            {lastSale ? (
              <div className="rounded border border-green-300 bg-green-50 p-3 text-sm">
                Venta confirmada: <strong>{lastSale.sale_number || `#${lastSale.id}`}</strong> por{' '}
                <strong>{money(lastSale.total_ars)}</strong>. Estado factura:{' '}
                <strong>{lastSale?.invoice?.status || 'sin generar'}</strong>.
              </div>
            ) : null}
          </div>

          <div className="card space-y-3">
            <h2 className="text-lg font-semibold">Borradores en espera</h2>
            <input
              className="input"
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              placeholder="Nombre borrador (ej: Cliente en probador)"
            />
            <div className="grid grid-cols-2 gap-2">
              <button type="button" className="btn-secondary" onClick={handleSaveDraft} disabled={busy || !items.length}>
                Guardar nuevo
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleUpdateDraft}
                disabled={busy || !items.length || !selectedDraftId}
              >
                Actualizar actual
              </button>
            </div>
            <button type="button" className="btn-secondary !py-2" onClick={loadDrafts} disabled={draftsLoading}>
              {draftsLoading ? 'Actualizando...' : 'Refrescar borradores'}
            </button>

            <div className="max-h-64 overflow-auto rounded-lg border border-neutral-200">
              {!drafts.length ? (
                <p className="px-3 py-2 text-sm text-gray-500">No hay borradores abiertos.</p>
              ) : (
                <div className="divide-y">
                  {drafts.map((row) => (
                    <div
                      key={row.id}
                      className={`flex items-center justify-between gap-2 px-3 py-2 ${
                        Number(row.id) === Number(selectedDraftId) ? 'bg-amber-50' : ''
                      }`}
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">
                          {row.name || row.draft_number || `#${row.id}`}
                        </p>
                        <p className="text-xs text-gray-500">
                          {row.item_count || 0} items | {money(row.total_ars)}
                        </p>
                      </div>
                      <button
                        type="button"
                        className="btn-secondary !px-2.5 !py-1.5 !text-xs"
                        onClick={() => handleLoadDraft(row.id)}
                        disabled={busy}
                      >
                        Cargar
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="card space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Ventas recientes (hoy)</h2>
              <button type="button" className="btn-secondary !px-2.5 !py-1.5 !text-xs" onClick={loadRecentSales}>
                Refrescar
              </button>
            </div>
            {recentLoading ? (
              <p className="text-sm text-gray-500">Cargando ventas...</p>
            ) : recentSales.length ? (
              <div className="space-y-1 text-sm">
                {recentSales.map((row) => (
                  <div key={row.id} className="flex items-center justify-between rounded border border-neutral-200 px-2 py-1.5">
                    <span className="truncate">{row.sale_number || `#${row.id}`}</span>
                    <strong>{money(row.total_ars)}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">Sin ventas registradas hoy.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
