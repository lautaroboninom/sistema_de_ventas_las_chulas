import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getDevices, patchDeviceIdentificadores, postDevicesMerge } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { isAdmin, isJefe, isJefeVeedor } from "../lib/authz";

function PropiedadBadge({ row }) {
  const isMg = !!row?.es_propietario_mg;
  const vendido = !!row?.vendido;
  const alquilado = !!row?.alquilado;
  if (isMg) {
    if (vendido) return <span className="px-2 py-1 text-xs rounded bg-amber-100 text-amber-800">Propio</span>;
    if (alquilado) return <span className="px-2 py-1 text-xs rounded bg-blue-100 text-blue-800">Propio (alquilado)</span>;
    return <span className="px-2 py-1 text-xs rounded bg-emerald-100 text-emerald-800">Propio (MG/BIO)</span>;
  }
  return <span className="px-2 py-1 text-xs rounded bg-gray-100 text-gray-700">Cliente</span>;
}

function EditModal({ row, onClose, onSaved, canEdit }) {
  const [ns, setNs] = useState(row?.numero_serie || "");
  const [mg, setMg] = useState(row?.numero_interno || "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  if (!row) return null;
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded shadow-lg w-full max-w-lg p-4">
        <div className="text-lg font-semibold mb-2">Editar identificadores</div>
        <div className="text-sm text-gray-600 mb-3">
          Equipo #{row.id} — Marca: {row.marca || "-"}, Modelo: {row.modelo || "-"}
        </div>
        {err && (
          <div className="bg-red-100 text-red-800 border border-red-300 rounded p-2 mb-3">
            {err}
          </div>
        )}
        <div className="space-y-3">
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Número de serie</div>
            <input
              type="text"
              value={ns}
              onChange={(e) => setNs(e.target.value)}
              className="border rounded p-2 w-full"
              disabled={!canEdit || saving}
            />
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Número interno (MG)</div>
            <input
              type="text"
              value={mg}
              onChange={(e) => setMg(e.target.value)}
              className="border rounded p-2 w-full"
              disabled={!canEdit || saving}
            />
          </label>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button
            className="px-3 py-1.5 rounded border"
            onClick={onClose}
            disabled={saving}
          >
            Cancelar
          </button>
          {canEdit && (
            <button
              className="px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              onClick={async () => {
                setErr("");
                try {
                  setSaving(true);
                  await patchDeviceIdentificadores(row.id, { numero_serie: ns, numero_interno: mg });
                  onSaved && onSaved();
                  onClose();
                } catch (e) {
                  const ctype = e?.data?.conflict_type;
                  if (ctype === "NS_DUPLICATE") {
                    setErr("El número de serie ya está asignado a otro equipo.");
                  } else if (ctype === "MG_DUPLICATE") {
                    setErr("El número interno ya está asignado a otro equipo.");
                  } else {
                    setErr(e?.message || "No se pudo guardar.");
                  }
                } finally {
                  setSaving(false);
                }
              }}
              disabled={saving}
            >
              Guardar
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Equipos() {
  const { user } = useAuth();
  const canEdit = isJefe(user) || isJefeVeedor(user) || isAdmin(user);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [err, setErr] = useState("");
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [search] = useSearchParams();
  const [q, setQ] = useState(search.get("q") || "");
  const [editRow, setEditRow] = useState(null);
  const [params, setParams] = useState({}); // to trigger reload
  const nav = useNavigate();
  const [mergeOpen, setMergeOpen] = useState(false);
  const [mergeTarget, setMergeTarget] = useState(null);
  const [mergeSourceId, setMergeSourceId] = useState("");
  const [mergeNs, setMergeNs] = useState("");
  const [mergeCopyMg, setMergeCopyMg] = useState(false);
  const [mergeErr, setMergeErr] = useState("");
  const [mergeSaving, setMergeSaving] = useState(false);
  const [sort, setSort] = useState("-id");

  const pageSize = 100;
  const highlightId = search.get("device_id");

  async function load(p = 1, { reset = false } = {}) {
    try {
      if (reset) {
        setRows([]);
        setPage(1);
        setHasNext(false);
      }
      const isFirst = reset || p === 1;
      isFirst ? setLoading(true) : setLoadingMore(true);
      setErr("");
      const query = {
        page: p,
        page_size: pageSize,
        q: q || undefined,
        propio: search.get("propio") || undefined,
        alquilado: search.get("alquilado") || undefined,
        sort: sort || undefined,
      };
      const res = await getDevices(query);
      const items = Array.isArray(res) ? res : (res.items || []);
      const next = Array.isArray(res) ? false : !!res.has_next;
      const total = Array.isArray(res) ? items.length : (res.total_count ?? items.length);

      // Si el backend reporta total > 0 pero la página vino vacía (inconsistencia), reintentar sin paginación
      if (isFirst && items.length === 0 && total > 0) {
        try {
          const res2 = await getDevices({ page: 1, page_size: 0 });
          const items2 = Array.isArray(res2) ? res2 : (res2.items || []);
          const total2 = Array.isArray(res2) ? items2.length : (res2.total_count ?? items2.length);
          setRows(items2);
          setHasNext(false);
          setPage(1);
          setErr(""); // borrar error si venía alguno
          // Mostrar un aviso suave si todavía no hay items pese a total > 0
          if (items2.length === 0 && total2 > 0) {
            setErr("El servidor reporta equipos pero no devolvió filas. Avisá si persiste.");
          }
          return;
        } catch (e2) {
          setErr(e2?.message || "No se pudieron cargar los equipos (reintento).");
          setRows([]);
          setHasNext(false);
          setPage(1);
          return;
        }
      }

      setRows((prev) => (isFirst ? items : [...prev, ...items]));
      setHasNext(next);
      setPage(p);
    } catch (e) {
      setErr(e?.message || "No se pudieron cargar los equipos");
      if (reset) setRows([]);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  useEffect(() => {
    load(1, { reset: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, search.get("propio"), search.get("alquilado"), sort]);

  const sentinelRef = useRef(null);
  useEffect(() => {
    if (!hasNext) return;
    const el = sentinelRef.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && !loadingMore) {
          load(page + 1);
        }
      }
    });
    io.observe(el);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasNext, page, loadingMore]);

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="h1">Equipos</div>
          <p className="text-sm text-gray-600">
            Editá N/S y MG desde aquí. Para conflictos detectados en hoja de servicio, te redirige acá.
          </p>
        </div>
        <button
          className="btn"
          onClick={() => load(1, { reset: true })}
          disabled={loading}
        >
          Recargar
        </button>
      </div>

      {err && <div className="bg-red-100 border border-red-300 text-red-800 p-2 rounded mb-3">{err}</div>}

      <div className="flex items-center gap-2 mb-3">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar por N/S, MG, cliente, marca, modelo..."
          className="border rounded p-2 w-full max-w-md"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setParams({ ts: Date.now() });
              load(1, { reset: true });
            }
          }}
        />
        <button
          className="btn"
          onClick={() => {
            setParams({ ts: Date.now() });
            load(1, { reset: true });
          }}
          disabled={loading}
        >
          Aplicar
        </button>
      </div>

      {loading ? (
        "Cargando..."
      ) : rows.length === 0 ? (
        <div className="text-sm text-gray-500">No hay resultados.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <SortableTh label="ID" field="id" sort={sort} setSort={setSort} />
                <th className="p-2">Propiedad</th>
                <SortableTh label="Último cliente/Dueño" field="cliente" sort={sort} setSort={setSort} />
                <SortableTh label="N/S" field="ns" sort={sort} setSort={setSort} />
                <SortableTh label="MG" field="mg" sort={sort} setSort={setSort} />
                <SortableTh label="Marca" field="marca" sort={sort} setSort={setSort} />
                <SortableTh label="Modelo" field="modelo" sort={sort} setSort={setSort} />
                <SortableTh label="Ubicación" field="ubicacion" sort={sort} setSort={setSort} />
                <th className="p-2">Alquiler</th>
                <th className="p-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const isHighlight = highlightId && String(highlightId) === String(row.id);
                return (
                  <tr
                    key={row.id}
                    className={`hover:bg-gray-50 ${isHighlight ? "bg-amber-50" : ""}`}
                  >
                    <td className="p-2 font-mono text-xs">{row.id}</td>
                    <td className="p-2"><PropiedadBadge row={row} /></td>
                    <td className="p-2">
                      <div className="font-medium">{row.last_customer_nombre || row.customer_nombre || "-"}</div>
                      {row.last_ingreso_id ? (
                        <div className="text-xs text-gray-500">
                          Último ingreso #{row.last_ingreso_id}
                        </div>
                      ) : null}
                      {row.es_propietario_mg && (
                        <div className="text-xs text-gray-500">Dueño base (propio MG/BIO)</div>
                      )}
                    </td>
                    <td className="p-2">{row.numero_serie || "-"}</td>
                    <td className="p-2">{row.numero_interno || "-"}</td>
                    <td className="p-2">{row.marca || "-"}</td>
                    <td className="p-2">{row.modelo || "-"}</td>
                    <td className="p-2">{row.ubicacion_nombre || "-"}</td>
                    <td className="p-2">
                      {row.alquilado ? (
                        <div>
                          <div className="text-xs text-gray-700">Alquilado</div>
                          <div className="text-xs text-gray-500">{row.alquiler_a || ""}</div>
                        </div>
                      ) : (
                        <span className="text-xs text-gray-500">No</span>
                      )}
                    </td>
                    <td className="p-2">
                      <div className="relative inline-block text-left">
                        <Menu
                          onOpen={() => {}}
                          button={({ open, toggle }) => (
                            <button
                              onClick={toggle}
                              className="px-2 py-1 rounded hover:bg-gray-100"
                              aria-label="Acciones"
                            >
                              &#8942;
                            </button>
                          )}
                        >
                          {({ close }) => (
                            <div className="absolute right-0 mt-1 w-40 bg-white border border-gray-200 rounded shadow z-10">
                              <button
                                className="block w-full text-left px-3 py-2 text-sm hover:bg-gray-50"
                                onClick={() => {
                                  close();
                                  if (row.last_ingreso_id) nav(`/ingresos/${row.last_ingreso_id}`);
                                }}
                              >
                                Ver ingreso
                              </button>
                              {canEdit && (
                                <button
                                  className="block w-full text-left px-3 py-2 text-sm hover:bg-gray-50"
                                  onClick={() => {
                                    close();
                                    setEditRow(row);
                                  }}
                                >
                                  Editar IDs
                                </button>
                              )}
                              {canEdit && (
                                <button
                                  className="block w-full text-left px-3 py-2 text-sm hover:bg-gray-50"
                                  onClick={() => {
                                    close();
                                    setMergeTarget(row);
                                    setMergeSourceId("");
                                    setMergeNs(row.numero_serie || "");
                                    setMergeCopyMg(false);
                                    setMergeErr("");
                                    setMergeOpen(true);
                                  }}
                                >
                                  Unificar
                                </button>
                              )}
                            </div>
                          )}
                        </Menu>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="text-xs text-gray-500 mt-2">
            Mostrando {rows.length} {hasNext ? "(hay más, baja para cargar…)" : ""}
          </div>
          <div ref={sentinelRef} style={{ height: 1 }} />
          {loadingMore && <div className="text-xs text-gray-500 mt-2">Cargando más…</div>}
        </div>
      )}

      {editRow && (
        <EditModal
          row={editRow}
          canEdit={canEdit}
          onClose={() => setEditRow(null)}
          onSaved={() => {
            setParams({ ts: Date.now() });
            load(1, { reset: true });
          }}
        />
      )}

      {mergeOpen && mergeTarget && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded shadow-lg w-full max-w-xl p-4">
            <div className="text-lg font-semibold mb-1">Unificar equipo</div>
            <div className="text-sm text-gray-600 mb-3">
              Se mantiene el equipo #{mergeTarget.id}. Mové ingresos del equipo fuente al destino y fijá N/S final.
            </div>
            {mergeErr && (
              <div className="bg-red-100 text-red-800 border border-red-300 rounded p-2 mb-3">
                {mergeErr}
              </div>
            )}
            <div className="space-y-3">
              <div className="text-sm">
                <div className="text-gray-700">Destino</div>
                <div className="text-gray-900 font-medium">
                  #{mergeTarget.id} · NS: {mergeTarget.numero_serie || "-"} · MG: {mergeTarget.numero_interno || "-"}
                </div>
              </div>
              <label className="block">
                <div className="text-sm text-gray-700 mb-1">Equipo fuente (ID)</div>
                <input
                  type="number"
                  value={mergeSourceId}
                  onChange={(e) => setMergeSourceId(e.target.value)}
                  className="border rounded p-2 w-full"
                  placeholder="ID del equipo a unificar (se eliminará)"
                  disabled={mergeSaving}
                />
              </label>
              <label className="block">
                <div className="text-sm text-gray-700 mb-1">Número de serie final (destino)</div>
                <input
                  type="text"
                  value={mergeNs}
                  onChange={(e) => setMergeNs(e.target.value)}
                  className="border rounded p-2 w-full"
                  disabled={mergeSaving}
                />
              </label>
              <label className="block flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={mergeCopyMg}
                  onChange={(e) => setMergeCopyMg(e.target.checked)}
                  disabled={mergeSaving}
                />
                Copiar MG del equipo fuente si el destino no tiene MG
              </label>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button className="px-3 py-1.5 rounded border" onClick={() => setMergeOpen(false)} disabled={mergeSaving}>
                Cancelar
              </button>
              <button
                className="px-3 py-1.5 rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
                disabled={mergeSaving || !mergeSourceId || !mergeNs}
                onClick={async () => {
                  setMergeErr("");
                  try {
                    setMergeSaving(true);
                    await postDevicesMerge({
                      target_id: mergeTarget.id,
                      source_id: Number(mergeSourceId),
                      numero_serie: mergeNs,
                      copy_mg_if_missing: mergeCopyMg,
                    });
                    setMergeOpen(false);
                    setMergeTarget(null);
                    setParams({ ts: Date.now() });
                    load(1, { reset: true });
                  } catch (e) {
                    const ctype = e?.data?.conflict_type;
                    if (ctype === "MG_MISMATCH") setMergeErr("Los equipos tienen MG distintos; no se puede unificar.");
                    else if (ctype === "NS_DUPLICATE") setMergeErr("El N/S final ya está en uso por otro equipo.");
                    else if (ctype === "MG_DUPLICATE") setMergeErr("El MG a copiar ya está en uso por otro equipo.");
                    else setMergeErr(e?.message || "No se pudo unificar.");
                  } finally {
                    setMergeSaving(false);
                  }
                }}
              >
                Unificar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Simple menu helper (similar al de ServiceSheet)
function Menu({ button, children }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const handler = (e) => {
      if (!open) return;
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);
  const toggle = () => setOpen((v) => !v);
  const close = () => setOpen(false);
  return (
    <div ref={ref}>
      {button({ open, toggle })}
      {open && children({ close })}
    </div>
  );
}

function SortableTh({ label, field, sort, setSort }) {
  const isAsc = sort === field;
  const isDesc = sort === `-${field}`;
  const next = () => {
    if (isAsc) setSort(`-${field}`);
    else if (isDesc) setSort("id"); // fallback
    else setSort(field);
  };
  return (
    <th className="p-2 cursor-pointer select-none" onClick={next}>
      <span className="inline-flex items-center gap-1">
        {label}
        {isAsc && <span aria-label="asc">▲</span>}
        {isDesc && <span aria-label="desc">▼</span>}
      </span>
    </th>
  );
}
