import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getMetricasResumen, getMetricasSeries, getTecnicos, getMarcas, getTiposEquipo, getMetricasCalibracion } from "../lib/api";
import { METRICAS_DESDE_MIN, clampDesdeMin } from "../lib/constants";
import ConfigPanel from "../components/metricas/ConfigPanel.jsx";
import SimpleBars from "../components/metricas/charts/SimpleBars.jsx";
import SimpleLine from "../components/metricas/charts/SimpleLine.jsx";
import BoxPlot from "../components/metricas/charts/BoxPlot.jsx";

function formatPct(n) {
  if (n == null || isNaN(n)) return "-";
  return `${(n * 100).toFixed(0)}%`;
}

function StatCard({ label, value, help, status }) {
  const dot = status === 'good' ? 'bg-emerald-500' : status === 'warn' ? 'bg-amber-500' : status === 'bad' ? 'bg-red-500' : 'bg-gray-300';
  return (
    <div className="p-4 border rounded bg-white">
      <div className="text-sm text-gray-500 flex items-center gap-2">
        <span className={`inline-block w-2 h-2 rounded-full ${dot}`}></span>
        <span>{label}</span>
      </div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      {help ? <div className="text-xs text-gray-400 mt-1">{help}</div> : null}
    </div>
  );
}

export default function Metricas() {
  const { user } = useAuth();
  const [search, setSearch] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [series, setSeries] = useState(null);
  const [calib, setCalib] = useState(null);
  const [tecnicos, setTecnicos] = useState([]);
  const [marcas, setMarcas] = useState([]);
  const [tipos, setTipos] = useState([]);
  const [tecnicoId, setTecnicoId] = useState(search.get('tecnico_id') || "");
  const [marcaId, setMarcaId] = useState(search.get('marca_id') || "");
  const [tipoEquipo, setTipoEquipo] = useState(search.get('tipo_equipo') || "");
  const [desde, setDesde] = useState(() => {
    const s = search.get('from');
    if (s) return clampDesdeMin(s);
    const d = new Date(); d.setDate(d.getDate() - 30);
    return clampDesdeMin(d.toISOString().slice(0, 10));
  });
  const [hasta, setHasta] = useState(() => search.get('to') || new Date().toISOString().slice(0, 10));
  const [slaExclDer, setSlaExclDer] = useState(() => {
    const v = search.get('sla_excluir_derivados');
    return v ? v === '1' : true; // por defecto: excluir derivados
  });
  const [configOpen, setConfigOpen] = useState(() => search.get('config') === '1' || (location?.pathname || '').endsWith('/metricas/config'));
  const [targets, setTargets] = useState(()=>{ try { return JSON.parse(localStorage.getItem('metricas_targets')||'{}')||{}; } catch { return {}; } });
  const [showCharts, setShowCharts] = useState(() => (search.get('view') || '') === 'charts');
  const [presets, setPresets] = useState(()=>{ try { return JSON.parse(localStorage.getItem('metricas_presets')||'[]')||[]; } catch { return []; } });
  const [presetSel, setPresetSel] = useState('');
  const [presetName, setPresetName] = useState('');

  useEffect(() => {
    // cargar filtros
    getTecnicos().then(setTecnicos).catch(() => {});
    getMarcas().then(setMarcas).catch(() => {});
    getTiposEquipo().then(setTipos).catch(() => {});
  }, []);

  const desdeClamped = useMemo(() => clampDesdeMin(desde), [desde]);

  // Sincronizar filtros en la URL
  useEffect(() => {
    const next = new URLSearchParams(search.toString());
    next.set('from', desdeClamped);
    next.set('to', hasta);
    if (tecnicoId) next.set('tecnico_id', tecnicoId); else next.delete('tecnico_id');
    if (marcaId) next.set('marca_id', marcaId); else next.delete('marca_id');
    if (tipoEquipo) next.set('tipo_equipo', tipoEquipo); else next.delete('tipo_equipo');
    if (slaExclDer) next.set('sla_excluir_derivados', '1'); else next.delete('sla_excluir_derivados');
    if (showCharts) next.set('view', 'charts'); else next.delete('view');
    setSearch(next, { replace: true });
  }, [desdeClamped, hasta, tecnicoId, marcaId, tipoEquipo, slaExclDer, showCharts]);

  // Abrir/cerrar config por query o ruta
  useEffect(() => {
    const shouldOpen = search.get('config') === '1' || (location?.pathname || '').endsWith('/metricas/config');
    setConfigOpen(!!shouldOpen);
  }, [search, location?.pathname]);

  function openConfig() {
    const next = new URLSearchParams(search.toString());
    next.set('config', '1');
    setSearch(next, { replace: false });
    setConfigOpen(true);
  }
  function closeConfig() {
    const next = new URLSearchParams(search.toString());
    next.delete('config');
    setSearch(next, { replace: true });
    setConfigOpen(false);
  }
  useEffect(() => {
    // recargar objetivos al abrir/cerrar
    try { setTargets(JSON.parse(localStorage.getItem('metricas_targets')||'{}')||{}); } catch {}
  }, [configOpen]);
  function statusFor(value, target, higherIsBetter = false) {
    if (target == null || isNaN(target) || value == null || isNaN(value)) return null;
    const v = Number(value), t = Number(target);
    if (higherIsBetter) {
      if (v >= t) return 'good';
      if (v >= t*0.8) return 'warn';
      return 'bad';
    } else {
      if (v <= t) return 'good';
      if (v <= t*1.2) return 'warn';
      return 'bad';
    }
  }
  function monthRange(period) {
    const [y,m] = String(period||'').split('-').map(Number);
    if (!y || !m) return { from: '', to: '' };
    const from = new Date(Date.UTC(y, m-1, 1));
    const to = new Date(Date.UTC(y, m, 0));
    const iso = d => new Date(d).toISOString().slice(0,10);
    return { from: iso(from), to: iso(to) };
  }
  function drillToDelivered(period) {
    const {from,to} = monthRange(period);
    if (from && to) navigate(`/equipos?from=${from}&to=${to}&delivered=1`);
  }

  function reloadPresets(){ try { setPresets(JSON.parse(localStorage.getItem('metricas_presets')||'[]')||[]); } catch {} }
  function savePreset(){
    const name = (presetName || '').trim(); if(!name) return;
    const obj = { name, filters: { from: desdeClamped, to: hasta, tecnicoId, marcaId, tipoEquipo, slaExclDer } };
    const list = presets.filter(p=>p.name!==name).concat([obj]);
    localStorage.setItem('metricas_presets', JSON.stringify(list));
    setPresets(list); setPresetSel(name); setPresetName('');
  }
  function applyPreset(){
    const p = presets.find(p=>p.name===presetSel); if(!p) return;
    const f = p.filters||{};
    setDesde(f.from || desde);
    setHasta(f.to || hasta);
    setTecnicoId(f.tecnicoId || "");
    setMarcaId(f.marcaId || "");
    setTipoEquipo(f.tipoEquipo || "");
    setSlaExclDer(!!f.slaExclDer);
  }
  function deletePreset(){
    if(!presetSel) return; const list = presets.filter(p=>p.name!==presetSel);
    localStorage.setItem('metricas_presets', JSON.stringify(list));
    setPresets(list); setPresetSel('');
  }

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    const params = { from: desdeClamped, to: hasta };
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
    const params = { from: desdeClamped, to: hasta };
    if (tecnicoId) params.tecnico_id = tecnicoId;
    if (marcaId) params.marca_id = marcaId;
    if (tipoEquipo) params.tipo_equipo = tipoEquipo;
    if (slaExclDer) params.sla_excluir_derivados = 1;
    getMetricasSeries(params)
      .then((res) => { if (alive) setSeries(res); })
      .catch(() => { /* silencio */ });
    return () => { alive = false; };
  }, [desde, hasta, tecnicoId, marcaId, tipoEquipo]);

  // Calibración (percentiles) para mostrar en UI
  useEffect(() => {
    let alive = true;
    setCalib(null);
    const params = { from: desdeClamped, to: hasta };
    if (tecnicoId) params.tecnico_id = tecnicoId;
    if (marcaId) params.marca_id = marcaId;
    if (tipoEquipo) params.tipo_equipo = tipoEquipo;
    if (slaExclDer) params.sla_excluir_derivados = 1;
    getMetricasCalibracion(params)
      .then((res)=>{ if (alive) setCalib(res); })
      .catch(()=>{});
    return () => { alive = false; };
  }, [desde, hasta, tecnicoId, marcaId, tipoEquipo, slaExclDer]);

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
    downloadCSV(`metricas_tablas_${desdeClamped}_${hasta}.csv`, rows);
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
    downloadCSV(`metricas_series_${kind}_${desdeClamped}_${hasta}.csv`, rows);
  }

  async function exportDetalleTecnicoMensual() {
    const params = { from: desdeClamped, to: hasta, group: 'tecnico' };
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
    downloadCSV(`metricas_detalle_tecnico_mensual_${desdeClamped}_${hasta}.csv`, rows);
  }

  async function exportDetalleMarcaMensual() {
    const params = { from: desdeClamped, to: hasta, group: 'marca' };
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
      downloadCSV(`metricas_detalle_marca_mensual_${desdeClamped}_${hasta}.csv`, rows);
    });
  }

  async function exportDetalleTipoMensual() {
    const params = { from: desdeClamped, to: hasta, group: 'tipo' };
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
      downloadCSV(`metricas_detalle_tipo_mensual_${desdeClamped}_${hasta}.csv`, rows);
    });
  }

  async function exportCalibracionCSV() {
    const params = { from: desdeClamped, to: hasta };
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
    downloadCSV(`metricas_calibracion_${desdeClamped}_${hasta}.csv`, rows);
  }

  const cerrados7 = useMemo(() => data?.cerrados_por_tecnico_7d || [], [data]);
  const cerrados30 = useMemo(() => data?.cerrados_por_tecnico_30d || [], [data]);
  const wip = useMemo(() => data?.wip_por_tecnico || [], [data]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Métricas</h1>
        <div className="flex items-center gap-2">
          <Link to="/metricas/clientes" className="text-blue-600 hover:underline">Ver métricas por clientes</Link>
          <button onClick={openConfig} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Configurar</button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-6 gap-3 items-end">
        <div>
          <div className="text-sm text-gray-600">Desde</div>
          <input
            type="date"
            value={desdeClamped}
            min={METRICAS_DESDE_MIN}
            onChange={(e) => setDesde(clampDesdeMin(e.target.value))}
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
          <div className="text-sm text-gray-600">Técnico</div>
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
          <div className="mr-2 inline-flex border rounded overflow-hidden">
            <button
              onClick={() => setShowCharts(false)}
              className={`px-3 py-1.5 ${!showCharts ? 'bg-gray-100 font-semibold' : 'bg-white hover:bg-gray-50'}`}
            >Tablas</button>
            <button
              onClick={() => setShowCharts(true)}
              className={`px-3 py-1.5 border-l ${showCharts ? 'bg-gray-100 font-semibold' : 'bg-white hover:bg-gray-50'}`}
            >Gráficos</button>
          </div>
          <button onClick={exportTablasCSV} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar tablas (CSV)</button>
          <button onClick={() => exportSeriesCSV('monthly')} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar series mensuales (CSV)</button>
          <button onClick={() => exportSeriesCSV('yearly')} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar series anuales (CSV)</button>
          <button onClick={exportDetalleTecnicoMensual} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar detalle mensual por técnico</button>
          <button onClick={exportDetalleMarcaMensual} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar detalle mensual por marca</button>
          <button onClick={exportDetalleTipoMensual} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar detalle mensual por tipo</button>
          <button onClick={exportCalibracionCSV} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar calibración (CSV)</button>
        </div>
      </div>

      {loading && <div className="text-gray-500">Cargando métricas</div>}
      {error && (
        <div className="text-red-600">Error al cargar métricas: {error}</div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              label="MTTR promedio (días)"
              value={data.mttr_dias != null ? Number(data.mttr_dias).toFixed(1) : "-"}
              status={statusFor(data.mttr_dias != null ? Number(data.mttr_dias) : null, targets?.mttr_days, false)}
              help="Desde iniciar reparación hasta reparado"
            />
            <StatCard
              label="SLA diagnóstico < 24h"
              value={formatPct(data.sla_diag_24h?.cumplimiento || 0)}
              status={statusFor(((data.sla_diag_24h?.cumplimiento || 0)*100), targets?.sla_diag_pct, true)}
              help={`${data.sla_diag_24h?.dentro || 0} de ${data.sla_diag_24h?.total || 0}`}
            />
            <StatCard
              label="Aprobación presupuestos"
              value={formatPct(data.aprob_presupuestos?.tasa || 0)}
              status={statusFor(((data.aprob_presupuestos?.tasa || 0)*100), targets?.aprob_pres_pct, true)}
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
              label="Derivación  Devuelto (días)"
              value={data?.derivaciones?.t_deriv_a_devuelto_dias != null ? data.derivaciones.t_deriv_a_devuelto_dias.toFixed(1) : "-"}
            />
            <StatCard
              label="Devuelto  Entregado (días)"
              value={data?.derivaciones?.t_devuelto_a_entregado_dias != null ? data.derivaciones.t_devuelto_a_entregado_dias.toFixed(1) : "-"}
            />
          </div>

          {data?.wip_aging_buckets && (
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <StatCard label="WIP 0–2 días" value={data.wip_aging_buckets["0-2"] ?? 0} />
              <StatCard label="WIP 3–5 días" value={data.wip_aging_buckets["3-5"] ?? 0} />
              <StatCard label="WIP 6–10 días" value={data.wip_aging_buckets["6-10"] ?? 0} />
              <StatCard label="WIP 11–15 días" value={data.wip_aging_buckets["11-15"] ?? 0} />
              <StatCard label="WIP 16+ días" value={data.wip_aging_buckets["16+"] ?? 0} />
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h2 className="font-semibold mb-2">Cerrados por técnico (7 días)</h2>
              <div className="border rounded bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-600">
                      <th className="text-left p-2">Técnico</th>
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
              <h2 className="font-semibold mb-2">WIP por técnico</h2>
              <div className="border rounded bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-600">
                      <th className="text-left p-2">Técnico</th>
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
            <h2 className="font-semibold mb-2">Cerrados por técnico (30 días)</h2>
            <div className="border rounded bg-white">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-600">
                    <th className="text-left p-2">Técnico</th>
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
              <h2 className="font-semibold mb-2">Facturación aprobada por técnico</h2>
              <div className="border rounded bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-600">
                      <th className="text-left p-2">Técnico</th>
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
                      <th className="text-left p-2">Técnico</th>
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
              <h2 className="font-semibold mb-2">Repuestos facturados por técnico</h2>
              <div className="border rounded bg-white">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-600">
                      <th className="text-left p-2">Técnico</th>
                      <th className="text-right p-2">$ Repuestos</th>
                    </tr>

          {calib && (
            <div className="mt-6">
              <h2 className="font-semibold mb-2">Calibración (percentiles)</h2>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <StatCard
                  label="Diag en horas hábiles (P50)"
                  value={calib.diag_business_minutes?.p50 != null ? (calib.diag_business_minutes.p50/60).toFixed(1) + ' h' : '-'}
                  help={`P75 ${(calib.diag_business_minutes?.p75/60)?.toFixed(1)||'-'} h • P90 ${(calib.diag_business_minutes?.p90/60)?.toFixed(1)||'-'} h`}
                />
                <StatCard
                  label="Ingreso→Emitir presupuesto (P50)"
                  value={calib.diag_to_emit_hours?.p50 != null ? calib.diag_to_emit_hours.p50.toFixed(1) + ' h' : '-'}
                  help={`P75 ${(calib.diag_to_emit_hours?.p75)?.toFixed(1)||'-'} h • P90 ${(calib.diag_to_emit_hours?.p90)?.toFixed(1)||'-'} h`}
                />
                <StatCard
                  label="Emitir→Aprobar (P50)"
                  value={calib.emit_to_approve_hours?.p50 != null ? calib.emit_to_approve_hours.p50.toFixed(1) + ' h' : '-'}
                  help={`P75 ${(calib.emit_to_approve_hours?.p75)?.toFixed(1)||'-'} h • P90 ${(calib.emit_to_approve_hours?.p90)?.toFixed(1)||'-'} h`}
                />
                <StatCard
                  label="Ingreso→Entregado (P50)"
                  value={calib.ingreso_to_deliver_days?.p50 != null ? calib.ingreso_to_deliver_days.p50.toFixed(1) + ' d' : '-'}
                  help={`P75 ${(calib.ingreso_to_deliver_days?.p75)?.toFixed(1)||'-'} d • P90 ${(calib.ingreso_to_deliver_days?.p90)?.toFixed(1)||'-'} d`}
                />
              </div>
            </div>
          )}
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
              {showCharts && (
                <>
                  <div className="space-y-4">
                    <SimpleBars
                      title="Entregados por mes"
                      categories={(series.monthly||[]).map(m=>m.period)}
                      values={(series.monthly||[]).map(m=>m.entregados||0)}
                      fmt={(v)=>Number(v).toLocaleString()}
                      onClickBar={(i)=>drillToDelivered((series.monthly||[])[i]?.period)}
                    />
                    <SimpleLine
                      title="MTTR (días) y TAT (días)"
                      categories={(series.monthly||[]).map(m=>m.period)}
                      series={[
                        { name: 'MTTR (días)', values: (series.monthly||[]).map(m=>m.mttr_dias||0) },
                        { name: 'TAT ingreso→entrega (días)', values: (series.monthly||[]).map(m=>m.tat_dias||0), color: '#ef4444' },
                      ]}
                      fmt={(v)=>Number(v).toFixed(1)}
                    />
                    <BoxPlot
                      title="MTTR percentiles (mensual)"
                      categories={(series.monthly||[]).map(m=>m.period)}
                      items={(series.monthly||[]).map(m=>({p25:m.mttr_percentiles?.p25, p50:m.mttr_percentiles?.p50, p75:m.mttr_percentiles?.p75, p90:m.mttr_percentiles?.p90, p95:m.mttr_percentiles?.p95}))}
                      onClickBox={(i)=>drillToDelivered((series.monthly||[])[i]?.period)}
                    />
                    <SimpleLine
                      title="Tiempos de presupuesto (h)"
                      categories={(series.monthly||[]).map(m=>m.period)}
                      series={[
                        { name: 'Emitir (h)', values: (series.monthly||[]).map(m=>m.aprob_presupuestos?.t_emitir_horas||0) },
                        { name: 'Aprobar (h)', values: (series.monthly||[]).map(m=>m.aprob_presupuestos?.t_aprobar_horas||0), color: '#f59e0b' },
                      ]}
                      fmt={(v)=>Number(v).toFixed(1)}
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <MiniSpark title="Entregados" values={(series.monthly||[]).map(m=>m.entregados||0)} fmt={(v)=>v} />
                    <MiniSpark title="MTTR (días)" values={(series.monthly||[]).map(m=>m.mttr_dias||0)} fmt={(v)=>Number(v).toFixed(1)} />
                    <MiniSpark title="SLA diag 24h (%)" values={(series.monthly||[]).map(m=>Math.round((m.sla_diag_24h?.cumplimiento||0)*100))} fmt={(v)=>`${v}%`} />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
                    <MiniSpark title="T emitir presupuesto (h)" values={(series.monthly||[]).map(m=>m.aprob_presupuestos?.t_emitir_horas||0)} fmt={(v)=>Number(v).toFixed(1)} />
                    <MiniSpark title="T aprobar presupuesto (h)" values={(series.monthly||[]).map(m=>m.aprob_presupuestos?.t_aprobar_horas||0)} fmt={(v)=>Number(v).toFixed(1)} />
                    <MiniSpark title="Derivados externos (mensual)" values={(series.monthly||[]).map(m=>m.externo?.derivados||0)} fmt={(v)=>v} />
                  </div>
                </>
              )}

              {!showCharts && (
              <div className="mt-8">
                <h2 className="font-semibold mb-2">Tendencias mensuales</h2>
                <div className="overflow-x-auto border rounded bg-white">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 text-gray-600">
                        <th className="p-2 text-left">Periodo</th>
                        <th className="p-2 text-right">Entregados</th>
                        <th className="p-2 text-right">MTTR (días)</th>
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
              )}

              {!showCharts && (
              <div className="mt-8">
                <h2 className="font-semibold mb-2">Tendencias anuales</h2>
                <div className="overflow-x-auto border rounded bg-white">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50 text-gray-600">
                        <th className="p-2 text-left">Año</th>
                        <th className="p-2 text-right">Entregados</th>
                        <th className="p-2 text-right">MTTR (días)</th>
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
              )}
            </>
          )}
        </>
      )}
      <ConfigPanel open={configOpen} onClose={closeConfig} />
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




