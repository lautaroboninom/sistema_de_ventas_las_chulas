import { useEffect, useState } from "react";
import { getMetricasConfig, getFeriados, postFeriado, deleteFeriado } from "../lib/api";

export default function ConfigMetricas() {
  const [cfg, setCfg] = useState(null);
  const [feriados, setFeriados] = useState([]);
  const [fecha, setFecha] = useState("");
  const [nombre, setNombre] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    getMetricasConfig().then(setCfg).catch(e => setErr(e.message||String(e)));
    getFeriados().then(setFeriados).catch(()=>setFeriados([]));
  }, []);

  async function addFeriado(e) {
    e.preventDefault();
    setErr("");
    try {
      if (!fecha) return;
      await postFeriado(fecha, nombre || "Feriado");
      setFecha(""); setNombre("");
      const rows = await getFeriados();
      setFeriados(rows);
    } catch (ex) {
      setErr(ex.message||String(ex));
    }
  }

  async function removeFeriado(f) {
    if (!confirm(`Eliminar feriado ${f.fecha}?`)) return;
    await deleteFeriado(f.fecha);
    const rows = await getFeriados();
    setFeriados(rows);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Configurar Mtricas</h1>
      {err && <div className="text-red-600 text-sm">{err}</div>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 border rounded bg-white">
          <div className="text-sm text-gray-500">Pas feriados</div>
          <div className="text-lg font-semibold">{cfg?.holidays_country || 'AR'}</div>
          <div className="text-xs text-gray-400 mt-1">Fuente automtica: Nager.Date</div>
        </div>
        <div className="p-4 border rounded bg-white">
          <div className="text-sm text-gray-500">Horario laboral</div>
          <div className="text-lg font-semibold">{cfg ? `${cfg.workday_start_hour}:00${cfg.workday_end_hour}:00` : '-'}</div>
          <div className="text-xs text-gray-400 mt-1">Das hbiles: {(cfg?.workdays||[]).join(', ')}</div>
        </div>
        <div className="p-4 border rounded bg-white">
          <div className="text-sm text-gray-500">SLA diagnstico</div>
          <div className="text-lg font-semibold">Excluir derivados por defecto</div>
          <div className="text-xs text-gray-400 mt-1">Se puede sobreescribir en la vista Mtricas</div>
        </div>
      </div>

      <div>
        <h2 className="font-semibold mb-2">Feriados locales (extras)</h2>
        <p className="text-sm text-gray-500 mb-2">Los feriados oficiales se toman automticamente. Aqu agregs excepciones locales que aplican a horas hbiles.</p>
        <form onSubmit={addFeriado} className="flex gap-2 items-end">
          <div>
            <div className="text-sm text-gray-600">Fecha</div>
            <input type="date" value={fecha} onChange={e=>setFecha(e.target.value)} className="mt-1 border rounded px-2 py-1" />
          </div>
          <div>
            <div className="text-sm text-gray-600">Nombre</div>
            <input type="text" value={nombre} onChange={e=>setNombre(e.target.value)} placeholder="Feriado local" className="mt-1 border rounded px-2 py-1" />
          </div>
          <button type="submit" className="px-3 py-1.5 border rounded bg-white hover:bg-gray-50">Agregar</button>
        </form>

        <div className="mt-3 border rounded bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-gray-600">
                <th className="p-2 text-left">Fecha</th>
                <th className="p-2 text-left">Nombre</th>
                <th className="p-2"></th>
              </tr>
            </thead>
            <tbody>
              {(feriados||[]).length === 0 && (
                <tr><td colSpan={3} className="p-3 text-gray-500">Sin feriados locales</td></tr>
              )}
              {(feriados||[]).map((f) => (
                <tr key={f.fecha} className="border-t">
                  <td className="p-2">{f.fecha}</td>
                  <td className="p-2">{f.nombre}</td>
                  <td className="p-2 text-right">
                    <button onClick={()=>removeFeriado(f)} className="px-2 py-1 border rounded hover:bg-gray-50">Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}


