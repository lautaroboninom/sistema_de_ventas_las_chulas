import { useEffect, useState } from "react";
import api from "../lib/api";
import { useNavigate } from "react-router-dom";
import { ingresoIdOf, formatOS, formatDateTime } from "../lib/ui-helpers";

export default function Tecnico() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const navigate = useNavigate();

  // helper: detectar motivo urgente control
  const isUrgente = (row) => (row?.motivo || "").toLowerCase() === "urgente control";

  // ordena: devueltos de derivación primero, luego urgentes, luego por fecha_ingreso asc
  const sortPendientes = (arr) => {
    return [...arr].sort((a, b) => {
      const aDev = a?.derivado_devuelto ? 1 : 0;
      const bDev = b?.derivado_devuelto ? 1 : 0;
      if (aDev !== bDev) return bDev - aDev;

      const au = isUrgente(a) ? 1 : 0;
      const bu = isUrgente(b) ? 1 : 0;
      if (au !== bu) return bu - au;

      // Fallback: por fecha_ingreso asc (más viejos primero)
      const dtA = a?.fecha_ingreso ? new Date(a.fecha_ingreso) : new Date("9999-12-31");
      const dtB = b?.fecha_ingreso ? new Date(b.fecha_ingreso) : new Date("9999-12-31");
      return dtA - dtB;
    });
  };

  async function load() {
    try {
      setErr("");
      setLoading(true);
      const data = await api.get("/api/tecnico/mis-pendientes/");
      const arr = Array.isArray(data) ? data : [];
      setRows(sortPendientes(arr));
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

  const StateSquare = ({ checked, label, disabled }) => {
    const cls = [
      "inline-flex items-center justify-center w-7 h-7 rounded border text-xs",
      checked ? "bg-green-600 border-green-700 text-white" : "bg-white border-gray-300 text-gray-500",
      disabled && "opacity-40",
      "cursor-default select-none",
    ]
      .filter(Boolean)
      .join(" ");

    return (
      <span className={cls} title={label} aria-label={`${label}: ${checked ? "si" : "no"}`}>
        {checked ? "✓" : ""}
      </span>
    );
  };

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
      <div className="h1 mb-3">Mis pendientes</div>

      {err && (
        <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-3">{err}</div>
      )}

      {loading ? (
        "Cargando..."
      ) : rows.length === 0 ? (
        <div className="text-sm text-gray-500">No tenés pendientes por ahora.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="p-2">OS</th>
                <th className="p-2">Fecha Ingreso</th>
                <th className="p-2">Marca</th>
                <th className="p-2">Modelo</th>
                <th className="p-2">Estado</th>
                <th className="p-2">Serie</th>
                <th className="p-2 text-right">Diagnosticado</th>
                <th className="p-2 text-right">Presupuestado</th>
                <th className="p-2 text-right">Aprobado</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const urgente = isUrgente(row);
                const devuelto = !!row?.derivado_devuelto;
                const rowCls = [
                  "hover:bg-gray-50 cursor-pointer",
                  urgente && "text-red-600 font-semibold",
                  devuelto && "text-blue-700 font-semibold",
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
                      {devuelto && (
                        <span className="ml-2 inline-block px-2 py-0.5 text-[10px] rounded bg-blue-100 text-blue-700 align-middle">
                          DERIVADO DEVUELTO
                        </span>
                      )}
                      {urgente && (
                        <span className="ml-2 inline-block px-2 py-0.5 text-[10px] rounded bg-red-100 text-red-700 align-middle">
                          URGENTE
                        </span>
                      )}
                    </td>
                    <td className="p-2 whitespace-nowrap">
                      {row?.fecha_ingreso ? formatDateTime(row.fecha_ingreso) : "-"}
                    </td>
                    <td className="p-2">{row?.marca ?? row?.equipo?.marca ?? "-"}</td>
                    <td className="p-2">{row?.modelo ?? row?.equipo?.modelo ?? "-"}</td>
                    <td className="p-2">{row?.estado ?? "-"}</td>
                    <td className="p-2">{row?.numero_serie ?? "-"}</td>

                    <td className="p-2 text-center" onClick={(e) => e.stopPropagation()}>
                      <StateSquare
                        label="Diagnosticado"
                        checked={(() => {
                          const e = (row?.estado || "").toLowerCase();
                          const diagChain = [
                            "diagnosticado",
                            "reparar",
                            "reparado",
                            "liberado",
                            "entregado",
                            "alquilado",
                          ];
                          return diagChain.includes(e);
                        })()}
                      />
                    </td>

                    <td className="p-2 text-center" onClick={(e) => e.stopPropagation()}>
                      <StateSquare
                        label="Presupuestado"
                        checked={(() => {
                          const p = (row?.presupuesto_estado || "").toLowerCase();
                          return ["presupuestado", "aprobado"].includes(p);
                        })()}
                      />
                    </td>

                    <td className="p-2 text-center" onClick={(e) => e.stopPropagation()}>
                      <StateSquare
                        label="Aprobado"
                        checked={(row?.presupuesto_estado || "").toLowerCase() === "aprobado"}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

