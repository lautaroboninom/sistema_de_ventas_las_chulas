import { useEffect, useMemo, useRef, useState } from 'react';
import {
  getRetailCajaActual,
  getRetailCajaCuentas,
  getRetailGarantiaTicket,
  getRetailVarianteByScan,
  postRetailCajaApertura,
  postRetailCajaCierre,
  postRetailVentaConfirmar,
  postRetailVentaCotizar,
} from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { can, PERMISSION_CODES } from '../lib/permissions';

const PAYMENT_OPTIONS = [
  { value: 'cash', label: 'Efectivo (-10%)' },
  { value: 'debit', label: 'Débito (lista)' },
  { value: 'transfer', label: 'Transferencia (lista)' },
  { value: 'credit', label: 'Crédito (+10%)' },
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
  return error?.message || 'Ocurrió un error inesperado';
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
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [paymentAccountCode, setPaymentAccountCode] = useState('cash');
  const [customerName, setCustomerName] = useState('');
  const [customerDoc, setCustomerDoc] = useState('');
  const [notes, setNotes] = useState('');
  const [priceOverrideReason, setPriceOverrideReason] = useState('');
  const [items, setItems] = useState([]);
  const [quote, setQuote] = useState(null);
  const [lastSale, setLastSale] = useState(null);
  const [ticketLookup, setTicketLookup] = useState(null);
  const [cashSession, setCashSession] = useState(null);
  const [accounts, setAccounts] = useState(FALLBACK_ACCOUNTS);
  const [openingCash, setOpeningCash] = useState('0');
  const [closingCash, setClosingCash] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

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

  const anyOverride = useMemo(
    () => canOverridePrice && items.some((it) => String(it.unit_price_override_ars || '').trim() !== ''),
    [canOverridePrice, items]
  );

  const quoteByVariant = useMemo(() => {
    const map = new Map();
    const lines = Array.isArray(quote?.items) ? quote.items : [];
    lines.forEach((line) => map.set(Number(line.variant_id), line));
    return map;
  }, [quote]);

  function focusScan(force = false) {
    setTimeout(() => {
      const activeTag = document?.activeElement?.tagName;
      const hasOtherFormFocus = ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(activeTag || '');
      if (!force && hasOtherFormFocus) return;
      scanRef.current?.focus();
    }, 0);
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

  useEffect(() => {
    loadCashSession();
    loadAccounts();
  }, []);

  useEffect(() => {
    busyRef.current = busy;
  }, [busy]);

  useEffect(() => {
    submitScanRef.current = submitScanCode;
  });

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
        const canSubmit = scanDetectedRef.current && code.length >= SCAN_MIN_LEN && !busyRef.current;
        clearCapture();
        if (!canSubmit) return;
        setScan('');
        void submitScanRef.current?.(code, { variantOnly: true });
      }, SCAN_ENTER_GAP_MS);
    }

    function onWindowKeyDown(event) {
      if (event.defaultPrevented || event.isComposing) return;
      const activeEl = document?.activeElement;
      const hasEditableFocus = isTextEditableTarget(activeEl) || Boolean(activeEl?.isContentEditable);
      if (hasEditableFocus) return;

      if (event.ctrlKey || event.altKey || event.metaKey) {
        event.preventDefault();
        clearCapture();
        return;
      }

      const now = Date.now();
      const key = String(event.key || '');

      if (key === 'Enter') {
        const code = String(scanBufferRef.current || '').trim();
        const age = scanLastKeyAtRef.current ? now - scanLastKeyAtRef.current : Number.MAX_SAFE_INTEGER;
        const looksLikeScan = scanDetectedRef.current && age <= SCAN_ENTER_GAP_MS && code.length >= SCAN_MIN_LEN;
        clearCapture();
        if (!looksLikeScan || busyRef.current) return;
        event.preventDefault();
        setScan('');
        void submitScanRef.current?.(code, { variantOnly: true });
        return;
      }

      if (key.length !== 1) return;

      if (!scanLastKeyAtRef.current || now - scanLastKeyAtRef.current > SCAN_RESET_GAP_MS) {
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
  }, []);

  useEffect(() => {
    const selectedExists = filteredAccounts.some((row) => row.code === paymentAccountCode);
    if (!selectedExists) {
      setPaymentAccountCode(defaultAccountCode(paymentMethod, filteredAccounts));
    }
  }, [paymentMethod, filteredAccounts, paymentAccountCode]);

  function upsertItem(row) {
    setItems((prev) => {
      const idx = prev.findIndex((it) => Number(it.variant_id) === Number(row.id));
      if (idx < 0) {
        return [
          ...prev,
          {
            variant_id: row.id,
            sku: row.sku,
            barcode_internal: row.barcode_internal,
            producto: row.producto,
            firma: row.option_signature,
            precio_local: Number(row.price_store_ars || 0),
            quantity: 1,
            unit_price_override_ars: '',
          },
        ];
      }
      const next = [...prev];
      next[idx] = { ...next[idx], quantity: Number(next[idx].quantity || 0) + 1 };
      return next;
    });
  }

  async function submitScanCode(rawCode, options = {}) {
    const code = String(rawCode || '').trim();
    if (!code) return;
    if (busyRef.current) return;
    const restoreFocus = Boolean(options.restoreFocus);
    const variantOnly = Boolean(options.variantOnly);
    busyRef.current = true;
    setErr('');
    setBusy(true);
    try {
      const row = await getRetailVarianteByScan(code);
      upsertItem(row);
      setScan('');
      setQuote(null);
      setTicketLookup(null);
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
        variant_id: it.variant_id,
        quantity: Number(it.quantity || 1),
      };
      const rawOverride = String(it.unit_price_override_ars || '').trim();
      if (canOverridePrice && rawOverride !== '') {
        const n = Number(rawOverride);
        if (!Number.isFinite(n) || n < 0) {
          throw new Error(`Override inválido en variante ${it.sku || it.variant_id}`);
        }
        line.unit_price_override_ars = n;
      }
      return line;
    });
  }

  async function handleQuote() {
    if (!items.length) return;
    setErr('');
    setBusy(true);
    try {
      const resp = await postRetailVentaCotizar({
        channel: 'local',
        payment_method: paymentMethod,
        payment_account_code: paymentAccountCode,
        items: buildItemsPayload(),
      });
      setQuote(resp);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
      focusScan(true);
    }
  }

  async function handleConfirm() {
    if (!items.length) return;
    if (anyOverride && !String(priceOverrideReason || '').trim()) {
      setErr('Debes indicar motivo de override de precio');
      return;
    }
    setErr('');
    setBusy(true);
    try {
      const sale = await postRetailVentaConfirmar({
        channel: 'local',
        payment_method: paymentMethod,
        payment_account_code: paymentAccountCode,
        customer_name: customerName || undefined,
        customer_doc: customerDoc || undefined,
        notes: notes || undefined,
        price_override_reason: anyOverride ? priceOverrideReason.trim() : undefined,
        auto_emit_invoice: true,
        items: buildItemsPayload(),
      });
      setLastSale(sale);
      setItems([]);
      setQuote(null);
      setTicketLookup(null);
      setPriceOverrideReason('');
      setCustomerName('');
      setCustomerDoc('');
      setNotes('');
      await loadCashSession();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
      focusScan(true);
    }
  }

  async function openCashSession() {
    setErr('');
    setBusy(true);
    try {
      await postRetailCajaApertura({ opening_amount_cash_ars: Number(openingCash || 0) });
      await loadCashSession();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
      focusScan(true);
    }
  }

  async function closeCashSession() {
    setErr('');
    setBusy(true);
    try {
      await postRetailCajaCierre({
        closing_counted_total_ars: closingCash === '' ? undefined : Number(closingCash),
      });
      setClosingCash('');
      await loadCashSession();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setBusy(false);
      focusScan(true);
    }
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">POS mostrador</h1>
        <p className="text-sm text-gray-600">
          Venta rápida por escaneo, caja diaria obligatoria y reglas automáticas por medio de pago.
        </p>
      </div>

      <div className="card grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
        <div>
          <p className="text-xs text-gray-500 mb-1">Estado caja</p>
          <p className="text-sm">
            {cashSession ? (
              <strong className="text-green-700">Abierta #{cashSession.id}</strong>
            ) : (
              <strong className="text-red-700">Sin apertura</strong>
            )}
          </p>
        </div>
        {!cashSession ? (
          <>
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
          </>
        ) : (
          <>
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
              className="px-3 py-2 rounded border"
              onClick={closeCashSession}
              disabled={busy || items.length > 0}
            >
              Cerrar caja
            </button>
          </>
        )}
      </div>

      <form className="card grid grid-cols-1 md:grid-cols-4 gap-3 items-end" onSubmit={handleScanSubmit}>
        <div className="md:col-span-3">
          <label className="block text-xs text-gray-500 mb-1">Escanear barcode interno o SKU</label>
          <input
            ref={scanRef}
            className="input"
            value={scan}
            onChange={(e) => setScan(e.target.value)}
            placeholder="Ej: CHU-001-NEG-M"
          />
        </div>
        <button type="submit" className="btn" disabled={busy}>
          Agregar
        </button>
      </form>

      {ticketLookup?.sale ? (
        <div className="card space-y-2">
          <h2 className="text-lg font-semibold">Ticket escaneado</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-sm">
            <div>
              Ticket: <strong>{ticketLookup.sale.sale_number || `#${ticketLookup.sale.id}`}</strong>
            </div>
            <div>
              Fecha: <strong>{String(ticketLookup.sale.created_at || '').slice(0, 16).replace('T', ' ')}</strong>
            </div>
            <div>
              Total: <strong>{money(ticketLookup.sale.total_ars)}</strong>
            </div>
            <div>
              Estado: <strong>{ticketLookup.sale.status}</strong>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
            <div>
              Cambio de talle:{' '}
              <strong>{ticketLookup?.warranty?.size?.active ? 'Vigente' : 'Vencida'}</strong>
              <div className="text-xs text-gray-500">
                Vence {ticketLookup?.warranty?.size?.expires_on || '-'} ({ticketLookup?.warranty?.size?.days_left ?? 0} dias)
              </div>
            </div>
            <div>
              Roturas:{' '}
              <strong>{ticketLookup?.warranty?.breakage?.active ? 'Vigente' : 'Vencida'}</strong>
              <div className="text-xs text-gray-500">
                Vence {ticketLookup?.warranty?.breakage?.expires_on || '-'} ({ticketLookup?.warranty?.breakage?.days_left ?? 0} dias)
              </div>
            </div>
          </div>
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2 pr-3">Producto</th>
                  <th className="py-2 pr-3">SKU</th>
                  <th className="py-2 pr-3">Vendidas</th>
                  <th className="py-2 pr-3">Devueltas</th>
                  <th className="py-2 pr-3">Disponibles</th>
                </tr>
              </thead>
              <tbody>
                {(ticketLookup.sale.items || []).map((item) => {
                  const available = Math.max(0, Number(item.quantity || 0) - Number(item.returned_qty || 0));
                  return (
                    <tr key={item.id} className="border-b last:border-b-0">
                      <td className="py-2 pr-3">{item.producto}</td>
                      <td className="py-2 pr-3">{item.sku || '-'}</td>
                      <td className="py-2 pr-3">{item.quantity}</td>
                      <td className="py-2 pr-3">{item.returned_qty}</td>
                      <td className="py-2 pr-3">{available}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Items ({totalQty})</h2>
          <button type="button" className="px-3 py-2 rounded border" onClick={() => setItems([])}>
            Limpiar
          </button>
        </div>
        {!items.length ? (
          <p className="text-sm text-gray-500">No hay ítems en la venta.</p>
        ) : (
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2 pr-3">SKU</th>
                  <th className="py-2 pr-3">Producto</th>
                  <th className="py-2 pr-3">Precio lista</th>
                  {canOverridePrice ? <th className="py-2 pr-3">Override</th> : null}
                  <th className="py-2 pr-3">Cantidad</th>
                  <th className="py-2 pr-3">Línea</th>
                  <th className="py-2 pr-3"></th>
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
                        <div className="text-xs text-gray-500">{it.firma}</div>
                      </td>
                      <td className="py-2 pr-3">{money(it.precio_local)}</td>
                      {canOverridePrice ? (
                        <td className="py-2 pr-3">
                          <input
                            className="input w-28"
                            type="number"
                            min="0"
                            step="0.01"
                            placeholder="Base ARS"
                            value={it.unit_price_override_ars || ''}
                            onChange={(e) => changeOverride(it.variant_id, e.target.value)}
                          />
                        </td>
                      ) : null}
                      <td className="py-2 pr-3">
                        <input
                          className="input w-24"
                          type="number"
                          min="1"
                          value={it.quantity}
                          onChange={(e) => changeQty(it.variant_id, e.target.value)}
                        />
                      </td>
                      <td className="py-2 pr-3">{money(qLine?.line_total_ars || 0)}</td>
                      <td className="py-2 pr-3">
                        <button
                          type="button"
                          className="px-3 py-1.5 rounded border border-red-300 text-red-700"
                          onClick={() => removeItem(it.variant_id)}
                        >
                          Quitar
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Cobro</h2>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Medio de pago</label>
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
            <label className="block text-xs text-gray-500 mb-1">Cuenta / caja</label>
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
          <textarea
            className="input"
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notas"
          />
        </div>

        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Totales</h2>
          {quote ? (
            <div className="space-y-1 text-sm">
              <div>
                Subtotal: <strong>{money(quote.subtotal_ars)}</strong>
              </div>
              <div>
                Modificador ({quote.price_modifier_pct}%): <strong>{money(quote.modifier_amount_ars)}</strong>
              </div>
              <div>
                Total: <strong>{money(quote.total_ars)}</strong>
              </div>
              <div>
                Factura requerida: <strong>{quote.invoice_required ? 'Sí' : 'No (comprobante interno)'}</strong>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500">Calculá una cotización para revisar totales antes de confirmar.</p>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              className="px-3 py-2 rounded border"
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
          {err ? <p className="text-sm text-red-700">{err}</p> : null}
          {lastSale ? (
            <div className="rounded border border-green-300 bg-green-50 p-3 text-sm">
              Venta confirmada: <strong>{lastSale.sale_number || `#${lastSale.id}`}</strong> por{' '}
              <strong>{money(lastSale.total_ars)}</strong>. Estado factura:{' '}
              <strong>{lastSale?.invoice?.status || 'sin generar'}</strong>.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

