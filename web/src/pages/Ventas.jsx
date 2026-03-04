import { useEffect, useMemo, useState } from 'react';
import {
  getRetailVentaDetail,
  getRetailVentas,
  postRetailFacturaEmitir,
  postRetailNotaCredito,
  postRetailVentaAnular,
  postRetailVentaDevolver,
} from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { can, PERMISSION_CODES } from '../lib/permissions';

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

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoIso(days) {
  return new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);
}

export default function VentasPage() {
  const { user } = useAuth();
  const canCancel = can(user, PERMISSION_CODES.ACTION_VENTAS_ANULAR);
  const canReturn = can(user, PERMISSION_CODES.ACTION_VENTAS_DEVOLVER);
  const canOverrideWarranty = can(user, PERMISSION_CODES.ACTION_VENTAS_DEVOLVER_OVERRIDE_GARANTIA);
  const canEmitInvoice = can(user, PERMISSION_CODES.ACTION_FACTURACION_EMITIR);
  const canEmitCreditNote = can(user, PERMISSION_CODES.ACTION_FACTURACION_NOTA_CREDITO);

  const [desde, setDesde] = useState(daysAgoIso(14));
  const [hasta, setHasta] = useState(todayIso());
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [channel, setChannel] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('');

  const [rows, setRows] = useState([]);
  const [paging, setPaging] = useState({ limit: 50, offset: 0, total: 0 });
  const [selectedId, setSelectedId] = useState(null);
  const [selectedSale, setSelectedSale] = useState(null);
  const [returnQty, setReturnQty] = useState({});
  const [reason, setReason] = useState('');
  const [warrantyType, setWarrantyType] = useState('size');
  const [overrideOutOfWarranty, setOverrideOutOfWarranty] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');
  const [creditNotesResult, setCreditNotesResult] = useState(null);

  const [loadingList, setLoadingList] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [acting, setActing] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const selectedInvoice = selectedSale?.invoice || null;

  const pendingItems = useMemo(() => {
    const items = Array.isArray(selectedSale?.items) ? selectedSale.items : [];
    return items
      .map((item) => ({
        ...item,
        available_qty: Math.max(0, Number(item.quantity || 0) - Number(item.returned_qty || 0)),
      }))
      .filter((item) => item.available_qty > 0);
  }, [selectedSale]);

  const selectedWarranty = selectedSale?.warranty || null;
  const selectedWarrantyLine = warrantyType === 'breakage' ? selectedWarranty?.breakage : selectedWarranty?.size;
  const warrantyInWindow = !!selectedWarrantyLine?.active;

  async function loadList(nextOffset = 0) {
    setLoadingList(true);
    setErr('');
    try {
      const resp = await getRetailVentas({
        desde,
        hasta,
        q: q || undefined,
        status: status || undefined,
        channel: channel || undefined,
        payment_method: paymentMethod || undefined,
        limit: paging.limit || 50,
        offset: nextOffset,
      });
      const nextRows = Array.isArray(resp?.rows) ? resp.rows : [];
      setRows(nextRows);
      setPaging(resp?.paging || { limit: 50, offset: nextOffset, total: nextRows.length });

      if (nextRows.length === 0) {
        setSelectedId(null);
        setSelectedSale(null);
        return;
      }

      const stillSelected = selectedId && nextRows.some((row) => Number(row.id) === Number(selectedId));
      const targetId = stillSelected ? selectedId : nextRows[0].id;
      await loadDetail(targetId);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoadingList(false);
    }
  }

  async function loadDetail(ventaId) {
    if (!ventaId) return;
    setLoadingDetail(true);
    setErr('');
    try {
      const row = await getRetailVentaDetail(Number(ventaId));
      setSelectedId(Number(ventaId));
      setSelectedSale(row);
      const defaults = {};
      (row?.items || []).forEach((item) => {
        defaults[item.id] = '';
      });
      setReturnQty(defaults);
      const preferredType = row?.warranty?.size?.active ? 'size' : row?.warranty?.breakage?.active ? 'breakage' : 'size';
      setWarrantyType(preferredType);
      setOverrideOutOfWarranty(false);
      setOverrideReason('');
      setCreditNotesResult(null);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoadingDetail(false);
    }
  }

  useEffect(() => {
    loadList(0);
  }, []);

  async function runAction(fn, successMessage) {
    setActing(true);
    setErr('');
    setMsg('');
    try {
      await fn();
      setMsg(successMessage);
      if (selectedId) {
        await loadDetail(selectedId);
      }
      await loadList(paging.offset || 0);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setActing(false);
    }
  }

  function buildPartialReturnItems() {
    const out = [];
    pendingItems.forEach((item) => {
      const raw = String(returnQty[item.id] || '').trim();
      if (!raw) return;
      const qty = Number(raw);
      if (!Number.isFinite(qty) || qty <= 0) {
        throw new Error(`Cantidad invalida para item ${item.id}`);
      }
      if (qty > item.available_qty) {
        throw new Error(`La devolucion supera lo disponible en item ${item.id}`);
      }
      out.push({ sale_item_id: item.id, quantity: Math.floor(qty) });
    });
    return out;
  }

  function assertWarrantyRules() {
    if (warrantyInWindow) return;
    if (!overrideOutOfWarranty) {
      throw new Error('Ticket fuera de garantia para el tipo seleccionado');
    }
    if (!canOverrideWarranty) {
      throw new Error('No tienes permiso para override de garantia');
    }
    if (!String(overrideReason || '').trim()) {
      throw new Error('Debes indicar motivo de override de garantia');
    }
  }

  function buildWarrantyPayload() {
    return {
      warranty_type: warrantyType,
      override_out_of_warranty: !warrantyInWindow && overrideOutOfWarranty ? true : undefined,
      override_reason: !warrantyInWindow && overrideOutOfWarranty ? overrideReason : undefined,
    };
  }

  async function issueInvoice() {
    if (!selectedId) return;
    await runAction(
      async () => {
        const sale = await postRetailFacturaEmitir(selectedId);
        setSelectedSale(sale || null);
      },
      'Facturacion ejecutada/reintentada',
    );
  }

  async function cancelSale() {
    if (!selectedId) return;
    await runAction(
      async () => {
        const sale = await postRetailVentaAnular(selectedId, {
          reason: reason || 'Anulacion desde pantalla de ventas',
        });
        setSelectedSale(sale || null);
      },
      'Venta anulada',
    );
  }

  async function returnFullSale() {
    if (!selectedId) return;
    await runAction(
      async () => {
        assertWarrantyRules();
        const resp = await postRetailVentaDevolver(selectedId, {
          reason: reason || 'Devolucion total desde pantalla de ventas',
          ...buildWarrantyPayload(),
        });
        setCreditNotesResult(resp);
      },
      'Devolucion total registrada',
    );
  }

  async function returnPartialSale() {
    if (!selectedId) return;
    await runAction(
      async () => {
        assertWarrantyRules();
        const items = buildPartialReturnItems();
        if (!items.length) {
          throw new Error('Carga cantidades a devolver en al menos un item');
        }
        const resp = await postRetailVentaDevolver(selectedId, {
          reason: reason || 'Devolucion parcial desde pantalla de ventas',
          ...buildWarrantyPayload(),
          items,
        });
        setCreditNotesResult(resp);
      },
      'Devolucion parcial registrada',
    );
  }

  async function issueCreditNote() {
    if (!selectedId) return;
    await runAction(
      async () => {
        const resp = await postRetailNotaCredito(selectedId, {});
        setCreditNotesResult(resp);
      },
      'Nota de credito procesada/reintentada',
    );
  }

  const canReturnNow =
    canReturn &&
    selectedSale &&
    selectedSale.status !== 'cancelled' &&
    pendingItems.length > 0;
  const needsOverride = canReturnNow && !warrantyInWindow;
  const overrideReady = !needsOverride || (overrideOutOfWarranty && canOverrideWarranty && String(overrideReason || '').trim());
  const returnBlocked = acting || loadingDetail || !overrideReady;

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">Ventas, devoluciones y facturacion</h1>
        <p className="text-sm text-gray-600">
          Gestion operativa de ventas con anulacion, devolucion total/parcial y circuito ARCA.
        </p>
      </div>

      <div className="card grid grid-cols-1 md:grid-cols-7 gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Desde</label>
          <input type="date" className="input" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Hasta</label>
          <input type="date" className="input" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Estado</label>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Todos</option>
            <option value="confirmed">Confirmada</option>
            <option value="partial_return">Parcialmente devuelta</option>
            <option value="returned">Devuelta</option>
            <option value="cancelled">Anulada</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Canal</label>
          <select className="input" value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="">Todos</option>
            <option value="local">Local</option>
            <option value="online">Online</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Medio pago</label>
          <select className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
            <option value="">Todos</option>
            <option value="cash">Efectivo</option>
            <option value="debit">Debito</option>
            <option value="transfer">Transferencia</option>
            <option value="credit">Credito</option>
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="block text-xs text-gray-500 mb-1">Buscar</label>
          <input
            className="input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Nro venta, orden online o cliente"
          />
        </div>
        <button type="button" className="btn" onClick={() => loadList(0)} disabled={loadingList}>
          Buscar ventas
        </button>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold">Ventas</h2>
          <p className="text-xs text-gray-500">
            {paging.total || 0} resultados
          </p>
        </div>
        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="py-2 pr-3">Nro</th>
                <th className="py-2 pr-3">Fecha</th>
                <th className="py-2 pr-3">Canal</th>
                <th className="py-2 pr-3">Estado</th>
                <th className="py-2 pr-3">Cobro</th>
                <th className="py-2 pr-3">Factura</th>
                <th className="py-2 pr-3">Total</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.id}
                  className={`border-b last:border-b-0 cursor-pointer ${
                    Number(row.id) === Number(selectedId) ? 'bg-gray-50' : ''
                  }`}
                  onClick={() => loadDetail(row.id)}
                >
                  <td className="py-2 pr-3">
                    {row.sale_number || `#${row.id}`}
                    <div className="text-xs text-gray-500">{row.customer_name || '-'}</div>
                  </td>
                  <td className="py-2 pr-3">{String(row.created_at || '').slice(0, 16).replace('T', ' ')}</td>
                  <td className="py-2 pr-3">{row.channel}</td>
                  <td className="py-2 pr-3">{row.status}</td>
                  <td className="py-2 pr-3">
                    {row.payment_method}
                    <div className="text-xs text-gray-500">{row.payment_account_label || row.payment_account_code}</div>
                  </td>
                  <td className="py-2 pr-3">{row.invoice_status || '-'}</td>
                  <td className="py-2 pr-3">{money(row.total_ars)}</td>
                </tr>
              ))}
              {!rows.length && !loadingList ? (
                <tr>
                  <td className="py-3 text-gray-500" colSpan={7}>
                    Sin ventas para el filtro actual.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card space-y-3">
        <h2 className="text-lg font-semibold">Detalle venta</h2>
        {!selectedSale ? (
          <p className="text-sm text-gray-500">Selecciona una venta para ver detalle y acciones.</p>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-sm">
              <div>
                Venta: <strong>{selectedSale.sale_number || `#${selectedSale.id}`}</strong>
              </div>
              <div>
                Estado: <strong>{selectedSale.status}</strong>
              </div>
              <div>
                Canal: <strong>{selectedSale.channel}</strong>
              </div>
              <div>
                Total: <strong>{money(selectedSale.total_ars)}</strong>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
              <div>
                Estado de factura: <strong>{selectedInvoice?.status || 'sin registro'}</strong>
              </div>
              <div>
                CAE: <strong>{selectedInvoice?.cae || '-'}</strong>
              </div>
              <div>
                Cbte nro: <strong>{selectedInvoice?.cbte_nro || '-'}</strong>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
              <div>
                Cambio de talle: <strong>{selectedWarranty?.size?.active ? 'Vigente' : 'Vencida'}</strong>
                <div className="text-xs text-gray-500">
                  Vence {selectedWarranty?.size?.expires_on || '-'} ({selectedWarranty?.size?.days_left ?? 0} dias)
                </div>
              </div>
              <div>
                Roturas: <strong>{selectedWarranty?.breakage?.active ? 'Vigente' : 'Vencida'}</strong>
                <div className="text-xs text-gray-500">
                  Vence {selectedWarranty?.breakage?.expires_on || '-'} ({selectedWarranty?.breakage?.days_left ?? 0} dias)
                </div>
              </div>
              <div>
                Tipo para devolucion
                <select
                  className="input mt-1"
                  value={warrantyType}
                  onChange={(e) => setWarrantyType(e.target.value)}
                  disabled={acting || loadingDetail}
                >
                  <option value="size">Cambio de talle</option>
                  <option value="breakage">Roturas</option>
                </select>
              </div>
            </div>

            {needsOverride ? (
              <div className="rounded border border-amber-300 bg-amber-50 p-2 text-sm space-y-2">
                <p>
                  La venta esta fuera de garantia para el tipo seleccionado.
                  {canOverrideWarranty ? ' Puedes continuar con override.' : ' No tienes permiso de override.'}
                </p>
                {canOverrideWarranty ? (
                  <>
                    <label className="inline-flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={overrideOutOfWarranty}
                        onChange={(e) => setOverrideOutOfWarranty(e.target.checked)}
                        disabled={acting || loadingDetail}
                      />
                      Aplicar override de garantia
                    </label>
                    {overrideOutOfWarranty ? (
                      <input
                        className="input"
                        value={overrideReason}
                        onChange={(e) => setOverrideReason(e.target.value)}
                        placeholder="Motivo de override (obligatorio)"
                      />
                    ) : null}
                  </>
                ) : null}
              </div>
            ) : null}

            <div className="overflow-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left border-b">
                    <th className="py-2 pr-3">Producto</th>
                    <th className="py-2 pr-3">SKU</th>
                    <th className="py-2 pr-3">Vendidas</th>
                    <th className="py-2 pr-3">Devueltas</th>
                    <th className="py-2 pr-3">Disponibles</th>
                    {canReturn ? <th className="py-2 pr-3">Devolver</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {(selectedSale.items || []).map((item) => {
                    const available = Math.max(0, Number(item.quantity || 0) - Number(item.returned_qty || 0));
                    return (
                      <tr key={item.id} className="border-b last:border-b-0">
                        <td className="py-2 pr-3">
                          {item.producto}
                          <div className="text-xs text-gray-500">{item.option_signature}</div>
                        </td>
                        <td className="py-2 pr-3">{item.sku}</td>
                        <td className="py-2 pr-3">{item.quantity}</td>
                        <td className="py-2 pr-3">{item.returned_qty}</td>
                        <td className="py-2 pr-3">{available}</td>
                        {canReturn ? (
                          <td className="py-2 pr-3">
                            <input
                              className="input w-24"
                              type="number"
                              min="0"
                              max={available}
                              value={returnQty[item.id] || ''}
                              onChange={(e) => setReturnQty((prev) => ({ ...prev, [item.id]: e.target.value }))}
                              disabled={available <= 0 || acting}
                            />
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <input
              className="input"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Motivo operativo (anulacion/devolucion)"
            />

            <div className="flex flex-wrap gap-2">
              {canEmitInvoice ? (
                <button
                  type="button"
                  className="btn"
                  onClick={issueInvoice}
                  disabled={acting || loadingDetail}
                >
                  Emitir / reintentar factura
                </button>
              ) : null}

              {canCancel ? (
                <button
                  type="button"
                  className="px-3 py-2 rounded border border-red-300 text-red-700"
                  onClick={cancelSale}
                  disabled={acting || loadingDetail || selectedSale.status === 'cancelled'}
                >
                  Anular venta
                </button>
              ) : null}

              {canReturnNow ? (
                <button
                  type="button"
                  className="px-3 py-2 rounded border"
                  onClick={returnPartialSale}
                  disabled={returnBlocked}
                >
                  Devolucion parcial
                </button>
              ) : null}

              {canReturnNow ? (
                <button
                  type="button"
                  className="px-3 py-2 rounded border"
                  onClick={returnFullSale}
                  disabled={returnBlocked}
                >
                  Devolucion total
                </button>
              ) : null}

              {canEmitCreditNote ? (
                <button
                  type="button"
                  className="px-3 py-2 rounded border"
                  onClick={issueCreditNote}
                  disabled={acting || loadingDetail}
                >
                  Emitir nota de credito
                </button>
              ) : null}
            </div>
          </>
        )}
      </div>

      {creditNotesResult ? (
        <div className="card">
          <h2 className="text-lg font-semibold mb-2">Resultado devolucion / nota de credito</h2>
          <pre className="text-xs bg-gray-50 border rounded p-2 overflow-auto max-h-72">
            {JSON.stringify(creditNotesResult, null, 2)}
          </pre>
        </div>
      ) : null}

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {msg ? <p className="text-sm text-green-700">{msg}</p> : null}
    </div>
  );
}
