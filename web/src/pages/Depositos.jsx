import { useEffect, useMemo, useState } from "react";
import { getUbicaciones, getGeneralEquipos } from "../lib/api";
import { ingresoIdOf, formatOS, formatDateTime, tipoEquipoOf } from "../lib/ui-helpers";
import { useNavigate } from "react-router-dom";
import useQueryState from "../hooks/useQueryState";

const numeroInternoOf = (row, fallback = "-") => {
  if (!row) return fallback;
  const raw = row?.numero_interno ?? row?.equipo?.numero_interno ?? "";
  const value = String(raw ?? "").trim();
  return value || fallback;
};

const numeroSerieOf = (row, fallback = "-") => {
  if (!row) return fallback;
  const raw = row?.numero_serie ?? row?.equipo?.numero_serie ?? "";
  const value = String(raw ?? "").trim();
  return value || fallback;
};

export default function Depositos() {
  const [ubicaciones, setUbicaciones] = useState([]);
  const [ubicacionId, setUbicacionId] = useQueryState("ubicacion_id", "");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const nav = useNavigate();

  useEffect(() => {
    getUbicaciones().then(setUbicaciones).catch(e => setErr(e.message||"Error ubicaciones"));
  }, []);

  const ubicacionesFiltradas = useMemo(() => {
    const banned = new Set(["-", "alquilado", "desguace"]);
    return (ubicaciones || []).filter(u => !banned.has(String(u?.nombre || "").toLowerCase().trim()));
  }, [ubicaciones]);

  const ubicacionNombre = useMemo(() => {
    const u = ubicacionesFiltradas.find(x => String(x.id) === String(ubicacionId));
    return u?.nombre || "";
  }, [ubicacionesFiltradas, ubicacionId]);

  useEffect(() => {
    if (!ubicacionId) { setRows([]); return; }
    (async () => {
      setLoading(true); setErr("");
      try {
        const params = {};
        if (ubicacionId === "bajas") {
          params["estado"] = "baja";
        } else if (ubicacionNombre) {
          // La API filtra por nombre (param "ubicacion"), no por id
          params["ubicacion"] = ubicacionNombre;
        }
        const data = await getGeneralEquipos(params);
        setRows(data);
      } catch (e) {
        setErr(e.message || "Error cargando equipos");
      } finally { setLoading(false); }
    })();
  }, [ubicacionId, ubicacionNombre]);

  return (
    <div className="p-4 w-full max-w-screen-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-3">Depósitos/Bajas</h1>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm">Depósito / Ubicación:</span>
        <select className="border rounded p-2" value={ubicacionId} onChange={(e)=>setUbicacionId(e.target.value)}>
          <option value="">Elegí una Ubicación</option>
          <option value="bajas">Bajas</option>
          {ubicacionesFiltradas.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
        </select>
      </div>
      {err && <div className="bg-red-100 text-red-700 border border-red-300 p-2 rounded mb-2">{err}</div>}
      {loading ? "Cargando..." :
        rows.length === 0 ? <div className="text-sm text-gray-500">Sin resultados.</div> :
        <div className="overflow-auto">
          <table className="min-w-full border">
            <thead>
              <tr className="bg-gray-50">
                <th className="p-2 text-left">OS</th>
                <th className="p-2 text-left">Cliente</th>
                <th className="p-2 text-left">Marca</th>
                <th className="p-2 text-left">Modelo</th>
                <th className="p-2 text-left">Tipo</th>
                <th className="p-2 text-left min-w-[180px] whitespace-nowrap">N° Interno</th>
                <th className="p-2 text-left">N° Serie</th>
                <th className="p-2 text-left">Estado</th>
                <th className="p-2 text-left">Fecha ingreso</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={ingresoIdOf(r)} className="hover:bg-gray-100 cursor-pointer" onClick={()=>nav(`/ingresos/${ingresoIdOf(r)}`)}>
                  <td className="p-2">{formatOS(r)}</td>
                  <td className="p-2">{r.razon_social}</td>
                  <td className="p-2">{r.marca}</td>
                  <td className="p-2">{r.modelo}</td>
                  <td className="p-2">{tipoEquipoOf(r)}</td>
                  <td className="p-2 min-w-[180px] whitespace-nowrap">{numeroInternoOf(r)}</td>
                  <td className="p-2">{numeroSerieOf(r)}</td>
                  <td className="p-2">{r.estado}</td>
                  <td className="p-2">{formatDateTime(r.fecha_ingreso)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>}
    </div>
  );
}
