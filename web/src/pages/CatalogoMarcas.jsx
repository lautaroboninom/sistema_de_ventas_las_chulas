import { useEffect, useMemo, useRef, useState } from "react";
import {
  getMarcas, postMarca, deleteMarcaCascade,
  getModelos, postModelo, deleteModelo,
  getTecnicos, patchMarcaTecnico, postMarcaAplicarTecnico, patchModeloTecnico,
  getTiposEquipo, patchModeloTipoEquipo,
  patchMarca, patchModelo, postModelMerge, postMarcaMerge,
  // Catálogo jerárquico (v2)
  getCatalogTipos as fetchCatalogTipos,
  getCatalogModelos as fetchCatalogModelos,
  getCatalogVariantes as fetchCatalogVariantes,
  postCatalogModelo as createCatalogModelo,
  postCatalogVariante, patchCatalogVariante, deleteCatalogVariante,
} from "../lib/api";
import { norm } from "../lib/ui-helpers";

const Input  = (p) => <input  {...p} className="border rounded p-2 w-full" />;
const Select = (p) => <select {...p} className="border rounded p-2 w-full" />;

export default function CatalogoMarcas() {
  // Canonicalizador general: minÃºsculas, sin acentos y con espacios colapsados
  const canon   = (v) => norm(v).replace(/\s+/g, " ").trim();
  const typeKey = (v) => (v ?? "").toString().toLowerCase().replace(/\s+/g, " ").trim();

  const [marcas, setMarcas] = useState([]);
  const [sel, setSel] = useState(null);

  const [modelos, setModelos] = useState([]);
  const [tecnicos, setTecnicos] = useState([]);
  const [tipos, setTipos] = useState([]);

  const [fm, setFm]   = useState({ nombre: "" });
  const [fmo, setFmo] = useState({ nombre: "", tipo_equipo: "", tecnico_id: "" });

  const [marcaTecId, setMarcaTecId] = useState(null);
  const [mdlTecSel, setMdlTecSel]   = useState({}); // { [modeloId]: tecnico_id }
  const [mdlTipoSel, setMdlTipoSel] = useState({}); // { [modeloId]: tipo_equipo }
  const [expandedModelId, setExpandedModelId] = useState(null);

  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [marcaQuery, setMarcaQuery] = useState("");
  const listRef = useRef(null);

  // Catálogo (v2) para variantes mÃºltiples
  const [hierLoading, setHierLoading] = useState(false);
  const [catalogTipos, setCatalogTipos] = useState([]);
  const [catalogModelos, setCatalogModelos] = useState([]);
  const [catalogVariantes, setCatalogVariantes] = useState([]);
  const [tipoSelId, setTipoSelId] = useState(null);
  const [modeloSelId, setModeloSelId] = useState(null);
  const [varianteForm, setVarianteForm] = useState({ nombre: "" });

  // Variantes por modelo (inline)
  const [perModelVariants, setPerModelVariants] = useState({});
  function updatePMV(modelId, updater) {
    setPerModelVariants((prev) => {
      const cur = prev[modelId] || { loading:false, error:"", variantes:[], tipoId:null, serieId:null, newName:"" };
      const next = typeof updater === 'function' ? updater(cur) : { ...(cur||{}), ...(updater||{}) };
      return { ...prev, [modelId]: next };
    });
  }

  async function ensureModelCatalogVariants(md) {
    if (!sel?.id || !md) return;
    updatePMV(md.id, { loading:true, error:"" });
    try {
      const tipos = await fetchCatalogTipos(sel.id, true);
      const tipoName = (md.tipo_equipo || "").trim();
      if (!tipoName) { updatePMV(md.id, { loading:false, error:"El modelo no tiene tipo de equipo asignado", variantes:[], tipoId:null, serieId:null }); return; }
      const tipo = (tipos||[]).find(t => {
        const tName = typeKey(t?.name || "");
        const tLabel = typeKey(t?.label || t?.name || "");
        const needle = typeKey(tipoName);
        return tName === needle || tLabel === needle;
      });
      if (!tipo) { updatePMV(md.id, { loading:false, error:`No se encontrÃ³ el Tipo en catálogo para: ${tipoName}`, variantes:[], tipoId:null, serieId:null }); return; }
      const modelosCat = await fetchCatalogModelos(sel.id, tipo.id);
      const mdName = canon(md.nombre || "");
      let serie = modelosCat.find(m => canon(m.name||"") === mdName || (m.alias && canon(m.alias) === mdName));
      if (!serie) {
        serie = modelosCat.find(m => {
          const sName = canon(m.name||"");
          const sAlias = canon(m.alias||"");
          return mdName && (sName.includes(mdName) || mdName.includes(sName) || (sAlias && (sAlias === mdName || sAlias.includes(mdName) || mdName.includes(sAlias))));
        });
      }
      if (!serie) {
        try {
          await createCatalogModelo({ marca_id: sel.id, tipo_id: tipo.id, name: md.nombre, active: true });
          const modelosCat2 = await fetchCatalogModelos(sel.id, tipo.id, true);
          const mdName2 = canon(md.nombre || "");
          serie = modelosCat2.find(m => canon(m.name||"") === mdName2 || (m.alias && canon(m.alias) === mdName2))
               || modelosCat2.find(m => {
                    const sName = canon(m.name||"");
                    const sAlias = canon(m.alias||"");
                    return mdName2 && (sName.includes(mdName2) || mdName2.includes(sName) || (sAlias && (sAlias === mdName2 || sAlias.includes(mdName2) || mdName2.includes(sAlias))));
                  });
        } catch (e) { updatePMV(md.id, { loading:false, error:`No hay Modelo de catálogo que coincida con: ${md.nombre}`, variantes:[], tipoId: tipo.id, serieId:null }); return; }
        if (!serie) { updatePMV(md.id, { loading:false, error:`No hay Modelo de catálogo que coincida con: ${md.nombre}`, variantes:[], tipoId: tipo.id, serieId:null }); return; }
      }
      const variantes = await fetchCatalogVariantes(sel.id, tipo.id, serie.id);
      updatePMV(md.id, { loading:false, error:"", variantes, tipoId: tipo.id, serieId: serie.id });
    } catch (e) { updatePMV(md.id, { loading:false, error: e?.message || "No se pudieron cargar variantes", variantes:[] }); }
  }

  async function addVarianteInline(modelId) {
    const state = perModelVariants[modelId];
    const nombre = (state?.newName || "").trim();
    if (!sel?.id || !state?.tipoId || !state?.serieId || !nombre) return;
    try { updatePMV(modelId, { loading:true }); await postCatalogVariante({ marca_id: sel.id, tipo_id: state.tipoId, serie_id: state.serieId, name: nombre, active: true }); const variantes = await fetchCatalogVariantes(sel.id, state.tipoId, state.serieId, true); updatePMV(modelId, { loading:false, variantes, newName:"" }); setMsg("Variante agregada"); }
    catch (e) { updatePMV(modelId, { loading:false }); setErr(e?.message || "No se pudo agregar la variante"); }
  }

  const filteredMarcas = useMemo(() => {
    const q = norm(marcaQuery);
    if (!q) return marcas;
    return (marcas || []).filter((m) => norm(m?.nombre || "").includes(q));
  }, [marcaQuery, marcas]);

  // CARGAS
  const loadMarcas = async () => { setErr(""); setMsg(""); try { setMarcas(await getMarcas()); } catch (e) { setErr(e.message); } };
  const loadTecnicos = async () => { try { setTecnicos(await getTecnicos()); } catch { /* RLS */ } };
  const loadTipos = async () => { try { setTipos(await getTiposEquipo()); } catch (e) { setErr(e.message); } };
  const loadModelos = async (brandId) => {
    setModelos([]); setMdlTecSel({}); setMdlTipoSel({});
    if (!brandId) return;
    try {
      const ms = await getModelos(brandId);
      setModelos(ms);
      const mapTec = {}, mapTipo = {};
      (ms || []).forEach((m) => { mapTec[m.id] = m.tecnico_id ?? ""; mapTipo[m.id] = m.tipo_equipo ?? ""; });
      setMdlTecSel(mapTec); setMdlTipoSel(mapTipo);
    } catch (e) { setErr(e.message); }
  };

  useEffect(() => { loadMarcas(); loadTecnicos(); loadTipos(); }, []);
  useEffect(() => {
    if (sel) {
      setMarcaTecId(sel?.tecnico_id ?? "");
      loadModelos(sel.id);
      (async()=>{ try{ setHierLoading(true); const ts = await fetchCatalogTipos(sel.id); setCatalogTipos(ts); setTipoSelId(null); setCatalogModelos([]); setModeloSelId(null); setCatalogVariantes([]);} catch(e){ setErr(e.message || "No se pudieron cargar tipos del catálogo"); setCatalogTipos([]); setTipoSelId(null); setCatalogModelos([]); setModeloSelId(null); setCatalogVariantes([]);} finally{ setHierLoading(false);} })();
    } else {
      setMarcaTecId("");
      setModelos([]); setMdlTecSel({}); setMdlTipoSel({}); setCatalogTipos([]); setTipoSelId(null); setCatalogModelos([]); setModeloSelId(null); setCatalogVariantes([]);
    }
  }, [sel?.id]);

  useEffect(() => { if (!sel?.id || !tipoSelId){ setCatalogModelos([]); setModeloSelId(null); setCatalogVariantes([]); return;} (async()=>{ try{ setHierLoading(true); const ms=await fetchCatalogModelos(sel.id, tipoSelId); setCatalogModelos(ms); setModeloSelId(null); setCatalogVariantes([]);} catch(e){ setErr(e.message||"No se pudieron cargar modelos del catálogo"); setCatalogModelos([]); setModeloSelId(null); setCatalogVariantes([]);} finally{ setHierLoading(false);} })(); }, [sel?.id, tipoSelId]);
  useEffect(() => { if (!sel?.id || !modeloSelId){ setCatalogVariantes([]); return;} (async()=>{ try{ setHierLoading(true); const vs=await fetchCatalogVariantes(sel.id, tipoSelId, modeloSelId); setCatalogVariantes(vs);} catch(e){ setErr(e.message||"No se pudieron cargar variantes"); setCatalogVariantes([]);} finally{ setHierLoading(false);} })(); }, [sel?.id, tipoSelId, modeloSelId]);

  async function handleAddVariante(e){
    e.preventDefault();
    if(!sel?.id || !tipoSelId || !modeloSelId) return;
    const nombre=(varianteForm.nombre||"").trim();
    if(!nombre) return;
    try{
      setHierLoading(true); setErr(""); setMsg("");
      await postCatalogVariante({ marca_id: sel.id, tipo_id: tipoSelId, serie_id: modeloSelId, name:nombre, active:true });
      setVarianteForm({nombre:""});
      const vs=await fetchCatalogVariantes(sel.id, tipoSelId, modeloSelId, true);
      setCatalogVariantes(vs);
      setMsg("Variante agregada");
    } catch(e){
      setErr(e.message||"No se pudo agregar la variante");
    } finally{
      setHierLoading(false);
    }
  }

  // ABM marcas/modelos
  const addMarca = async (e) => { e.preventDefault(); try { await postMarca(fm.nombre); setFm({ nombre: "" }); setMsg("Marca agregada"); loadMarcas(); } catch (e) { setErr(e.message); } };
  const delMarcaCascade = async (id) => {
    const typed = prompt(
      "Esta acciÃ³n eliminará la marca y TODOS sus modelos. Se desvincularán equipos relacionados.\nEscribe ELIMINAR para confirmar:",
      ""
    );
    if (typed !== "ELIMINAR") return;
    try { setErr(""); setMsg(""); await deleteMarcaCascade(id); setSel(null); loadMarcas(); setMsg("Marca y modelos eliminados"); }
    catch (e) { setErr(e?.message || "No se pudo eliminar en cascada"); }
  };
  const addModelo = async (e) => { e.preventDefault(); if (!sel) return; try { await postModelo(sel.id, { nombre: fmo.nombre, tipo_equipo: (fmo.tipo_equipo || "").trim() || undefined, tecnico_id: fmo.tecnico_id ? Number(fmo.tecnico_id) : undefined }); setFmo({ nombre: "", tipo_equipo: "", tecnico_id: "" }); setMsg("Modelo agregado"); loadModelos(sel.id); } catch (e) { setErr(e.message); } };
  const delModelo = async (id) => { if (!confirm("Â¿Eliminar modelo?")) return; try { await deleteModelo(id); loadModelos(sel.id); } catch (e) { setErr(e.message); } };

  // Técnicos / tipo de equipo
  async function guardarTecnicoMarcaYApli(){ if(!sel) return; if(!marcaTecId ? !confirm("Vas a dejar la marca sin técnico. Â¿Continuar?") : !confirm("Aplicar este técnico a TODOS los modelos de la marca (sobrescribe). Â¿Continuar?")) return; try{ setLoading(true); setErr(""); setMsg(""); await patchMarcaTecnico(sel.id, marcaTecId ? Number(marcaTecId) : null); await postMarcaAplicarTecnico(sel.id, true); setMsg("Técnico de marca guardado y aplicado a todos los modelos."); setSel(prev => prev ? { ...prev, tecnico_id: (marcaTecId || null) ? Number(marcaTecId) : null } : prev); await loadModelos(sel.id);} catch(e){ setErr(e.message || "No se pudo asignar/aplicar el técnico de la marca"); } finally{ setLoading(false);} }
  async function guardarTecnicoModelo(modelId){ const tId = mdlTecSel[modelId] || null; try{ setLoading(true); setErr(""); setMsg(""); await patchModeloTecnico(sel.id, modelId, tId ? Number(tId) : null); setMsg("Técnico del modelo guardado."); setModelos(ms => ms.map(m => m.id === modelId ? { ...m, tecnico_id: tId ? Number(tId) : null } : m)); } catch(e){ setErr(e.message || "No se pudo guardar el técnico del modelo"); } finally{ setLoading(false);} }
  async function guardarTipoEquipo(modelId){ const tipoText=(mdlTipoSel[modelId]||"").trim(); try{ setLoading(true); setErr(""); setMsg(""); await patchModeloTipoEquipo(sel.id, modelId, { tipo_equipo: tipoText }); setMsg("Tipo de equipo del modelo guardado."); setModelos(ms => ms.map(m => m.id === modelId ? { ...m, tipo_equipo: tipoText } : m)); const updated = modelos.find(m=>m.id===modelId); if(updated){ await ensureModelCatalogVariants({ ...updated, tipo_equipo: tipoText }); } } catch(e){ setErr(e.message || "No se pudo guardar el tipo de equipo"); } finally{ setLoading(false);} }

  return (
    <div className="grid md:grid-cols-2 gap-6">
      {/* IZQUIERDA: Marcas */}
      <div>
        <h1 className="text-2xl font-bold mb-3">Marcas</h1>
        {err && <div className="bg-red-100 text-red-700 p-2 rounded mb-2">{err}</div>}
        {msg && <div className="bg-green-100 text-green-700 p-2 rounded mb-2">{msg}</div>}

        <form onSubmit={addMarca} className="border rounded p-3 mb-3 flex gap-2">
          <Input placeholder="Nombre de marca" value={fm.nombre} onChange={(e) => setFm({ nombre: e.target.value })} required />
          <button className="bg-blue-600 text-white px-4 py-2 rounded">Agregar</button>
        </form>

        <div className="mb-2">
          <Input placeholder="Buscar marca" value={marcaQuery} onChange={(e) => setMarcaQuery(e.target.value)} />
        </div>

        <div ref={listRef} className="border rounded max-h-80 overflow-auto">
          <ul className="divide-y">
            {marcas.filter(m => norm(m?.nombre||"").includes(norm(marcaQuery))).map((m) => (
              <li key={m.id} className={`p-2 ${sel?.id === m.id ? "bg-gray-50" : ""}`}>
                <div className="flex items-center justify-between">
                  <button className="text-left" onClick={() => { setSel(m); try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch { window.scrollTo(0,0);} if (listRef.current) { try { listRef.current.scrollTop = 0; } catch {} } }}>{m.nombre}</button>
                  <div className="flex gap-2">
                    <button className="px-2 py-1 border rounded" onClick={async () => { const nuevo = prompt("Renombrar marca", m.nombre || ""); const nombre = (nuevo || "").trim(); if (!nombre || nombre === m.nombre) return; try { setErr(""); setMsg(""); await patchMarca(m.id, { nombre }); setMarcas(arr => arr.map(x => x.id === m.id ? { ...x, nombre } : x)); if (sel?.id === m.id) setSel(prev => prev ? { ...prev, nombre } : prev); setMsg("Marca renombrada"); } catch (e) { const msg = e?.message || ""; if (msg.includes("409")) { try { const desired = canon(nombre); const dup = (marcas||[]).find(x => x.id !== m.id && canon(x.nombre||"") === desired); if (dup) { const ok = confirm(`Ya existe una marca con ese nombre (ID ${dup.id}). ¿Unificar?`); if (ok) { await postMarcaMerge(m.id, dup.id); await loadMarcas(); if (sel?.id === m.id) setSel(dup); setMsg("Marcas unificadas"); return; } } } catch {} } setErr(msg || "No se pudo renombrar la marca"); } }}>Renombrar</button>
                    <button className="px-2 py-1 border rounded text-red-700" title="Elimina la marca y TODOS sus modelos" onClick={() => delMarcaCascade(m.id)}>Eliminar TODO</button>
                  </div>
                </div>

                {sel?.id === m.id && (
                  <div className="mt-3 border-t pt-3">
                    <label className="text-sm block mb-1">Técnico asignado a la marca</label>
                    <Select value={marcaTecId ?? ""} onChange={(e) => setMarcaTecId(e.target.value ? Number(e.target.value) : "") }>
                      <option value="">- Sin técnico -</option>
                      {tecnicos.map((t) => (<option key={t.id} value={t.id}>{t.nombre}</option>))}
                    </Select>
                    <div className="flex gap-2 mt-2">
                      <button className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60" onClick={guardarTecnicoMarcaYApli} type="button" disabled={loading} title="Guarda en la marca y aplica a todos los modelos (sobrescribe).">Guardar y aplicar a TODOS los modelos</button>
                    </div>
                  </div>
                )}
              </li>
            ))}
            {!filteredMarcas.length && <li className="p-3 text-center text-gray-500">Sin marcas</li>}
          </ul>
        </div>
      </div>

      {/* DERECHA: Modelos */}
      <div>
        <h2 className="text-xl font-semibold mb-3">Modelos {sel ? `de ${sel.nombre}` : ""}</h2>

        {sel && (
          <form onSubmit={addModelo} className="border rounded p-3 mb-3 grid grid-cols-1 md:grid-cols-5 gap-2 items-end">
            <div className="md:col-span-2">
              <label className="text-sm block mb-1">Nombre de modelo</label>
              <Input placeholder="Nombre de modelo" value={fmo.nombre} onChange={(e) => setFmo((f) => ({ ...f, nombre: e.target.value }))} required />
            </div>
            <div>
              <label className="text-sm block mb-1">Tipo de equipo</label>
              <Select value={fmo.tipo_equipo || ""} onChange={(e) => setFmo((f) => ({ ...f, tipo_equipo: e.target.value }))}>
                <option value="">- Sin tipo -</option>
                {tipos.map((t) => (<option key={t.id ?? t.nombre} value={t.nombre}>{t.nombre}</option>))}
              </Select>
            </div>
            <div>
              <label className="text-sm block mb-1">Técnico</label>
              <Select value={fmo.tecnico_id || ""} onChange={(e) => setFmo((f) => ({ ...f, tecnico_id: e.target.value }))}>
                <option value="">- Heredar/ninguno -</option>
                {tecnicos.map((t) => (<option key={t.id} value={t.id}>{t.nombre}</option>))}
              </Select>
            </div>
            <div className="md:col-span-5 flex justify-end">
              <button className="bg-blue-600 text-white px-4 py-2 rounded">Agregar</button>
            </div>
          </form>
        )}

        <ul className="border rounded divide-y">
          {sel ? (
            modelos.map((md) => (
              <li key={md.id} className="p-2">
                {/* Cabecera compacta clickeable */}
                <div className="flex items-center justify-between">
                  <button className="text-left font-medium hover:underline" onClick={() => { const expanding = expandedModelId !== md.id; setExpandedModelId(expanding ? md.id : null); if (expanding) ensureModelCatalogVariants(md); }}>{md.nombre}</button>
                  <div className="text-xs text-gray-600 flex gap-3 items-center">
                    <span>Tipo: {md.tipo_equipo || "-"}</span>
                    <span>Var.: {(perModelVariants[md.id]?.variantes || []).length || (md.variante ? 1 : 0)}</span>
                    <span>Téc.: {md.tecnico_id ? (tecnicos.find((t) => t.id === md.tecnico_id)?.nombre || md.tecnico_id) : "hereda/ninguno"}</span>
                    <button className="px-2 py-1 border rounded text-xs" type="button" onClick={async () => {
  const nuevo = prompt("Renombrar modelo", md.nombre || "");
  const nombre = (nuevo || "").trim();
  if (!nombre || nombre === md.nombre) return;
  try {
    setLoading(true); setErr(""); setMsg("");
    await patchModelo(md.id, { nombre });
    setModelos(arr => arr.map(x => x.id === md.id ? { ...x, nombre } : x));
    setMsg("Modelo renombrado");
  } catch (e) {
    const msg = e?.message || "";
    if (msg.includes("409")) {
      try {
        const ms = await getModelos(sel.id);
        const desired = canon(nombre);
        const myTipo = typeKey(mdlTipoSel[md.id] ?? md.tipo_equipo ?? "");
        const dup = (ms||[]).find(x => x.id !== md.id && canon(x.nombre||"") === desired && typeKey(x.tipo_equipo||"") === myTipo);
        if (dup) {
          const ok = confirm(`Ya existe un modelo con ese nombre y tipo de equipo (ID ${dup.id}). ¿Unificar?`);
          if (ok) {
            await postModelMerge(md.id, dup.id);
            await loadModelos(sel.id);
            setExpandedModelId(dup.id);
            setMsg("Modelos unificados");
            return;
          }
        }
      } catch {}
    }
    setErr(msg || "No se pudo renombrar el modelo");
  } finally { setLoading(false); }
}}>Renombrar</button>
                  </div>
                </div>

                {/* Panel de ediciÃ³n expandible */}
                {expandedModelId === md.id && (
                  <div className="mt-3 border rounded p-3 grid grid-cols-1 md:grid-cols-12 gap-3 items-end bg-gray-50">
                    <div className="md:col-span-4">
                      <label className="text-sm block mb-1">Tipo de equipo</label>
                      <Select value={mdlTipoSel[md.id] ?? (md.tipo_equipo || "")} onChange={(e) => setMdlTipoSel((s) => ({ ...s, [md.id]: e.target.value }))}>
                        <option value="">- Sin tipo -</option>
                        {tipos.map((t) => (<option key={t.id ?? t.nombre} value={t.nombre}>{t.nombre}</option>))}
                      </Select>
                    </div>
                    <div className="md:col-span-4">
                      <label className="text-sm block mb-1">Técnico</label>
                      <Select value={mdlTecSel[md.id] ?? (md.tecnico_id || "")} onChange={(e) => setMdlTecSel((s) => ({ ...s, [md.id]: e.target.value ? Number(e.target.value) : "" }))}>
                        <option value="">- Heredar/ninguno -</option>
                        {tecnicos.map((t) => (<option key={t.id} value={t.id}>{t.nombre}</option>))}
                      </Select>
                    </div>
                    <div className="md:col-span-12">
                      <label className="text-sm block mb-1">Variantes (catálogo)</label>
                      {perModelVariants[md.id]?.error ? (<div className="text-xs text-red-600 mb-2">{perModelVariants[md.id]?.error}</div>) : null}
                      <ul className="border rounded divide-y max-h-56 overflow-auto">
                        {(perModelVariants[md.id]?.variantes || []).map((v) => (
                          <li key={v.id ?? v.name} className="p-2 text-sm flex items-center justify-between gap-2">
                            <div className="flex-1 truncate">
                              <span className="font-medium">{v.name}</span>
                              <span className="ml-2 text-xs text-gray-500">{v.active ? "activo" : "inactivo"}</span>
                            </div>
                            {v.id != null && (
                              <div className="flex gap-2">
                                <button type="button" className="px-2 py-1 border rounded text-xs" onClick={() => { const nuevo = prompt("Renombrar variante", v.name); const nombre = (nuevo || "").trim(); if (!nombre || nombre === v.name) return; (async () => { try { updatePMV(md.id, { loading:true }); await patchCatalogVariante(v.id, { name: nombre }); const vs = await fetchCatalogVariantes(sel.id, perModelVariants[md.id]?.tipoId, perModelVariants[md.id]?.serieId, true); updatePMV(md.id, { loading:false, variantes: vs }); setMsg("Variante renombrada"); } catch (e) { updatePMV(md.id, { loading:false }); setErr(e?.message || "No se pudo renombrar la variante"); } })(); }}>Renombrar</button>
                                <button type="button" className="px-2 py-1 border rounded text-xs" onClick={() => { (async () => { try { updatePMV(md.id, { loading:true }); await patchCatalogVariante(v.id, { active: !v.active }); const vs = await fetchCatalogVariantes(sel.id, perModelVariants[md.id]?.tipoId, perModelVariants[md.id]?.serieId, true); updatePMV(md.id, { loading:false, variantes: vs }); setMsg("Variante actualizada"); } catch (e) { updatePMV(md.id, { loading:false }); setErr(e?.message || "No se pudo actualizar la variante"); } })(); }}>{v.active ? "Desactivar" : "Activar"}</button>
                                <button type="button" className="px-2 py-1 border rounded text-xs" onClick={() => { if (!confirm('Â¿Eliminar variante?')) return; (async () => { try { updatePMV(md.id, { loading:true }); await deleteCatalogVariante(v.id); const vs = await fetchCatalogVariantes(sel.id, perModelVariants[md.id]?.tipoId, perModelVariants[md.id]?.serieId, true); updatePMV(md.id, { loading:false, variantes: vs }); setMsg("Variante eliminada"); } catch (e) { updatePMV(md.id, { loading:false }); setErr(e?.message || "No se pudo eliminar la variante"); } })(); }}>Eliminar</button>
                              </div>
                            )}
                          </li>
                        ))}
                        {!perModelVariants[md.id]?.variantes?.length && (<li className="p-2 text-xs text-gray-500">{perModelVariants[md.id]?.loading ? "Cargando..." : "Sin variantes"}</li>)}
                      </ul>
                      <form className="mt-2 flex gap-2 items-end" onSubmit={(e)=>{ e.preventDefault(); addVarianteInline(md.id); }}>
                        <div className="flex-1">
                          <label className="block text-xs text-gray-500">Agregar variante</label>
                          <Input placeholder="Nombre de variante" value={perModelVariants[md.id]?.newName || ""} onChange={(e)=> updatePMV(md.id, (cur)=> ({ ...cur, newName: e.target.value }))}/>
                        </div>
                        <button type="submit" className="px-3 py-2 border rounded text-sm bg-blue-600 text-white disabled:opacity-60" disabled={perModelVariants[md.id]?.loading || !perModelVariants[md.id]?.serieId || !(perModelVariants[md.id]?.newName||'').trim()} title={!perModelVariants[md.id]?.serieId ? "No se pudo resolver el modelo del catálogo" : ""}>Agregar</button>
                      </form>
                    </div>

                    <div className="md:col-span-12 flex gap-2 justify-end mt-3">
                      <button className="px-3 py-2 border rounded disabled:opacity-60" onClick={() => guardarTipoEquipo(md.id)} type="button" disabled={loading} title="Guardar tipo de equipo">Guardar tipo</button>
                      <button className="px-3 py-2 border rounded disabled:opacity-60" onClick={() => guardarTecnicoModelo(md.id)} type="button" disabled={loading}>Guardar técnico</button>
                      <button className="px-3 py-2 border rounded" onClick={() => delModelo(md.id)} type="button">Eliminar</button>
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






