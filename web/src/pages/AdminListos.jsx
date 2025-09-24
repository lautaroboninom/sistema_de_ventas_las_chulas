// web/src/pages/AdminListos.jsx
import { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { useNavigate } from "react-router-dom";
import { ingresoIdOf, formatOS, formatDateTime, norm, tipoEquipoOf, catalogEquipmentLabel } from "../lib/ui-helpers";
import StatusChip from "../components/StatusChip.jsx";
import { resolutionLabel } from "../lib/constants";


// Ajustá si tu backend usa otra ruta
const ENDPOINT = "/api/ingresos/liberados/";


export default function AdminListos() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState("");
  const [busyId, setBusyId] = useState(null);
  const navigate = useNavigate();

  async function load() {
    try {
      setErr("");
      setLoading(true);
      const data = await api.get(ENDPOINT);
      const list = Array.isArray(data) ? data : [];
      // Orden sugerido: primero los más recientes marcados como "listos"
      list.sort((a, b) => {
        const da =
          new Date(a?.fecha_listo ?? a?.fecha_reparado ?? a?.fecha_estado ?? 0).getTime();
        const db =
          new Date(b?.fecha_listo ?? b?.fecha_reparado ?? b?.fecha_estado ?? 0).getTime();
        return db - da;
      });
      setRows(list);
    } catch (e) {
      setErr(e?.message || "No se pudieron cargar los equipos listos para retiro");
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
        row?.resolucion,
        resolutionLabel(row?.resolucion ?? ""),
        row?.numero_serie,
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

  async function entregar(row) {
    const id = ingresoIdOf(row);
    if (!id) return;
    try {
      setBusyId(id);
      await api.post(`/api/ingresos/${id}/entregar/`);
      await load();
    } catch (e) {
      setErr(e?.message || "No se pudo marcar como entregado");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="card">
      <div className="h1 mb-3">Listos para retiro</div>

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
          placeholder="Filtrar por OS, cliente, equipo, serie, resolución…"
          className="border rounded p-2 w-full max-w-md"
          aria-label="Filtrar listos para retiro"
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
        <div className="text-sm text-gray-500">No hay equipos listos para retiro.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th scope="col" className="p-2">OS</th>
                <th scope="col" className="p-2">Cliente</th>
                <th scope="col" className="p-2">Marca</th>
                <th scope="col" className="p-2">Equipo</th>
                <th scope="col" className="p-2">Tipo</th>
                <th scope="col" className="p-2">Resolución</th>
                <th scope="col" className="p-2">Serie</th>
                <th scope="col" className="p-2">Fecha listo</th>
                <th scope="col" className="p-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr
                  key={ingresoIdOf(row)}
                  onClick={() => go(row)}
                  onKeyDown={(e) => onRowKeyDown(e, row)}
                  className="hover:bg-gray-50 cursor-pointer border-t"
                  role="link"
                  tabIndex={0}
                  aria-label={`Abrir hoja de servicio de ${formatOS(row)}`}
                  data-testid={`row-${ingresoIdOf(row)}`}
                >
                  <td className="p-2 underline">{formatOS(row)}</td>
                  <td className="p-2">{row?.razon_social ?? row?.cliente ?? row?.cliente_nombre ?? "-"}</td>
                  <td className="p-2">{row?.marca ?? row?.equipo?.marca ?? "-"}</td>
                  <td className="p-2">{catalogEquipmentLabel(row) ?? "-"}</td>
                  <td className="p-2">{tipoEquipoOf(row)}</td>
                  <td className="p-2">
                    <StatusChip value={resolutionLabel(row?.resolucion)} title="Resolución" />
                  </td>
                  <td className="p-2">{row?.numero_serie ?? "-"}</td>
                  <td className="p-2 whitespace-nowrap">
                    {formatDateTime(row?.fecha_listo ?? row?.fecha_reparado ?? row?.fecha_estado)}
                  </td>
                  <td className="p-2">
                    <div className="flex gap-2 justify-end">
                      <button
                        className="btn"
                        onClick={(e) => {
                          e.stopPropagation(); // no navegar al clickear
                          entregar(row);
                        }}
                        disabled={busyId === ingresoIdOf(row)}
                        aria-busy={busyId === ingresoIdOf(row) ? "true" : "false"}
                        title="Marcar como entregado"
                      >
                        Entregado
                      </button>
                    </div>
                  </td>
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
