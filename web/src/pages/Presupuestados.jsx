// web/src/pages/JefePresupuestos.jsx
import { useEffect, useMemo, useState } from "react";
import api, { getBlob } from "../lib/api";
import { useNavigate } from "react-router-dom";
import { ingresoIdOf,
  formatOS,
  formatDateTime,
  norm,
  tipoEquipoOf,
  formatMoney,
  resolveFechaCreacion, catalogEquipmentLabel, nsPreferInternoOf } from "../lib/ui-helpers";

// ENDPOINT para "presupuestados" (ya emitidos/enviados)
const ENDPOINT = "/api/ingresos/presupuestados/"; // <-- AJUSTAR si tu API usa otra ruta

export default function JefePresupuestos() {
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
      // Orden sugerido: más recientes primero por fecha de emisión/envío o ingreso
      list.sort((a, b) => {
        const da = new Date(a?.presupuesto_fecha_envio ?? a?.presupuesto_fecha_emision ?? resolveFechaCreacion(a) ?? 0).getTime();
        const db = new Date(b?.presupuesto_fecha_envio ?? b?.presupuesto_fecha_emision ?? resolveFechaCreacion(b) ?? 0).getTime();
        return db - da;
      });
      setRows(list);
    } catch (e) {
      setErr(e?.message || "No se pudo cargar la lista de presupuestados");
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
        String(row?.presupuesto_monto ?? row?.presupuesto_total ?? ""),
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

  // Acción: Aprobar presupuesto (por ingreso_id)
  async function aprobar(row) {
    const ingresoId = ingresoIdOf(row);
    if (!ingresoId) {
      setErr("No se encontró el ID de ingreso para aprobar.");
      return;
    }
    try {
      setBusyId(ingresoId);
      const shouldPrint = (row?.estado || "").toLowerCase() === "reparado" &&
        window.confirm("Este equipo ya está reparado, ¿imprimir remito de salida?");
      await api.post(`/api/quotes/${ingresoId}/aprobar/`);
      if (shouldPrint) {
        try {
          const blob = await getBlob(`/api/ingresos/${ingresoId}/remito/`);
          if (!(blob instanceof Blob)) throw new Error("La respuesta no fue un PDF");
          const url = URL.createObjectURL(blob);
          window.open(url, "_blank", "noopener");
          setTimeout(() => URL.revokeObjectURL(url), 60_000);
        } catch (e) {
          setErr(e?.message || "No se pudo imprimir el remito de salida");
        }
      }
      await load();
    } catch (e) {
      setErr(e?.message || "No se pudo aprobar el presupuesto");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="card">
      <div className="h1 mb-3">Presupuestados</div>

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
          placeholder="Filtrar por OS, cliente, equipo, estado, monto…"
          className="border rounded p-2 w-full max-w-md"
          aria-label="Filtrar presupuestados"
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
        <div className="text-sm text-gray-500">No hay presupuestos emitidos/enviados.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th scope="col" className="p-2">OS</th>
                <th scope="col" className="p-2">Cliente</th>
                <th scope="col" className="p-2">Equipo</th>
                <th scope="col" className="p-2">Serie</th>
                <th scope="col" className="p-2">Estado</th>
                <th scope="col" className="p-2">Monto</th>
                <th scope="col" className="p-2">Fecha emisión</th>
                <th scope="col" className="p-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => {
                const moneda = row?.presupuesto_moneda ?? "ARS";
                const monto = row?.presupuesto_monto ?? row?.presupuesto_total ?? null;
                const ingresoId = ingresoIdOf(row);

                return (
                  <tr
                    key={ingresoId}
                    onClick={() => go(row)}
                    onKeyDown={(e) => onRowKeyDown(e, row)}
                    className="hover:bg-gray-50 cursor-pointer border-t"
                    role="link"
                    tabIndex={0}
                    aria-label={`Abrir hoja de servicio de ${formatOS(row)}`}
                    data-testid={`row-${ingresoId}`}
                  >
                    <td className="p-2 underline">{formatOS(row)}</td>
                    <td className="p-2">
                      {row?.razon_social ?? row?.cliente ?? row?.cliente_nombre ?? "-"}
                    </td>
                    <td className="p-2">{catalogEquipmentLabel(row) ?? "-"}</td>
                    <td className="p-2">{nsPreferInternoOf(row)}</td>
                    <td className="p-2">{row?.estado ?? "-"}</td>
                    <td className="p-2">{formatMoney(monto, moneda)}</td>
                    <td className="p-2 whitespace-nowrap">
                      {formatDateTime(row?.presupuesto_fecha_emision ?? row?.fecha_emision)}
                    </td>
                    <td className="p-2">
                      <div className="flex gap-2 justify-end">
                        <button
                          className="btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            aprobar(row);
                          }}
                          disabled={busyId === ingresoId}
                          aria-busy={busyId === ingresoId ? "true" : "false"}
                          title="Aprobar presupuesto"
                        >
                          Aprobar
                        </button>
                        {/* Si tu backend permite rechazar / anular, podés agregar acá otro botón */}
                      </div>
                    </td>
                  </tr>
                );
              })}
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
