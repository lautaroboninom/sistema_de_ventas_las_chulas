import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getMetricasSeries, getTecnicos, getMarcas, getTiposEquipo } from "../lib/api";
import { METRICAS_DESDE_MIN, clampDesdeMin } from "../lib/constants";
import MetricasNav from "../components/metricas/MetricasNav.jsx";
import SimpleBars from "../components/metricas/charts/SimpleBars.jsx";
import SimpleLine from "../components/metricas/charts/SimpleLine.jsx";
import { downloadExcel } from "../lib/excel";

function formatNumber(value, decimals = 0) {
  if (value == null || isNaN(value)) return "-";
  const v = Number(value);
  if (Number.isNaN(v)) return "-";
  return v.toLocaleString("es-AR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatMoney(value, decimals = 0) {
  if (value == null || isNaN(value)) return "-";
  return `$${formatNumber(value, decimals)}`;
}

function StatCard({ label, value, help, meta }) {
  return (
    <div className="p-4 border rounded bg-white">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
          <div className="text-2xl font-semibold mt-1 text-gray-900">{value}</div>
        </div>
        {meta ? <div className="text-xs text-gray-500 text-right">{meta}</div> : null}
      </div>
      {help ? <div className="text-xs text-gray-500 mt-2">{help}</div> : null}
    </div>
  );
}

function FilterChip({ label, onClear }) {
  return (
    <button
      type="button"
      onClick={onClear}
      className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-white px-2 py-0.5 text-xs text-gray-700 hover:bg-gray-50"
    >
      <span>{label}</span>
      {onClear ? <span aria-hidden="true">x</span> : null}
    </button>
  );
}

function QuickRangeButton({ label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-2.5 py-1 rounded border text-xs ${active ? "bg-gray-100 border-gray-300 font-semibold" : "bg-white border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-50"}`}
    >
      {label}
    </button>
  );
}

export default function MetricasClientes() {
  const [search, setSearch] = useSearchParams();
  const [desde, setDesde] = useState(() => {
    const s = search.get("from");
    if (s) return clampDesdeMin(s);
    const d = new Date(); d.setMonth(d.getMonth() - 3);
    return clampDesdeMin(d.toISOString().slice(0, 10));
  });
  const [hasta, setHasta] = useState(() => search.get("to") || new Date().toISOString().slice(0, 10));
  const [tecnicos, setTecnicos] = useState([]);
  const [marcas, setMarcas] = useState([]);
  const [tipos, setTipos] = useState([]);
  const [tecnicoId, setTecnicoId] = useState(search.get("tecnico_id") || "");
  const [marcaId, setMarcaId] = useState(search.get("marca_id") || "");
  const [tipoEquipo, setTipoEquipo] = useState(search.get("tipo_equipo") || "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);

  useEffect(() => {
    getTecnicos().then(setTecnicos).catch(() => {});
    getMarcas().then(setMarcas).catch(() => {});
    getTiposEquipo().then(setTipos).catch(() => {});
  }, []);

  const desdeClamped = useMemo(() => clampDesdeMin(desde), [desde]);
  const tecnicoMap = useMemo(() => new Map(tecnicos.map((t) => [String(t.id), t.nombre])), [tecnicos]);
  const marcaMap = useMemo(() => new Map(marcas.map((m) => [String(m.id), m.nombre])), [marcas]);
  const tipoMap = useMemo(() => new Map(tipos.map((t) => [String(t.nombre), t.nombre])), [tipos]);

  const rangeDays = useMemo(() => {
    if (!desdeClamped || !hasta) return null;
    const from = new Date(desdeClamped);
    const to = new Date(hasta);
    if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return null;
    const ms = to.setHours(0, 0, 0, 0) - from.setHours(0, 0, 0, 0);
    if (ms < 0) return null;
    return Math.round(ms / 86400000) + 1;
  }, [desdeClamped, hasta]);
  const periodLabel = useMemo(() => {
    if (!desdeClamped || !hasta) return "";
    if (!rangeDays) return `${desdeClamped} a ${hasta}`;
    return `${desdeClamped} a ${hasta} (${rangeDays} días)`;
  }, [desdeClamped, hasta, rangeDays]);

  function applyQuickRange(days) {
    const to = new Date();
    const from = new Date();
    from.setDate(from.getDate() - (days - 1));
    setDesde(clampDesdeMin(from.toISOString().slice(0, 10)));
    setHasta(to.toISOString().slice(0, 10));
  }

  function applyYearToDate() {
    const now = new Date();
    const from = new Date(now.getFullYear(), 0, 1);
    setDesde(clampDesdeMin(from.toISOString().slice(0, 10)));
    setHasta(now.toISOString().slice(0, 10));
  }

  const activeFilters = useMemo(() => {
    const items = [];
    if (tecnicoId) items.push({ key: "tecnico", label: `Técnico: ${tecnicoMap.get(String(tecnicoId)) || tecnicoId}` });
    if (marcaId) items.push({ key: "marca", label: `Marca: ${marcaMap.get(String(marcaId)) || marcaId}` });
    if (tipoEquipo) items.push({ key: "tipo", label: `Tipo: ${tipoMap.get(String(tipoEquipo)) || tipoEquipo}` });
    return items;
  }, [tecnicoId, marcaId, tipoEquipo, tecnicoMap, marcaMap, tipoMap]);

  useEffect(() => {
    const next = new URLSearchParams(search.toString());
    next.set("from", desdeClamped);
    next.set("to", hasta);
    if (tecnicoId) next.set("tecnico_id", tecnicoId); else next.delete("tecnico_id");
    if (marcaId) next.set("marca_id", marcaId); else next.delete("marca_id");
    if (tipoEquipo) next.set("tipo_equipo", tipoEquipo); else next.delete("tipo_equipo");
    setSearch(next, { replace: true });
  }, [desdeClamped, hasta, tecnicoId, marcaId, tipoEquipo]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    const params = { from: desdeClamped, to: hasta, group: "cliente" };
    if (tecnicoId) params.tecnico_id = tecnicoId;
    if (marcaId) params.marca_id = marcaId;
    if (tipoEquipo) params.tipo_equipo = tipoEquipo;
    getMetricasSeries(params)
      .then((res) => { if (alive) setData(res); })
      .catch((err) => { if (alive) setError(err?.message || String(err)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [desdeClamped, hasta, tecnicoId, marcaId, tipoEquipo]);

  function exportExcel(filename, rows) {
    downloadExcel(filename, rows, "MetricasClientes");
  }

  function buildClientesRows() {
    const header = ["period", "cliente", "entregados", "facturacion", "mano_obra", "repuestos"];
    const key = (p, id) => `${p}:${id}`;
    const map = new Map();
    (data?.by_cliente_monthly || []).forEach((r) => {
      const k = key(r.period, r.cliente_id);
      map.set(k, { period: r.period, cliente: r.cliente_nombre, entregados: r.entregados, facturacion: 0, mo: 0, rep: 0 });
    });
    (data?.facturacion_cliente_monthly || []).forEach((r) => {
      const k = key(r.period, r.cliente_id);
      const o = map.get(k) || { period: r.period, cliente: r.cliente_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
      o.facturacion = r.facturacion || 0; map.set(k, o);
    });
    (data?.mo_cliente_monthly || []).forEach((r) => {
      const k = key(r.period, r.cliente_id);
      const o = map.get(k) || { period: r.period, cliente: r.cliente_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
      o.mo = r.monto_mo || 0; map.set(k, o);
    });
    (data?.repuestos_cliente_monthly || []).forEach((r) => {
      const k = key(r.period, r.cliente_id);
      const o = map.get(k) || { period: r.period, cliente: r.cliente_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
      o.rep = r.monto_repuestos || 0; map.set(k, o);
    });
    const rows = [
      header,
      ...Array.from(map.values())
        .sort((a, b) => a.period.localeCompare(b.period) || a.cliente.localeCompare(b.cliente))
        .map((o) => [o.period, o.cliente, o.entregados, o.facturacion, o.mo, o.rep]),
    ];
    return rows;
  }

  function exportClientesExcel() {
    const rows = buildClientesRows();
    exportExcel(`metricas_clientes_mensual_${desdeClamped}_${hasta}.xls`, rows);
  }

  function downloadCSV(filename, rows) {
    const bom = "\uFEFF";
    const csv = rows.map((r) => r.map((v) => {
      if (v == null) return "";
      const s = String(v).replaceAll('"', '""');
      return /[",\n]/.test(s) ? `"${s}"` : s;
    }).join(",")).join("\n");
    const blob = new Blob([bom + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportClientesCSV() {
    const rows = buildClientesRows();
    downloadCSV(`metricas_clientes_mensual_${desdeClamped}_${hasta}.csv`, rows);
  }

  function shortLabel(value, max = 22) {
    if (!value) return "-";
    const s = String(value);
    if (s.length <= max) return s;
    return `${s.slice(0, max - 3)}...`;
  }

  const clientTotals = useMemo(() => {
    const map = new Map();
    const ensure = (id, nombre) => {
      const key = String(id ?? nombre ?? "");
      if (!key) return null;
      const current = map.get(key) || { key, id, nombre: nombre || "(sin nombre)", entregados: 0, facturacion: 0, mo: 0, rep: 0 };
      map.set(key, current);
      return current;
    };
    (data?.by_cliente_monthly || []).forEach((r) => {
      const o = ensure(r.cliente_id, r.cliente_nombre);
      if (!o) return;
      o.entregados += Number(r.entregados || 0);
    });
    (data?.facturacion_cliente_monthly || []).forEach((r) => {
      const o = ensure(r.cliente_id, r.cliente_nombre);
      if (!o) return;
      o.facturacion += Number(r.facturacion || 0);
    });
    (data?.mo_cliente_monthly || []).forEach((r) => {
      const o = ensure(r.cliente_id, r.cliente_nombre);
      if (!o) return;
      o.mo += Number(r.monto_mo || 0);
    });
    (data?.repuestos_cliente_monthly || []).forEach((r) => {
      const o = ensure(r.cliente_id, r.cliente_nombre);
      if (!o) return;
      o.rep += Number(r.monto_repuestos || 0);
    });
    return Array.from(map.values());
  }, [data]);

  const totalEntregados = useMemo(() => clientTotals.reduce((acc, it) => acc + (Number(it.entregados) || 0), 0), [clientTotals]);
  const totalFacturacion = useMemo(() => clientTotals.reduce((acc, it) => acc + (Number(it.facturacion) || 0), 0), [clientTotals]);
  const totalMo = useMemo(() => clientTotals.reduce((acc, it) => acc + (Number(it.mo) || 0), 0), [clientTotals]);
  const totalRep = useMemo(() => clientTotals.reduce((acc, it) => acc + (Number(it.rep) || 0), 0), [clientTotals]);

  const topEntregados = useMemo(() => clientTotals.slice().sort((a, b) => (b.entregados || 0) - (a.entregados || 0)).slice(0, 8), [clientTotals]);
  const topFacturacion = useMemo(() => clientTotals.slice().sort((a, b) => (b.facturacion || 0) - (a.facturacion || 0)).slice(0, 8), [clientTotals]);
  const topTabla = useMemo(() => clientTotals.slice().sort((a, b) => (b.facturacion || 0) - (a.facturacion || 0)).slice(0, 15), [clientTotals]);

  const top5Share = useMemo(() => {
    if (!totalFacturacion) return null;
    const topSum = topFacturacion.slice(0, 5).reduce((acc, it) => acc + (Number(it.facturacion) || 0), 0);
    return (topSum / totalFacturacion) * 100;
  }, [topFacturacion, totalFacturacion]);

  const periods = useMemo(() => {
    const set = new Set();
    (data?.by_cliente_monthly || []).forEach((r) => { if (r.period) set.add(r.period); });
    return Array.from(set).sort();
  }, [data]);

  const entregadosMap = useMemo(() => {
    const map = new Map();
    (data?.by_cliente_monthly || []).forEach((r) => {
      const key = `${r.cliente_id ?? r.cliente_nombre}:${r.period}`;
      map.set(key, Number(r.entregados || 0));
    });
    return map;
  }, [data]);

  const trendSeries = useMemo(() => {
    return topEntregados.slice(0, 3).map((client) => {
      const values = periods.map((p) => entregadosMap.get(`${client.id ?? client.nombre}:${p}`) || 0);
      return { name: client.nombre, values };
    });
  }, [topEntregados, periods, entregadosMap]);

  const topEntregadosLabels = useMemo(() => topEntregados.map((c) => shortLabel(c.nombre)), [topEntregados]);
  const topFacturacionLabels = useMemo(() => topFacturacion.map((c) => shortLabel(c.nombre)), [topFacturacion]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Métricas por clientes</h1>
          <div className="text-sm text-gray-500">Indicadores por cliente para entender volumen, facturación y mix.</div>
        </div>
      </div>

      <MetricasNav />

      <div className="border rounded bg-white p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <div>
            <div className="text-sm text-gray-600">Desde</div>
            <input type="date" value={desdeClamped} min={METRICAS_DESDE_MIN} onChange={e=>setDesde(clampDesdeMin(e.target.value))} className="mt-1 border rounded px-2 py-1" />
          </div>
          <div>
            <div className="text-sm text-gray-600">Hasta</div>
            <input type="date" value={hasta} onChange={e=>setHasta(e.target.value)} className="mt-1 border rounded px-2 py-1" />
          </div>
          <div>
            <div className="text-sm text-gray-600">Técnico</div>
            <select className="mt-1 border rounded px-2 py-1 w-full" value={tecnicoId} onChange={e=>setTecnicoId(e.target.value)}>
              <option value="">Todos</option>
              {tecnicos.map(t => (<option key={t.id} value={t.id}>{t.nombre}</option>))}
            </select>
          </div>
          <div>
            <div className="text-sm text-gray-600">Marca</div>
            <select className="mt-1 border rounded px-2 py-1 w-full" value={marcaId} onChange={e=>setMarcaId(e.target.value)}>
              <option value="">Todas</option>
              {marcas.map(m => (<option key={m.id} value={m.id}>{m.nombre}</option>))}
            </select>
          </div>
          <div>
            <div className="text-sm text-gray-600">Tipo equipo</div>
            <select className="mt-1 border rounded px-2 py-1 w-full" value={tipoEquipo} onChange={e=>setTipoEquipo(e.target.value)}>
              <option value="">Todos</option>
              {tipos.map((t, idx) => (<option key={t.id || idx} value={t.nombre}>{t.nombre}</option>))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          <div className="text-xs text-gray-500 mr-2">Rangos rapidos</div>
          <QuickRangeButton label="7 días" active={rangeDays === 7} onClick={() => applyQuickRange(7)} />
          <QuickRangeButton label="30 días" active={rangeDays === 30} onClick={() => applyQuickRange(30)} />
          <QuickRangeButton label="90 días" active={rangeDays === 90} onClick={() => applyQuickRange(90)} />
          <QuickRangeButton
            label="YTD"
            active={desdeClamped === `${new Date().getFullYear()}-01-01` && hasta === new Date().toISOString().slice(0, 10)}
            onClick={applyYearToDate}
          />
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          <div className="text-xs text-gray-500 mr-2">Filtros activos</div>
          {activeFilters.length === 0 ? (
            <span className="text-xs text-gray-400">Sin filtros adicionales</span>
          ) : (
            activeFilters.map((f) => (
              <FilterChip
                key={f.key}
                label={f.label}
                onClear={() => {
                  if (f.key === "tecnico") setTecnicoId("");
                  if (f.key === "marca") setMarcaId("");
                  if (f.key === "tipo") setTipoEquipo("");
                }}
              />
            ))
          )}
          {activeFilters.length > 0 ? (
            <button
              type="button"
              onClick={() => { setTecnicoId(""); setMarcaId(""); setTipoEquipo(""); }}
              className="px-2.5 py-1 text-xs border rounded bg-white hover:bg-gray-50"
            >
              Limpiar
            </button>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          <div className="text-xs text-gray-500 mr-2">Exportar</div>
          <button onClick={exportClientesCSV} className="px-2.5 py-1 border rounded text-xs bg-white hover:bg-gray-50">CSV</button>
          <button onClick={exportClientesExcel} className="px-2.5 py-1 border rounded text-xs bg-white hover:bg-gray-50">Excel</button>
        </div>
      </div>

      {loading && <div className="text-gray-500">Cargando métricas</div>}
      {error && (
        <div className="text-red-600">Error al cargar métricas: {error}</div>
      )}

      {data && (
        <>
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Resumen</h2>
            {periodLabel ? <div className="text-xs text-gray-500">Periodo {periodLabel}</div> : null}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <StatCard label="Entregados" value={formatNumber(totalEntregados)} />
            <StatCard
              label="Facturacion"
              value={formatMoney(totalFacturacion)}
              help={top5Share != null ? `Top 5: ${formatNumber(top5Share, 1)}%` : null}
            />
            <StatCard label="Mano de obra" value={formatMoney(totalMo)} />
            <StatCard label="Repuestos" value={formatMoney(totalRep)} />
            <StatCard label="Clientes activos" value={formatNumber(clientTotals.length)} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SimpleBars
              title="Top clientes por entregados"
              subtitle="Top 8 del periodo"
              categories={topEntregadosLabels}
              labels={topEntregadosLabels}
              titles={topEntregados.map((c) => c.nombre)}
              values={topEntregados.map((c) => c.entregados)}
              fmt={(v) => formatNumber(v)}
              showValues
            />
            <SimpleBars
              title="Top clientes por facturacion"
              subtitle="Top 8 del periodo"
              categories={topFacturacionLabels}
              labels={topFacturacionLabels}
              titles={topFacturacion.map((c) => c.nombre)}
              values={topFacturacion.map((c) => c.facturacion)}
              fmt={(v) => formatMoney(v)}
              showValues
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SimpleLine
              title="Tendencia de entregados"
              subtitle="Top 3 clientes del periodo"
              categories={periods}
              series={trendSeries}
              fmt={(v) => formatNumber(v)}
            />
            <div className="border rounded bg-white p-3">
              <div className="text-sm font-medium text-gray-700 mb-2">Ranking por facturacion</div>
              <div className="overflow-auto max-h-80">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-600">
                      <th className="text-left p-2">#</th>
                      <th className="text-left p-2">Cliente</th>
                      <th className="text-right p-2">Entregados</th>
                      <th className="text-right p-2">Facturacion</th>
                      <th className="text-right p-2">MO</th>
                      <th className="text-right p-2">Repuestos</th>
                      <th className="text-right p-2">% fact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topTabla.length === 0 && (
                      <tr><td colSpan={7} className="p-3 text-gray-500">Sin datos</td></tr>
                    )}
                    {topTabla.map((row, idx) => {
                      const pct = totalFacturacion ? (row.facturacion / totalFacturacion) * 100 : 0;
                      return (
                        <tr key={row.key} className="border-t">
                          <td className="p-2">{idx + 1}</td>
                          <td className="p-2">{row.nombre}</td>
                          <td className="p-2 text-right">{formatNumber(row.entregados)}</td>
                          <td className="p-2 text-right">{formatMoney(row.facturacion)}</td>
                          <td className="p-2 text-right">{formatMoney(row.mo)}</td>
                          <td className="p-2 text-right">{formatMoney(row.rep)}</td>
                          <td className="p-2 text-right">{pct ? `${formatNumber(pct, 1)}%` : "-"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

