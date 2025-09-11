import { useEffect, useState } from "react";
import {
  getMarcas, postMarca, deleteMarca,
  getModelos, postModelo, deleteModelo,
  getTecnicos, patchMarcaTecnico, postMarcaAplicarTecnico, patchModeloTecnico,
  getTiposEquipo, patchModeloTipoEquipo, // 👈 NUEVO
} from "../lib/api";

const Input  = (p) => <input  {...p} className="border rounded p-2 w-full" />;
const Select = (p) => <select {...p} className="border rounded p-2 w-full" />;

export default function CatalogoMarcas() {
  const [marcas, setMarcas] = useState([]);
  const [sel, setSel] = useState(null);

  const [modelos, setModelos] = useState([]);
  const [tecnicos, setTecnicos] = useState([]);
  const [tipos, setTipos] = useState([]);                 // 👈 lista desde BD

  const [fm, setFm]   = useState({ nombre:"" });
  const [fmo, setFmo] = useState({ nombre:"" });

  const [marcaTecId, setMarcaTecId] = useState(null);     // técnico de la marca seleccionada
  const [mdlTecSel, setMdlTecSel]   = useState({});       // { [modeloId]: tecnico_id }
  const [mdlTipoSel, setMdlTipoSel] = useState({});       // { [modeloId]: tipo_equipo (texto) }
  const [expandedModelId, setExpandedModelId] = useState(null);

  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  // ==== CARGAS ====
  const loadMarcas = async () => {
    setErr(""); setMsg("");
    try { setMarcas(await getMarcas()); } catch(e){ setErr(e.message); }
  };
  const loadTecnicos = async () => {
    try { setTecnicos(await getTecnicos()); } catch { /* puede haber RLS */ }
  };
  const loadTipos = async () => {
    try { setTipos(await getTiposEquipo()); } catch(e){ setErr(e.message); }
  };
  const loadModelos = async (brandId) => {
    setModelos([]); setMdlTecSel({}); setMdlTipoSel({});
    if (!brandId) return;
    try {
      const ms = await getModelos(brandId); // ⚠️ debe incluir campo m.tipo_equipo
      setModelos(ms);
      const mapTec = {};
      const mapTipo = {};
      (ms || []).forEach(m => {
        mapTec[m.id] = m.tecnico_id ?? "";
        mapTipo[m.id] = m.tipo_equipo ?? "";
      });
      setMdlTecSel(mapTec);
      setMdlTipoSel(mapTipo);
    } catch(e){ setErr(e.message); }
  };

  useEffect(() => { loadMarcas(); loadTecnicos(); loadTipos(); }, []);
  useEffect(() => {
    if (sel) {
      setMarcaTecId(sel?.tecnico_id ?? "");
      loadModelos(sel.id);
    } else {
      setMarcaTecId("");
      setModelos([]); setMdlTecSel({}); setMdlTipoSel({});
    }
  }, [sel?.id]);

  // ==== ABM MARCAS/MODELOS ====
  const addMarca = async (e) => {
    e.preventDefault();
    try { await postMarca(fm.nombre); setFm({nombre:""}); setMsg("Marca agregada"); loadMarcas(); }
    catch(e){ setErr(e.message); }
  };
  const delMarca = async (id) => {
    if (!confirm("¿Eliminar marca?")) return;
    try { await deleteMarca(id); setSel(null); loadMarcas(); }
    catch(e){ setErr(e.message); }
  };
  const addModelo = async (e) => {
    e.preventDefault(); if (!sel) return;
    try {
      await postModelo(sel.id, {
        nombre: fmo.nombre,
        tipo_equipo: (fmo.tipo_equipo || "").trim() || undefined,
        tecnico_id: fmo.tecnico_id ? Number(fmo.tecnico_id) : undefined,
      });
      setFmo({ nombre: "", tipo_equipo: "", tecnico_id: "" });
      setMsg("Modelo agregado");
      loadModelos(sel.id);
    }
    catch(e){ setErr(e.message); }
  };
  const delModelo = async (id) => {
    if (!confirm("¿Eliminar modelo?")) return;
    try { await deleteModelo(id); loadModelos(sel.id); }
    catch(e){ setErr(e.message); }
  };

  // ==== ASIGNACIÓN DE TÉCNICOS ====
  async function guardarTecnicoMarcaYApli() {
    if (!sel) return;
    if (!marcaTecId) {
      if (!confirm("Vas a dejar la marca sin técnico. ¿Continuar?")) return;
    } else {
      if (!confirm("Aplicará este técnico a TODOS los modelos de la marca (sobrescribe). ¿Continuar?")) return;
    }
    try {
      setLoading(true); setErr(""); setMsg("");
      await patchMarcaTecnico(sel.id, marcaTecId ? Number(marcaTecId) : null);
      await postMarcaAplicarTecnico(sel.id, true);
      setMsg("Técnico de marca guardado y aplicado a todos los modelos.");
      setSel(prev => prev ? { ...prev, tecnico_id: (marcaTecId || null) ? Number(marcaTecId) : null } : prev);
      await loadModelos(sel.id);
    } catch (e) {
      setErr(e.message || "No se pudo asignar/aplicar el técnico de la marca");
    } finally {
      setLoading(false);
    }
  }

  async function guardarTecnicoModelo(modelId) {
    const tId = mdlTecSel[modelId] || null;
    try {
      setLoading(true); setErr(""); setMsg("");
      await patchModeloTecnico(sel.id, modelId, tId ? Number(tId) : null);
      setMsg("Técnico del modelo guardado.");
      setModelos(ms => ms.map(m => m.id === modelId ? { ...m, tecnico_id: tId ? Number(tId) : null } : m));
    } catch (e) {
      setErr(e.message || "No se pudo guardar el técnico del modelo");
    } finally {
      setLoading(false);
    }
  }

  // ==== TIPO DE EQUIPO ====
  async function guardarTipoEquipo(modelId) {
    const tipoText = (mdlTipoSel[modelId] || "").trim(); // mandamos el TEXTO
    try {
      setLoading(true); setErr(""); setMsg("");
      await patchModeloTipoEquipo(sel.id, modelId, { tipo_equipo: tipoText });
      setMsg("Tipo de equipo del modelo guardado.");
      setModelos(ms => ms.map(m => m.id === modelId ? { ...m, tipo_equipo: tipoText } : m));
    } catch (e) {
      setErr(e.message || "No se pudo guardar el tipo de equipo");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid md:grid-cols-2 gap-6">
      {/* IZQUIERDA: Marcas + técnico de marca */}
      <div>
        <h1 className="text-2xl font-bold mb-3">Marcas</h1>
        {err && <div className="bg-red-100 text-red-700 p-2 rounded mb-2">{err}</div>}
        {msg && <div className="bg-green-100 text-green-700 p-2 rounded mb-2">{msg}</div>}

        <form onSubmit={addMarca} className="border rounded p-3 mb-3 flex gap-2">
          <Input placeholder="Nombre de marca" value={fm.nombre} onChange={e => setFm({nombre:e.target.value})} required/>
          <button className="bg-blue-600 text-white px-4 py-2 rounded">Agregar</button>
        </form>

        <ul className="border rounded divide-y">
          {marcas.map(m => (
            <li key={m.id} className={`p-2 ${sel?.id===m.id ? "bg-gray-50" : ""}`}>
              <div className="flex items-center justify-between">
                <button className="text-left" onClick={() => setSel(m)}>{m.nombre}</button>
                <button className="px-2 py-1 border rounded" onClick={() => delMarca(m.id)}>Eliminar</button>
              </div>

              {sel?.id === m.id && (
                <div className="mt-3 border-t pt-3">
                  <label className="text-sm block mb-1">Técnico asignado a la marca</label>
                  <Select
                    value={marcaTecId ?? ""}
                    onChange={(e) => setMarcaTecId(e.target.value ? Number(e.target.value) : "")}
                  >
                    <option value="">— Sin técnico —</option>
                    {tecnicos.map(t => <option key={t.id} value={t.id}>{t.nombre}</option>)}
                  </Select>

                  <div className="flex gap-2 mt-2">
                    <button
                      className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
                      onClick={guardarTecnicoMarcaYApli}
                      type="button"
                      disabled={loading}
                      title="Guarda en la marca y aplica a todos los modelos (sobrescribe)."
                    >
                      Guardar y aplicar a TODOS los modelos
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
          {!marcas.length && <li className="p-3 text-center text-gray-500">Sin marcas</li>}
        </ul>
      </div>

      {/* DERECHA: Modelos de la marca seleccionada */}
      <div>
        <h2 className="text-xl font-semibold mb-3">
          Modelos {sel ? `de ${sel.nombre}` : ""}
        </h2>

        {sel && (
          <form onSubmit={addModelo} className="border rounded p-3 mb-3 grid grid-cols-1 md:grid-cols-4 gap-2 items-end">
            <div className="md:col-span-2">
              <label className="text-sm block mb-1">Nombre de modelo</label>
              <Input placeholder="Nombre de modelo" value={fmo.nombre} onChange={e => setFmo(f=>({...f, nombre:e.target.value}))} required/>
            </div>
            <div>
              <label className="text-sm block mb-1">Tipo de equipo</label>
              <Select value={fmo.tipo_equipo || ""} onChange={e => setFmo(f=>({...f, tipo_equipo:e.target.value}))}>
                <option value="">— Sin tipo —</option>
                {tipos.map(t => (
                  <option key={t.id ?? t.nombre} value={t.nombre}>{t.nombre}</option>
                ))}
              </Select>
            </div>
            <div>
              <label className="text-sm block mb-1">Técnico</label>
              <Select value={fmo.tecnico_id || ""} onChange={e => setFmo(f=>({...f, tecnico_id:e.target.value}))}>
                <option value="">— Heredar/ninguno —</option>
                {tecnicos.map(t => <option key={t.id} value={t.id}>{t.nombre}</option>)}
              </Select>
            </div>
            <div className="md:col-span-4 flex justify-end">
              <button className="bg-blue-600 text-white px-4 py-2 rounded">Agregar</button>
            </div>
          </form>
        )}

        <ul className="border rounded divide-y">
          {sel ? (
            modelos.map(md => (
              <li key={md.id} className="p-2">
                {/* Cabecera compacta clickeable */}
                <div className="flex items-center justify-between">
                  <button className="text-left font-medium hover:underline" onClick={() => setExpandedModelId(expandedModelId === md.id ? null : md.id)}>
                    {md.nombre}
                  </button>
                  <div className="text-xs text-gray-600 flex gap-3">
                    <span>Tipo: {md.tipo_equipo || "—"}</span>
                    <span>Téc.: {md.tecnico_id ? (tecnicos.find(t => t.id === md.tecnico_id)?.nombre || md.tecnico_id) : "hereda/ninguno"}</span>
                  </div>
                </div>

                {/* Panel de edición expandible */}
                {expandedModelId === md.id && (
                  <div className="mt-3 border rounded p-3 grid grid-cols-1 md:grid-cols-12 gap-3 items-end bg-gray-50">
                    <div className="md:col-span-4">
                      <label className="text-sm block mb-1">Tipo de equipo</label>
                      <Select
                        value={mdlTipoSel[md.id] ?? (md.tipo_equipo || "")}
                        onChange={(e) => setMdlTipoSel(s => ({ ...s, [md.id]: e.target.value }))}
                      >
                        <option value="">— Sin tipo —</option>
                        {tipos.map(t => (
                          <option key={t.id ?? t.nombre} value={t.nombre}>{t.nombre}</option>
                        ))}
                      </Select>
                    </div>
                    <div className="md:col-span-4">
                      <label className="text-sm block mb-1">Técnico</label>
                      <Select
                        value={mdlTecSel[md.id] ?? (md.tecnico_id || "")}
                        onChange={(e) => setMdlTecSel((s) => ({ ...s, [md.id]: e.target.value ? Number(e.target.value) : "" }))}
                      >
                        <option value="">— Heredar/ninguno —</option>
                        {tecnicos.map(t => <option key={t.id} value={t.id}>{t.nombre}</option>)}
                      </Select>
                    </div>
                    <div className="md:col-span-4 flex gap-2 justify-end">
                      <button
                        className="px-3 py-2 border rounded disabled:opacity-60"
                        onClick={() => guardarTipoEquipo(md.id)}
                        type="button"
                        disabled={loading}
                        title="Guardar tipo de equipo"
                      >
                        Guardar tipo
                      </button>
                      <button
                        className="px-3 py-2 border rounded disabled:opacity-60"
                        onClick={() => guardarTecnicoModelo(md.id)}
                        type="button"
                        disabled={loading}
                      >
                        Guardar técnico
                      </button>
                      <button
                        className="px-3 py-2 border rounded"
                        onClick={() => delModelo(md.id)}
                        type="button"
                      >
                        Eliminar
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))
          ) : (
            <li className="p-3 text-center text-gray-500">Seleccioná una marca</li>
          )}
          {sel && !modelos.length && <li className="p-3 text-center text-gray-500">Sin modelos</li>}
        </ul>
      </div>
    </div>
  );
}
