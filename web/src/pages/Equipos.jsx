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
  const [mergeEquipo1, setMergeEquipo1] = useState(null);
  const [mergeEquipo2, setMergeEquipo2] = useState(null);
  const [mergeStep, setMergeStep] = useState(1);
  const [mergeSearch, setMergeSearch] = useState("");
  const [mergeSearchResults, setMergeSearchResults] = useState([]);
  const [mergeSearching, setMergeSearching] = useState(false);
  const [mergeSearchErr, setMergeSearchErr] = useState("");
  const [mergeNsChoice, setMergeNsChoice] = useState("equipo1");
  const [mergeMgChoice, setMergeMgChoice] = useState("equipo1");
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

  const resetMergeState = () => {
    setMergeOpen(false);
    setMergeEquipo1(null);
    setMergeEquipo2(null);
    setMergeStep(1);
    setMergeSearch("");
    setMergeSearchResults([]);
    setMergeSearching(false);
    setMergeSearchErr("");
    setMergeNsChoice("equipo1");
    setMergeMgChoice("equipo1");
    setMergeErr("");
    setMergeSaving(false);
  };

  const openMergeFor = (row) => {
    setMergeEquipo1(row);
    setMergeEquipo2(null);
    setMergeStep(1);
    setMergeSearch("");
    setMergeSearchResults([]);
    setMergeSearching(false);
    setMergeSearchErr("");
    setMergeNsChoice("equipo1");
    setMergeMgChoice("equipo1");
    setMergeErr("");
    setMergeSaving(false);
    setMergeOpen(true);
  };

  const runMergeSearch = async () => {
    const term = (mergeSearch || "").trim();
    if (!term) {
      setMergeSearchResults([]);
      setMergeSearchErr("Ingresá un N/S o número interno para buscar.");
      return;
    }
    try {
      setMergeSearching(true);
      setMergeSearchErr("");
      const res = await getDevices({ q: term, page: 1, page_size: 20, sort: "id" });
      const items = Array.isArray(res) ? res : (res.items || []);
      const filtered = items.filter((item) => item.id !== mergeEquipo1?.id);
      setMergeSearchResults(filtered);
      if (!filtered.length) {
        setMergeSearchErr("No hay resultados para esa búsqueda.");
      }
    } catch (e) {
      setMergeSearchErr(e?.message || "No se pudo buscar el equipo.");
      setMergeSearchResults([]);
    } finally {
      setMergeSearching(false);
    }
  };

  const selectMergeEquipo2 = (row) => {
    setMergeEquipo2(row);
    const nsDefault = mergeEquipo1?.numero_serie
      ? "equipo1"
      : (row?.numero_serie ? "equipo2" : "equipo1");
    const mgDefault = mergeEquipo1?.numero_interno
      ? "equipo1"
      : (row?.numero_interno ? "equipo2" : "equipo1");
    setMergeNsChoice(nsDefault);
    setMergeMgChoice(mgDefault);
    setMergeStep(2);
    setMergeErr("");
  };

  const mergeNsFinal = mergeNsChoice === "equipo1"
    ? (mergeEquipo1?.numero_serie || "")
    : (mergeEquipo2?.numero_serie || "");
  const mergeMgFinal = mergeMgChoice === "equipo1"
    ? (mergeEquipo1?.numero_interno || "")
    : (mergeEquipo2?.numero_interno || "");
  const mergeNsFinalValue = (mergeNsFinal || "").trim();
  const mergeMgFinalValue = (mergeMgFinal || "").trim();
  const canSubmitMerge = !!mergeEquipo1 && !!mergeEquipo2 && !!mergeNsFinalValue && !mergeSaving;

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
        <div className="overflow-x-auto overflow-y-visible">
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
                                    openMergeFor(row);
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

      {mergeOpen && mergeEquipo1 && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded shadow-lg w-full max-w-4xl p-4">
            <div className="flex items-start justify-between mb-3 gap-3">
              <div>
                <div className="text-lg font-semibold">Unificar equipos</div>
                <div className="text-sm text-gray-600">Paso {mergeStep} de 2</div>
              </div>
              {mergeStep === 2 && (
                <button
                  className="px-3 py-1.5 rounded border text-sm hover:bg-gray-50"
                  onClick={() => setMergeStep(1)}
                  disabled={mergeSaving}
                >
                  Cambiar equipo 2
                </button>
              )}
            </div>

            {mergeErr && (
              <div className="bg-red-100 text-red-800 border border-red-300 rounded p-2 mb-3">
                {mergeErr}
              </div>
            )}

            {mergeStep === 1 ? (
              <div className="space-y-3">
                <div className="text-sm">
                  <div className="text-gray-700">Equipo 1</div>
                  <div className="text-gray-900 font-medium">
                    #{mergeEquipo1.id} - NS: {mergeEquipo1.numero_serie || "-"} - MG: {mergeEquipo1.numero_interno || "-"}
                  </div>
                  <div className="text-xs text-gray-500">
                    {mergeEquipo1.marca || "-"} {mergeEquipo1.modelo || ""}
                  </div>
                </div>

                <label className="block">
                  <div className="text-sm text-gray-700 mb-1">Buscar equipo 2 (N/S o MG)</div>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={mergeSearch}
                      onChange={(e) => setMergeSearch(e.target.value)}
                      className="border rounded p-2 w-full"
                      placeholder="Ej: MG 1234 o NS 00123"
                      disabled={mergeSearching}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") runMergeSearch();
                      }}
                    />
                    <button
                      className="btn"
                      onClick={runMergeSearch}
                      disabled={mergeSearching}
                    >
                      Buscar
                    </button>
                  </div>
                </label>

                {mergeSearchErr && (
                  <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
                    {mergeSearchErr}
                  </div>
                )}

                <div className="border rounded overflow-auto max-h-72">
                  {mergeSearching ? (
                    <div className="text-xs text-gray-500 p-3">Buscando...</div>
                  ) : mergeSearchResults.length ? (
                    <table className="min-w-full text-xs">
                      <thead>
                        <tr className="text-left bg-gray-50">
                          <th className="p-2">ID</th>
                          <th className="p-2">N/S</th>
                          <th className="p-2">MG</th>
                          <th className="p-2">Marca/Modelo</th>
                          <th className="p-2 text-right">Accion</th>
                        </tr>
                      </thead>
                      <tbody>
                        {mergeSearchResults.map((row) => (
                          <tr key={row.id} className="border-t">
                            <td className="p-2 font-mono">{row.id}</td>
                            <td className="p-2">{row.numero_serie || "-"}</td>
                            <td className="p-2">{row.numero_interno || "-"}</td>
                            <td className="p-2">
                              <div className="font-medium">{row.marca || "-"}</div>
                              <div className="text-xs text-gray-500">{row.modelo || "-"}</div>
                            </td>
                            <td className="p-2 text-right">
                              <button
                                className="px-2 py-1 rounded border text-xs hover:bg-gray-50"
                                onClick={() => selectMergeEquipo2(row)}
                              >
                                Seleccionar
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="text-xs text-gray-500 p-3">
                      Busca por N/S o MG para ver resultados.
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {mergeEquipo2 ? (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="border rounded p-3 bg-gray-50">
                        <div className="text-xs uppercase text-gray-500">Equipo 1</div>
                        <div className="text-sm font-medium">#{mergeEquipo1.id}</div>
                        <div className="text-xs text-gray-600">NS: {mergeEquipo1.numero_serie || "-"}</div>
                        <div className="text-xs text-gray-600">MG: {mergeEquipo1.numero_interno || "-"}</div>
                        <div className="text-xs text-gray-500">
                          {mergeEquipo1.marca || "-"} {mergeEquipo1.modelo || ""}
                        </div>
                      </div>
                      <div className="border rounded p-3 bg-gray-50">
                        <div className="text-xs uppercase text-gray-500">Equipo 2</div>
                        <div className="text-sm font-medium">#{mergeEquipo2.id}</div>
                        <div className="text-xs text-gray-600">NS: {mergeEquipo2.numero_serie || "-"}</div>
                        <div className="text-xs text-gray-600">MG: {mergeEquipo2.numero_interno || "-"}</div>
                        <div className="text-xs text-gray-500">
                          {mergeEquipo2.marca || "-"} {mergeEquipo2.modelo || ""}
                        </div>
                      </div>
                    </div>

                    <div className="border rounded p-3">
                      <div className="text-sm font-medium mb-2">N/S final</div>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="radio"
                          name="merge-ns"
                          value="equipo1"
                          checked={mergeNsChoice === "equipo1"}
                          onChange={() => setMergeNsChoice("equipo1")}
                          disabled={mergeSaving}
                        />
                        Equipo 1: {mergeEquipo1.numero_serie || "(vacio)"}
                      </label>
                      <label className="flex items-center gap-2 text-sm mt-2">
                        <input
                          type="radio"
                          name="merge-ns"
                          value="equipo2"
                          checked={mergeNsChoice === "equipo2"}
                          onChange={() => setMergeNsChoice("equipo2")}
                          disabled={mergeSaving}
                        />
                        Equipo 2: {mergeEquipo2.numero_serie || "(vacio)"}
                      </label>
                      {!mergeNsFinalValue && (
                        <div className="text-xs text-amber-700 mt-2">
                          El N/S elegido esta vacio; no se puede unificar.
                        </div>
                      )}
                    </div>

                    <div className="border rounded p-3">
                      <div className="text-sm font-medium mb-2">Numero interno final</div>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="radio"
                          name="merge-mg"
                          value="equipo1"
                          checked={mergeMgChoice === "equipo1"}
                          onChange={() => setMergeMgChoice("equipo1")}
                          disabled={mergeSaving}
                        />
                        Equipo 1: {mergeEquipo1.numero_interno || "(vacio)"}
                      </label>
                      <label className="flex items-center gap-2 text-sm mt-2">
                        <input
                          type="radio"
                          name="merge-mg"
                          value="equipo2"
                          checked={mergeMgChoice === "equipo2"}
                          onChange={() => setMergeMgChoice("equipo2")}
                          disabled={mergeSaving}
                        />
                        Equipo 2: {mergeEquipo2.numero_interno || "(vacio)"}
                      </label>
                      {!mergeMgFinalValue && (mergeEquipo1.numero_interno || mergeEquipo2.numero_interno) && (
                        <div className="text-xs text-amber-700 mt-2">
                          El equipo elegido no tiene MG; el MG final quedara vacio.
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-gray-600">Selecciona un equipo 2 para continuar.</div>
                )}
              </div>
            )}

            <div className="flex justify-between items-center mt-4">
              <button
                className="px-3 py-1.5 rounded border"
                onClick={resetMergeState}
                disabled={mergeSaving}
              >
                Cancelar
              </button>
              {mergeStep === 2 && (
                <button
                  className="px-3 py-1.5 rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
                  disabled={!canSubmitMerge}
                  onClick={async () => {
                    if (!mergeEquipo1 || !mergeEquipo2 || !mergeNsFinalValue) return;
                    setMergeErr("");
                    try {
                      setMergeSaving(true);
                      await postDevicesMerge({
                        target_id: mergeEquipo1.id,
                        source_id: mergeEquipo2.id,
                        numero_serie: mergeNsFinalValue,
                        numero_interno: mergeMgFinalValue,
                      });
                      resetMergeState();
                      setParams({ ts: Date.now() });
                      load(1, { reset: true });
                    } catch (e) {
                      const ctype = e?.data?.conflict_type;
                      if (ctype === "MG_MISMATCH") setMergeErr("Los equipos tienen MG distintos; no se puede unificar.");
                      else if (ctype === "NS_DUPLICATE") setMergeErr("El N/S final ya esta en uso por otro equipo.");
                      else if (ctype === "MG_DUPLICATE") setMergeErr("El MG elegido ya esta en uso por otro equipo.");
                      else if (ctype === "MG_INVALID") setMergeErr("El MG elegido no es valido.");
                      else setMergeErr(e?.message || "No se pudo unificar.");
                    } finally {
                      setMergeSaving(false);
                    }
                  }}
                >
                  Unificar
                </button>
              )}
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

