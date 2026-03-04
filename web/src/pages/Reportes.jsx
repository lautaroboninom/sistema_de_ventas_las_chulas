import { useEffect, useMemo, useState } from 'react';
import {
  getRetailReporteBajoStock,
  getRetailReporteCierreCaja,
  getRetailReporteDevoluciones,
  getRetailReporteMasVendidos,
  getRetailReporteRentabilidad,
  getRetailReporteTallesColores,
  getRetailReporteVentasPorMedio,
} from '../lib/api';

function errMsg(error) {
  return error?.message || 'Ocurrio un error inesperado';
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoIso(days) {
  return new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);
}

function emptySection() {
  return { status: 'idle', rows: [], error: '' };
}

function emptySections() {
  return {
    top: emptySection(),
    attrs: emptySection(),
    lowStock: emptySection(),
    profit: emptySection(),
    payments: emptySection(),
    cashClose: emptySection(),
    returns: emptySection(),
  };
}

const moneyFmt = new Intl.NumberFormat('es-AR', {
  style: 'currency',
  currency: 'ARS',
  maximumFractionDigits: 2,
});

const intFmt = new Intl.NumberFormat('es-AR');

function money(value) {
  const n = Number(value || 0);
  return moneyFmt.format(Number.isFinite(n) ? n : 0);
}

function intVal(value) {
  const n = Number(value || 0);
  return intFmt.format(Number.isFinite(n) ? n : 0);
}

function toNum(value) {
  const n = Number(value || 0);
  return Number.isFinite(n) ? n : 0;
}

function sectionMessage(section, emptyLabel = 'Sin datos para el rango seleccionado.') {
  if (!section) return null;
  if (section.status === 'loading') {
    return <p className="text-sm text-gray-500">Cargando reporte...</p>;
  }
  if (section.status === 'error') {
    return <p className="text-sm text-red-700">{section.error || 'No se pudo cargar este reporte.'}</p>;
  }
  if (section.status === 'empty') {
    return <p className="text-sm text-gray-500">{emptyLabel}</p>;
  }
  return null;
}

function dateTimeLabel(value) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleString('es-AR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

export default function ReportesPage() {
  const [desde, setDesde] = useState(daysAgoIso(30));
  const [hasta, setHasta] = useState(todayIso());
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');
  const [sections, setSections] = useState(emptySections());

  const topRows = sections.top.rows || [];
  const paymentRows = sections.payments.rows || [];
  const profitRows = sections.profit.rows || [];

  const paymentSummary = useMemo(() => {
    const grouped = new Map();
    paymentRows.forEach((row) => {
      const method = String(row?.payment_method || '-').toLowerCase() || '-';
      const account = row?.payment_account_label || row?.payment_account_code || '-';
      const key = `${method}::${account}`;
      const prev = grouped.get(key) || { method, account, salesCount: 0, totalArs: 0 };
      prev.salesCount += toNum(row?.sales_count);
      prev.totalArs += toNum(row?.total_ars);
      grouped.set(key, prev);
    });
    return Array.from(grouped.values()).sort((a, b) => b.totalArs - a.totalArs);
  }, [paymentRows]);

  const kpis = useMemo(() => {
    const ventasTotales = paymentRows.reduce((acc, row) => acc + toNum(row?.total_ars), 0);
    const tickets = paymentRows.reduce((acc, row) => acc + toNum(row?.sales_count), 0);
    const ticketPromedio = tickets > 0 ? ventasTotales / tickets : 0;
    const margenBruto = profitRows.reduce((acc, row) => acc + toNum(row?.margen_ars), 0);

    return {
      ventasTotales,
      tickets,
      ticketPromedio,
      margenBruto: sections.profit.status === 'error' ? null : margenBruto,
    };
  }, [paymentRows, profitRows, sections.profit.status]);

  async function loadReports() {
    if (!desde || !hasta) {
      setErr('Debes indicar desde y hasta.');
      return;
    }
    if (hasta < desde) {
      setErr('Rango invalido: "hasta" debe ser mayor o igual a "desde".');
      return;
    }

    setLoading(true);
    setErr('');
    setSections((prev) =>
      Object.fromEntries(
        Object.keys(prev).map((key) => [
          key,
          {
            status: 'loading',
            rows: [],
            error: '',
          },
        ]),
      ),
    );

    const loaders = [
      {
        key: 'top',
        request: () => getRetailReporteMasVendidos({ desde, hasta, limit: 10 }),
        mapRows: (resp) => (Array.isArray(resp?.rows) ? resp.rows : []),
      },
      {
        key: 'payments',
        request: () => getRetailReporteVentasPorMedio({ desde, hasta }),
        mapRows: (resp) => (Array.isArray(resp?.rows) ? resp.rows : []),
      },
      {
        key: 'profit',
        request: () => getRetailReporteRentabilidad({ desde, hasta }),
        mapRows: (resp) => (Array.isArray(resp?.rows) ? resp.rows : []),
      },
      {
        key: 'attrs',
        request: () => getRetailReporteTallesColores({ desde, hasta }),
        mapRows: (resp) => (Array.isArray(resp?.rows) ? resp.rows : []),
      },
      {
        key: 'lowStock',
        request: () => getRetailReporteBajoStock(),
        mapRows: (resp) => (Array.isArray(resp) ? resp : []),
      },
      {
        key: 'cashClose',
        request: () => getRetailReporteCierreCaja({ desde, hasta }),
        mapRows: (resp) => (Array.isArray(resp?.rows) ? resp.rows : []),
      },
      {
        key: 'returns',
        request: () => getRetailReporteDevoluciones({ desde, hasta }),
        mapRows: (resp) => (Array.isArray(resp?.rows) ? resp.rows : []),
      },
    ];

    try {
      const settled = await Promise.allSettled(loaders.map((item) => item.request()));
      const next = {};

      settled.forEach((result, idx) => {
        const item = loaders[idx];
        if (result.status === 'fulfilled') {
          const rows = item.mapRows(result.value);
          next[item.key] = {
            status: rows.length ? 'success' : 'empty',
            rows,
            error: '',
          };
          return;
        }

        next[item.key] = {
          status: 'error',
          rows: [],
          error: errMsg(result.reason),
        };
      });

      const hasAnySuccess = Object.values(next).some((section) => section.status === 'success' || section.status === 'empty');
      setSections(next);
      setLastUpdatedAt(new Date().toISOString());
      if (!hasAnySuccess) {
        setErr('No se pudo cargar ningun reporte.');
      }
    } catch (error) {
      setErr(errMsg(error) || 'No se pudieron cargar los reportes.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadReports();
    // Carga inicial con rango por defecto.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">Reportes retail</h1>
        <p className="text-sm text-gray-600">
          Vista ejecutiva enfocada en ventas y margen, con detalle operativo solo cuando hace falta.
        </p>
      </div>

      <div className="card grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Desde</label>
          <input type="date" className="input" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Hasta</label>
          <input type="date" className="input" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </div>
        <button type="button" className="btn" onClick={loadReports} disabled={loading}>
          {loading ? 'Cargando...' : 'Actualizar reportes'}
        </button>
        <div className="md:col-span-2 text-xs text-gray-500">
          Ultima actualizacion: <strong>{dateTimeLabel(lastUpdatedAt)}</strong>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <div className="card">
          <p className="text-xs uppercase tracking-wide text-gray-500">Ventas totales</p>
          <p className="text-2xl font-semibold mt-1">{money(kpis.ventasTotales)}</p>
        </div>
        <div className="card">
          <p className="text-xs uppercase tracking-wide text-gray-500">Tickets</p>
          <p className="text-2xl font-semibold mt-1">{intVal(kpis.tickets)}</p>
        </div>
        <div className="card">
          <p className="text-xs uppercase tracking-wide text-gray-500">Ticket promedio</p>
          <p className="text-2xl font-semibold mt-1">{money(kpis.ticketPromedio)}</p>
        </div>
        <div className="card">
          <p className="text-xs uppercase tracking-wide text-gray-500">Margen bruto</p>
          <p className="text-2xl font-semibold mt-1">
            {kpis.margenBruto == null ? '-' : money(kpis.margenBruto)}
          </p>
        </div>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Top vendidos</h2>
        {sectionMessage(sections.top)}
        {sections.top.status === 'success' ? (
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2 pr-3">Producto</th>
                  <th className="py-2 pr-3">SKU</th>
                  <th className="py-2 pr-3">Unidades</th>
                  <th className="py-2 pr-3">Total</th>
                </tr>
              </thead>
              <tbody>
                {topRows.map((row) => (
                  <tr key={`${row.variant_id}`} className="border-b last:border-b-0">
                    <td className="py-2 pr-3">
                      {row.producto}
                      <div className="text-xs text-gray-500">{row.option_signature || '-'}</div>
                    </td>
                    <td className="py-2 pr-3">{row.sku || '-'}</td>
                    <td className="py-2 pr-3">{intVal(row.unidades)}</td>
                    <td className="py-2 pr-3">{money(row.total_ars)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Ventas por medio de pago</h2>
        {sectionMessage(sections.payments)}
        {sections.payments.status === 'success' ? (
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2 pr-3">Metodo</th>
                  <th className="py-2 pr-3">Cuenta</th>
                  <th className="py-2 pr-3">Tickets</th>
                  <th className="py-2 pr-3">Total</th>
                </tr>
              </thead>
              <tbody>
                {paymentSummary.map((row) => (
                  <tr key={`${row.method}-${row.account}`} className="border-b last:border-b-0">
                    <td className="py-2 pr-3">{row.method}</td>
                    <td className="py-2 pr-3">{row.account}</td>
                    <td className="py-2 pr-3">{intVal(row.salesCount)}</td>
                    <td className="py-2 pr-3">{money(row.totalArs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-2">Rentabilidad por producto</h2>
        {sectionMessage(sections.profit)}
        {sections.profit.status === 'success' ? (
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2 pr-3">Producto</th>
                  <th className="py-2 pr-3">Ventas</th>
                  <th className="py-2 pr-3">Costo</th>
                  <th className="py-2 pr-3">Margen</th>
                </tr>
              </thead>
              <tbody>
                {profitRows.slice(0, 10).map((row) => (
                  <tr key={`${row.product_id}`} className="border-b last:border-b-0">
                    <td className="py-2 pr-3">{row.producto}</td>
                    <td className="py-2 pr-3">{money(row.ventas_ars)}</td>
                    <td className="py-2 pr-3">{money(row.costo_ars)}</td>
                    <td className="py-2 pr-3">{money(row.margen_ars)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      <details className="card">
        <summary className="cursor-pointer text-lg font-semibold">Detalle operativo secundario</summary>
        <div className="mt-3 grid grid-cols-1 xl:grid-cols-2 gap-3">
          <div className="rounded border p-3">
            <h3 className="font-semibold mb-2">Bajo stock</h3>
            {sectionMessage(sections.lowStock)}
            {sections.lowStock.status === 'success' ? (
              <div className="overflow-auto max-h-56">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-2 pr-3">Producto</th>
                      <th className="py-2 pr-3">SKU</th>
                      <th className="py-2 pr-3">Stock</th>
                      <th className="py-2 pr-3">Min</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sections.lowStock.rows.map((row) => (
                      <tr key={row.id} className="border-b last:border-b-0">
                        <td className="py-2 pr-3">
                          {row.producto || '-'}
                          <div className="text-xs text-gray-500">{row.option_signature || '-'}</div>
                        </td>
                        <td className="py-2 pr-3">{row.sku || '-'}</td>
                        <td className="py-2 pr-3">{intVal(row.stock_on_hand)}</td>
                        <td className="py-2 pr-3">{intVal(row.stock_min)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
          <div className="rounded border p-3">
            <h3 className="font-semibold mb-2">Devoluciones</h3>
            {sectionMessage(sections.returns)}
            {sections.returns.status === 'success' ? (
              <div className="overflow-auto max-h-56">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-2 pr-3">Fecha</th>
                      <th className="py-2 pr-3">Venta</th>
                      <th className="py-2 pr-3">Estado</th>
                      <th className="py-2 pr-3">Reintegro</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sections.returns.rows.map((row) => (
                      <tr key={row.return_id} className="border-b last:border-b-0">
                        <td className="py-2 pr-3">{row.day || '-'}</td>
                        <td className="py-2 pr-3">#{row.sale_id || '-'}</td>
                        <td className="py-2 pr-3">{row.status || '-'}</td>
                        <td className="py-2 pr-3">{money(row.total_refund_ars)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
          <div className="rounded border p-3">
            <h3 className="font-semibold mb-2">Cierres de caja</h3>
            {sectionMessage(sections.cashClose)}
            {sections.cashClose.status === 'success' ? (
              <div className="overflow-auto max-h-56">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-2 pr-3">Caja</th>
                      <th className="py-2 pr-3">Estado</th>
                      <th className="py-2 pr-3">Apertura</th>
                      <th className="py-2 pr-3">Cierre</th>
                      <th className="py-2 pr-3">Dif.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sections.cashClose.rows.map((row) => (
                      <tr key={row.id} className="border-b last:border-b-0">
                        <td className="py-2 pr-3">#{row.id}</td>
                        <td className="py-2 pr-3">{row.status || '-'}</td>
                        <td className="py-2 pr-3">{dateTimeLabel(row.opened_at)}</td>
                        <td className="py-2 pr-3">{dateTimeLabel(row.closed_at)}</td>
                        <td className="py-2 pr-3">{money(row.difference_total_ars)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
          <div className="rounded border p-3">
            <h3 className="font-semibold mb-2">Atributos (talles/colores)</h3>
            {sectionMessage(sections.attrs)}
            {sections.attrs.status === 'success' ? (
              <div className="overflow-auto max-h-56">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-2 pr-3">Atributo</th>
                      <th className="py-2 pr-3">Valor</th>
                      <th className="py-2 pr-3">Unidades</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sections.attrs.rows.map((row, idx) => (
                      <tr key={`${row.atributo}-${row.valor}-${idx}`} className="border-b last:border-b-0">
                        <td className="py-2 pr-3">{row.atributo || '-'}</td>
                        <td className="py-2 pr-3">{row.valor || '-'}</td>
                        <td className="py-2 pr-3">{intVal(row.unidades)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </div>
      </details>

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
    </div>
  );
}
