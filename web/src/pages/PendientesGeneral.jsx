import { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { useNavigate } from "react-router-dom";
import { ingresoIdOf, formatOS, formatDateTime, norm } from "../lib/ui-helpers";

// Ajustá si tu backend usa otro endpoint
const ENDPOINT = "/api/ingresos/pendientes/";

export default function PendientesGeneral() {
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
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setErr(e?.message || "No se pudieron cargar los pendientes");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // helper: detectar motivo urgente control
  const isUrgente = (row) => (row?.motivo || "").toLowerCase() === "urgente control";

  // Aplico filtro y luego ordeno: urgentes primero, después por fecha_ingreso asc
  const filteredAndSorted = useMemo(() => {
    const needle = norm(filter);
    const base = needle
      ? rows.filter((row) => {
          const campos = [
            formatOS(row),
            row?.razon_social ?? row?.cliente ?? row?.cliente_nombre,
            row?.marca ?? row?.equipo?.marca,
            row?.modelo ?? row?.equipo?.modelo,
            row?.estado,
            row?.numero_serie,
          ];
          return campos.some((c) => norm(c).includes(needle));
        })
      : rows;

    return [...base].sort((a, b) => {
      const au = isUrgente(a) ? 1 : 0;
      const bu = isUrgente(b) ? 1 : 0;
      if (au !== bu) return bu - au; // urgentes arriba

      // Fallback: por fecha_ingreso asc (más viejos primero)
      const ad = a?.fecha_ingreso ? new Date(a.fecha_ingreso) : new Date("9999-12-31");
      const bd = b?.fecha_ingreso ? new Date(b.fecha_ingreso) : new Date("9999-12-31");
      return ad - bd;
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
      <div className="h1 mb-3">Pendientes — General</div>

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
          placeholder="Filtrar por OS, cliente, marca, modelo, serie…"
          className="border rounded p-2 w-full max-w-md"
          aria-label="Filtrar pendientes"
        />
        <button className="btn" onClick={load} title="Recargar lista">
          Recargar
        </button>
      </div>

      {loading ? (
        "Cargando..."
      ) : filteredAndSorted.length === 0 ? (
        <div className="text-sm text-gray-500">No hay pendientes que coincidan con el filtro.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="p-2">OS</th>
                <th className="p-2">Cliente</th>
                <th className="p-2">Marca</th>
                <th className="p-2">Modelo</th>
                <th className="p-2">Estado</th>
                <th className="p-2">Serie</th>
                <th className="p-2">Fecha ingreso</th>
              </tr>
            </thead>
            <tbody>
              {filteredAndSorted.map((row) => {
                const urgente = isUrgente(row);
                const rowCls = [
                  "hover:bg-gray-50 cursor-pointer",
                  urgente && "text-red-600 font-semibold",
                ]
                  .filter(Boolean)
                  .join(" ");

                return (
                  <tr
                    key={ingresoIdOf(row)}
                    onClick={() => go(row)}
                    onKeyDown={(e) => onRowKeyDown(e, row)}
                    className={rowCls}
                    role="link"
                    tabIndex={0}
                    aria-label={`Abrir hoja de servicio de ${formatOS(row)}`}
                    data-testid={`row-${ingresoIdOf(row)}`}
                  >
                    <td className="p-2 underline">
                      <span>{formatOS(row)}</span>
                      {urgente && (
                        <span className="ml-2 inline-block px-2 py-0.5 text-[10px] rounded bg-red-100 text-red-700 align-middle">
                          URGENTE
                        </span>
                      )}
                    </td>
                    <td className="p-2">
                      {row?.razon_social ?? row?.cliente ?? row?.cliente_nombre ?? "-"}
                    </td>
                    <td className="p-2">{row?.marca ?? row?.equipo?.marca ?? "-"}</td>
                    <td className="p-2">{row?.modelo ?? row?.equipo?.modelo ?? "-"}</td>
                    <td className="p-2">{row?.estado ?? "-"}</td>
                    <td className="p-2">{row?.numero_serie ?? "-"}</td>
                    <td className="p-2 whitespace-nowrap">{formatDateTime(row?.fecha_ingreso)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="text-xs text-gray-500 mt-2">
            Mostrando {filteredAndSorted.length} de {rows.length}.
          </div>
        </div>
      )}
    </div>
  );
}
