import { useEffect, useMemo, useState } from 'react';
import {
  getRetailGarantiasActivas,
  getRetailGarantiaTicket,
  getRetailVentaDetail,
} from '../lib/api';

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

function fmtDate(value) {
  if (!value) return '-';
  return String(value).slice(0, 10);
}

function fmtDateTime(value) {
  if (!value) return '-';
  return String(value).slice(0, 16).replace('T', ' ');
}

function warrantyStatusLabel(warrantyLine) {
  if (!warrantyLine) return '-';
  return warrantyLine.active ? 'Vigente' : 'Vencida';
}

export default function GarantiasPage() {
  const [q, setQ] = useState('');
  const [tipo, setTipo] = useState('all');
  const [rows, setRows] = useState([]);
  const [paging, setPaging] = useState({ limit: 50, offset: 0, total: 0 });
  const [selectedId, setSelectedId] = useState(null);
  const [selectedSale, setSelectedSale] = useState(null);
  const [ticketCode, setTicketCode] = useState('');

  const [loadingList, setLoadingList] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [lookupBusy, setLookupBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  async function loadDetail(saleId) {
    if (!saleId) return;
    setLoadingDetail(true);
    setErr('');
    try {
      const row = await getRetailVentaDetail(Number(saleId));
      setSelectedSale(row || null);
      setSelectedId(Number(saleId));
    } catch (error) {
      setErr(errMsg(error));
      setSelectedSale(null);
    } finally {
      setLoadingDetail(false);
    }
  }

  async function loadActivas(nextOffset = 0) {
    setLoadingList(true);
    setErr('');
    setMsg('');
    try {
      const resp = await getRetailGarantiasActivas({
        q: q || undefined,
        tipo,
        limit: paging.limit || 50,
        offset: nextOffset,
      });
      const nextRows = Array.isArray(resp?.rows) ? resp.rows : [];
      setRows(nextRows);
      setPaging(resp?.paging || { limit: 50, offset: nextOffset, total: nextRows.length });

      if (!nextRows.length) {
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

  useEffect(() => {
    loadActivas(0);
  }, []);

  async function lookupTicket(e) {
    e?.preventDefault?.();
    const code = String(ticketCode || '').trim();
    if (!code) return;
    setLookupBusy(true);
    setErr('');
    setMsg('');
    try {
      const resp = await getRetailGarantiaTicket(code);
      const sale = resp?.sale || null;
      if (!sale?.id) {
        throw new Error('Ticket sin venta asociada');
      }
      setSelectedId(Number(sale.id));
      setSelectedSale(sale);
      setMsg(`Ticket encontrado: ${sale.sale_number || `#${sale.id}`}`);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLookupBusy(false);
    }
  }

  const selectedWarranty = selectedSale?.warranty || null;
  const selectedItems = Array.isArray(selectedSale?.items) ? selectedSale.items : [];

  const pendingQty = useMemo(
    () =>
      selectedItems.reduce(
        (acc, item) => acc + Math.max(0, Number(item.quantity || 0) - Number(item.returned_qty || 0)),
        0,
      ),
    [selectedItems],
  );

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">Cambios y devoluciones vigentes</h1>
        <p className="text-sm text-gray-600">
          Consulta rapida por ticket y listado de ventas con ventana activa para cambio de talle o roturas.
        </p>
      </div>

      <div className="card grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <div className="md:col-span-2">
          <label className="block text-xs text-gray-500 mb-1">Buscar en vigentes</label>
          <input
            className="input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Nro venta, orden online o cliente"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Tipo</label>
          <select className="input" value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="all">Todos</option>
            <option value="size">Cambio de talle</option>
            <option value="breakage">Roturas</option>
          </select>
        </div>
        <button type="button" className="btn" onClick={() => loadActivas(0)} disabled={loadingList}>
          Buscar vigentes
        </button>
      </div>

      <form className="card grid grid-cols-1 md:grid-cols-4 gap-3 items-end" onSubmit={lookupTicket}>
        <div className="md:col-span-3">
          <label className="block text-xs text-gray-500 mb-1">Escanear o ingresar ticket</label>
          <input
            className="input"
            value={ticketCode}
            onChange={(e) => setTicketCode(e.target.value)}
            placeholder="Ej: VTA-20260303-000123 o numero de orden"
          />
        </div>
        <button type="submit" className="btn" disabled={lookupBusy}>
          Consultar ticket
        </button>
      </form>

      <div className="card">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold">Garantias activas</h2>
          <p className="text-xs text-gray-500">{paging.total || 0} resultados</p>
        </div>
        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="py-2 pr-3">Ticket</th>
                <th className="py-2 pr-3">Fecha</th>
                <th className="py-2 pr-3">Cliente</th>
                <th className="py-2 pr-3">Pendiente</th>
                <th className="py-2 pr-3">Cambio talle</th>
                <th className="py-2 pr-3">Roturas</th>
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
                    <div className="text-xs text-gray-500">{row.source_order_id || '-'}</div>
                  </td>
                  <td className="py-2 pr-3">{fmtDateTime(row.created_at)}</td>
                  <td className="py-2 pr-3">{row.customer_name || '-'}</td>
                  <td className="py-2 pr-3">{row.pending_return_qty || 0}</td>
                  <td className="py-2 pr-3">
                    {warrantyStatusLabel(row?.warranty?.size)}
                    <div className="text-xs text-gray-500">Vence {fmtDate(row?.warranty?.size?.expires_on)}</div>
                  </td>
                  <td className="py-2 pr-3">
                    {warrantyStatusLabel(row?.warranty?.breakage)}
                    <div className="text-xs text-gray-500">Vence {fmtDate(row?.warranty?.breakage?.expires_on)}</div>
                  </td>
                  <td className="py-2 pr-3">{money(row.total_ars)}</td>
                </tr>
              ))}
              {!rows.length && !loadingList ? (
                <tr>
                  <td className="py-3 text-gray-500" colSpan={7}>
                    No hay tickets con garantia activa para el filtro actual.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card space-y-3">
        <h2 className="text-lg font-semibold">Detalle ticket</h2>
        {!selectedSale ? (
          <p className="text-sm text-gray-500">Selecciona una venta activa o consulta un ticket para ver detalle.</p>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-sm">
              <div>
                Ticket: <strong>{selectedSale.sale_number || `#${selectedSale.id}`}</strong>
              </div>
              <div>
                Fecha: <strong>{fmtDateTime(selectedSale.created_at)}</strong>
              </div>
              <div>
                Estado venta: <strong>{selectedSale.status}</strong>
              </div>
              <div>
                Total: <strong>{money(selectedSale.total_ars)}</strong>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
              <div>
                Cambio de talle: <strong>{warrantyStatusLabel(selectedWarranty?.size)}</strong>
                <div className="text-xs text-gray-500">
                  {selectedWarranty?.size?.days_left ?? 0} dias restantes - vence {fmtDate(selectedWarranty?.size?.expires_on)}
                </div>
              </div>
              <div>
                Roturas: <strong>{warrantyStatusLabel(selectedWarranty?.breakage)}</strong>
                <div className="text-xs text-gray-500">
                  {selectedWarranty?.breakage?.days_left ?? 0} dias restantes - vence {fmtDate(selectedWarranty?.breakage?.expires_on)}
                </div>
              </div>
              <div>
                Pendiente de devolver: <strong>{pendingQty}</strong>
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
                  {selectedItems.map((item) => {
                    const available = Math.max(0, Number(item.quantity || 0) - Number(item.returned_qty || 0));
                    return (
                      <tr key={item.id} className="border-b last:border-b-0">
                        <td className="py-2 pr-3">
                          {item.producto}
                          <div className="text-xs text-gray-500">{item.option_signature}</div>
                        </td>
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
          </>
        )}
      </div>

      {loadingDetail ? <p className="text-sm text-gray-500">Cargando detalle...</p> : null}
      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {msg ? <p className="text-sm text-green-700">{msg}</p> : null}
    </div>
  );
}
