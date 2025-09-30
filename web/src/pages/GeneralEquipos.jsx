// web/src/pages/GeneralEquipos.jsx
import { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { useNavigate } from "react-router-dom";
import { ingresoIdOf, formatOS, formatDateTime, norm, tipoEquipoOf, resolveFechaIngreso, resolveFechaCreacion, catalogEquipmentLabel } from "../lib/ui-helpers";


// Ajustá si tu backend usa otra ruta (histórico completo)
const ENDPOINT = "/api/equipos/";


export default function GeneralEquipos() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState("");
  const navigate = useNavigate();

  async function load() {
    try {
      setErr("");
      setLoading(true);
      const data = await api.get(ENDPOINT);
      // Si tu API ya ordena por fecha, podés omitir el sort local:
      const safe = Array.isArray(data) ? data : [];
      safe.sort((a, b) => {
        const da = new Date(resolveFechaCreacion(a) ?? 0).getTime();
        const db = new Date(resolveFechaCreacion(b) ?? 0).getTime();
        return db - da; // más recientes primero
      });
      // Reordenar por OS descendente (mayor a menor)
      safe.sort((a, b) => Number(ingresoIdOf(b) ?? 0) - Number(ingresoIdOf(a) ?? 0));
      setRows(safe);
    } catch (e) {
      setErr(e?.message || "No se pudo cargar el histórico de equipos");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    const needle = norm(filter);
    if (!needle) return rows;
    return rows.filter((row) => {
      const campos = [
        formatOS(row),
        row?.razon_social ?? row?.cliente ?? row?.cliente_nombre,
        row?.marca ?? row?.equipo?.marca,
        catalogEquipmentLabel(row),
        tipoEquipoOf(row),
        row?.estado,
        row?.numero_serie,
        row?.ubicacion_nombre,
      ];
      return campos.some((c) => norm(c).includes(needle));
    });
  }, [rows, filter]);

  const go = (row) => {
    const id = ingresoIdOf(row);
    if (!id) return;
    navigate(`/ingresos/${id}`);
  };

  const onRowKeyDown = (e, row) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      go(row);
    }
  };

  return (
    <div className="card">
      <div className="h1 mb-3">General de equipos (histórico)</div>

      {err && (
        <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-3">
          {err}
        </div>
      )}

      <div className="flex items-center gap-2 mb-3">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filtrar por OS, cliente, marca, equipo, estado, serie…"
          className="border rounded p-2 w-full max-w-md"
          aria-label="Filtrar histórico"
        />
        <button
          className="btn"
          onClick={load}
          title="Recargar lista"
          disabled={loading}
          aria-busy={loading ? "true" : "false"}
        >
          Recargar
        </button>
      </div>

      {loading ? (
        "Cargando..."
      ) : filtered.length === 0 ? (
        <div className="text-sm text-gray-500">
          No hay resultados que coincidan con el filtro.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th scope="col" className="p-2">OS</th>
                <th scope="col" className="p-2">Cliente</th>
                <th scope="col" className="p-2">Equipo</th>
                <th scope="col" className="p-2">Tipo</th>
                <th scope="col" className="p-2">Estado</th>
                <th scope="col" className="p-2">Serie</th>
                <th scope="col" className="p-2">Ubicación</th>
                <th scope="col" className="p-2">Fecha ingreso</th>
                <th scope="col" className="p-2">Fecha entrega</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr
                  key={ingresoIdOf(row)}
                  onClick={() => go(row)}
                  onKeyDown={(e) => onRowKeyDown(e, row)}
                  className="hover:bg-gray-50 cursor-pointer"
                  role="link"
                  tabIndex={0}
                  aria-label={`Abrir hoja de servicio de ${formatOS(row)}`}
                  data-testid={`row-${ingresoIdOf(row)}`}
                >
                  <td className="p-2 underline">{formatOS(row)}</td>
                  <td className="p-2">
                    {row?.razon_social ?? row?.cliente ?? row?.cliente_nombre ?? "-"}
                  </td>
                  <td className="p-2">{catalogEquipmentLabel(row) ?? "-"}</td>
                  <td className="p-2">{tipoEquipoOf(row)}</td>
                  <td className="p-2">{row?.estado ?? "-"}</td>
                  <td className="p-2">{row?.numero_serie ?? "-"}</td>
                  <td className="p-2">{row?.ubicacion_nombre ?? "-"}</td>
                  <td className="p-2 whitespace-nowrap">{formatDateTime(resolveFechaIngreso(row))}</td>
                  <td className="p-2 whitespace-nowrap">{formatDateTime(row?.fecha_entrega)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-xs text-gray-500 mt-2">
            Mostrando {filtered.length} de {rows.length}.
          </div>
        </div>
      )}
    </div>
  );
}
