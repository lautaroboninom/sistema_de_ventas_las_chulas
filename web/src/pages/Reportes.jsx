import { useEffect, useMemo, useState } from 'react';
import {
  getRetailReporteAnalisisProductos,
  getRetailReporteAnalisisProveedores,
  getRetailReporteBajoStock,
  getRetailReporteCierreCaja,
  getRetailReporteDevoluciones,
  getRetailReporteResumenComercial,
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

function emptyRowsSection() {
  return { status: 'idle', rows: [], error: '' };
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

function SortButton({ active, dir, onClick, children }) {
  return (
    <button type="button" className="inline-flex items-center gap-1 font-semibold hover:text-[#d9584b]" onClick={onClick}>
      <span>{children}</span>
      <span className="text-[10px] text-gray-400">{active ? (dir === 'asc' ? '▲' : '▼') : '↕'}</span>
    </button>
  );
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

function normalizeLabel(label) {
  const map = {
    buen_margen_poca_venta: 'Buen margen / baja venta',
    mucha_venta_margen_bajo: 'Alta venta / margen bajo',
    mas_ganancia: 'Mas ganancia',
    rotador: 'Rotador',
    conviene: 'Conviene',
  };
  return map[label] || label;
}

function badgeClass(label) {
  if (label === 'buen_margen_poca_venta') return 'bg-amber-100 text-amber-800 border-amber-200';
  if (label === 'mucha_venta_margen_bajo') return 'bg-blue-100 text-blue-800 border-blue-200';
  if (label === 'mas_ganancia') return 'bg-emerald-100 text-emerald-800 border-emerald-200';
  if (label === 'rotador') return 'bg-violet-100 text-violet-800 border-violet-200';
  if (label === 'conviene') return 'bg-rose-100 text-rose-800 border-rose-200';
  return 'bg-gray-100 text-gray-700 border-gray-200';
}

export default function ReportesPage() {
  const [desde, setDesde] = useState(daysAgoIso(30));
  const [hasta, setHasta] = useState(todayIso());
  const [viewMode, setViewMode] = useState('producto');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');

  const [summarySection, setSummarySection] = useState({ status: 'idle', summary: null, error: '' });
  const [productSection, setProductSection] = useState(emptyRowsSection());
  const [supplierSection, setSupplierSection] = useState(emptyRowsSection());
  const [lowStockSection, setLowStockSection] = useState(emptyRowsSection());
  const [cashCloseSection, setCashCloseSection] = useState(emptyRowsSection());
  const [returnsSection, setReturnsSection] = useState(emptyRowsSection());

  const [productSort, setProductSort] = useState({ key: 'margen_ars', dir: 'desc' });
  const [supplierSort, setSupplierSort] = useState({ key: 'ganancia_potencial_ars', dir: 'desc' });

  const summary = summarySection.summary || {};

  const kpis = useMemo(() => {
    const ventasBrutas = toNum(summary?.ventas_brutas_ars);
    const descuentos = toNum(summary?.descuentos_ars);
    const ventasNetas = toNum(summary?.ventas_netas_ars);
    const tickets = toNum(summary?.tickets);
    const margenBruto = toNum(summary?.margen_bruto_ars);
    const unidades = toNum(summary?.unidades);
    const ticketPromedio = tickets > 0 ? ventasNetas / tickets : toNum(summary?.ticket_promedio_ars);

    return {
      ventasBrutas,
      descuentos,
      ventasNetas,
      margenBruto,
      tickets,
      ticketPromedio,
      unidades,
    };
  }, [summary]);

  const sortedProductRows = useMemo(() => {
    const rows = Array.isArray(productSection.rows) ? [...productSection.rows] : [];
    const { key, dir } = productSort;
    rows.sort((a, b) => {
      const av = a?.[key];
      const bv = b?.[key];
      const an = Number(av);
      const bn = Number(bv);
      let cmp;
      if (Number.isFinite(an) && Number.isFinite(bn)) {
        cmp = an - bn;
      } else {
        cmp = String(av || '').localeCompare(String(bv || ''), 'es', { sensitivity: 'base' });
      }
      return dir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [productSection.rows, productSort]);

  const sortedSupplierRows = useMemo(() => {
    const rows = Array.isArray(supplierSection.rows) ? [...supplierSection.rows] : [];
    const { key, dir } = supplierSort;
    rows.sort((a, b) => {
      const av = a?.[key];
      const bv = b?.[key];
      const an = Number(av);
      const bn = Number(bv);
      let cmp;
      if (Number.isFinite(an) && Number.isFinite(bn)) {
        cmp = an - bn;
      } else {
        cmp = String(av || '').localeCompare(String(bv || ''), 'es', { sensitivity: 'base' });
      }
      return dir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [supplierSection.rows, supplierSort]);

  function toggleProductSort(key, defaultDir = 'desc') {
    setProductSort((prev) => {
      if (prev.key !== key) return { key, dir: defaultDir };
      return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' };
    });
  }

  function toggleSupplierSort(key, defaultDir = 'desc') {
    setSupplierSort((prev) => {
      if (prev.key !== key) return { key, dir: defaultDir };
      return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' };
    });
  }

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
    setSummarySection({ status: 'loading', summary: null, error: '' });
    setProductSection({ status: 'loading', rows: [], error: '' });
    setSupplierSection({ status: 'loading', rows: [], error: '' });
    setLowStockSection({ status: 'loading', rows: [], error: '' });
    setCashCloseSection({ status: 'loading', rows: [], error: '' });
    setReturnsSection({ status: 'loading', rows: [], error: '' });

    const loaders = [
      { key: 'summary', request: () => getRetailReporteResumenComercial({ desde, hasta }) },
      { key: 'products', request: () => getRetailReporteAnalisisProductos({ desde, hasta }) },
      { key: 'suppliers', request: () => getRetailReporteAnalisisProveedores({ desde, hasta }) },
      { key: 'lowStock', request: () => getRetailReporteBajoStock() },
      { key: 'cashClose', request: () => getRetailReporteCierreCaja({ desde, hasta }) },
      { key: 'returns', request: () => getRetailReporteDevoluciones({ desde, hasta }) },
    ];

    try {
      const settled = await Promise.allSettled(loaders.map((item) => item.request()));

      settled.forEach((result, idx) => {
        const key = loaders[idx].key;
        if (result.status === 'rejected') {
          const msg = errMsg(result.reason);
          if (key === 'summary') setSummarySection({ status: 'error', summary: null, error: msg });
          if (key === 'products') setProductSection({ status: 'error', rows: [], error: msg });
          if (key === 'suppliers') setSupplierSection({ status: 'error', rows: [], error: msg });
          if (key === 'lowStock') setLowStockSection({ status: 'error', rows: [], error: msg });
          if (key === 'cashClose') setCashCloseSection({ status: 'error', rows: [], error: msg });
          if (key === 'returns') setReturnsSection({ status: 'error', rows: [], error: msg });
          return;
        }

        const data = result.value;
        if (key === 'summary') {
          const summaryData = data?.summary || null;
          setSummarySection({ status: summaryData ? 'success' : 'empty', summary: summaryData, error: '' });
        }
        if (key === 'products') {
          const rows = Array.isArray(data?.rows) ? data.rows : [];
          setProductSection({ status: rows.length ? 'success' : 'empty', rows, error: '' });
        }
        if (key === 'suppliers') {
          const rows = Array.isArray(data?.rows) ? data.rows : [];
          setSupplierSection({ status: rows.length ? 'success' : 'empty', rows, error: '' });
        }
        if (key === 'lowStock') {
          const rows = Array.isArray(data) ? data : [];
          setLowStockSection({ status: rows.length ? 'success' : 'empty', rows, error: '' });
        }
        if (key === 'cashClose') {
          const rows = Array.isArray(data?.rows) ? data.rows : [];
          setCashCloseSection({ status: rows.length ? 'success' : 'empty', rows, error: '' });
        }
        if (key === 'returns') {
          const rows = Array.isArray(data?.rows) ? data.rows : [];
          setReturnsSection({ status: rows.length ? 'success' : 'empty', rows, error: '' });
        }
      });

      setLastUpdatedAt(new Date().toISOString());
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
          Vista ejecutiva para decidir rapido por producto y proveedor, sin perder detalle operativo.
        </p>
      </div>

      <div className="card grid grid-cols-1 md:grid-cols-6 gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Desde</label>
          <input type="date" className="input" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Hasta</label>
          <input type="date" className="input" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </div>
        <button type="button" className="btn" onClick={loadReports} disabled={loading}>
          {loading ? 'Cargando...' : 'Actualizar'}
        </button>
        <div className="md:col-span-3 text-xs text-gray-500">
          Ultima actualizacion: <strong>{dateTimeLabel(lastUpdatedAt)}</strong>
        </div>
      </div>

      <div className="space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="card">
            <p className="text-xs uppercase tracking-wide text-gray-500">Ventas brutas</p>
            <p className="text-xl font-semibold mt-1">{money(kpis.ventasBrutas)}</p>
          </div>
          <div className="card">
            <p className="text-xs uppercase tracking-wide text-gray-500">Margen bruto</p>
            <p className="text-xl font-semibold mt-1">{money(kpis.margenBruto)}</p>
          </div>
          <div className="card">
            <p className="text-xs uppercase tracking-wide text-gray-500">Ticket promedio</p>
            <p className="text-xl font-semibold mt-1">{money(kpis.ticketPromedio)}</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="card">
            <p className="text-xs uppercase tracking-wide text-gray-500">Descuentos</p>
            <p className="text-xl font-semibold mt-1">{money(kpis.descuentos)}</p>
          </div>
          <div className="card">
            <p className="text-xs uppercase tracking-wide text-gray-500">Ventas netas</p>
            <p className="text-xl font-semibold mt-1">{money(kpis.ventasNetas)}</p>
          </div>
          <div className="card">
            <p className="text-xs uppercase tracking-wide text-gray-500">Tickets</p>
            <p className="text-xl font-semibold mt-1">{intVal(kpis.tickets)}</p>
          </div>
        </div>
      </div>

      <div className="card space-y-3">
        <div className="flex flex-wrap gap-2 items-center justify-between">
          <h2 className="text-lg font-semibold">Analisis principal</h2>
          <div className="inline-flex rounded border border-neutral-200 p-1 bg-neutral-50">
            <button
              type="button"
              onClick={() => setViewMode('producto')}
              className={`px-3 py-1.5 rounded text-sm font-semibold ${viewMode === 'producto' ? 'bg-white shadow text-[#d9584b]' : 'text-gray-600'}`}
            >
              Por producto
            </button>
            <button
              type="button"
              onClick={() => setViewMode('proveedor')}
              className={`px-3 py-1.5 rounded text-sm font-semibold ${viewMode === 'proveedor' ? 'bg-white shadow text-[#d9584b]' : 'text-gray-600'}`}
            >
              Por proveedor
            </button>
          </div>
        </div>

        {viewMode === 'producto' ? (
          <>
            {sectionMessage(productSection)}
            {productSection.status === 'success' ? (
              <div className="overflow-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-2 pr-3">Producto</th>
                      <th className="py-2 pr-3">SKU</th>
                      <th className="py-2 pr-3"><SortButton active={productSort.key === 'unidades'} dir={productSort.dir} onClick={() => toggleProductSort('unidades')}>Unidades</SortButton></th>
                      <th className="py-2 pr-3"><SortButton active={productSort.key === 'ventas_netas_ars'} dir={productSort.dir} onClick={() => toggleProductSort('ventas_netas_ars')}>Ventas netas</SortButton></th>
                      <th className="py-2 pr-3"><SortButton active={productSort.key === 'costo_ars'} dir={productSort.dir} onClick={() => toggleProductSort('costo_ars')}>Costo</SortButton></th>
                      <th className="py-2 pr-3"><SortButton active={productSort.key === 'margen_ars'} dir={productSort.dir} onClick={() => toggleProductSort('margen_ars')}>Margen</SortButton></th>
                      <th className="py-2 pr-3"><SortButton active={productSort.key === 'margen_pct'} dir={productSort.dir} onClick={() => toggleProductSort('margen_pct')}>Margen %</SortButton></th>
                      <th className="py-2 pr-3"><SortButton active={productSort.key === 'rotacion_idx'} dir={productSort.dir} onClick={() => toggleProductSort('rotacion_idx')}>Rotacion</SortButton></th>
                      <th className="py-2 pr-3">Insights</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedProductRows.map((row) => (
                      <tr key={`${row.variant_id}`} className="border-b last:border-b-0 align-top">
                        <td className="py-2 pr-3">
                          {row.producto}
                          <div className="text-xs text-gray-500">{row.option_signature || '-'}</div>
                        </td>
                        <td className="py-2 pr-3">{row.sku || '-'}</td>
                        <td className="py-2 pr-3">{intVal(row.unidades)}</td>
                        <td className="py-2 pr-3">{money(row.ventas_netas_ars)}</td>
                        <td className="py-2 pr-3">{money(row.costo_ars)}</td>
                        <td className="py-2 pr-3">{money(row.margen_ars)}</td>
                        <td className={`py-2 pr-3 ${toNum(row.margen_pct) < 0 ? 'text-red-700 font-semibold' : ''}`}>
                          {row.margen_pct == null ? '-' : `${toNum(row.margen_pct).toFixed(2)}%`}
                        </td>
                        <td className="py-2 pr-3">{row.rotacion_idx == null ? '-' : toNum(row.rotacion_idx).toFixed(3)}</td>
                        <td className="py-2 pr-3">
                          <div className="flex flex-wrap gap-1 max-w-[280px]">
                            {(row.labels || []).length ? (
                              (row.labels || []).map((label) => (
                                <span key={`${row.variant_id}-${label}`} className={`inline-flex rounded border px-2 py-0.5 text-[11px] font-semibold ${badgeClass(label)}`}>
                                  {normalizeLabel(label)}
                                </span>
                              ))
                            ) : (
                              <span className="text-xs text-gray-400">-</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        ) : (
          <>
            {sectionMessage(supplierSection)}
            {supplierSection.status === 'success' ? (
              <div className="overflow-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-2 pr-3">Proveedor</th>
                      <th className="py-2 pr-3"><SortButton active={supplierSort.key === 'ganancia_potencial_ars'} dir={supplierSort.dir} onClick={() => toggleSupplierSort('ganancia_potencial_ars')}>Ganancia total</SortButton></th>
                      <th className="py-2 pr-3"><SortButton active={supplierSort.key === 'margen_promedio_pct'} dir={supplierSort.dir} onClick={() => toggleSupplierSort('margen_promedio_pct')}>Margen prom. %</SortButton></th>
                      <th className="py-2 pr-3"><SortButton active={supplierSort.key === 'margen_ponderado_pct'} dir={supplierSort.dir} onClick={() => toggleSupplierSort('margen_ponderado_pct')}>Margen pond. %</SortButton></th>
                      <th className="py-2 pr-3"><SortButton active={supplierSort.key === 'consistencia_stddev_pct'} dir={supplierSort.dir} onClick={() => toggleSupplierSort('consistencia_stddev_pct', 'asc')}>Consistencia</SortButton></th>
                      <th className="py-2 pr-3"><SortButton active={supplierSort.key === 'dependencia_pct_costo'} dir={supplierSort.dir} onClick={() => toggleSupplierSort('dependencia_pct_costo')}>Dependencia</SortButton></th>
                      <th className="py-2 pr-3"><SortButton active={supplierSort.key === 'costo_total_ars'} dir={supplierSort.dir} onClick={() => toggleSupplierSort('costo_total_ars')}>Costo comprado</SortButton></th>
                      <th className="py-2 pr-3">Ranking</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedSupplierRows.map((row) => (
                      <tr key={row.supplier_id} className="border-b last:border-b-0">
                        <td className="py-2 pr-3">
                          {row.proveedor}
                          <div className="text-xs text-gray-500">{intVal(row.variantes)} variantes</div>
                        </td>
                        <td className="py-2 pr-3">{money(row.ganancia_potencial_ars)}</td>
                        <td className="py-2 pr-3">{toNum(row.margen_promedio_pct).toFixed(2)}%</td>
                        <td className="py-2 pr-3">{toNum(row.margen_ponderado_pct).toFixed(2)}%</td>
                        <td className="py-2 pr-3">{toNum(row.consistencia_stddev_pct).toFixed(2)}%</td>
                        <td className="py-2 pr-3">{toNum(row.dependencia_pct_costo).toFixed(2)}%</td>
                        <td className="py-2 pr-3">{money(row.costo_total_ars)}</td>
                        <td className="py-2 pr-3">
                          <span className={`inline-flex rounded border px-2 py-0.5 text-xs font-semibold ${row.conviene_trabajar_mas ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-neutral-200 bg-neutral-50 text-neutral-600'}`}>
                            #{row.rank}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        )}
      </div>

      <details className="card">
        <summary className="cursor-pointer text-lg font-semibold">Detalle operativo secundario</summary>
        <div className="mt-3 grid grid-cols-1 xl:grid-cols-3 gap-3">
          <div className="rounded border p-3">
            <h3 className="font-semibold mb-2">Bajo stock</h3>
            {sectionMessage(lowStockSection)}
            {lowStockSection.status === 'success' ? (
              <div className="overflow-auto max-h-56">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-2 pr-3">Producto</th>
                      <th className="py-2 pr-3">SKU</th>
                      <th className="py-2 pr-3">Stock</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lowStockSection.rows.map((row) => (
                      <tr key={row.id} className="border-b last:border-b-0">
                        <td className="py-2 pr-3">{row.producto || '-'}</td>
                        <td className="py-2 pr-3">{row.sku || '-'}</td>
                        <td className="py-2 pr-3">{intVal(row.stock_on_hand)} / {intVal(row.stock_min)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>

          <div className="rounded border p-3">
            <h3 className="font-semibold mb-2">Devoluciones</h3>
            {sectionMessage(returnsSection)}
            {returnsSection.status === 'success' ? (
              <div className="overflow-auto max-h-56">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-2 pr-3">Fecha</th>
                      <th className="py-2 pr-3">Venta</th>
                      <th className="py-2 pr-3">Reintegro</th>
                    </tr>
                  </thead>
                  <tbody>
                    {returnsSection.rows.map((row) => (
                      <tr key={row.return_id} className="border-b last:border-b-0">
                        <td className="py-2 pr-3">{row.day || '-'}</td>
                        <td className="py-2 pr-3">#{row.sale_id || '-'}</td>
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
            {sectionMessage(cashCloseSection)}
            {cashCloseSection.status === 'success' ? (
              <div className="overflow-auto max-h-56">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-2 pr-3">Caja</th>
                      <th className="py-2 pr-3">Apertura</th>
                      <th className="py-2 pr-3">Dif.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cashCloseSection.rows.map((row) => (
                      <tr key={row.id} className="border-b last:border-b-0">
                        <td className="py-2 pr-3">#{row.id}</td>
                        <td className="py-2 pr-3">{dateTimeLabel(row.opened_at)}</td>
                        <td className="py-2 pr-3">{money(row.difference_total_ars)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </div>
      </details>

      {sectionMessage(summarySection, 'Sin resumen para el rango seleccionado.')}
      {err ? <p className="text-sm text-red-700">{err}</p> : null}
    </div>
  );
}
