//web\src\pages\StockAlquiler.jsx

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getGeneralEquipos } from "../lib/api";
import { ingresoIdOf, formatOS, norm } from "../lib/ui-helpers";

// Catálogo (DB):
const TARGET_ID = 2;
const TARGET_NAME = "Estantería alquileres";
const isStockAlquiler = (r) => {
  const id = Number(r?.ubicacion_id ?? NaN);
  const name = r?.ubicacion_nombre;
  return id === TARGET_ID || norm(name) === norm(TARGET_NAME);
};

export default function StockAlquiler() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState("");
  const nav = useNavigate();

  useEffect(() => {
    // ⛑️ Si no hay token (p. ej., estás en /login), no llamamos a la API
    const tok = localStorage.getItem("token");
    if (!tok) { setLoading(false); return; }

    (async () => {
      setErr(""); setLoading(true);
      try {
        // Intento server-side: por ubicacion_id
        let data = await getGeneralEquipos({ ubicacion_id: TARGET_ID });
        if (!Array.isArray(data) || data.length === 0) {
          // Fallback: traer todo y filtrar en cliente
          data = await getGeneralEquipos({});
        }
        const safe = Array.isArray(data) ? data : [];
        setRows(safe.filter(isStockAlquiler));
      } catch (e) {
        setErr(e?.message || "Error cargando stock");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    const needle = norm(filter);
    if (!needle) return rows;
    return rows.filter(r => {
      const campos = [formatOS(r), r?.marca, r?.modelo, r?.numero_serie, r?.razon_social];
      return campos.some(c => norm(c).includes(needle));
    });
  }, [rows, filter]);

  return (
    <div className="card">
      <div className="h1 mb-3">Stock de Alquiler</div>
      {err && <div className="bg-red-100 text-red-700 p-2 rounded mb-3">{err}</div>}

      <div className="flex items-center gap-2 mb-3">
        <input
          className="border rounded p-2 w-full max-w-md"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filtrar por OS, marca, modelo, serie…"
        />
      </div>

      {loading ? "Cargando..." :
        filtered.length === 0 ? (
          <div className="text-sm text-gray-500">No hay equipos en Estantería alquileres.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left">
                  <th className="p-2">OS</th>
                  <th className="p-2">Marca</th>
                  <th className="p-2">Modelo</th>
                  <th className="p-2">Serie</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr
                    key={ingresoIdOf(row)}
                    className="border-t hover:bg-gray-50 cursor-pointer"
                    onClick={() => nav(`/ingresos/${ingresoIdOf(row)}`)}
                  >
                    <td className="p-2 underline">{formatOS(row)}</td>
                    <td className="p-2">{row.marca}</td>
                    <td className="p-2">{row.modelo}</td>
                    <td className="p-2">{row.numero_serie}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="text-xs text-gray-500 mt-2">Mostrando {filtered.length} equipos.</div>
          </div>
        )}
    </div>
  );
}
