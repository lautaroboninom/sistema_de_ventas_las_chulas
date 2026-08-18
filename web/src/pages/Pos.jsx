import { useEffect, useMemo, useRef, useState } from 'react';
import {
  getRetailCajaActual,
  getRetailCajaCuentas,
  getRetailConfigArcaAccounts,
  getRetailOperacionPendientes,
  getRetailStoreCredits,
  getRetailGarantiaTicket,
  getRetailPosDraftDetail,
  getRetailPosDrafts,
  getRetailVarianteByScan,
  getRetailVariantes,
  patchRetailPosDraft,
  postRetailCajaApertura,
  postRetailCajaCierre,
  postRetailCajaCierreAsistido,
  postRetailPosDraft,
  postRetailPosDraftConfirm,
  postRetailVentaConfirmar,
  postRetailVentaCotizar,
} from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { can, PERMISSION_CODES } from '../lib/permissions';
import { parseOptionSignature } from '../lib/variantAttributes';

const PAYMENT_OPTIONS = [
  { value: 'cash', label: 'Efectivo' },
  { value: 'debit', label: 'Debito' },
  { value: 'transfer', label: 'Transferencia' },
  { value: 'credit', label: 'Credito' },
  { value: 'store_credit', label: 'Credito tienda' },
];

const ACCOUNT_BY_METHOD = {
  cash: 'cash',
  debit: 'payway',
  credit: 'payway',
  transfer: 'transfer_1',
  store_credit: 'store_credit',
};

const FALLBACK_ACCOUNTS = [
  { code: 'cash', label: 'Caja', payment_method: 'cash', price_modifier_pct: -10, active: true, sort_order: 10 },
  { code: 'bbva', label: 'BBVA', payment_method: 'transfer', price_modifier_pct: 0, active: true, sort_order: 20 },
  { code: 'pbs', label: 'PBS', payment_method: 'transfer', price_modifier_pct: 0, active: true, sort_order: 30 },
  { code: 'payway', label: 'Payway', payment_method: 'credit', price_modifier_pct: 10, active: true, sort_order: 40 },
  { code: 'transfer_1', label: 'Transferencia Cuenta 1', payment_method: 'transfer', price_modifier_pct: 0, active: true, sort_order: 50 },
  { code: 'transfer_2', label: 'Transferencia Cuenta 2', payment_method: 'transfer', price_modifier_pct: 0, active: true, sort_order: 60 },
  { code: 'store_credit', label: 'Credito tienda', payment_method: 'store_credit', price_modifier_pct: 0, active: true, sort_order: 70 },
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

function normalizeDocDigits(value) {
  return String(value || '').replace(/\D+/g, '');
}

function summarizePendingRows(rows) {
  const list = Array.isArray(rows) ? rows : [];
  return {
    total: list.length,
    critical: list.filter((row) => row?.severity === 'critical').length,
    high: list.filter((row) => row?.severity === 'high').length,
    medium: list.filter((row) => row?.severity === 'medium').length,
    low: list.filter((row) => row?.severity === 'low').length,
  };
}

function normalizeAccounts(rows) {
  const list = Array.isArray(rows) && rows.length ? rows : FALLBACK_ACCOUNTS;
  const normalized = list
    .filter((row) => !!row && row.active !== false)
    .map((row) => ({
      ...row,
      price_modifier_pct:
        row?.price_modifier_pct == null || row?.price_modifier_pct === ''
          ? 0
          : Number(row.price_modifier_pct),
    }))
    .sort((a, b) => Number(a.sort_order || 100) - Number(b.sort_order || 100));
  if (!normalized.some((row) => row.code === 'store_credit')) {
    normalized.push({
      code: 'store_credit',
      label: 'Credito tienda',
      payment_method: 'store_credit',
      price_modifier_pct: 0,
      active: true,
      sort_order: 70,
    });
  }
  return normalized;
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

function accountModifierPct(accountCode, accounts) {
  const list = normalizeAccounts(accounts);
  const row = list.find((item) => String(item.code || '') === String(accountCode || ''));
  const value = Number(row?.price_modifier_pct ?? 0);
  return Number.isFinite(value) ? value : 0;
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

function Chevron({ open }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-neutral-200 text-neutral-500 transition-transform ${
        open ? 'rotate-90' : ''
      }`}
    >
      <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 3.5L11 8L6 12.5" />
      </svg>
    </span>
  );
}

function Accordion({ title, open, onToggle, badge = null, children }) {
  return (
    <div className="panel">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 text-left"
        onClick={onToggle}
        aria-expanded={open}
      >
        <span className="flex items-center gap-2">
          <span className="h2">{title}</span>
          {badge}
        </span>
        <Chevron open={open} />
      </button>
      {open ? <div className="mt-3 space-y-3">{children}</div> : null}
    </div>
  );
}

export default function PosPage() {
  const { user } = useAuth();
  const isAdmin = String(user?.rol || '').toLowerCase() === 'admin';
  const canOverridePrice = can(user, PERMISSION_CODES.ACTION_VENTAS_OVERRIDE_PRECIO);
  const canAssistedClose = can(user, PERMISSION_CODES.ACTION_CAJA_CIERRE_ASISTIDO);

  const scanRef = useRef(null);
  const scanBufferRef = useRef('');
  const scanLastKeyAtRef = useRef(0);
  const scanDetectedRef = useRef(false);
  const scanFlushTimerRef = useRef(null);
  const busyRef = useRef(false);
  const submitScanRef = useRef(null);
  const quoteRequestSeqRef = useRef(0);

  const [scan, setScan] = useState('');
  const [manualQuery, setManualQuery] = useState('');
  const [manualRows, setManualRows] = useState([]);
  const [manualLoading, setManualLoading] = useState(false);

  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [paymentAccountCode, setPaymentAccountCode] = useState('cash');
  const [cashReceived, setCashReceived] = useState('');
  const [splitPaymentsEnabled, setSplitPaymentsEnabled] = useState(false);
  const [splitPayments, setSplitPayments] = useState([
    { method: 'cash', account_code: 'cash', amount_ars: '', store_credit_id: '', modifier_pct: '' },
  ]);
  const [invoiceOverrideMode, setInvoiceOverrideMode] = useState('default');
  const [invoiceOverrideArcaAccountId, setInvoiceOverrideArcaAccountId] = useState('');

  const [customerName, setCustomerName] = useState('');
  const [customerDoc, setCustomerDoc] = useState('');
  const [storeCredits, setStoreCredits] = useState([]);
  const [storeCreditsLoading, setStoreCreditsLoading] = useState(false);
  const [selectedStoreCreditId, setSelectedStoreCreditId] = useState('');
  const [notes, setNotes] = useState('');
  const [couponCodes, setCouponCodes] = useState('');
  const [priceOverrideReason, setPriceOverrideReason] = useState('');
  const [items, setItems] = useState([]);
  const [quote, setQuote] = useState(null);
  const [lastSale, setLastSale] = useState(null);
  const [ticketLookup, setTicketLookup] = useState(null);

  const [cashSession, setCashSession] = useState(null);
  const [accounts, setAccounts] = useState(FALLBACK_ACCOUNTS);
  const [arcaAccounts, setArcaAccounts] = useState([]);
  const [openingCash, setOpeningCash] = useState('0');
  const [closingCash, setClosingCash] = useState('');
  const [closingDifferenceReason, setClosingDifferenceReason] = useState('');
  const [closingIncidentTitle, setClosingIncidentTitle] = useState('');
  const [closingIncidentDetail, setClosingIncidentDetail] = useState('');
  const [quickMode, setQuickMode] = useState(() => window.localStorage.getItem('retailhub_pos_quick_mode') !== '0');

  const [drafts, setDrafts] = useState([]);
  const [selectedDraftId, setSelectedDraftId] = useState(null);
  const [draftName, setDraftName] = useState('');
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [pendingSummary, setPendingSummary] = useState(null);

  const [manualSearchOpen, setManualSearchOpen] = useState(false);
  const [customerPanelOpen, setCustomerPanelOpen] = useState(false);
  const [draftsPanelOpen, setDraftsPanelOpen] = useState(false);
  const [cajaPanelOpen, setCajaPanelOpen] = useState(true);
  const [totalsDetailOpen, setTotalsDetailOpen] = useState(false);
  const cajaWasOpenRef = useRef(false);
  const [flashVariantId, setFlashVariantId] = useState(null);

  const [busy, setBusy] = useState(false);
  const [quoteBusy, setQuoteBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const totalQty = useMemo(
    () => items.reduce((acc, it) => acc + Number(it.quantity || 0), 0),
    [items]
  );

  const totalDue = Number(quote?.total_ars || 0);
  const cashChange = Math.max(0, Number(cashReceived || 0) - totalDue);

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
    const expected = Number(quote?.subtotal_after_promotions_ars || 0);
    const current = splitPayments.reduce((acc, row) => {
      const n = Number(row.amount_ars || 0);
      return acc + (Number.isFinite(n) ? n : 0);
    }, 0);
    const diff = current - expected;
    return { expected, current, diff };
  }, [splitPayments, quote]);
  const splitMismatch = splitPaymentsEnabled && Math.round((splitTotals.diff || 0) * 100) !== 0;
  const storeCreditSelectionMissing = useMemo(() => {
    if (!splitPaymentsEnabled) {
      return paymentMethod === 'store_credit' && !selectedStoreCreditId;
    }
    return splitPayments.some(
      (row) => String(row.method || '').trim() === 'store_credit' && !String(row.store_credit_id || '').trim()
    );
  }, [splitPaymentsEnabled, paymentMethod, selectedStoreCreditId, splitPayments]);
  const confirmActionDisabled =
    !items.length ||
    busy ||
    quoteBusy ||
    !cashSession ||
    splitMismatch ||
    storeCreditSelectionMissing;
  const cashRequiredNotice =
    'Primero abri la caja para cotizar/confirmar la venta';

  const selectedDraft = useMemo(
    () => drafts.find((row) => Number(row.id) === Number(selectedDraftId)) || null,
    [drafts, selectedDraftId]
  );
  const expectedClosingTotal = Number(cashSession?.summary?.expected_total_ars || 0);
  const closingCountedValue = closingCash === '' ? null : Number(closingCash);
  const closingDiffValue =
    closingCountedValue == null || !Number.isFinite(closingCountedValue)
      ? null
      : Math.round((closingCountedValue - expectedClosingTotal) * 100) / 100;
  const closingNeedsReason = closingDiffValue != null && closingDiffValue !== 0;

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

  function hasEditableFocus() {
    const activeEl = document?.activeElement;
    return isTextEditableTarget(activeEl) || Boolean(activeEl?.isContentEditable);
  }

  function focusScanIfIdle() {
    if (!quickMode) return;
    if (hasEditableFocus()) return;
    focusScan(true);
  }

  function resetMessages() {
    setErr('');
    setMsg('');
  }

  function toggleManualSearch() {
    setManualSearchOpen((prev) => {
      if (prev) {
        setManualQuery('');
        setManualRows([]);
      }
      return !prev;
    });
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
    setFlashVariantId(row.variant_id);
    setQuote(null);
    setTicketLookup(null);
  }

  function clearCart() {
    setItems([]);
    setQuote(null);
    setTicketLookup(null);
    setCouponCodes('');
    setPriceOverrideReason('');
    setCashReceived('');
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

  function buildInvoiceOverridePayload() {
    const mode = isAdmin ? String(invoiceOverrideMode || 'default').toLowerCase() : 'default';
    if (mode === 'default') return undefined;
    if (mode === 'none') return { mode: 'none' };
    if (mode !== 'arca') return undefined;
    const accountId = Number(invoiceOverrideArcaAccountId || 0);
    if (!Number.isFinite(accountId) || accountId <= 0) {
      throw new Error('Selecciona una cuenta ARCA valida para override');
    }
    return { mode: 'arca', arca_account_id: accountId };
  }

  function buildPaymentsPayload(expectedBase) {
    const expected = Number(expectedBase);
    const hasExpected = Number.isFinite(expected);

    if (!splitPaymentsEnabled) {
      if (paymentMethod !== 'store_credit') return undefined;
      if (!hasExpected) {
        return undefined;
      }
      const creditId = Number(selectedStoreCreditId || 0);
      if (!Number.isFinite(creditId) || creditId <= 0) {
        throw new Error('Selecciona un credito tienda valido');
      }
      return [
        {
          method: 'store_credit',
          account_code: paymentAccountCode || defaultAccountCode('store_credit', accounts),
          amount_ars: expected,
          metadata: { store_credit_id: creditId },
          store_credit_id: creditId,
        },
      ];
    }

    const rows = splitPayments
      .map((row) => ({
        method: String(row.method || '').trim(),
        account_code: String(row.account_code || '').trim(),
        amount_ars: Number(row.amount_ars || 0),
        store_credit_id: row.store_credit_id ? Number(row.store_credit_id) : undefined,
        modifier_pct:
          row.modifier_pct == null || String(row.modifier_pct).trim() === ''
            ? undefined
            : Number(row.modifier_pct),
      }))
      .filter((row) => row.method && row.amount_ars > 0);
    if (!rows.length) {
      throw new Error('Debes cargar al menos un tramo de pago');
    }
    rows.forEach((row, idx) => {
      if (!['cash', 'debit', 'transfer', 'credit', 'store_credit'].includes(row.method)) {
        throw new Error(`Metodo invalido en pago #${idx + 1}`);
      }
      if (!row.account_code) {
        throw new Error(`Cuenta requerida en pago #${idx + 1}`);
      }
      if (row.method === 'store_credit') {
        if (!Number.isFinite(Number(row.store_credit_id || 0)) || Number(row.store_credit_id) <= 0) {
          throw new Error(`Selecciona credito tienda en pago #${idx + 1}`);
        }
        row.metadata = { store_credit_id: Number(row.store_credit_id) };
      }
      if (row.modifier_pct != null && !Number.isFinite(row.modifier_pct)) {
        throw new Error(`modifier_pct invalido en pago #${idx + 1}`);
      }
      if (!isAdmin) {
        delete row.modifier_pct;
      }
    });
    if (hasExpected) {
      const sum = rows.reduce((acc, row) => acc + Number(row.amount_ars || 0), 0);
      const roundedDiff = Math.round((sum - expected) * 100) / 100;
      if (roundedDiff !== 0) {
        throw new Error('La suma base de pagos debe coincidir con subtotal base');
      }
    }
    return rows;
  }

  function buildBaseSalePayload() {
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
      items: buildItemsPayload(),
    };
    const invoiceOverride = buildInvoiceOverridePayload();
    if (invoiceOverride) payload.invoice_override = invoiceOverride;
    return payload;
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
    const invoiceOverride = buildInvoiceOverridePayload();
    if (invoiceOverride) payload.invoice_override = invoiceOverride;
    if (!splitPaymentsEnabled && paymentMethod === 'store_credit' && selectedStoreCreditId) {
      payload.payments = [
        {
          method: 'store_credit',
          account_code: paymentAccountCode || defaultAccountCode('store_credit', accounts),
          amount_ars:
            quote?.subtotal_after_promotions_ars != null
              ? String(quote.subtotal_after_promotions_ars)
              : '',
          store_credit_id: selectedStoreCreditId,
          metadata: { store_credit_id: Number(selectedStoreCreditId) },
        },
      ];
    }
    if (splitPaymentsEnabled) {
      payload.payments = splitPayments.map((row) => ({
        method: row.method,
        account_code: row.account_code,
        amount_ars: row.amount_ars,
        modifier_pct:
          isAdmin && row.modifier_pct !== '' && row.modifier_pct != null
            ? Number(row.modifier_pct)
            : undefined,
        store_credit_id: row.store_credit_id || undefined,
        metadata: row.store_credit_id ? { store_credit_id: Number(row.store_credit_id) } : undefined,
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
    const rawInvoiceOverride = data.invoice_override && typeof data.invoice_override === 'object' ? data.invoice_override : {};
    const nextInvoiceMode = ['default', 'arca', 'none'].includes(String(rawInvoiceOverride.mode || '').toLowerCase())
      ? String(rawInvoiceOverride.mode || '').toLowerCase()
      : 'default';
    setInvoiceOverrideMode(nextInvoiceMode);
    setInvoiceOverrideArcaAccountId(
      rawInvoiceOverride.arca_account_id != null ? String(rawInvoiceOverride.arca_account_id) : ''
    );
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
        modifier_pct:
          row.modifier_pct != null
            ? String(row.modifier_pct)
            : row.price_modifier_pct != null
              ? String(row.price_modifier_pct)
              : '',
        store_credit_id:
          row.store_credit_id != null
            ? String(row.store_credit_id)
            : row?.metadata?.store_credit_id != null
              ? String(row.metadata.store_credit_id)
              : '',
      }))
      .filter((row) => row.method);
    const singleCreditId = mapped.length === 1 ? String(mapped[0].store_credit_id || '') : '';
    if (nextMethod === 'store_credit') {
      setSelectedStoreCreditId(singleCreditId);
    } else if (singleCreditId) {
      setSelectedStoreCreditId(singleCreditId);
    } else {
      setSelectedStoreCreditId('');
    }

    if (mapped.length > 1) {
      setSplitPaymentsEnabled(true);
      setSplitPayments(mapped);
    } else {
      setSplitPaymentsEnabled(false);
      setSplitPayments([
        {
          method: nextMethod,
          account_code: nextAccount,
          amount_ars:
            quoteSnapshot?.subtotal_after_promotions_ars != null
              ? String(quoteSnapshot.subtotal_after_promotions_ars)
              : '',
          store_credit_id: '',
          modifier_pct: '',
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

  async function loadArcaAccounts() {
    try {
      const resp = await getRetailConfigArcaAccounts();
      const rows = Array.isArray(resp?.accounts) ? resp.accounts : [];
      const activeRows = rows
        .filter((row) => row?.active !== false)
        .sort((a, b) => Number(a.sort_order || 100) - Number(b.sort_order || 100));
      setArcaAccounts(activeRows);
    } catch {
      setArcaAccounts([]);
    }
  }

  async function loadStoreCreditsByDoc() {
    const doc = normalizeDocDigits(customerDoc);
    if (!doc) {
      setStoreCredits([]);
      setSelectedStoreCreditId('');
      setErr('Ingresa DNI/CUIT del cliente para buscar creditos tienda');
      return;
    }
    setStoreCreditsLoading(true);
    try {
      const resp = await getRetailStoreCredits({ customer_doc: doc, status: 'active', limit: 50 });
      const rows = Array.isArray(resp?.rows) ? resp.rows : [];
      setStoreCredits(rows);
      if (!rows.length) {
        setSelectedStoreCreditId('');
        setMsg('No hay creditos tienda activos para ese documento');
        return;
      }
      const currentId = Number(selectedStoreCreditId || 0);
      const stillExists = rows.some((row) => Number(row.id) === currentId);
      if (!stillExists) {
        setSelectedStoreCreditId(String(rows[0].id));
      }
      setMsg(`Se cargaron ${rows.length} credito(s) disponibles`);
    } catch (error) {
      setStoreCredits([]);
      setSelectedStoreCreditId('');
      setErr(errMsg(error));
    } finally {
      setStoreCreditsLoading(false);
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

  async function loadOperationalPending() {
    try {
      const resp = await getRetailOperacionPendientes({ limit: 30 });
      const allRows = Array.isArray(resp?.rows) ? resp.rows : [];
      const posRows = allRows.filter((row) => String(row?.source || '').toLowerCase() !== 'online');
      setPendingSummary(summarizePendingRows(posRows));
    } catch {
      setPendingSummary(summarizePendingRows([]));
    }
  }

  useEffect(() => {
    loadCashSession();
    loadAccounts();
    loadArcaAccounts();
    loadDrafts();
    loadOperationalPending();
  }, []);

  useEffect(() => {
    busyRef.current = busy;
  }, [busy]);

  useEffect(() => {
    window.localStorage.setItem('retailhub_pos_quick_mode', quickMode ? '1' : '0');
  }, [quickMode]);

  // Los avisos de exito se autodescartan; los errores quedan hasta que la cajera los cierre.
  useEffect(() => {
    if (!msg) return undefined;
    const timer = window.setTimeout(() => setMsg(''), 4000);
    return () => window.clearTimeout(timer);
  }, [msg]);

  // Caja recien abierta: colapsa el panel. Caja cerrada: lo despliega.
  useEffect(() => {
    const isOpenNow = Boolean(cashSession);
    if (isOpenNow === cajaWasOpenRef.current) return;
    cajaWasOpenRef.current = isOpenNow;
    setCajaPanelOpen(!isOpenNow);
  }, [cashSession]);

  useEffect(() => {
    if (!flashVariantId) return undefined;
    const timer = window.setTimeout(() => setFlashVariantId(null), 700);
    return () => window.clearTimeout(timer);
  }, [flashVariantId]);

  useEffect(() => {
    if (quickMode) {
      focusScanIfIdle();
    }
  }, [quickMode]);

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
            amount_ars:
              quote?.subtotal_after_promotions_ars != null
                ? String(quote.subtotal_after_promotions_ars)
                : '',
            store_credit_id: '',
            modifier_pct: '',
          },
        ];
      }
      return prev.map((row) => {
        const method = row.method || paymentMethod;
        const available = accountsByMethod(method);
        const exists = available.some((acc) => acc.code === row.account_code);
        const nextAccountCode = exists ? row.account_code : defaultAccountCode(method, accounts);
        const defaultPct = accountModifierPct(nextAccountCode, accounts);
        return {
          ...row,
          method,
          account_code: nextAccountCode,
          modifier_pct:
            row?.modifier_pct == null || row?.modifier_pct === ''
              ? String(defaultPct)
              : row.modifier_pct,
        };
      });
    });
  }, [splitPaymentsEnabled, paymentMethod, paymentAccountCode, accounts, quote]);

  useEffect(() => {
    const doc = normalizeDocDigits(customerDoc);
    if (!doc) {
      setStoreCredits([]);
      setSelectedStoreCreditId('');
    }
  }, [customerDoc]);

  useEffect(() => {
    if (!quote) return;
    if (invoiceOverrideMode !== 'default') return;
    if (invoiceOverrideArcaAccountId) return;
    const suggested =
      quote?.invoice_arca_account_id ??
      quote?.invoice_default?.arca_account_id ??
      '';
    if (suggested) {
      setInvoiceOverrideArcaAccountId(String(suggested));
    }
  }, [quote, invoiceOverrideMode, invoiceOverrideArcaAccountId]);

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
    if (!items.length || !cashSession) {
      quoteRequestSeqRef.current += 1;
      setQuoteBusy(false);
      setQuote(null);
      return;
    }
    if (busy) return;
    const timer = setTimeout(() => {
      void requestQuote({ showError: true });
    }, 400);
    return () => clearTimeout(timer);
  }, [
    items,
    paymentMethod,
    paymentAccountCode,
    couponCodes,
    splitPaymentsEnabled,
    splitPayments,
    invoiceOverrideMode,
    invoiceOverrideArcaAccountId,
    cashSession,
    busy,
  ]);

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
        focusScanIfIdle();
      }
    }
  }

  async function handleScanSubmit(e) {
    e?.preventDefault?.();
    await submitScanCode(scan, { restoreFocus: true });
  }

  async function requestQuote(options = {}) {
    const showError = options.showError !== false;
    if (!items.length || !cashSession) return null;
    const requestId = ++quoteRequestSeqRef.current;
    setQuoteBusy(true);
    try {
      const resp = await postRetailVentaCotizar({
        channel: 'local',
        payment_method: paymentMethod,
        payment_account_code: paymentAccountCode,
        coupon_codes: parseCouponCodes(couponCodes),
        invoice_override: buildInvoiceOverridePayload(),
        payments: buildPaymentsPayload(quote?.subtotal_after_promotions_ars),
        items: buildItemsPayload(),
      });
      if (requestId !== quoteRequestSeqRef.current) return null;
      setQuote(resp);
      if (splitPaymentsEnabled && splitPayments.length === 1) {
        setSplitPayments((prev) =>
          prev.map((row, idx) =>
            idx === 0
              ? {
                  ...row,
                  amount_ars: String(resp?.subtotal_after_promotions_ars ?? ''),
                }
              : row
          )
        );
      }
      return resp;
    } catch (error) {
      if (requestId !== quoteRequestSeqRef.current) return null;
      if (showError) {
        setMsg('');
        setErr(errMsg(error));
      }
      return null;
    } finally {
      if (requestId === quoteRequestSeqRef.current) {
        setQuoteBusy(false);
      }
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
    if (busy) return;
    if (!items.length) {
      setMsg('');
      setErr('Agrega al menos un producto para confirmar la venta');
      return;
    }
    if (!cashSession) {
      setMsg('');
      setErr(cashRequiredNotice);
      return;
    }
    if (storeCreditSelectionMissing) {
      setMsg('');
      setErr('Falta seleccionar credito tienda para uno o mas tramos de pago');
      return;
    }
    if (anyOverride && !String(priceOverrideReason || '').trim()) {
      setMsg('');
      setErr('Debes indicar motivo de override de precio');
      return;
    }
    resetMessages();
    setBusy(true);
    try {
      const refreshedQuote = await requestQuote({ showError: false });
      if (!refreshedQuote) {
        throw new Error('No se pudo recalcular la cotizacion antes de confirmar');
      }
      const basePayload = buildBaseSalePayload();
      const expectedBase = refreshedQuote?.subtotal_after_promotions_ars;
      const paymentsPayload = buildPaymentsPayload(expectedBase);
      if (paymentsPayload?.length) {
        basePayload.payments = paymentsPayload;
      }

      let sale;
        if (selectedDraftId) {
          const resp = await postRetailPosDraftConfirm(selectedDraftId, {
            payload: { ...buildDraftPayload(), ...basePayload, payments: paymentsPayload },
            quote_snapshot: refreshedQuote || quote || undefined,
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
      setStoreCredits([]);
      setSelectedStoreCreditId('');
      setNotes('');
      setCashReceived('');
      setInvoiceOverrideMode('default');
      setInvoiceOverrideArcaAccountId('');
      setSplitPaymentsEnabled(false);
      setSplitPayments([
        {
          method: paymentMethod,
          account_code: paymentAccountCode,
          amount_ars: '',
          store_credit_id: '',
          modifier_pct: '',
        },
      ]);
      setMsg('Venta confirmada');
      await Promise.all([loadCashSession(), loadDrafts(), loadOperationalPending()]);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
      focusScanIfIdle();
    }
  }

  async function openCashSession() {
    resetMessages();
    setBusy(true);
    try {
      await postRetailCajaApertura({ opening_amount_cash_ars: Number(openingCash || 0) });
      setMsg('Caja abierta');
      await Promise.all([loadCashSession(), loadOperationalPending()]);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
      focusScanIfIdle();
    }
  }

  async function closeCashSession() {
    if (canAssistedClose && closingCash === '') {
      setErr('Ingresa el contado de cierre para ejecutar cierre asistido');
      return;
    }
    if (canAssistedClose && closingNeedsReason && !String(closingDifferenceReason || '').trim()) {
      setErr('Debes indicar motivo de diferencia de caja');
      return;
    }
    resetMessages();
    setBusy(true);
    try {
      if (canAssistedClose) {
        const incidents = [];
        if (String(closingIncidentTitle || '').trim()) {
          incidents.push({
            title: String(closingIncidentTitle || '').trim(),
            detail: String(closingIncidentDetail || '').trim() || undefined,
            severity: 'medium',
            action_required: 'Revisar incidencia de cierre',
            sla_minutes: 180,
          });
        }
        await postRetailCajaCierreAsistido({
          closing_counted_total_ars: Number(closingCash),
          difference_reason: closingNeedsReason ? String(closingDifferenceReason || '').trim() : undefined,
          closing_note: 'Cierre asistido POS',
          incidents,
        });
      } else {
        await postRetailCajaCierre({
          closing_counted_total_ars: closingCash === '' ? undefined : Number(closingCash),
        });
      }
      setClosingCash('');
      setClosingDifferenceReason('');
      setClosingIncidentTitle('');
      setClosingIncidentDetail('');
      setMsg('Caja cerrada');
      await Promise.all([loadCashSession(), loadOperationalPending()]);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
      focusScanIfIdle();
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
      focusScanIfIdle();
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
        if (patch.method && patch.method !== row.method) {
          next.store_credit_id = patch.method === 'store_credit' ? String(next.store_credit_id || '') : '';
        }
        if (patch.method || patch.account_code) {
          const nextCode = String(next.account_code || defaultAccountCode(String(next.method || paymentMethod), accounts));
          if (next.modifier_pct == null || String(next.modifier_pct).trim() === '') {
            next.modifier_pct = String(accountModifierPct(nextCode, accounts));
          }
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
        store_credit_id: '',
        modifier_pct: String(accountModifierPct(defaultAccountCode(paymentMethod, accounts), accounts)),
      },
    ]);
  }

  function removeSplitRow(idx) {
    setSplitPayments((prev) => prev.filter((_, i) => i !== idx));
  }

  function selectPaymentMethod(next) {
    setPaymentMethod(next);
    setPaymentAccountCode(defaultAccountCode(next, accounts));
    if (next !== 'store_credit') {
      setSelectedStoreCreditId('');
    }
    setQuote(null);
  }

  return (
    <div className="space-y-4 pb-6 xl:flex xl:min-h-[calc(100vh_-_7rem)] xl:flex-col xl:pb-44">
      <div className="pointer-events-none fixed right-4 top-[4.5rem] z-40 flex w-[min(22rem,calc(100vw_-_2rem))] flex-col gap-2">
        {err ? (
          <div className="pointer-events-auto flex animate-lc-toast-in items-start gap-2 rounded-2xl border border-rose-200 bg-white/90 p-3 text-sm text-rose-800 shadow-lift backdrop-blur">
            <span className="flex-1">{err}</span>
            <button
              type="button"
              className="shrink-0 rounded px-1 text-rose-400 transition hover:text-rose-700"
              onClick={() => setErr('')}
              aria-label="Cerrar aviso de error"
            >
              &times;
            </button>
          </div>
        ) : null}
        {msg ? (
          <div className="pointer-events-auto animate-lc-toast-in rounded-2xl border border-emerald-200 bg-white/90 p-3 text-sm font-medium text-emerald-800 shadow-lift backdrop-blur">
            {msg}
          </div>
        ) : null}
      </div>

      <div className="panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="font-display text-xl font-bold tracking-tight">POS</h1>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              className={`chip transition ${quickMode ? 'chip-active' : 'hover:border-neutral-300'}`}
              onClick={() => setQuickMode((prev) => !prev)}
            >
              Venta rapida {quickMode ? 'ON' : 'OFF'}
            </button>
            <span
              className={`chip ${
                cashSession
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-rose-200 bg-rose-50 text-rose-700'
              }`}
            >
              Caja {cashSession ? `abierta #${cashSession.id}` : 'sin apertura'}
            </span>
            <span className="chip num">Items {totalQty}</span>
            {selectedDraft ? <span className="chip">Draft {selectedDraft.draft_number}</span> : null}
            {pendingSummary?.total ? (
              <span className="chip border-amber-200 bg-amber-50 text-amber-700">
                Pendientes {pendingSummary.total}
                {pendingSummary.critical ? ` (${pendingSummary.critical} crit)` : ''}
              </span>
            ) : null}
          </div>
        </div>
        <p className="mt-2 text-xs text-neutral-400">
          F2 foco scanner &middot; F8 guardar borrador &middot; F9 confirmar &middot; Ctrl+Backspace limpia carrito
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:flex-1 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-4">
          <form className="panel space-y-2" onSubmit={handleScanSubmit}>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
              <div className="md:col-span-3">
                <label className="label">Escanear barcode interno o SKU</label>
                <input
                  ref={scanRef}
                  className={`input ${quickMode ? 'ring-2 ring-brand-accent/25' : ''}`}
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
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-neutral-400">
                {manualSearchOpen ? 'Buscando en el catalogo' : 'Sin el codigo a mano?'}
              </span>
              <button type="button" className="btn-ghost" onClick={toggleManualSearch}>
                {manualSearchOpen ? 'Ocultar busqueda' : 'Buscar manualmente'}
              </button>
            </div>
            {manualSearchOpen ? (
              <>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
                  <div className="md:col-span-3">
                    <input
                      className="input"
                      value={manualQuery}
                      onChange={(e) => setManualQuery(e.target.value)}
                      placeholder="Buscar por SKU, barcode o producto"
                      autoFocus
                    />
                  </div>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => {
                      setManualQuery('');
                      setManualRows([]);
                    }}
                  >
                    Limpiar
                  </button>
                </div>
                {manualQuery.trim().length >= 2 ? (
                  <div className="rounded-xl border border-neutral-200">
                    {manualLoading ? (
                      <p className="px-3 py-2 text-sm text-neutral-500">Buscando variantes...</p>
                    ) : manualRows.length ? (
                      <div className="max-h-72 divide-y divide-neutral-100 overflow-auto">
                        {manualRows.map((row) => {
                          const attrs = parseOptionSignature(row.option_signature);
                          return (
                            <div key={row.id} className="flex items-center justify-between gap-3 px-3 py-2">
                              <div className="min-w-0">
                                <p className="truncate text-sm font-semibold">{row.producto}</p>
                                <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                                  {attrs.map((attr, idx) => (
                                    <span key={`manual-${row.id}-${idx}`} className="chip chip-active px-2 text-[11px]">
                                      {attr.label ? <span className="opacity-60">{attr.label}</span> : null}
                                      {attr.value}
                                    </span>
                                  ))}
                                  <span className="text-[11px] text-neutral-400">{row.sku || '-'}</span>
                                </div>
                              </div>
                              <div className="flex shrink-0 items-center gap-2">
                                <span className="num text-sm font-semibold">{money(row.price_store_ars)}</span>
                                <button
                                  type="button"
                                  className="btn-secondary btn-sm"
                                  onClick={() => {
                                    addOrIncreaseItem(row);
                                    setManualQuery('');
                                    setManualRows([]);
                                  }}
                                >
                                  Agregar
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="px-3 py-2 text-sm text-neutral-500">Sin resultados para la busqueda.</p>
                    )}
                  </div>
                ) : null}
              </>
            ) : null}
          </form>

          {ticketLookup?.sale ? (
            <div className="panel space-y-2">
              <h2 className="h2">Ticket escaneado</h2>
              <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-4">
                <div>Ticket: <strong>{ticketLookup.sale.sale_number || `#${ticketLookup.sale.id}`}</strong></div>
                <div>Fecha: <strong>{String(ticketLookup.sale.created_at || '').slice(0, 16).replace('T', ' ')}</strong></div>
                <div>Total: <strong className="num">{money(ticketLookup.sale.total_ars)}</strong></div>
                <div>Estado: <strong>{ticketLookup.sale.status}</strong></div>
              </div>
            </div>
          ) : null}

          <div className="panel flex min-h-[16rem] flex-col overflow-hidden md:min-h-[20rem] xl:min-h-[24rem] xl:flex-1">
            <div className="flex items-center justify-between gap-2">
              <h2 className="h2">
                Carrito <span className="num font-normal text-neutral-400">({totalQty})</span>
              </h2>
              <div className="flex gap-1">
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={resetDraftContext}
                  disabled={!selectedDraftId}
                >
                  Soltar draft
                </button>
                <button type="button" className="btn-ghost" onClick={clearCart} disabled={!items.length}>
                  Limpiar
                </button>
              </div>
            </div>

            {!items.length ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 py-10 text-center">
                <span
                  aria-hidden="true"
                  className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-brand-accent/10 text-brand-accent"
                >
                  <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                    <path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" />
                    <path d="M7 8v8M10.5 8v8M14 8v8M17 8v8" />
                  </svg>
                </span>
                <p className="font-display text-sm font-semibold text-neutral-600">
                  Escanea una prenda para empezar
                </p>
                <p className="text-xs text-neutral-400">
                  O usa la busqueda manual si no tenes el codigo a mano.
                </p>
              </div>
            ) : (
              <ul className="mt-2 flex-1 divide-y divide-neutral-100 overflow-y-auto">
                {items.map((it) => {
                  const qLine = quoteByVariant.get(Number(it.variant_id));
                  const attrs = parseOptionSignature(it.firma);
                  return (
                    <li
                      key={it.variant_id}
                      className={`rounded-xl px-1 py-2.5 ${
                        Number(flashVariantId) === Number(it.variant_id) ? 'animate-lc-pop' : ''
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate font-display text-sm font-semibold">{it.producto}</p>
                          <div className="mt-1 flex flex-wrap items-center gap-1.5">
                            {attrs.map((attr, idx) => (
                              <span key={`${it.variant_id}-attr-${idx}`} className="chip chip-active px-2 text-[11px]">
                                {attr.label ? <span className="opacity-60">{attr.label}</span> : null}
                                {attr.value}
                              </span>
                            ))}
                            <span className="text-[11px] text-neutral-400">
                              {it.sku || it.barcode_internal || '-'}
                            </span>
                          </div>
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="num font-display text-sm font-semibold">
                            {money(qLine?.line_total_ars || 0)}
                          </p>
                          <p className="num text-[11px] text-neutral-400">{money(it.precio_local)} c/u</p>
                        </div>
                      </div>

                      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-neutral-200 text-neutral-600 transition hover:border-brand-accent hover:text-brand-accent"
                            onClick={() => stepQty(it.variant_id, -1)}
                            aria-label="Restar una unidad"
                          >
                            &minus;
                          </button>
                          <input
                            className="input num w-14 px-1 py-1 text-center text-sm"
                            type="number"
                            min="1"
                            value={it.quantity}
                            onChange={(e) => changeQty(it.variant_id, e.target.value)}
                            aria-label="Cantidad"
                          />
                          <button
                            type="button"
                            className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-neutral-200 text-neutral-600 transition hover:border-brand-accent hover:text-brand-accent"
                            onClick={() => stepQty(it.variant_id, 1)}
                            aria-label="Sumar una unidad"
                          >
                            +
                          </button>
                        </div>
                        <div className="flex items-center gap-2">
                          {canOverridePrice ? (
                            <input
                              className="input num w-28 px-2 py-1 text-xs"
                              type="number"
                              min="0"
                              step="0.01"
                              value={it.unit_price_override_ars || ''}
                              onChange={(e) => changeOverride(it.variant_id, e.target.value)}
                              placeholder="Precio manual"
                            />
                          ) : null}
                          <button
                            type="button"
                            className="rounded-lg px-2 py-1 text-xs font-semibold text-rose-500 transition hover:bg-rose-50 hover:text-rose-700"
                            onClick={() => removeItem(it.variant_id)}
                          >
                            Quitar
                          </button>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Accordion
              title="Cliente y notas"
              open={customerPanelOpen}
              onToggle={() => setCustomerPanelOpen((prev) => !prev)}
              badge={
                customerName || customerDoc ? (
                  <span className="chip chip-active px-2 text-[11px]">{customerName || customerDoc}</span>
                ) : null
              }
            >
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
            </Accordion>

            <Accordion
              title="Borradores en espera"
              open={draftsPanelOpen}
              onToggle={() => setDraftsPanelOpen((prev) => !prev)}
              badge={drafts.length ? <span className="chip num px-2 text-[11px]">{drafts.length}</span> : null}
            >
              <input
                className="input"
                value={draftName}
                onChange={(e) => setDraftName(e.target.value)}
                placeholder="Nombre borrador (ej: Cliente en probador)"
              />
              <div className="grid grid-cols-2 gap-2">
                <button type="button" className="btn-secondary btn-sm" onClick={handleSaveDraft} disabled={busy || !items.length}>
                  Guardar nuevo
                </button>
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={handleUpdateDraft}
                  disabled={busy || !items.length || !selectedDraftId}
                >
                  Actualizar actual
                </button>
              </div>
              <button type="button" className="btn-ghost w-full" onClick={loadDrafts} disabled={draftsLoading}>
                {draftsLoading ? 'Actualizando...' : 'Refrescar borradores'}
              </button>

              <div className="max-h-64 overflow-auto rounded-xl border border-neutral-200">
                {!drafts.length ? (
                  <p className="px-3 py-2 text-sm text-neutral-500">No hay borradores abiertos.</p>
                ) : (
                  <div className="divide-y divide-neutral-100">
                    {drafts.map((row) => (
                      <div
                        key={row.id}
                        className={`flex items-center justify-between gap-2 px-3 py-2 ${
                          Number(row.id) === Number(selectedDraftId) ? 'bg-brand-accent/5' : ''
                        }`}
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold">
                            {row.name || row.draft_number || `#${row.id}`}
                          </p>
                          <p className="num text-xs text-neutral-400">
                            {row.item_count || 0} items | {money(row.total_ars)}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="btn-secondary btn-sm"
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
            </Accordion>
          </div>
        </div>

        <div className="space-y-4">
          <Accordion
            title="Caja"
            open={cajaPanelOpen}
            onToggle={() => setCajaPanelOpen((prev) => !prev)}
            badge={
              <span
                className={`chip px-2 text-[11px] ${
                  cashSession
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    : 'border-rose-200 bg-rose-50 text-rose-700'
                }`}
              >
                {cashSession ? 'Abierta' : 'Cerrada'}
              </span>
            }
          >
            <div className="rounded-xl border border-neutral-200 bg-neutral-50/70 p-2.5 text-sm">
              {cashSession ? (
                <div className="space-y-0.5">
                  <div>
                    Estado: <strong className="text-emerald-700">Abierta #{cashSession.id}</strong>
                  </div>
                  <div>
                    Esperado efectivo: <strong className="num">{money(cashSession?.summary?.expected_total_ars)}</strong>
                  </div>
                  <div>
                    Neto no-cash: <strong className="num">{money(cashSession?.summary?.net_non_cash_ars)}</strong>
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
                  className="input num"
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
                  className="input num"
                  type="number"
                  step="0.01"
                  value={closingCash}
                  onChange={(e) => setClosingCash(e.target.value)}
                  placeholder={canAssistedClose ? 'Conteo al cierre (requerido)' : 'Conteo al cierre (opcional)'}
                />
                {closingDiffValue != null ? (
                  <p className={`text-xs ${closingDiffValue === 0 ? 'text-emerald-700' : 'text-amber-700'}`}>
                    Diferencia estimada: <strong className="num">{money(closingDiffValue)}</strong>
                  </p>
                ) : null}
                {canAssistedClose && closingNeedsReason ? (
                  <input
                    className="input"
                    value={closingDifferenceReason}
                    onChange={(e) => setClosingDifferenceReason(e.target.value)}
                    placeholder="Motivo de diferencia (obligatorio)"
                  />
                ) : null}
                {canAssistedClose ? (
                  <>
                    <input
                      className="input"
                      value={closingIncidentTitle}
                      onChange={(e) => setClosingIncidentTitle(e.target.value)}
                      placeholder="Incidencia de cierre (opcional)"
                    />
                    {closingIncidentTitle.trim() ? (
                      <textarea
                        className="input"
                        rows={2}
                        value={closingIncidentDetail}
                        onChange={(e) => setClosingIncidentDetail(e.target.value)}
                        placeholder="Detalle de incidencia"
                      />
                    ) : null}
                  </>
                ) : null}
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={closeCashSession}
                  disabled={busy || items.length > 0}
                >
                  {canAssistedClose ? 'Cerrar caja (asistido)' : 'Cerrar caja'}
                </button>
              </div>
            )}

            <div className="rounded-xl border border-neutral-200">
              <div className="border-b border-neutral-100 px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-neutral-400">
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
                        <strong className="num">{money(row.total_ars)}</strong>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-neutral-400">Sin movimientos en esta caja.</p>
                )}
              </div>
            </div>
          </Accordion>

          <div className="xl:sticky xl:top-20 xl:self-start">
            <div className="panel space-y-3">
              <h2 className="h2">Cobro</h2>

              <div>
                <span className="label">Medio de pago</span>
                <div role="radiogroup" aria-label="Medio de pago" className="flex flex-wrap gap-1.5">
                  {PAYMENT_OPTIONS.map((op) => {
                    const active = paymentMethod === op.value;
                    return (
                      <button
                        key={op.value}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        className={`chip transition ${active ? 'chip-active' : 'hover:border-neutral-300'}`}
                        onClick={(event) => {
                          selectPaymentMethod(op.value);
                          // Devolvemos el foco al scanner para no romper la captura global de teclado.
                          event.currentTarget.blur();
                          focusScanIfIdle();
                        }}
                      >
                        {op.label}
                      </button>
                    );
                  })}
                </div>
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

              {paymentMethod === 'store_credit' ? (
                <div className="space-y-2 rounded-xl border border-neutral-200 p-2">
                  <div className="flex flex-wrap items-end gap-2">
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={loadStoreCreditsByDoc}
                      disabled={storeCreditsLoading}
                    >
                      {storeCreditsLoading ? 'Buscando...' : 'Buscar creditos por DNI/CUIT'}
                    </button>
                    <span className="text-xs text-neutral-500">
                      Doc cliente: <strong>{normalizeDocDigits(customerDoc) || '-'}</strong>
                    </span>
                  </div>
                  <select
                    className="input"
                    value={selectedStoreCreditId}
                    onChange={(e) => setSelectedStoreCreditId(e.target.value)}
                  >
                    <option value="">Seleccionar credito tienda</option>
                    {storeCredits.map((row) => (
                      <option key={`base-credit-${row.id}`} value={String(row.id)}>
                        #{row.id} | saldo {money(row.amount_balance_ars)} | {row.customer_name || row.customer_doc || 'cliente'}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}

              {!splitPaymentsEnabled && paymentMethod === 'cash' ? (
                <div className="grid grid-cols-3 gap-2 rounded-xl border border-neutral-200 p-2">
                  <label className="col-span-1 block">
                    <span className="label">Recibido</span>
                    <input
                      className="input num px-2 py-1.5 text-sm"
                      type="number"
                      min="0"
                      step="0.01"
                      value={cashReceived}
                      onChange={(e) => setCashReceived(e.target.value)}
                    />
                  </label>
                  <div className="rounded-lg bg-neutral-50 px-2 py-1">
                    <div className="text-[10px] uppercase tracking-wide text-neutral-400">Total</div>
                    <strong className="num text-sm">{money(totalDue)}</strong>
                  </div>
                  <div className="rounded-lg bg-brand-accent/10 px-2 py-1">
                    <div className="text-[10px] uppercase tracking-wide text-brand-accent-dark">Vuelto</div>
                    <strong className="num text-sm text-brand-accent-dark">{money(cashChange)}</strong>
                  </div>
                </div>
              ) : null}

              <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
                <input
                  type="checkbox"
                  className="accent-brand-accent"
                  checked={splitPaymentsEnabled}
                  onChange={(e) => setSplitPaymentsEnabled(e.target.checked)}
                />
                Pago mixto (split tender)
              </label>

              {splitPaymentsEnabled ? (
                <div className="space-y-2 rounded-xl border border-neutral-200 p-2">
                  {splitPayments.map((row, idx) => {
                    const scopedAccounts = accountsByMethod(row.method || paymentMethod);
                    return (
                      <div key={`split-${idx}`} className="grid grid-cols-1 gap-2 rounded-lg bg-neutral-50/70 p-2">
                        <select
                          className="input px-2 py-1.5 text-sm"
                          value={row.method}
                          onChange={(e) =>
                            changeSplitRow(idx, {
                              method: e.target.value,
                              account_code: defaultAccountCode(e.target.value, accounts),
                              modifier_pct: String(
                                accountModifierPct(defaultAccountCode(e.target.value, accounts), accounts)
                              ),
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
                          className="input px-2 py-1.5 text-sm"
                          value={row.account_code}
                          onChange={(e) =>
                            changeSplitRow(idx, {
                              account_code: e.target.value,
                              modifier_pct: String(accountModifierPct(e.target.value, accounts)),
                            })
                          }
                        >
                          {scopedAccounts.map((acc) => (
                            <option key={`${idx}-${acc.code}`} value={acc.code}>
                              {acc.label}
                            </option>
                          ))}
                        </select>
                        {row.method === 'store_credit' ? (
                          <select
                            className="input px-2 py-1.5 text-sm"
                            value={row.store_credit_id || ''}
                            onChange={(e) => changeSplitRow(idx, { store_credit_id: e.target.value })}
                          >
                            <option value="">Seleccionar credito</option>
                            {storeCredits.map((credit) => (
                              <option key={`split-credit-${idx}-${credit.id}`} value={String(credit.id)}>
                                #{credit.id} | saldo {money(credit.amount_balance_ars)}
                              </option>
                            ))}
                          </select>
                        ) : null}
                        <div className="flex items-center gap-2">
                          <input
                            className="input num px-2 py-1.5 text-sm"
                            type="number"
                            step="0.01"
                            min="0"
                            placeholder="Monto base"
                            value={row.amount_ars}
                            onChange={(e) => changeSplitRow(idx, { amount_ars: e.target.value })}
                          />
                          {isAdmin ? (
                            <input
                              className="input num w-24 px-2 py-1.5 text-sm"
                              type="number"
                              step="0.01"
                              min="-99.99"
                              placeholder="% ajuste"
                              value={row.modifier_pct ?? ''}
                              onChange={(e) => changeSplitRow(idx, { modifier_pct: e.target.value })}
                            />
                          ) : null}
                          <button
                            type="button"
                            className="shrink-0 rounded-lg px-2 py-1 text-xs font-semibold text-rose-500 transition hover:bg-rose-50 disabled:opacity-40"
                            onClick={() => removeSplitRow(idx)}
                            disabled={splitPayments.length <= 1}
                          >
                            Quitar
                          </button>
                        </div>
                      </div>
                    );
                  })}
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={loadStoreCreditsByDoc}
                      disabled={storeCreditsLoading}
                    >
                      {storeCreditsLoading ? 'Buscando...' : 'Actualizar creditos'}
                    </button>
                    <button type="button" className="btn-secondary btn-sm" onClick={addSplitRow}>
                      Agregar tramo
                    </button>
                    <span className="text-xs text-neutral-400">
                      Creditos: <strong>{storeCredits.length}</strong>
                    </span>
                  </div>
                  <div className="space-y-0.5 rounded-lg border border-dashed border-neutral-200 px-2 py-1.5 text-xs">
                    <div>
                      Suma base tramos: <strong className="num">{money(splitTotals.current)}</strong>
                    </div>
                    <div>
                      Subtotal base: <strong className="num">{money(splitTotals.expected)}</strong>
                    </div>
                    <div className={splitTotals.diff === 0 ? 'text-emerald-700' : 'text-rose-700'}>
                      Diferencia: <strong className="num">{money(splitTotals.diff)}</strong>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3 xl:fixed xl:bottom-3 xl:left-60 xl:right-3 xl:z-20 xl:max-h-[70vh] xl:overflow-y-auto">
        <div className="space-y-2 rounded-2xl border border-neutral-200 bg-white/85 p-3 shadow-lift backdrop-blur-xl">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="flex flex-wrap items-end gap-5">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-neutral-400">Total</p>
                <p className="num font-display text-3xl font-bold leading-none tracking-tight">
                  {money(totalDue)}
                </p>
              </div>
              <div className="flex gap-4 pb-0.5 text-xs">
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-neutral-400">Subtotal</p>
                  <strong className="num text-neutral-700">{money(quote?.subtotal_ars || 0)}</strong>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-neutral-400">Promos</p>
                  <strong className="num text-brand-accent-dark">
                    {money(quote?.promotion_discount_total_ars || 0)}
                  </strong>
                </div>
                {!splitPaymentsEnabled && paymentMethod === 'cash' && Number(cashReceived || 0) > 0 ? (
                  <div>
                    <p className="text-[10px] uppercase tracking-wide text-neutral-400">Vuelto</p>
                    <strong className="num text-neutral-700">{money(cashChange)}</strong>
                  </div>
                ) : null}
              </div>
            </div>

            <div className="flex w-full items-center gap-2 sm:w-auto sm:flex-1 sm:justify-end">
              {quickMode ? (
                <button
                  type="button"
                  className="btn-secondary btn-sm shrink-0"
                  onClick={() => focusScan(true)}
                  disabled={busy}
                >
                  F2 Scanner
                </button>
              ) : null}
              <button
                type="button"
                className="btn btn-lg flex-1 sm:flex-none"
                onClick={handleConfirm}
                disabled={confirmActionDisabled}
              >
                Confirmar venta
              </button>
              {quickMode ? (
                <button
                  type="button"
                  className="btn-secondary btn-sm shrink-0"
                  onClick={quickSaveDraft}
                  disabled={busy || !items.length}
                >
                  F8 Draft
                </button>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-neutral-100 pt-2 text-xs">
            <span className="text-neutral-400">
              {quoteBusy
                ? 'Calculando cotizacion...'
                : quote
                  ? `Factura: ${quote.invoice_required ? 'si' : 'comprobante interno'}`
                  : 'Sin cotizacion activa'}
            </span>
            {quote ? (
              <button type="button" className="btn-ghost" onClick={() => setTotalsDetailOpen((prev) => !prev)}>
                {totalsDetailOpen ? 'Ocultar detalle' : 'Ver detalle'}
              </button>
            ) : null}
          </div>

          {!cashSession ? (
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
              {cashRequiredNotice}
            </p>
          ) : null}
          {splitMismatch ? (
            <p className="text-xs text-rose-700">
              La suma base de pagos mixtos no coincide con el subtotal base cotizado.
            </p>
          ) : null}
          {storeCreditSelectionMissing ? (
            <p className="text-xs text-rose-700">
              Falta seleccionar credito tienda para uno o mas tramos de pago.
            </p>
          ) : null}

          {totalsDetailOpen && quote ? (
            <div className="space-y-2 border-t border-neutral-100 pt-2 text-sm">
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 md:grid-cols-4">
                <div>
                  Subtotal promos: <strong className="num">{money(quote.subtotal_after_promotions_ars)}</strong>
                </div>
                <div>
                  Modificador ({quote.price_modifier_pct}%):{' '}
                  <strong className="num">{money(quote.modifier_amount_ars)}</strong>
                </div>
                <div>
                  Factura requerida: <strong>{quote.invoice_required ? 'Si' : 'No (comprobante interno)'}</strong>
                </div>
              </div>

              {Array.isArray(quote?.payment_breakdown) && quote.payment_breakdown.length ? (
                <div className="rounded-lg border border-dashed border-neutral-200 px-2 py-1.5">
                  <p className="text-[11px] uppercase tracking-wide text-neutral-400">Desglose de cobro</p>
                  <div className="mt-1 space-y-1">
                    {quote.payment_breakdown.map((row, idx) => (
                      <div key={`quote-pay-${idx}`} className="num text-xs">
                        <strong>{row.account_label || row.account_code || row.method}</strong> | base{' '}
                        {money(row.base_amount_ars)} | {Number(row.modifier_pct || 0)}% ({money(row.modifier_amount_ars)}) | final{' '}
                        <strong>{money(row.amount_ars)}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="space-y-2 rounded-lg border border-neutral-200 bg-neutral-50/70 p-2">
                <p className="text-[11px] uppercase tracking-wide text-neutral-400">Facturacion de la venta</p>
                <p className="text-xs">
                  Default:{' '}
                  <strong>
                    {quote?.invoice_default?.invoice_required
                      ? quote?.invoice_default?.arca_account_label || quote?.invoice_default?.arca_account_code || 'Cuenta ARCA'
                      : 'No facturar'}
                  </strong>
                </p>
                {isAdmin ? (
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    <select
                      className="input px-2 py-1.5 text-sm"
                      value={invoiceOverrideMode}
                      onChange={(e) => setInvoiceOverrideMode(e.target.value)}
                    >
                      <option value="default">Usar default</option>
                      <option value="none">No facturar</option>
                      <option value="arca">Forzar cuenta ARCA</option>
                    </select>
                    {invoiceOverrideMode === 'arca' ? (
                      <select
                        className="input px-2 py-1.5 text-sm"
                        value={invoiceOverrideArcaAccountId}
                        onChange={(e) => setInvoiceOverrideArcaAccountId(e.target.value)}
                      >
                        <option value="">Seleccionar cuenta ARCA</option>
                        {arcaAccounts.map((arca) => (
                          <option key={`override-arca-${arca.id}`} value={String(arca.id)}>
                            {arca.label || arca.code}
                          </option>
                        ))}
                      </select>
                    ) : null}
                  </div>
                ) : (
                  <p className="text-xs text-neutral-600">
                    Modo aplicado:{' '}
                    <strong>
                      {quote.invoice_required
                        ? quote.invoice_arca_account_label || quote.invoice_arca_account_code || 'Cuenta ARCA'
                        : 'No facturar'}
                    </strong>
                  </p>
                )}
              </div>
            </div>
          ) : null}

          {lastSale ? (
            <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-xs text-emerald-900">
              Venta confirmada: <strong>{lastSale.sale_number || `#${lastSale.id}`}</strong> por{' '}
              <strong className="num">{money(lastSale.total_ars)}</strong>. Estado factura:{' '}
              <strong>{lastSale?.invoice?.status || 'sin generar'}</strong>.
              {lastSale?.invoice?.arca_account_label || lastSale?.invoice?.arca_account_code ? (
                <>
                  {' '}Cuenta ARCA:{' '}
                  <strong>{lastSale?.invoice?.arca_account_label || lastSale?.invoice?.arca_account_code}</strong>.
                </>
              ) : null}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
