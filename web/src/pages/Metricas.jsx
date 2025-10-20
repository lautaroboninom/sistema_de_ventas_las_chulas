import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getMetricasResumen, getMetricasSeries, getTecnicos, getMarcas, getTiposEquipo, getMetricasCalibracion } from "../lib/api";

function formatPct(n) {
  if (n == null || isNaN(n)) return "-";
  return `${(n * 100).toFixed(0)}%`;
}

function StatCard({ label, value, help }) {
  return (
    <div className="p-4 border rounded bg-white">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      {help ? <div className="text-xs text-gray-400 mt-1">{help}</div> : null}
    </div>
  );
}

export default function Metricas() {
  const { user } = useAuth();
  const [search, setSearch] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [series, setSeries] = useState(null);
  const [tecnicos, setTecnicos] = useState([]);
  const [marcas, setMarcas] = useState([]);
  const [tipos, setTipos] = useState([]);
  const [tecnicoId, setTecnicoId] = useState(search.get('tecnico_id') || "");
  const [marcaId, setMarcaId] = useState(search.get('marca_id') || "");
  const [tipoEquipo, setTipoEquipo] = useState(search.get('tipo_equipo') || "");
  const [desde, setDesde] = useState(() => {
    const s = search.get('from');
    if (s) return s;
    const d = new Date(); d.setDate(d.getDate() - 30);
    return d.toISOString().slice(0, 10);
  });
  const [hasta, setHasta] = useState(() => search.get('to') || new Date().toISOString().slice(0, 10));
  const [slaExclDer, setSlaExclDer] = useState(() => {
    const v = search.get('sla_excluir_derivados');
    return v ? v === '1' : true; // por defecto: excluir derivados
  });

  useEffect(() => {
    // cargar filtros
    getTecnicos().then(setTecnicos).catch(() => {});
    getMarcas().then(setMarcas).catch(() => {});
    getTiposEquipo().then(setTipos).catch(() => {});
  }, []);

  // Sincronizar filtros en la URL
  useEffect(() => {
    const next = new URLSearchParams(search.toString());
    next.set('from', desde);
    next.set('to', hasta);
    if (tecnicoId) next.set('tecnico_id', tecnicoId); else next.delete('tecnico_id');
    if (marcaId) next.set('marca_id', marcaId); else next.delete('marca_id');
    if (tipoEquipo) next.set('tipo_equipo', tipoEquipo); else next.delete('tipo_equipo');
    if (slaExclDer) next.set('sla_excluir_derivados', '1'); else next.delete('sla_excluir_derivados');
    setSearch(next, { replace: true });
  }, [desde, hasta, tecnicoId, marcaId, tipoEquipo, slaExclDer]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    const params = { from: desde, to: hasta };
    if (tecnicoId) params.tecnico_id = tecnicoId;
    if (marcaId) params.marca_id = marcaId;
    if (tipoEquipo) params.tipo_equipo = tipoEquipo;
    if (slaExclDer) params.sla_excluir_derivados = 1;
    getMetricasResumen(params)
      .then((res) => {
        if (!alive) return;
        setData(res);
      })
      .catch((err) => {
        if (!alive) return;
        setError(err?.message || String(err));
      })
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [desde, hasta, tecnicoId, marcaId, tipoEquipo]);

  useEffect(() => {
    let alive = true;
    setSeries(null);
    const params = { from: desde, to: hasta };
    if (tecnicoId) params.tecnico_id = tecnicoId;
    if (marcaId) params.marca_id = marcaId;
    if (tipoEquipo) params.tipo_equipo = tipoEquipo;
    if (slaExclDer) params.sla_excluir_derivados = 1;
    getMetricasSeries(params)
      .then((res) => { if (alive) setSeries(res); })
      .catch(() => { /* silencio */ });
    return () => { alive = false; };
  }, [desde, hasta, tecnicoId, marcaId, tipoEquipo]);

  function downloadCSV(filename, rows) {
    const bom = "\uFEFF"; // para Excel UTF-8
    const csv = rows.map(r => r.map(v => {
      if (v == null) return "";
      const s = String(v).replaceAll('"', '""');
      return /[",\n]/.test(s) ? `"${s}"` : s;
    }).join(",")).join("\n");
    const blob = new Blob([bom + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportTablasCSV() {
    const rows = [];
    rows.push(["Tabla","Tecnico","Valor"]);
    (data?.cerrados_por_tecnico_7d || []).forEach(r => rows.push(["cerrados_7d", r.tecnico_nombre, r.cerrados]));
    (data?.cerrados_por_tecnico_30d || []).forEach(r => rows.push(["cerrados_30d", r.tecnico_nombre, r.cerrados]));
    (data?.wip_por_tecnico || []).forEach(r => rows.push(["wip", r.tecnico_nombre, r.wip]));
    (data?.facturacion_por_tecnico || []).forEach(r => rows.push(["facturacion_aprobada", r.tecnico_nombre, r.facturacion]));
    (data?.utilidad_mo_por_tecnico || []).forEach(r => rows.push(["utilidad_mo", r.tecnico_nombre, r.utilidad_mo]));
    (data?.repuestos_por_tecnico || []).forEach(r => rows.push(["repuestos", r.tecnico_nombre, r.ingreso_repuestos]));
    downloadCSV(`metricas_tablas_${desde}_${hasta}.csv`, rows);
  }

  function exportSeriesCSV(kind) {
    const src = kind === 'yearly' ? (series?.yearly || []) : (series?.monthly || []);
    const header = ["period","entregados","mttr_dias","sla_diag_24h","t_emitir_horas","t_aprobar_horas","ext_derivados","ext_devueltos","ext_t_deriv_a_dev_dias"];
    const rows = [header];
    src.forEach(m => {
      rows.push([
        m.period,
        m.entregados,
        m.mttr_dias != null ? m.mttr_dias.toFixed(2) : "",
        m.sla_diag_24h ? (m.sla_diag_24h.cumplimiento * 100).toFixed(0) + "%" : "",
        m.aprob_presupuestos?.t_emitir_horas != null ? m.aprob_presupuestos.t_emitir_horas.toFixed(2) : "",
        m.aprob_presupuestos?.t_aprobar_horas != null ? m.aprob_presupuestos.t_aprobar_horas.toFixed(2) : "",
        m.externo?.derivados ?? "",
        m.externo?.devueltos ?? "",
        m.externo?.t_deriv_a_devuelto_dias != null ? m.externo.t_deriv_a_devuelto_dias.toFixed(2) : "",
      ]);
    });
    downloadCSV(`metricas_series_${kind}_${desde}_${hasta}.csv`, rows);
  }

  async function exportDetalleTecnicoMensual() {
    const params = { from: desde, to: hasta, group: 'tecnico' };
    if (tecnicoId) params.tecnico_id = tecnicoId;
    if (marcaId) params.marca_id = marcaId;
    if (tipoEquipo) params.tipo_equipo = tipoEquipo;
    if (slaExclDer) params.sla_excluir_derivados = 1;
    const res = await getMetricasSeries(params);
    const header = ["period","tecnico","entregados","facturacion","mano_obra","repuestos"];
    const key = (p, id) => `${p}:${id}`;
    const map = new Map();
    (res.by_tecnico_monthly || []).forEach(r => {
      const k = key(r.period, r.tecnico_id);
      map.set(k, { period: r.period, tecnico: r.tecnico_nombre, entregados: r.entregados, facturacion: 0, mo: 0, rep: 0 });
    });
    (res.facturacion_tecnico_monthly || []).forEach(r => {
      const k = key(r.period, r.tecnico_id);
      const o = map.get(k) || { period: r.period, tecnico: r.tecnico_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
      o.facturacion = r.facturacion || 0;
      map.set(k, o);
    });
    (res.mo_tecnico_monthly || []).forEach(r => {
      const k = key(r.period, r.tecnico_id);
      const o = map.get(k) || { period: r.period, tecnico: r.tecnico_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
      o.mo = r.monto_mo || 0;
      map.set(k, o);
    });
    (res.repuestos_tecnico_monthly || []).forEach(r => {
      const k = key(r.period, r.tecnico_id);
      const o = map.get(k) || { period: r.period, tecnico: r.tecnico_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
      o.rep = r.monto_repuestos || 0;
      map.set(k, o);
    });
    const rows = [header, ...Array.from(map.values())
      .sort((a,b) => a.period.localeCompare(b.period) || a.tecnico.localeCompare(b.tecnico))
      .map(o => [o.period, o.tecnico, o.entregados, o.facturacion, o.mo, o.rep])];
    downloadCSV(`metricas_detalle_tecnico_mensual_${desde}_${hasta}.csv`, rows);
  }

  async function exportDetalleMarcaMensual() {
    const params = { from: desde, to: hasta, group: 'marca' };
    if (tecnicoId) params.tecnico_id = tecnicoId;
    if (marcaId) params.marca_id = marcaId;
    if (tipoEquipo) params.tipo_equipo = tipoEquipo;
    getMetricasSeries(params).then((res) => {
      const header = ["period","marca","entregados","facturacion","mano_obra","repuestos"];
      const key = (p, id) => `${p}:${id}`;
      const map = new Map();
      (res.by_marca_monthly || []).forEach(r => {
        const k = key(r.period, r.marca_id);
        map.set(k, { period: r.period, marca: r.marca_nombre, entregados: r.entregados, facturacion: 0, mo: 0, rep: 0 });
      });
      (res.facturacion_marca_monthly || []).forEach(r => {
        const k = key(r.period, r.marca_id);
        const o = map.get(k) || { period: r.period, marca: r.marca_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
        o.facturacion = r.facturacion || 0;
        map.set(k, o);
      });
      (res.mo_marca_monthly || []).forEach(r => {
        const k = key(r.period, r.marca_id);
        const o = map.get(k) || { period: r.period, marca: r.marca_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
        o.mo = r.monto_mo || 0;
        map.set(k, o);
      });
      (res.repuestos_marca_monthly || []).forEach(r => {
        const k = key(r.period, r.marca_id);
        const o = map.get(k) || { period: r.period, marca: r.marca_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
        o.rep = r.monto_repuestos || 0;
        map.set(k, o);
      });
      const rows = [header, ...Array.from(map.values())
        .sort((a,b) => a.period.localeCompare(b.period) || a.marca.localeCompare(b.marca))
        .map(o => [o.period, o.marca, o.entregados, o.facturacion, o.mo, o.rep])];
      downloadCSV(`metricas_detalle_marca_mensual_${desde}_${hasta}.csv`, rows);
    });
  }

  async function exportDetalleTipoMensual() {
    const params = { from: desde, to: hasta, group: 'tipo' };
    if (tecnicoId) params.tecnico_id = tecnicoId;
    if (marcaId) params.marca_id = marcaId;
    if (tipoEquipo) params.tipo_equipo = tipoEquipo;
    getMetricasSeries(params).then((res) => {
      const header = ["period","tipo","entregados","facturacion","mano_obra","repuestos"];
      const key = (p, name) => `${p}:${name || ''}`;
      const map = new Map();
      (res.by_tipo_monthly || []).forEach(r => {
        const k = key(r.period, r.tipo_equipo);
        map.set(k, { period: r.period, tipo: r.tipo_equipo || '(sin tipo)', entregados: r.entregados, facturacion: 0, mo: 0, rep: 0 });
      });
      (res.facturacion_tipo_monthly || []).forEach(r => {
        const k = key(r.period, r.tipo_equipo);
        const o = map.get(k) || { period: r.period, tipo: r.tipo_equipo || '(sin tipo)', entregados: 0, facturacion: 0, mo: 0, rep: 0 };
        o.facturacion = r.facturacion || 0;
        map.set(k, o);
      });
      (res.mo_tipo_monthly || []).forEach(r => {
        const k = key(r.period, r.tipo_equipo);
        const o = map.get(k) || { period: r.period, tipo: r.tipo_equipo || '(sin tipo)', entregados: 0, facturacion: 0, mo: 0, rep: 0 };
        o.mo = r.monto_mo || 0;
        map.set(k, o);
      });
      (res.repuestos_tipo_monthly || []).forEach(r => {
        const k = key(r.period, r.tipo_equipo);
        const o = map.get(k) || { period: r.period, tipo: r.tipo_equipo || '(sin tipo)', entregados: 0, facturacion: 0, mo: 0, rep: 0 };
        o.rep = r.monto_repuestos || 0;
        map.set(k, o);
      });
      const rows = [header, ...Array.from(map.values())
        .sort((a,b) => a.period.localeCompare(b.period) || a.tipo.localeCompare(b.tipo))
        .map(o => [o.period, o.tipo, o.entregados, o.facturacion, o.mo, o.rep])];
      downloadCSV(`metricas_detalle_tipo_mensual_${desde}_${hasta}.csv`, rows);
    });
  }

  async function exportCalibracionCSV() {
    const params = { from: desde, to: hasta };
    if (tecnicoId) params.tecnico_id = tecnicoId;
    if (marcaId) params.marca_id = marcaId;
    if (tipoEquipo) params.tipo_equipo = tipoEquipo;
    const res = await getMetricasCalibracion(params);
    const rows = [["metric","p50","p75","p90","p95","avg","count"]];
    const push = (name, obj) => rows.push([
      name,
      obj?.p50 != null ? obj.p50.toFixed(2) : "",
      obj?.p75 != null ? obj.p75.toFixed(2) : "",
      obj?.p90 != null ? obj.p90.toFixed(2) : "",
      obj?.p95 != null ? obj.p95.toFixed(2) : "",
      obj?.avg != null ? obj.avg.toFixed(2) : "",
      obj?.count ?? 0,
    ]);
    push('diag_business_minutes', res.diag_business_minutes);
    push('diag_to_emit_hours', res.diag_to_emit_hours);
    push('emit_to_approve_hours', res.emit_to_approve_hours);
    push('approve_to_repair_days', res.approve_to_repair_days);
    push('repair_to_deliver_days', res.repair_to_deliver_days);
    push('ingreso_to_deliver_days', res.ingreso_to_deliver_days);
    downloadCSV(`metricas_calibracion_${desde}_${hasta}.csv`, rows);
  }

  const cerrados7 = useMemo(() => data?.cerrados_por_tecnico_7d || [], [data]);
  const cerrados30 = useMemo(() => data?.cerrados_por_tecnico_30d || [], [data]);
  const wip = useMemo(() => data?.wip_por_tecnico || [], [data]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Mtricas</h1>
        <Link to="/metricas/clientes" className="text-blue-600 hover:underline">Ver mtricas por clientes </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-6 gap-3 items-end">
        <div>
          <div className="text-sm text-gray-600">Desde</div>
          <input
            type="date"
            value={desde}
            onChange={(e) => setDesde(e.target.value)}
            className="mt-1 border rounded px-2 py-1"
          />
        </div>
        <div>
          <div className="text-sm text-gray-600">Hasta</div>
          <input
            type="date"
            value={hasta}
            onChange={(e) => setHasta(e.target.value)}
            className="mt-1 border rounded px-2 py-1"
          />
        </div>
        <div>
          <div className="text-sm text-gray-600">Tcnico</div>
          <select className="mt-1 border rounded px-2 py-1 w-full" value={tecnicoId} onChange={(e) => setTecnicoId(e.target.value)}>
            <option value="">Todos</option>
            {tecnicos.map(t => (
              <option key={t.id} value={t.id}>{t.nombre}</option>
            ))}
          </select>
        </div>
        <div>
          <div className="text-sm text-gray-600">Marca</div>
          <select className="mt-1 border rounded px-2 py-1 w-full" value={marcaId} onChange={(e) => setMarcaId(e.target.value)}>
            <option value="">Todas</option>
            {marcas.map(m => (
              <option key={m.id} value={m.id}>{m.nombre}</option>
            ))}
          </select>
        </div>
        <div>
          <div className="text-sm text-gray-600">Tipo equipo</div>
          <select className="mt-1 border rounded px-2 py-1 w-full" value={tipoEquipo} onChange={(e) => setTipoEquipo(e.target.value)}>
            <option value="">Todos</option>
            {tipos.map((t, idx) => (
              <option key={t.id || idx} value={t.nombre}>{t.nombre}</option>
            ))}
          </select>
        </div>
        <div>
          <div className="text-sm text-gray-600">&nbsp;</div>
          <label className="inline-flex items-center gap-2 mt-1">
            <input type="checkbox" className="h-4 w-4" checked={slaExclDer} onChange={(e)=>setSlaExclDer(e.target.checked)} />
            <span className="text-sm">Excluir derivados del SLA</span>
          </label>
        </div>
        <div className="md:col-span-6 flex gap-2 flex-wrap">
          <button onClick={exportTablasCSV} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar tablas (CSV)</button>
          <button onClick={() => exportSeriesCSV('monthly')} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar series mensuales (CSV)</button>
          <button onClick={() => exportSeriesCSV('yearly')} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar series anuales (CSV)</button>
          <button onClick={exportDetalleTecnicoMensual} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar detalle mensual por tcnico</button>
          <button onClick={exportDetalleMarcaMensual} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar detalle mensual por marca</button>
          <button onClick={exportDetalleTipoMensual} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar detalle mensual por tipo</button>
          <button onClick={exportCalibracionCSV} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar calibracin (CSV)</button>
        </div>
      </div>

      {loading && <div className="text-gray-500">Cargando mtricas</div>}
      {error && (
        <div className="text-red-600">Error al cargar mtricas: {error}</div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              label="MTTR promedio (das)"
              value={data.mttr_dias != null ? Number(data.mttr_dias).toFixed(1) : "-"}
              help="Desde iniciar reparacin hasta reparado"
            />
            <StatCard
              label="SLA diagnstico < 24h"
              value={formatPct(data.sla_diag_24h?.cumplimiento || 0)}
              help={`${data.sla_diag_24h?.dentro || 0} de ${data.sla_diag_24h?.total || 0}`}
            />
            <StatCard
              label="Aprobacin presupuestos"
              value={formatPct(data.aprob_presupuestos?.tasa || 0)}
              help={`${data.aprob_presupuestos?.aprobados || 0} de ${data.aprob_presupuestos?.emitidos || 0}`}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              label="Derivados externos (WIP)"
              value={data?.derivaciones?.wip_externo ?? 0}
              help="Estado derivado/en_servicio"
            />
            <StatCard
              label="Derivados (en periodo)"
              value={data?.derivaciones?.derivados_periodo ?? 0}
            />
            <StatCard
              label="Devueltos (en periodo)"
              value={data?.derivaciones?.devueltos_periodo ?? 0}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <StatCard
              label="Derivacin  Devuelto (das)"
              value={data?.derivaciones?.t_deriv_a_devuelto_dias != null ? data.derivaciones.t_deriv_a_devuelto_dias.toFixed(1) : "-"}
            />
            <StatCard
              label="Devuelto  Entregado (das)"
              value={data?.derivaciones?.t_devuelto_a_entregado_dias != null ? data.derivaciones.t_devuelto_a_entregado_dias.toFixed(1) : "-"}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h2 className="font-semibold mb-2">Cerrados por tcnico (7 das)</h2>
              <div className="border rounded bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-600">
                      <th className="text-left p-2">Tcnico</th>
                      <th className="text-right p-2">Cerrados</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cerrados7.length === 0 && (
                      <tr><td colSpan={2} className="p-3 text-gray-500">Sin datos</td></tr>
                    )}
                    {cerrados7.map((r) => (
                      <tr key={`c7-${r.tecnico_id}`} className="border-t">
                        <td className="p-2">{r.tecnico_nombre || '(sin asignar)'}</td>
                        <td className="p-2 text-right">{r.cerrados}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h2 className="font-semibold mb-2">WIP por tcnico</h2>
              <div className="border rounded bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-600">
                      <th className="text-left p-2">Tcnico</th>
                      <th className="text-right p-2">En curso</th>
                    </tr>
                  </thead>
                  <tbody>
                    {wip.length === 0 && (
                      <tr><td colSpan={2} className="p-3 text-gray-500">Sin datos</td></tr>
                    )}
                    {wip.map((r) => (
                      <tr key={`wip-${r.tecnico_id}`} className="border-t">
                        <td className="p-2">{r.tecnico_nombre || '(sin asignar)'}</td>
                        <td className="p-2 text-right">{r.wip}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div>
            <h2 className="font-semibold mb-2">Cerrados por tcnico (30 das)</h2>
            <div className="border rounded bg-white">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-600">
                    <th className="text-left p-2">Tcnico</th>
                    <th className="text-right p-2">Cerrados</th>
                  </tr>
                </thead>
                <tbody>
                  {cerrados30.length === 0 && (
                    <tr><td colSpan={2} className="p-3 text-gray-500">Sin datos</td></tr>
                  )}
                  {cerrados30.map((r) => (
                    <tr key={`c30-${r.tecnico_id}`} className="border-t">
                      <td className="p-2">{r.tecnico_nombre || '(sin asignar)'}</td>
                      <td className="p-2 text-right">{r.cerrados}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            <div>
              <h2 className="font-semibold mb-2">Facturacin aprobada por tcnico</h2>
              <div className="border rounded bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-600">
                      <th className="text-left p-2">Tcnico</th>
                      <th className="text-right p-2">$ Aprobado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.facturacion_por_tecnico || []).length === 0 && (
                      <tr><td colSpan={2} className="p-3 text-gray-500">Sin datos</td></tr>
                    )}
                    {(data?.facturacion_por_tecnico || []).map((r) => (
                      <tr key={`fac-${r.tecnico_id}`} className="border-t">
                        <td className="p-2">{r.tecnico_nombre || '(sin asignar)'}</td>
                        <td className="p-2 text-right">{Number(r.facturacion || 0).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h2 className="font-semibold mb-2">Utilidad estimada (mano de obra)</h2>
              <div className="border rounded bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-600">
                      <th className="text-left p-2">Tcnico</th>
                      <th className="text-right p-2">$ MO</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.utilidad_mo_por_tecnico || []).length === 0 && (
                      <tr><td colSpan={2} className="p-3 text-gray-500">Sin datos</td></tr>
                    )}
                    {(data?.utilidad_mo_por_tecnico || []).map((r) => (
                      <tr key={`umo-${r.tecnico_id}`} className="border-t">
                        <td className="p-2">{r.tecnico_nombre || '(sin asignar)'}</td>
                        <td className="p-2 text-right">{Number(r.utilidad_mo || 0).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            <div>
              <h2 className="font-semibold mb-2">Repuestos facturados por tcnico</h2>
              <div className="border rounded bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-600">
                      <th className="text-left p-2">Tcnico</th>
                      <th className="text-right p-2">$ Repuestos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.repuestos_por_tecnico || []).length === 0 && (
                      <tr><td colSpan={2} className="p-3 text-gray-500">Sin datos</td></tr>
                    )}
                    {(data?.repuestos_por_tecnico || []).map((r) => (
                      <tr key={`rep-${r.tecnico_id}`} className="border-t">
                        <td className="p-2">{r.tecnico_nombre || '(sin asignar)'}</td>
                        <td className="p-2 text-right">{Number(r.ingreso_repuestos || 0).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {series && (
            <>
              {/* Grficos ligeros */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <MiniSpark title="Entregados" values={(series.monthly||[]).map(m=>m.entregados||0)} fmt={(v)=>v} />
                <MiniSpark title="MTTR (das)" values={(series.monthly||[]).map(m=>m.mttr_dias||0)} fmt={(v)=>v?.toFixed(1)} />
                <MiniSpark title="SLA diag 24h (%)" values={(series.monthly||[]).map(m=>Math.round((m.sla_diag_24h?.cumplimiento||0)*100))} fmt={(v)=>`${v}%`} />
              </div>
              
              <div className="mt-8">
                <h2 className="font-semibold mb-2">Tendencias mensuales</h2>
                <div className="overflow-x-auto border rounded bg-white">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 text-gray-600">
                        <th className="p-2 text-left">Periodo</th>
                        <th className="p-2 text-right">Entregados</th>
                        <th className="p-2 text-right">MTTR (das)</th>
                        <th className="p-2 text-right">SLA diag 24h</th>
                        <th className="p-2 text-right">T. emitir (h)</th>
                        <th className="p-2 text-right">T. aprobar (h)</th>
                        <th className="p-2 text-right">Derivados ext</th>
                        <th className="p-2 text-right">Devueltos ext</th>
                        <th className="p-2 text-right">T derivdev (d)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(series.monthly || []).map((m) => (
                        <tr className="border-t" key={m.period}>
                          <td className="p-2">{m.period}</td>
                          <td className="p-2 text-right">{m.entregados}</td>
                          <td className="p-2 text-right">{m.mttr_dias != null ? m.mttr_dias.toFixed(1) : '-'}</td>
                          <td className="p-2 text-right">{formatPct(m.sla_diag_24h?.cumplimiento || 0)}</td>
                          <td className="p-2 text-right">{m.aprob_presupuestos?.t_emitir_horas != null ? m.aprob_presupuestos.t_emitir_horas.toFixed(1) : '-'}</td>
                          <td className="p-2 text-right">{m.aprob_presupuestos?.t_aprobar_horas != null ? m.aprob_presupuestos.t_aprobar_horas.toFixed(1) : '-'}</td>
                          <td className="p-2 text-right">{m.externo?.derivados ?? 0}</td>
                          <td className="p-2 text-right">{m.externo?.devueltos ?? 0}</td>
                          <td className="p-2 text-right">{m.externo?.t_deriv_a_devuelto_dias != null ? m.externo.t_deriv_a_devuelto_dias.toFixed(1) : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="mt-8">
                <h2 className="font-semibold mb-2">Tendencias anuales</h2>
                <div className="overflow-x-auto border rounded bg-white">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 text-gray-600">
                        <th className="p-2 text-left">Ao</th>
                        <th className="p-2 text-right">Entregados</th>
                        <th className="p-2 text-right">MTTR (das)</th>
                        <th className="p-2 text-right">SLA diag 24h</th>
                        <th className="p-2 text-right">T. emitir (h)</th>
                        <th className="p-2 text-right">T. aprobar (h)</th>
                        <th className="p-2 text-right">Derivados ext</th>
                        <th className="p-2 text-right">Devueltos ext</th>
                        <th className="p-2 text-right">T derivdev (d)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(series.yearly || []).map((m) => (
                        <tr className="border-t" key={m.period}>
                          <td className="p-2">{m.period}</td>
                          <td className="p-2 text-right">{m.entregados}</td>
                          <td className="p-2 text-right">{m.mttr_dias != null ? m.mttr_dias.toFixed(1) : '-'}</td>
                          <td className="p-2 text-right">{formatPct(m.sla_diag_24h?.cumplimiento || 0)}</td>
                          <td className="p-2 text-right">{m.aprob_presupuestos?.t_emitir_horas != null ? m.aprob_presupuestos.t_emitir_horas.toFixed(1) : '-'}</td>
                          <td className="p-2 text-right">{m.aprob_presupuestos?.t_aprobar_horas != null ? m.aprob_presupuestos.t_aprobar_horas.toFixed(1) : '-'}</td>
                          <td className="p-2 text-right">{m.externo?.derivados ?? 0}</td>
                          <td className="p-2 text-right">{m.externo?.devueltos ?? 0}</td>
                          <td className="p-2 text-right">{m.externo?.t_deriv_a_devuelto_dias != null ? m.externo.t_deriv_a_devuelto_dias.toFixed(1) : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

function MiniSpark({ title, values = [], fmt = (v)=>v }) {
  const w = 300, h = 60, p = 6;
  const n = values.length;
  const max = values.reduce((m,v)=>Math.max(m, v||0), 0) || 1;
  const pts = values.map((v,i)=>{
    const x = p + (i*(w-2*p))/Math.max(1, n-1);
    const y = h - p - ((v||0)/max)*(h-2*p);
    return `${x},${y}`;
  }).join(" ");
  const last = values[n-1] || 0;
  return (
    <div className="p-3 border rounded bg-white">
      <div className="text-sm text-gray-600 flex justify-between">
        <span>{title}</span>
        <span className="font-semibold">{fmt(last)}</span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-16 mt-1">
        <polyline fill="none" stroke="#3b82f6" strokeWidth="2" points={pts} />
      </svg>
    </div>
  );
}

