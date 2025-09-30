import { useEffect, useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { getMetricasSeries, getTecnicos, getMarcas, getTiposEquipo } from "../lib/api";

export default function MetricasClientes() {
  const [search, setSearch] = useSearchParams();
  const [desde, setDesde] = useState(() => search.get('from') || (()=>{const d=new Date(); d.setMonth(d.getMonth()-3); return d.toISOString().slice(0,10);})());
  const [hasta, setHasta] = useState(() => search.get('to') || new Date().toISOString().slice(0, 10));
  const [tecnicos, setTecnicos] = useState([]);
  const [marcas, setMarcas] = useState([]);
  const [tipos, setTipos] = useState([]);
  const [tecnicoId, setTecnicoId] = useState(search.get('tecnico_id') || "");
  const [marcaId, setMarcaId] = useState(search.get('marca_id') || "");
  const [tipoEquipo, setTipoEquipo] = useState(search.get('tipo_equipo') || "");
  const [data, setData] = useState(null);

  useEffect(() => {
    getTecnicos().then(setTecnicos).catch(()=>{});
    getMarcas().then(setMarcas).catch(()=>{});
    getTiposEquipo().then(setTipos).catch(()=>{});
  }, []);

  useEffect(() => {
    const next = new URLSearchParams(search.toString());
    next.set('from', desde); next.set('to', hasta);
    if (tecnicoId) next.set('tecnico_id', tecnicoId); else next.delete('tecnico_id');
    if (marcaId) next.set('marca_id', marcaId); else next.delete('marca_id');
    if (tipoEquipo) next.set('tipo_equipo', tipoEquipo); else next.delete('tipo_equipo');
    setSearch(next, { replace: true });
  }, [desde, hasta, tecnicoId, marcaId, tipoEquipo]);

  useEffect(() => {
    const params = { from: desde, to: hasta, group: 'cliente' };
    if (tecnicoId) params.tecnico_id = tecnicoId;
    if (marcaId) params.marca_id = marcaId;
    if (tipoEquipo) params.tipo_equipo = tipoEquipo;
    getMetricasSeries(params).then(setData).catch(()=>{});
  }, [desde, hasta, tecnicoId, marcaId, tipoEquipo]);

  function downloadCSV(filename, rows) {
    const bom = "\uFEFF";
    const csv = rows.map(r => r.map(v => {
      const s = (v==null?"":String(v)).replaceAll('"','""');
      return /[",\n]/.test(s) ? `"${s}"` : s;
    }).join(",")).join("\n");
    const blob = new Blob([bom + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href=url; a.download=filename; a.click(); URL.revokeObjectURL(url);
  }

  function exportClientesCSV() {
    const header = ["period","cliente","entregados","facturacion","mano_obra","repuestos"];
    const key = (p, id) => `${p}:${id}`;
    const map = new Map();
    (data?.by_cliente_monthly || []).forEach(r => {
      const k = key(r.period, r.cliente_id);
      map.set(k, { period: r.period, cliente: r.cliente_nombre, entregados: r.entregados, facturacion: 0, mo: 0, rep: 0 });
    });
    (data?.facturacion_cliente_monthly || []).forEach(r => {
      const k = key(r.period, r.cliente_id);
      const o = map.get(k) || { period: r.period, cliente: r.cliente_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
      o.facturacion = r.facturacion || 0; map.set(k, o);
    });
    (data?.mo_cliente_monthly || []).forEach(r => {
      const k = key(r.period, r.cliente_id);
      const o = map.get(k) || { period: r.period, cliente: r.cliente_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
      o.mo = r.monto_mo || 0; map.set(k, o);
    });
    (data?.repuestos_cliente_monthly || []).forEach(r => {
      const k = key(r.period, r.cliente_id);
      const o = map.get(k) || { period: r.period, cliente: r.cliente_nombre, entregados: 0, facturacion: 0, mo: 0, rep: 0 };
      o.rep = r.monto_repuestos || 0; map.set(k, o);
    });
    const rows = [header, ...Array.from(map.values()).sort((a,b)=> a.period.localeCompare(b.period) || a.cliente.localeCompare(b.cliente)).map(o => [o.period, o.cliente, o.entregados, o.facturacion, o.mo, o.rep])];
    downloadCSV(`metricas_clientes_mensual_${desde}_${hasta}.csv`, rows);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Métricas por clientes</h1>
        <Link to="/metricas" className="text-blue-600 hover:underline">← Volver a Métricas</Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
        <div>
          <div className="text-sm text-gray-600">Desde</div>
          <input type="date" value={desde} onChange={e=>setDesde(e.target.value)} className="mt-1 border rounded px-2 py-1" />
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
        <div className="md:col-span-5">
          <button onClick={exportClientesCSV} className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Exportar por clientes (CSV)</button>
        </div>
      </div>

      <div className="text-sm text-gray-500">Esta vista está centrada en exportar. Si querés visual, abrimos otra iteración con top clientes.</div>
    </div>
  );
}

