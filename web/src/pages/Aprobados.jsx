// web/src/pages/Aprobados.jsx
import { useEffect, useMemo, useState } from "react";
import api, { getBlob } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { canRelease } from "../lib/authz";
import { useNavigate } from "react-router-dom";
import {
  ingresoIdOf,
  formatOS,
  formatDateTime,
  norm,
  tipoEquipoOf,
  catalogEquipmentLabel,
  nsPreferInternoOf,
} from "../lib/ui-helpers";
import StatusChip from "../components/StatusChip.jsx";

// Endpoint combinado del backend
const ENDPOINT = "/api/ingresos/aprobados/";

export default function Aprobados() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState("");
  const navigate = useNavigate();
  const { user } = useAuth();
  const release = canRelease(user);

  async function load() {
    try {
      setErr("");
      setLoading(true);
      const data = await api.get(ENDPOINT);
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setErr(e?.message || "No se pudieron cargar los aprobados");
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
        row?.numero_interno,
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
      <div className="h1 mb-3">Aprobados</div>

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
          placeholder="Filtrar por OS, cliente, marca, equipo, serie"
          className="border rounded p-2 w-full max-w-md"
          aria-label="Filtrar aprobados"
        />
        <button className="btn" onClick={load} title="Recargar lista">
          Recargar
        </button>
      </div>

      {loading ? (
        "Cargando..."
      ) : filtered.length === 0 ? (
        <div className="text-sm text-gray-500">No hay aprobados que coincidan con el filtro.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="p-2">OS</th>
                <th className="p-2">Cliente</th>
                <th className="p-2">Equipo</th>
                <th className="p-2">Estado</th>
                <th className="p-2">Serie</th>
                <th className="p-2">Fecha aprob./repar.</th>
                <th className="p-2">Acciones</th>
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
                  <td className="p-2">{row?.razon_social ?? row?.cliente ?? row?.cliente_nombre ?? "-"}</td>
                  <td className="p-2">{catalogEquipmentLabel(row) ?? "-"}</td>
                  <td className="p-2">
                    <StatusChip value={row?.estado} />
                  </td>
                  <td className="p-2">{nsPreferInternoOf(row)}</td>
                  <td className="p-2 whitespace-nowrap">{formatDateTime(
                    row?.fecha_aprobacion ||
                      row?.presupuesto_fecha_aprobacion ||
                      row?.fecha_reparado ||
                      row?.fecha_reparacion ||
                      row?.estado_fecha
                  )}</td>
                  <td className="p-2">
                    {release && row?.estado === "reparado" && (
                      <button
                        className="btn"
                        type="button"
                        title="Imprimir remito"
                        onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            const id = ingresoIdOf(row);
                            if (!id) return;
                            const blob = await getBlob(`/api/ingresos/${id}/remito/`);
                            if (!(blob instanceof Blob)) throw new Error("La respuesta no fue un PDF");
                            const url = URL.createObjectURL(blob);
                            window.open(url, "_blank", "noopener");
                            setTimeout(() => URL.revokeObjectURL(url), 60_000);
                            await load();
                          } catch (e) {
                            setErr(e?.message || "No se pudo imprimir el remito");
                          }
                        }}
                      >
                        Imprimir remito
                      </button>
                    )}
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

