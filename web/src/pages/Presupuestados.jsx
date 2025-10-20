// web/src/pages/JefePresupuestos.jsx
import { useEffect, useMemo, useState } from "react";
import api, { getBlob, downloadAuth } from "../lib/api";
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
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [exporting, setExporting] = useState(false);

  const navigate = useNavigate();

  async function load() {
    try {
      setErr("");
      setLoading(true);
      const data = await api.get(ENDPOINT);
      const list = Array.isArray(data) ? data : [];
      // Orden sugerido: ms recientes primero por fecha de emisin/envo o ingreso
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

  const visibleIds = useMemo(() => new Set(filtered.map((r) => ingresoIdOf(r))), [filtered]);
  const allVisibleSelected = useMemo(() => {
    if (visibleIds.size === 0) return false;
    for (const id of visibleIds) if (!selectedIds.has(id)) return false;
    return true;
  }, [visibleIds, selectedIds]);

  const toggleSelectAllVisible = () => {
    const next = new Set(selectedIds);
    if (allVisibleSelected) {
      for (const id of visibleIds) next.delete(id);
    } else {
      for (const id of visibleIds) next.add(id);
    }
    setSelectedIds(next);
  };

  const toggleRow = (e, row) => {
    e.stopPropagation();
    const id = ingresoIdOf(row);
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };

  async function exportByIds(ids, fnameHint = "presupuestados") {
    if (!ids || ids.length === 0) return;
    try {
      setExporting(true);
      const qs = new URLSearchParams({ ids: ids.join(",") }).toString();
      await downloadAuth(`/api/ingresos/presupuestados/export/?${qs}`, `${fnameHint}.xlsx`);
    } catch (e) {
      setErr(e?.message || "No se pudo exportar el Excel");
    } finally {
      setExporting(false);
    }
  }

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

  // Accin: Aprobar presupuesto (por ingreso_id)
  async function aprobar(row) {
    const ingresoId = ingresoIdOf(row);
    if (!ingresoId) {
      setErr("No se encontr el ID de ingreso para aprobar.");
      return;
    }
    try {
      setBusyId(ingresoId);
      const shouldPrint = (row?.estado || "").toLowerCase() === "reparado" &&
        window.confirm("Este equipo ya est reparado, imprimir remito de salida?");
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
          placeholder="Filtrar por OS, cliente, equipo, estado, monto"
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
        <div className="flex items-center gap-2 ml-auto">
          <button
            className="btn"
            onClick={() => exportByIds(filtered.map(ingresoIdOf), `presupuestados_filtrados_${filtered.length}`)}
            disabled={exporting || filtered.length === 0}
            aria-busy={exporting ? "true" : "false"}
            title="Exportar todos los filtrados a Excel"
          >
            Exportar filtrados
          </button>
          <button
            className="btn"
            onClick={() => exportByIds(Array.from(selectedIds), `presupuestados_seleccion_${selectedIds.size}`)}
            disabled={exporting || selectedIds.size === 0}
            aria-busy={exporting ? "true" : "false"}
            title="Exportar seleccin a Excel"
          >
            Exportar seleccin
          </button>
        </div>
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
                <th scope="col" className="p-2">
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    onChange={toggleSelectAllVisible}
                    aria-label="Seleccionar todos los visibles"
                  />
                </th>
                <th scope="col" className="p-2">OS</th>
                <th scope="col" className="p-2">Cliente</th>
                <th scope="col" className="p-2">Equipo</th>
                <th scope="col" className="p-2">Serie</th>
                <th scope="col" className="p-2">Estado</th>
                <th scope="col" className="p-2">Monto</th>
                <th scope="col" className="p-2">Fecha emisin</th>
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
                    <td className="p-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(ingresoId)}
                        onChange={(e) => toggleRow(e, row)}
                        aria-label={`Seleccionar ${formatOS(row)}`}
                      />
                    </td>
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
                        {/* Si tu backend permite rechazar / anular, pods agregar ac otro botn */}
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

