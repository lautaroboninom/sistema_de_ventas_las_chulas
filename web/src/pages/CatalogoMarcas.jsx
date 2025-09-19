import { useEffect, useMemo, useRef, useState } from "react";
import {
  getMarcas, postMarca, deleteMarca,
  getModelos, postModelo, deleteModelo,
  getTecnicos, patchMarcaTecnico, postMarcaAplicarTecnico, patchModeloTecnico,
  getTiposEquipo, patchModeloTipoEquipo, // 👈 NUEVO
  getCatalogBrandsV2, getCatalogTypes, createCatalogType, updateCatalogType, deleteCatalogType,
  getCatalogSeries, createCatalogSeries, updateCatalogSeries, deleteCatalogSeries,
  getCatalogVariants, createCatalogVariant, updateCatalogVariant, deleteCatalogVariant,
} from "../lib/api";
import { norm } from "@/lib/ui-helpers";
import { featureEnabled } from "@/lib/features";


const Input  = (p) => <input  {...p} className="border rounded p-2 w-full" />;
const Select = (p) => <select {...p} className="border rounded p-2 w-full" />;

function CatalogoMarcasLegacy() {
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

  const [marcaQuery, setMarcaQuery] = useState("");
  const listRef = useRef(null);

  const filteredMarcas = useMemo(() => {
    const q = norm(marcaQuery);
    if (!q) return marcas;
    return marcas.filter((m) => norm(m.nombre).includes(q));
  }, [marcaQuery, marcas]);

  // ==== CARGAS ====
  const loadMarcas = async (preserveMsg = false) => {
    setErr("");
    if (!preserveMsg) setMsg("");
    try {
      const rows = await getMarcas();
      setMarcas(rows);
      return rows;
    } catch(e){
      setErr(e.message);
      return [];
    }
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
    setExpandedModelId(null);
    if (sel) {
      setMarcaTecId(sel?.tecnico_id ?? "");
      loadModelos(sel.id);
      const node = listRef.current?.querySelector(`[data-id="${sel.id}"]`);
      if (node && typeof node.scrollIntoView === "function") {
        node.scrollIntoView({ block: "nearest" });
      }
    } else {
      setMarcaTecId("");
      setModelos([]); setMdlTecSel({}); setMdlTipoSel({});
    }
  }, [sel?.id]);

  const handleSelectMarca = (marca) => {
    setSel(marca);
    if (typeof window !== 'undefined') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  // ==== ABM MARCAS/MODELOS ====
  const addMarca = async (e) => {
    e.preventDefault();
    const nombre = (fm.nombre || "").trim();
    if (!nombre) return;
    setErr("");
    try {
      const res = await postMarca(nombre);
      setFm({ nombre: "" });
      setMarcaQuery("");
      const rows = await loadMarcas(true);
      if (Array.isArray(rows) && res?.id) {
        const found = rows.find((m) => m.id === res.id);
        if (found) handleSelectMarca(found);
      }
      if (res?.created) {
        setMsg("Marca agregada");
      } else if (res?.updated) {
        setMsg("Marca actualizada");
      } else {
        setMsg("Marca disponible");
      }
    } catch(e){
      setErr(e.message);
    }
  };
  const delMarca = async (id) => {
    if (!confirm("¿Eliminar marca?")) return;
    setErr("");
    try {
      await deleteMarca(id);
      setSel(null);
      await loadMarcas(true);
      setMsg("Marca eliminada");
    } catch(e){ setErr(e.message); }
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

        <div className="mb-3">
          <Input
            placeholder="Buscar marca"
            value={marcaQuery}
            onChange={(e) => setMarcaQuery(e.target.value)}
          />
        </div>

        <ul ref={listRef} className="border rounded divide-y max-h-[60vh] overflow-auto">
          {filteredMarcas.map(m => (
            <li
              key={m.id}
              data-id={m.id}
              className={`p-2 border-l-4 ${sel?.id === m.id ? "border-blue-500 bg-blue-50" : "border-transparent hover:bg-gray-50"}`}
            >
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  className="text-left font-medium hover:underline flex-1"
                  onClick={() => handleSelectMarca(m)}
                >
                  {m.nombre}
                </button>
                <button
                  type="button"
                  className="px-2 py-1 border rounded text-xs"
                  onClick={(ev) => { ev.stopPropagation(); delMarca(m.id); }}
                >
                  Eliminar
                </button>
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
          {!filteredMarcas.length && (
            <li className="p-3 text-center text-gray-500">
              {marcaQuery.trim() ? "Sin coincidencias" : "Sin marcas"}
            </li>
          )}
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
export { CatalogoMarcasLegacy };


function CatalogoMarcasV2() {
  const [brands, setBrands] = useState([]);
  const [brandFilter, setBrandFilter] = useState("");
  const [selectedBrandId, setSelectedBrandId] = useState(null);
  const [types, setTypes] = useState([]);
  const [selectedTypeId, setSelectedTypeId] = useState(null);
  const [series, setSeries] = useState([]);
  const [selectedSeriesId, setSelectedSeriesId] = useState(null);
  const [variants, setVariants] = useState([]);
  const [newTypeName, setNewTypeName] = useState("");
  const [newSeriesName, setNewSeriesName] = useState("");
  const [newSeriesAlias, setNewSeriesAlias] = useState("");
  const [newVariantName, setNewVariantName] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const filteredBrands = useMemo(() => {
    if (!brands.length) return brands;
    const q = norm(brandFilter);
    if (!q) return brands;
    return brands.filter((b) => norm(b.name).includes(q));
  }, [brands, brandFilter]);

  useEffect(() => {
    loadBrands();
  }, []);

  async function loadBrands() {
    try {
      const rows = await getCatalogBrandsV2();
      setBrands(rows || []);
    } catch (error) {
      setErr(error.message || "Error cargando marcas");
      setBrands([]);
    }
  }

  async function loadTypes(brandId, preserveSelection = false) {
    if (!brandId) {
      setTypes([]);
      setSelectedTypeId(null);
      setSeries([]);
      setSelectedSeriesId(null);
      setVariants([]);
      return;
    }
    try {
      const rows = await getCatalogTypes(Number(brandId));
      setTypes(rows || []);
      if (preserveSelection) {
        if (!rows?.some((t) => String(t.id) === String(selectedTypeId))) {
          setSelectedTypeId(null);
        }
      } else {
        setSelectedTypeId(null);
      }
    } catch (error) {
      setErr(error.message || "Error cargando tipos");
      setTypes([]);
      setSelectedTypeId(null);
      setSeries([]);
      setSelectedSeriesId(null);
      setVariants([]);
    }
  }

  async function loadSeries(brandId, typeId, preserveSelection = false) {
    if (!brandId || !typeId) {
      setSeries([]);
      setSelectedSeriesId(null);
      setVariants([]);
      return;
    }
    try {
      const rows = await getCatalogSeries(Number(brandId), Number(typeId));
      setSeries(rows || []);
      if (preserveSelection) {
        if (!rows?.some((s) => String(s.id) === String(selectedSeriesId))) {
          setSelectedSeriesId(null);
        }
      } else {
        setSelectedSeriesId(null);
      }
    } catch (error) {
      setErr(error.message || "Error cargando modelos");
      setSeries([]);
      setSelectedSeriesId(null);
      setVariants([]);
    }
  }

  async function loadVariants(brandId, typeId, seriesId) {
    if (!brandId || !typeId || !seriesId) {
      setVariants([]);
      return;
    }
    try {
      const rows = await getCatalogVariants(Number(brandId), Number(typeId), Number(seriesId));
      setVariants(rows || []);
    } catch (error) {
      setErr(error.message || "Error cargando variantes");
      setVariants([]);
    }
  }

  useEffect(() => {
    loadTypes(selectedBrandId);
  }, [selectedBrandId]);

  useEffect(() => {
    loadSeries(selectedBrandId, selectedTypeId);
  }, [selectedBrandId, selectedTypeId]);

  useEffect(() => {
    loadVariants(selectedBrandId, selectedTypeId, selectedSeriesId);
  }, [selectedBrandId, selectedTypeId, selectedSeriesId]);

  const currentType = types.find((t) => String(t.id) === String(selectedTypeId)) || null;
  const currentSeries = series.find((s) => String(s.id) === String(selectedSeriesId)) || null;

  async function handleAddType(event) {
    event.preventDefault();
    if (!selectedBrandId) return;
    const name = newTypeName.trim();
    if (!name) return;
    setLoading(true);
    setErr("");
    try {
      await createCatalogType(selectedBrandId, name);
      setNewTypeName("");
      setMsg("Tipo agregado");
      await loadTypes(selectedBrandId);
    } catch (error) {
      setErr(error.message || "No se pudo crear el tipo");
    } finally {
      setLoading(false);
    }
  }

  async function handleAddSeries(event) {
    event.preventDefault();
    if (!selectedBrandId || !selectedTypeId) return;
    const name = newSeriesName.trim();
    if (!name) return;
    const alias = newSeriesAlias.trim();
    setLoading(true);
    setErr("");
    try {
      const payload = { name };
      if (alias) payload.alias = alias;
      await createCatalogSeries(selectedBrandId, selectedTypeId, payload);
      setNewSeriesName("");
      setNewSeriesAlias("");
      setMsg("Serie agregada");
      await loadSeries(selectedBrandId, selectedTypeId);
    } catch (error) {
      setErr(error.message || "No se pudo crear la serie");
    } finally {
      setLoading(false);
    }
  }

  async function handleAddVariant(event) {
    event.preventDefault();
    if (!selectedBrandId || !selectedTypeId || !selectedSeriesId) return;
    const name = newVariantName.trim();
    if (!name) return;
    setLoading(true);
    setErr("");
    try {
      await createCatalogVariant({
        marca_id: Number(selectedBrandId),
        tipo_id: Number(selectedTypeId),
        modelo_id: Number(selectedSeriesId),
        name,
      });
      setNewVariantName("");
      setMsg("Variante agregada");
      await loadVariants(selectedBrandId, selectedTypeId, selectedSeriesId);
    } catch (error) {
      setErr(error.message || "No se pudo crear la variante");
    } finally {
      setLoading(false);
    }
  }

  async function toggleTypeActive(type) {
    if (!selectedBrandId) return;
    setLoading(true);
    setErr("");
    try {
      await updateCatalogType(type.id, { active: !type.active });
      setMsg(!type.active ? "Tipo activado" : "Tipo desactivado");
      await loadTypes(selectedBrandId, true);
    } catch (error) {
      setErr(error.message || "No se pudo actualizar el tipo");
    } finally {
      setLoading(false);
    }
  }

  async function toggleSeriesActive(serie) {
    if (!selectedBrandId || !selectedTypeId) return;
    setLoading(true);
    setErr("");
    try {
      await updateCatalogSeries(serie.id, { active: !serie.active });
      setMsg(!serie.active ? "Serie activada" : "Serie desactivada");
      await loadSeries(selectedBrandId, selectedTypeId, true);
    } catch (error) {
      setErr(error.message || "No se pudo actualizar la serie");
    } finally {
      setLoading(false);
    }
  }

  async function toggleVariantActive(variant) {
    if (!selectedBrandId || !selectedTypeId || !selectedSeriesId || variant.id == null) return;
    setLoading(true);
    setErr("");
    try {
      await updateCatalogVariant(variant.id, { active: !variant.active });
      setMsg(!variant.active ? "Variante activada" : "Variante desactivada");
      await loadVariants(selectedBrandId, selectedTypeId, selectedSeriesId);
    } catch (error) {
      setErr(error.message || "No se pudo actualizar la variante");
    } finally {
      setLoading(false);
    }
  }

  async function removeType(type) {
    if (!selectedBrandId) return;
    if (!window.confirm("¿Dar de baja el tipo?")) return;
    setLoading(true);
    setErr("");
    try {
      await deleteCatalogType(type.id);
      setMsg("Tipo desactivado");
      await loadTypes(selectedBrandId);
    } catch (error) {
      setErr(error.message || "No se pudo dar de baja el tipo");
    } finally {
      setLoading(false);
    }
  }

  async function removeSeries(serie) {
    if (!selectedBrandId || !selectedTypeId) return;
    if (!window.confirm("¿Dar de baja la serie?")) return;
    setLoading(true);
    setErr("");
    try {
      await deleteCatalogSeries(serie.id);
      setMsg("Serie desactivada");
      await loadSeries(selectedBrandId, selectedTypeId);
    } catch (error) {
      setErr(error.message || "No se pudo dar de baja la serie");
    } finally {
      setLoading(false);
    }
  }

  async function removeVariant(variant) {
    if (!selectedBrandId || !selectedTypeId || !selectedSeriesId || variant.id == null) return;
    if (!window.confirm("¿Dar de baja la variante?")) return;
    setLoading(true);
    setErr("");
    try {
      await deleteCatalogVariant(variant.id);
      setMsg("Variante desactivada");
      await loadVariants(selectedBrandId, selectedTypeId, selectedSeriesId);
    } catch (error) {
      setErr(error.message || "No se pudo dar de baja la variante");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-2xl font-bold">Catálogo de marcas</h1>
      {err && (
        <div className="bg-red-100 border border-red-300 text-red-700 px-3 py-2 rounded">
          {err}
        </div>
      )}
      {msg && (
        <div className="bg-green-100 border border-green-300 text-green-700 px-3 py-2 rounded">
          {msg}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="border rounded p-3 bg-white max-h-[480px] flex flex-col">
          <h2 className="text-lg font-semibold mb-2">Marcas</h2>
          <Input
            value={brandFilter}
            onChange={(event) => setBrandFilter(event.target.value)}
            placeholder="Filtrar marcas"
          />
          <div className="mt-3 space-y-1 overflow-auto">
            {filteredBrands.map((brand) => (
              <button
                key={brand.id}
                className={`w-full text-left px-2 py-1 rounded border ${
                  String(brand.id) === String(selectedBrandId)
                    ? "bg-blue-600 text-white border-blue-600"
                    : "border-transparent hover:bg-blue-50"
                }`}
                onClick={() => setSelectedBrandId(String(brand.id))}
              >
                <div className="font-medium">{brand.name}</div>
              </button>
            ))}
            {!filteredBrands.length && (
              <div className="text-sm text-gray-500">Sin marcas cargadas</div>
            )}
          </div>
        </div>
        <div className="md:col-span-3 grid gap-4 md:grid-cols-3">
          <div className="border rounded p-3 bg-white flex flex-col">
            <h3 className="text-lg font-semibold mb-2">Tipos de equipo</h3>
            {!selectedBrandId ? (
              <div className="text-sm text-gray-500">Seleccioná una marca</div>
            ) : (
              <>
                <form onSubmit={handleAddType} className="flex gap-2 mb-3">
                  <Input
                    value={newTypeName}
                    onChange={(event) => setNewTypeName(event.target.value)}
                    placeholder="Nombre de tipo"
                  />
                  <button
                    type="submit"
                    className="px-3 py-2 bg-blue-600 text-white rounded disabled:opacity-60"
                    disabled={!newTypeName.trim() || loading}
                  >
                    Agregar
                  </button>
                </form>
                <div className="space-y-2 overflow-auto">
                  {types.map((type) => (
                    <div
                      key={type.id}
                      className={`border rounded px-2 py-1 ${
                        String(type.id) === String(selectedTypeId) ? "border-blue-500" : "border-gray-200"
                      }`}
                    >
                      <button
                        className="w-full text-left font-medium"
                        onClick={() => setSelectedTypeId(String(type.id))}
                      >
                        {type.name}
                        {!type.active && <span className="ml-2 text-xs text-red-600">inactivo</span>}
                      </button>
                      <div className="flex gap-2 text-xs mt-1">
                        <button
                          type="button"
                          className="text-blue-600"
                          onClick={() => toggleTypeActive(type)}
                          disabled={loading}
                        >
                          {type.active ? "Desactivar" : "Activar"}
                        </button>
                        <button
                          type="button"
                          className="text-red-600"
                          onClick={() => removeType(type)}
                          disabled={loading}
                        >
                          Dar de baja
                        </button>
                      </div>
                    </div>
                  ))}
                  {!types.length && (
                    <div className="text-sm text-gray-500">Sin tipos disponibles</div>
                  )}
                </div>
              </>
            )}
          </div>
          <div className="border rounded p-3 bg-white flex flex-col">
            <h3 className="text-lg font-semibold mb-2">Modelos / Series</h3>
            {!selectedBrandId || !selectedTypeId ? (
              <div className="text-sm text-gray-500">Seleccioná un tipo</div>
            ) : (
              <>
                <form onSubmit={handleAddSeries} className="grid gap-2 mb-3">
                  <Input
                    value={newSeriesName}
                    onChange={(event) => setNewSeriesName(event.target.value)}
                    placeholder="Nombre de serie"
                  />
                  <Input
                    value={newSeriesAlias}
                    onChange={(event) => setNewSeriesAlias(event.target.value)}
                    placeholder="Alias (opcional)"
                  />
                  <button
                    type="submit"
                    className="justify-self-start px-3 py-2 bg-blue-600 text-white rounded disabled:opacity-60"
                    disabled={!newSeriesName.trim() || loading}
                  >
                    Agregar
                  </button>
                </form>
                <div className="space-y-2 overflow-auto">
                  {series.map((serie) => (
                    <div
                      key={serie.id}
                      className={`border rounded px-2 py-1 ${
                        String(serie.id) === String(selectedSeriesId) ? "border-blue-500" : "border-gray-200"
                      }`}
                    >
                      <button
                        className="w-full text-left font-medium"
                        onClick={() => setSelectedSeriesId(String(serie.id))}
                      >
                        {serie.name}
                        {serie.alias && <span className="ml-2 text-xs text-gray-500">({serie.alias})</span>}
                        {!serie.active && <span className="ml-2 text-xs text-red-600">inactiva</span>}
                      </button>
                      <div className="flex gap-2 text-xs mt-1">
                        <button
                          type="button"
                          className="text-blue-600"
                          onClick={() => toggleSeriesActive(serie)}
                          disabled={loading}
                        >
                          {serie.active ? "Desactivar" : "Activar"}
                        </button>
                        <button
                          type="button"
                          className="text-red-600"
                          onClick={() => removeSeries(serie)}
                          disabled={loading}
                        >
                          Dar de baja
                        </button>
                      </div>
                    </div>
                  ))}
                  {!series.length && (
                    <div className="text-sm text-gray-500">Sin series cargadas</div>
                  )}
                </div>
              </>
            )}
          </div>
          <div className="border rounded p-3 bg-white flex flex-col">
            <h3 className="text-lg font-semibold mb-2">Variantes</h3>
            {!selectedBrandId || !selectedTypeId || !selectedSeriesId ? (
              <div className="text-sm text-gray-500">Seleccioná una serie</div>
            ) : (
              <>
                <form onSubmit={handleAddVariant} className="flex gap-2 mb-3">
                  <Input
                    value={newVariantName}
                    onChange={(event) => setNewVariantName(event.target.value)}
                    placeholder="Nombre de variante"
                  />
                  <button
                    type="submit"
                    className="px-3 py-2 bg-blue-600 text-white rounded disabled:opacity-60"
                    disabled={!newVariantName.trim() || loading}
                  >
                    Agregar
                  </button>
                </form>
                <div className="space-y-2 overflow-auto">
                  {variants.map((variant) => (
                    <div
                      key={variant.id ?? "none"}
                      className="border rounded px-2 py-1 border-gray-200"
                    >
                      <div className="font-medium">
                        {variant.name}
                        {variant.optional && <span className="ml-2 text-xs text-gray-500">(sin variante)</span>}
                        {!variant.optional && !variant.active && (
                          <span className="ml-2 text-xs text-red-600">inactiva</span>
                        )}
                      </div>
                      {!variant.optional && (
                        <div className="flex gap-2 text-xs mt-1">
                          <button
                            type="button"
                            className="text-blue-600"
                            onClick={() => toggleVariantActive(variant)}
                            disabled={loading}
                          >
                            {variant.active ? "Desactivar" : "Activar"}
                          </button>
                          <button
                            type="button"
                            className="text-red-600"
                            onClick={() => removeVariant(variant)}
                            disabled={loading}
                          >
                            Dar de baja
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                  {!variants.length && (
                    <div className="text-sm text-gray-500">Sin variantes cargadas</div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
      {currentType && (
        <div className="text-sm text-gray-500">
          Tipo seleccionado: <span className="font-medium">{currentType.name}</span>
        </div>
      )}
      {currentSeries && (
        <div className="text-sm text-gray-500">
          Serie seleccionada: <span className="font-medium">{currentSeries.name}</span>
        </div>
      )}
    </div>
  );
}

function CatalogoMarcas() {
  const useV2 = featureEnabled("catalog_v2_selects");
  return useV2 ? <CatalogoMarcasV2 /> : <CatalogoMarcasLegacy />;
}

export default CatalogoMarcas;

