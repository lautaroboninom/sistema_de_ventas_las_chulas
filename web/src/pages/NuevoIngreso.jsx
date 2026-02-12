// web/src/pages/NuevoIngreso.jsx (UTF-8 authoring; will be re-encoded to Windows-1252)
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  getClientes,
  getMarcas,
  getModelosByBrand,
  getTecnicos,
  postNuevoIngreso,
  getMotivos,
  checkGarantiaReparacion,
  checkGarantiaFabrica,
  getAccesoriosCatalogo,
  getTiposEquipo,
  getMarcasPorTipo,
  getCatalogTipos,
  getCatalogModelos,
  getCatalogVariantes,
  lookupScan,
} from "@/lib/api";

const Input = (p) => <input {...p} className={`border rounded p-2 w-full ${p.className || ""}`} />;
const Select = (p) => <select {...p} className={`border rounded p-2 w-full ${p.className || ""}`} />;
const TextArea = (p) => <textarea {...p} className={`border rounded p-2 w-full ${p.className || ""}`} />;

// clone helper (fallback if structuredClone is missing)
function clone(obj) {
  try {
    return typeof structuredClone === "function" ? structuredClone(obj) : JSON.parse(JSON.stringify(obj));
  } catch (_) {
    return JSON.parse(JSON.stringify(obj));
  }
}

export default function NuevoIngreso() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const prefillRef = useRef(null);
  const prefillAppliedRef = useRef(false);
  const prefillModelAppliedRef = useRef(false);
  const prefillClienteAppliedRef = useRef(false);
  const prefillSkipTipoResetRef = useRef(false);
  const prefillTipoAppliedRef = useRef(false);

  // Catálogos base
  const [marcas, setMarcas] = useState([]);
  const [motivos, setMotivos] = useState([]);
  const [modelos, setModelos] = useState([]);

  // Marca y tipo
  const [marcaTxt, setMarcaTxt] = useState("");
  const [marcaId, setMarcaId] = useState(null);
  const [tiposEquipo, setTiposEquipo] = useState([]);
  const [tipoSel, setTipoSel] = useState("");
  const [marcasPorTipo, setMarcasPorTipo] = useState([]);

  // Clientes (autocompletar)
  const [clientes, setClientes] = useState([]);
  const [selectedCliente, setSelectedCliente] = useState(null);
  const [clienteRsInput, setClienteRsInput] = useState("");
  const [clienteCodInput, setClienteCodInput] = useState("");

  // Variantes (opcional)
  const [varianteTxt, setVarianteTxt] = useState("");
  const [varianteSugeridas, setVarianteSugeridas] = useState([]);
  const [catTipoId, setCatTipoId] = useState(null);
  const [catModelos, setCatModelos] = useState([]);

  // Form principal
  const [form, setForm] = useState({
    etiq_garantia_ok: false,
    cliente: { id: null, razon_social: "", cod_empresa: "", telefono: "" },
    equipo: {
      marca_id: "",
      modelo_id: "",
      numero_serie: "",
      numero_interno: "",
      garantia: false,
    },
    motivo: "",
    informe_preliminar: "",
    comentarios: "",
    garantia_reparacion: false,
    remito_ingreso: "",
    fecha_ingreso: "",
  });

  // Accesorios
  const [accesCatalogo, setAccesCatalogo] = useState([]);
  const [nuevoAcc, setNuevoAcc] = useState({ descripcion: "", referencia: "" });
  const [accItems, setAccItems] = useState([]);

  // Propietario y técnico
  const [propietario, setPropietario] = useState({ nombre: "", contacto: "", doc: "" });
  const [tecnicos, setTecnicos] = useState([]);
  const [tecnicoId, setTecnicoId] = useState(null);
  // Empresa a facturar (SEPID por defecto)
  const [empresaFact, setEmpresaFact] = useState("SEPID");

  const [loading, setLoading] = useState(false);
  const [out, setOut] = useState(null);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");
  const [dupPrompt, setDupPrompt] = useState({ open: false, ingresoId: null, fechaIngreso: null, os: "" });

  const [clientesPerm, setClientesPerm] = useState(true);
  const [garRepLoading, setGarRepLoading] = useState(false);
  const [garRepError, setGarRepError] = useState(false);
  const [mgLookup, setMgLookup] = useState({ loading: false, notFound: false, checkedNs: "" });
  const [mgAutoFilled, setMgAutoFilled] = useState(false);
  const mgLookupSeqRef = useRef(0);
  const mgAutoNsRef = useRef("");
  const mgValueRef = useRef("");
  const mgAutoRef = useRef(false);

  // Helpers de clientes
  const findClienteByRS = (v) =>
    (clientes || []).find((c) => (c.razon_social || "").toLowerCase() === String(v || "").trim().toLowerCase());
  const findClienteByCod = (v) =>
    (clientes || []).find((c) => String(c.cod_empresa || "").toLowerCase() === String(v || "").trim().toLowerCase());

  function resolveCliente(rsVal, codVal) {
    const byRs = rsVal ? findClienteByRS(rsVal) : null;
    const byCod = codVal ? findClienteByCod(codVal) : null;
    if (byRs && !codVal) return byRs;
    if (byCod && !rsVal) return byCod;
    if (byRs && byCod && byRs.id === byCod.id) return byRs;
    return null;
  }

  function syncClienteFromInputs(rsVal, codVal) {
    const c = resolveCliente(rsVal, codVal);
    setSelectedCliente(c);
    setForm((f0) => {
      const f = clone(f0);
      f.cliente = {
        id: c?.id || null,
        razon_social: rsVal || "",
        cod_empresa: codVal || "",
        telefono: c?.telefono || "",
      };
      return f;
    });
  }

  const formatFechaIngreso = (val) => {
    if (!val) return "-";
    const d = new Date(val);
    if (Number.isNaN(d.getTime())) return String(val);
    return d.toLocaleDateString();
  };
  const normalizeFechaIngreso = (val) => {
    const s = String(val || "").trim();
    if (!s) return "";
    const m = s.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})$/);
    if (m) {
      const [, dd, mm, yyyy] = m;
      return `${yyyy}-${mm.padStart(2, "0")}-${dd.padStart(2, "0")}`;
    }
    return s;
  };

  const resetFormFields = () => {
    setMarcaTxt("");
    setMarcaId(null);
    setModelos([]);
    setClienteRsInput("");
    setClienteCodInput("");
    setSelectedCliente(null);
    setForm({
      etiq_garantia_ok: false,
      cliente: { id: null, razon_social: "", cod_empresa: "", telefono: "" },
      equipo: { marca_id: "", modelo_id: "", numero_serie: "", numero_interno: "", garantia: false },
      motivo: "",
      informe_preliminar: "",
      comentarios: "",
      garantia_reparacion: false,
      remito_ingreso: "",
      fecha_ingreso: "",
    });
    setAccItems([]);
    setPropietario({ nombre: "", contacto: "", doc: "" });
    setTecnicoId(null);
    setEmpresaFact("SEPID");
    setVarianteTxt("");
    setMgLookup({ loading: false, notFound: false, checkedNs: "" });
    setMgAutoFilled(false);
    mgAutoNsRef.current = "";
  };

  useEffect(() => {
    mgValueRef.current = form.equipo.numero_interno || "";
  }, [form.equipo.numero_interno]);

  useEffect(() => {
    mgAutoRef.current = mgAutoFilled;
  }, [mgAutoFilled]);

  useEffect(() => {
    if (prefillAppliedRef.current) return;
    const payload = location?.state?.prefill || null;
    const serieParam = (searchParams.get("serie") || "").trim();
    const prefill = payload || (serieParam ? { numero_serie: serieParam } : null);
    if (!prefill) return;

    prefillAppliedRef.current = true;
    prefillModelAppliedRef.current = false;
    prefillClienteAppliedRef.current = false;
    prefillSkipTipoResetRef.current = true;
    prefillTipoAppliedRef.current = false;
    prefillRef.current = prefill;

    setForm((f0) => {
      const f = clone(f0);
      if (prefill.numero_serie) f.equipo.numero_serie = prefill.numero_serie;
      if (prefill.numero_interno) f.equipo.numero_interno = prefill.numero_interno;
      if (prefill.marca_id) f.equipo.marca_id = prefill.marca_id;
      if (prefill.model_id) f.equipo.modelo_id = prefill.model_id;
      return f;
    });
    if (prefill.marca_id) setMarcaId(prefill.marca_id);
    if (prefill.marca) setMarcaTxt(prefill.marca);
    if (prefill.tipo_equipo) {
      prefillSkipTipoResetRef.current = true;
      prefillTipoAppliedRef.current = true;
      setTipoSel(prefill.tipo_equipo);
    }
    const variantePrefill = prefill.variante || prefill.equipo_variante || "";
    if (variantePrefill) setVarianteTxt(variantePrefill);
    if (prefill.customer_nombre || prefill.alquiler_a) {
      setClienteRsInput(prefill.customer_nombre || prefill.alquiler_a || "");
      setClienteCodInput(prefill.customer_cod || "");
    }
    if (prefill.propietario_nombre || prefill.propietario_contacto || prefill.propietario_doc) {
      setPropietario({
        nombre: prefill.propietario_nombre || "",
        contacto: prefill.propietario_contacto || "",
        doc: prefill.propietario_doc || "",
      });
    }
    if (prefill.alquilado && prefill.alquiler_a) {
      setNotice(`Equipo alquilado a ${prefill.alquiler_a}. Completa los datos restantes.`);
    } else if (prefill.customer_nombre) {
      setNotice("Datos cargados desde lectura de codigo.");
    } else if (prefill.numero_serie || prefill.numero_interno) {
      setNotice("Serie cargada desde lectura de codigo.");
    }
  }, [location, searchParams]);

  useEffect(() => {
    if (prefillModelAppliedRef.current) return;
    const prefill = prefillRef.current;
    if (!prefill || !prefill.model_id) return;
    if (!modelos || modelos.length === 0) return;
    const exists = modelos.some((m) => String(m.id) === String(prefill.model_id));
    if (!exists) return;
    setForm((f0) => ({ ...f0, equipo: { ...f0.equipo, modelo_id: prefill.model_id } }));
    prefillModelAppliedRef.current = true;
  }, [modelos]);

  useEffect(() => {
    if (prefillClienteAppliedRef.current) return;
    const prefill = prefillRef.current;
    if (!prefill) return;
    if (!clientes || clientes.length === 0) return;
    const rsVal = (clienteRsInput || prefill.customer_nombre || prefill.alquiler_a || "").trim();
    const codVal = (clienteCodInput || prefill.customer_cod || "").trim();
    if (!rsVal && !codVal) {
      prefillClienteAppliedRef.current = true;
      return;
    }
    if (!clienteRsInput && rsVal) setClienteRsInput(rsVal);
    if (!clienteCodInput && codVal) setClienteCodInput(codVal);
    syncClienteFromInputs(rsVal, codVal);
    prefillClienteAppliedRef.current = true;
  }, [clientes]);

  // Autocompletar MG por N/S (debounce 400ms)
  useEffect(() => {
    const ns = (form.equipo.numero_serie || "").trim();
    if (!ns) {
      setMgLookup({ loading: false, notFound: false, checkedNs: "" });
      if (mgAutoRef.current && (mgValueRef.current || "").trim()) {
        setForm((prev) => {
          const copy = clone(prev);
          copy.equipo.numero_interno = "";
          return copy;
        });
        setMgAutoFilled(false);
        mgAutoNsRef.current = "";
      }
      return;
    }

    if (mgAutoRef.current && mgAutoNsRef.current && mgAutoNsRef.current !== ns) {
      setForm((prev) => {
        const copy = clone(prev);
        copy.equipo.numero_interno = "";
        return copy;
      });
      setMgAutoFilled(false);
      mgAutoNsRef.current = "";
    }

    setMgLookup((s) => (s.notFound || s.loading ? { ...s, notFound: false, loading: false } : s));
    const seq = ++mgLookupSeqRef.current;
    const h = setTimeout(async () => {
      setMgLookup((s) => ({ ...s, loading: true, notFound: false, checkedNs: ns }));
      try {
        const res = await lookupScan(ns);
        if (mgLookupSeqRef.current !== seq) return;
        const foundMg = (res?.device?.numero_interno || "").trim();
        const currentMg = (mgValueRef.current || "").trim();
        const canAuto = !currentMg || mgAutoRef.current;
        if (foundMg && canAuto) {
          setForm((prev) => {
            const copy = clone(prev);
            copy.equipo.numero_interno = foundMg;
            return copy;
          });
          setMgAutoFilled(true);
          mgAutoNsRef.current = ns;
        }
        if (foundMg) {
          setMgLookup({ loading: false, notFound: false, checkedNs: ns });
        } else {
          const showNotFound = !currentMg || mgAutoRef.current;
          setMgLookup({ loading: false, notFound: showNotFound, checkedNs: ns });
        }
      } catch {
        if (mgLookupSeqRef.current !== seq) return;
        setMgLookup((s) => ({ ...s, loading: false }));
      }
    }, 400);
    return () => clearTimeout(h);
  }, [form.equipo.numero_serie]);

  // Garantía de reparación (por N/S o MG) - debounce 400ms
  useEffect(() => {
    const ns = (form.equipo.numero_serie || "").trim();
    const mg = (form.equipo.numero_interno || "").trim();
    if (!ns && !mg) {
      setForm((f) => ({ ...f, garantia_reparacion: false }));
      setGarRepLoading(false);
      setGarRepError(false);
      return;
    }
    const h = setTimeout(async () => {
      try {
        setGarRepLoading(true);
        setGarRepError(false);
        const r = await checkGarantiaReparacion(ns, mg);
        setForm((f) => ({ ...f, garantia_reparacion: !!r?.within_90_days }));
        setGarRepLoading(false);
      } catch {
        setGarRepLoading(false);
        setGarRepError(true);
      }
    }, 400);
    return () => clearTimeout(h);
  }, [form.equipo.numero_serie, form.equipo.numero_interno]);

  // Garantía de fábrica por N/S (debounce 400ms)
  useEffect(() => {
    const ns = (form.equipo.numero_serie || "").trim();
    const marcaSel = (() => {
      const m = (marcas || []).find((x) => x.id === (marcaId || form.equipo.marca_id));
      return m?.nombre || "";
    })();
    if (!ns) {
      setForm((f) => ({ ...f, equipo: { ...f.equipo, garantia: false } }));
      return;
    }
    const h = setTimeout(async () => {
      try {
        const r = await checkGarantiaFabrica(ns, marcaSel, {
          brand_id: marcaId || form.equipo.marca_id || null,
          model_id: form.equipo.modelo_id || null,
        });
        const enGarantia = !!r?.within_365_days;
        setForm((f) => ({ ...f, equipo: { ...f.equipo, garantia: enGarantia } }));
      } catch {
        /* noop: no bloquear */
      }
    }, 400);
    return () => clearTimeout(h);
  }, [form.equipo.numero_serie, marcaId, form.equipo.marca_id, form.equipo.modelo_id, marcas]);

  const tipoEquipoSel = useMemo(() => {
    const m = (modelos || []).find((x) => x.id === Number(form.equipo.modelo_id));
    return m?.tipo_equipo || "";
  }, [modelos, form.equipo.modelo_id]);

  useEffect(() => {
    if (!prefillAppliedRef.current || prefillTipoAppliedRef.current) return;
    if (tipoSel) {
      prefillTipoAppliedRef.current = true;
      return;
    }
    if (!tipoEquipoSel) return;
    prefillSkipTipoResetRef.current = true;
    prefillTipoAppliedRef.current = true;
    setTipoSel(tipoEquipoSel);
  }, [tipoEquipoSel, tipoSel]);

  // Carga inicial por secciones (mensajes por sección)
  useEffect(() => {
    (async () => {
      const errs = [];
      try {
        const mks = await getMarcas();
        setMarcas(mks || []);
      } catch (_) {
        errs.push("Error cargando marcas");
      }
      try {
        const mts = await getMotivos();
        setMotivos(mts || []);
      } catch (_) {
        errs.push("Error cargando motivos");
      }
      try {
        const cls = await getClientes();
        setClientes(cls || []);
        setClientesPerm(true);
      } catch (e) {
        const msg = String(e?.message || "");
        if (msg.startsWith("403 ")) {
          setClientesPerm(false);
        } else if (msg.startsWith("401 ")) {
          errs.push("No autenticado");
        } else {
          errs.push("Error cargando clientes");
        }
      }
      try {
        const accs = await getAccesoriosCatalogo();
        setAccesCatalogo(accs || []);
      } catch (_) {
        errs.push("Error cargando accesorios");
      }
      try {
        const tps = await getTiposEquipo();
        const list = (tps || [])
          .map((t) => t?.nombre || t?.label || t?.name || t?.value || t)
          .map(String)
          .filter(Boolean);
        setTiposEquipo(Array.from(new Set(list)));
      } catch (_) {
        errs.push("Error cargando tipos de equipo");
      }
      try {
        const tecs = await getTecnicos();
        setTecnicos(tecs || []);
      } catch (_) {
        /* noop */
      }
      if (errs.length) setErr(errs.join(" | "));
    })();
  }, []);

  // Cambio de marca / tipo
  useEffect(() => {
    setForm((f) => ({ ...f, equipo: { ...f.equipo, marca_id: marcaId || "", modelo_id: "" } }));

    if (!marcaId) {
      setModelos([]);
      setVarianteTxt("");
      setVarianteSugeridas([]);
      return;
    }
    getModelosByBrand(marcaId)
      .then((rows) => {
        const list = rows || [];
        if (tipoSel) {
          const norm = (s) => (s || "").toString().trim().toUpperCase();
          const filtered = list.filter((m) => norm(m.tipo_equipo) === norm(tipoSel));
          setModelos(filtered);
          const currentId = (form?.equipo?.modelo_id ?? "").toString();
          const exists = filtered.some((x) => String(x.id) === currentId);
          if (!exists) setForm((f) => ({ ...f, equipo: { ...f.equipo, modelo_id: "" } }));
        } else {
          setModelos(list);
        }
        (async () => {
          setCatTipoId(null);
          setCatModelos([]);
          setVarianteSugeridas([]);
          if (!tipoSel) return;
          try {
            const tiposBrand = await getCatalogTipos(marcaId);
            const match = (tiposBrand || []).find(
              (t) => (t.name || "").trim().toUpperCase() === (tipoSel || "").trim().toUpperCase()
            );
            const tId = match?.id ?? null;
            setCatTipoId(tId);
            if (tId) {
              const mods = await getCatalogModelos(marcaId, tId);
              setCatModelos(mods || []);
            }
          } catch {
            setCatTipoId(null);
            setCatModelos([]);
          }
        })();
      })
      .catch((e) => setErr(e?.message || "Error cargando modelos"));
  }, [marcaId, tipoSel]);

  // Variantes desde catálogo según modelo interno seleccionado
  useEffect(() => {
    const m = (modelos || []).find((x) => x.id === Number(form.equipo.modelo_id));
    if (!m || !marcaId || !catTipoId) {
      setVarianteSugeridas([]);
      if (!varianteTxt) setVarianteTxt("");
      return;
    }
    const needle = (m.nombre || "").trim().toUpperCase();
    const cmatch = (catModelos || []).filter((cm) => {
      const a = (cm.name || "").trim().toUpperCase();
      const alias = (cm.alias || "").trim().toUpperCase();
      return a === needle || a.includes(needle) || needle.includes(a) || (alias && (alias === needle || needle.includes(alias) || alias.includes(needle)));
    });
    if (cmatch.length !== 1) {
      setVarianteSugeridas([]);
      if (!varianteTxt) setVarianteTxt("");
      return;
    }
    const cm = cmatch[0];
    (async () => {
      try {
        const vars = await getCatalogVariantes(marcaId, catTipoId, cm.id);
        const names = (vars || []).filter((v) => v && v.name).map((v) => v.name);
        setVarianteSugeridas(names);
        if (!varianteTxt && names.length === 1) setVarianteTxt(names[0]);
      } catch {
        setVarianteSugeridas([]);
      }
    })();
  }, [form.equipo.modelo_id, modelos, marcaId, catTipoId, catModelos, varianteTxt]);

  // Técnico por modelo
  useEffect(() => {
    const m = (modelos || []).find((x) => x.id === Number(form.equipo.modelo_id));
    if (m?.tecnico_id) setTecnicoId(m.tecnico_id);
  }, [form.equipo.modelo_id, modelos]);

  // Fallback: técnico por marca si el modelo no define
  useEffect(() => {
    const m = (modelos || []).find((x) => x.id === Number(form.equipo.modelo_id));
    if (m?.tecnico_id) {
      setTecnicoId(m.tecnico_id);
    } else {
      const marcaObj = (marcas || []).find((x) => x.id === marcaId);
      if (marcaObj?.tecnico_id) setTecnicoId(marcaObj.tecnico_id);
    }
  }, [form.equipo.modelo_id, modelos, marcaId, marcas]);

  const onChange = (path) => (e) => {
    const v = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((prev) => {
      const copy = clone(prev);
      const parts = path.split(".");
      let obj = copy;
      for (let i = 0; i < parts.length - 1; i++) obj = obj[parts[i]];
      obj[parts.at(-1)] = v;
      return copy;
    });
  };

  const onNumeroSerieChange = (e) => {
    setMgLookup((s) => (s.notFound || s.loading ? { ...s, notFound: false, loading: false } : s));
    onChange("equipo.numero_serie")(e);
  };

  const onNumeroInternoChange = (e) => {
    setMgAutoFilled(false);
    mgAutoNsRef.current = "";
    setMgLookup((s) => (s.notFound ? { ...s, notFound: false } : s));
    onChange("equipo.numero_interno")(e);
  };

  function onMarcaInput(val) {
    setMarcaTxt(val);
    const pool = tipoSel ? (marcasPorTipo.length ? marcasPorTipo : marcas) : marcas;
    const match = (pool || []).find((m) => (m.nombre || "").toLowerCase() === String(val || "").trim().toLowerCase());
    setMarcaId(match ? match.id : null);
  }

  // Cambio de tipo => filtra marcas
  useEffect(() => {
    if (prefillSkipTipoResetRef.current) {
      prefillSkipTipoResetRef.current = false;
      if (!tipoSel) {
        setMarcasPorTipo([]);
        return;
      }
      (async () => {
        try {
          const rows = await getMarcasPorTipo(tipoSel);
          setMarcasPorTipo(rows || []);
        } catch {
          setMarcasPorTipo([]);
        }
      })();
      return;
    }
    setMarcaTxt("");
    setMarcaId(null);
    setModelos([]);
    setVarianteTxt("");
    setVarianteSugeridas([]);
    if (!tipoSel) {
      setMarcasPorTipo([]);
      return;
    }
    (async () => {
      try {
        const rows = await getMarcasPorTipo(tipoSel);
        setMarcasPorTipo(rows || []);
      } catch {
        setMarcasPorTipo([]);
      }
    })();
  }, [tipoSel]);

  // Handlers cliente
  function onClienteRsChange(v) {
    setClienteRsInput(v);
    syncClienteFromInputs(v, clienteCodInput);
  }
  function onClienteCodChange(v) {
    setClienteCodInput(v);
    syncClienteFromInputs(clienteRsInput, v);
  }

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErr("");
    setOut(null);
    setNotice("");
    setDupPrompt({ open: false, ingresoId: null, fechaIngreso: null, os: "" });

    if (!form.equipo.marca_id) {
      setLoading(false);
      setErr("Seleccion? una marca v?lida de la lista.");
      return;
    }
    if (!form.equipo.modelo_id) {
      setLoading(false);
      setErr("Seleccion? un modelo.");
      return;
    }
    if (!form.motivo) {
      setLoading(false);
      setErr("Seleccion? un motivo.");
      return;
    }

    const c = resolveCliente(clienteRsInput, clienteCodInput);
    if (!c?.id) {
      setLoading(false);
      setErr("Deb?s seleccionar un cliente v?lido de la lista.");
      return;
    }

    try {
      const fechaIngresoNorm = normalizeFechaIngreso(form.fecha_ingreso);
      const payload = {
        cliente: { id: c.id },
        equipo: {
          marca_id: Number(form.equipo.marca_id),
          modelo_id: Number(form.equipo.modelo_id),
          numero_serie: (form.equipo.numero_serie || "").trim(),
          garantia: !!form.equipo.garantia,
          numero_interno: (form.equipo.numero_interno || "").trim(),
        },
        equipo_variante: (varianteTxt || "").trim() || null,
        motivo: form.motivo,
        informe_preliminar: form.informe_preliminar,
        comentarios: form.comentarios,
        remito_ingreso: (form.remito_ingreso || "").trim(),
        ...(fechaIngresoNorm ? { fecha_ingreso: fechaIngresoNorm } : {}),
        accesorios_items: accItems.map((it) => ({
          accesorio_id: Number(it.accesorio_id),
          referencia: (it.referencia || "").trim(),
        })),
        tecnico_id: tecnicoId ? Number(tecnicoId) : null,
        garantia_reparacion: !!form.garantia_reparacion,
        propietario: {
          nombre: propietario.nombre || "",
          contacto: propietario.contacto || "",
          doc: propietario.doc || "",
        },
        empresa_facturar: (empresaFact || "SEPID").toUpperCase(),
        // Checkbox representa "fajas abiertas" => etiq_garantia_ok debe ser la negaci?n
        etiq_garantia_ok: !form.etiq_garantia_ok,
      };

      const r = await postNuevoIngreso(payload);
      if (r?.existing === true) {
        setDupPrompt({
          open: true,
          ingresoId: r.ingreso_id || null,
          fechaIngreso: r.fecha_ingreso || null,
          os: r.os || "",
        });
        return;
      }
      setOut(r);
      if (r?.ingreso_id) navigate(`/ingresos/${r.ingreso_id}`);

      resetFormFields();
    } catch (e2) {
      setErr(e2?.message || "Error creando ingreso");
    } finally {
      setLoading(false);
    }
  };

  const rsMatch = clienteRsInput ? findClienteByRS(clienteRsInput) : null;
  const codMatch = clienteCodInput ? findClienteByCod(clienteCodInput) : null;
  const clienteMismatch = rsMatch && codMatch && rsMatch.id !== codMatch.id;
  const canSubmitCliente = !!resolveCliente(clienteRsInput, clienteCodInput)?.id;
  const closeDupPrompt = () => setDupPrompt({ open: false, ingresoId: null, fechaIngreso: null, os: "" });
  const confirmDupPrompt = () => {
    if (dupPrompt.ingresoId) navigate(`/ingresos/${dupPrompt.ingresoId}`);
    closeDupPrompt();
  };

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">Nuevo Ingreso (Orden de Servicio)</h1>

      {dupPrompt.open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded shadow-lg p-5 w-full max-w-md">
            <div className="text-lg font-semibold mb-2">Ingreso duplicado</div>
            <p className="text-sm text-gray-700 mb-1">
              Equipo ya ingresado el <b>{formatFechaIngreso(dupPrompt.fechaIngreso)}</b>: redirigir a su Hoja de servicio?
            </p>
            {dupPrompt.os && (
              <div className="text-xs text-gray-500 mb-4">OS {dupPrompt.os}</div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                className="px-3 py-2 rounded border border-gray-300 text-gray-700 hover:bg-gray-100"
                onClick={closeDupPrompt}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="px-3 py-2 rounded bg-blue-600 text-white hover:bg-blue-700"
                onClick={confirmDupPrompt}
              >
                Aceptar
              </button>
            </div>
          </div>
        </div>
      )}

      {notice && (
        <div className="bg-blue-100 border border-blue-300 text-blue-700 p-2 rounded">{notice}</div>
      )}
      {err && (
        <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded">{err}</div>
      )}
      {out && (
        <div className="bg-green-100 border border-green-300 text-green-700 p-2 rounded">
          Ingreso creado: <b>{out.os}</b> (ID: {out.ingreso_id})
        </div>
      )}

      <form onSubmit={submit} className="space-y-6">
        {/* Cliente */}
        <fieldset className="border rounded p-3">
          <legend className="px-2 font-semibold">Cliente</legend>
          {!clientesPerm && (
            <div className="text-xs text-gray-600 mb-2">No tenés permisos para listar clientes</div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="text-sm">Razón social</label>
              <Input
                list={clientesPerm ? "clientes_rs" : undefined}
                value={clienteRsInput}
                onChange={(e) => onClienteRsChange(e.target.value)}
                placeholder="Escribí y elegí de la lista"
                required
              />
              {clientesPerm && (
                <datalist id="clientes_rs">
                  {(Array.isArray(clientes) ? clientes : []).map((c) => (
                    <option key={c.id} value={c.razon_social} />
                  ))}
                </datalist>
              )}
              {clienteRsInput && !rsMatch && (
                <div className="text-xs text-red-600 mt-1">Debés seleccionar de la lista</div>
              )}
            </div>
            <div>
              <label className="text-sm">Código empresa</label>
              <Input
                list={clientesPerm ? "clientes_cod" : undefined}
                value={clienteCodInput}
                onChange={(e) => onClienteCodChange(e.target.value)}
                placeholder="Opcional: podés buscar por código"
              />
              {clientesPerm && (
                <datalist id="clientes_cod">
                  {(Array.isArray(clientes) ? clientes : [])
                    .filter((c) => c.cod_empresa)
                    .map((c) => (
                      <option key={c.id} value={c.cod_empresa} />
                    ))}
                </datalist>
              )}
              {clienteCodInput && !codMatch && (
                <div className="text-xs text-red-600 mt-1">Debés seleccionar de la lista</div>
              )}
            </div>
            <div>
              <label className="text-sm">Teléfono</label>
              <Input value={form.cliente.telefono} readOnly placeholder="-" />
            </div>
          </div>
          {clienteMismatch && (
            <div className="text-xs text-red-600 mt-2">
              El código no corresponde a la razón social seleccionada.
            </div>
          )}
        </fieldset>

        {/* Propietario: requerido si cliente es Particular */}
        <div className="mt-4 border rounded p-3">
          <h3 className="font-semibold mb-2">Propietario</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="text-sm">Nombre</label>
              <Input
                value={propietario.nombre}
                onChange={(e) => setPropietario((p) => ({ ...p, nombre: e.target.value }))}
                placeholder="Nombre del propietario"
                required={selectedCliente?.razon_social?.trim().toLowerCase() === 'particular'}
              />
            </div>
            <div>
              <label className="text-sm">Contacto</label>
              <Input
                value={propietario.contacto}
                onChange={(e) => setPropietario((p) => ({ ...p, contacto: e.target.value }))}
                placeholder="Contacto (opcional)"
              />
            </div>
            <div>
              <label className="text-sm">CUIT</label>
              <Input
                value={propietario.doc}
                onChange={(e) => setPropietario((p) => ({ ...p, doc: e.target.value }))}
                placeholder="CUIT"
                required={selectedCliente?.razon_social?.trim().toLowerCase() === 'particular'}
              />
            </div>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Obligatorio cuando el cliente es "Particular".
          </div>
        </div>

        {/* Empresa a facturar */}
        <div className="border rounded p-3">
          <label className="text-sm">Empresa a facturar</label>
          <Select value={empresaFact} onChange={(e) => setEmpresaFact((e.target.value || "SEPID").toUpperCase())}>
            <option value="SEPID">SEPID SA</option>
            <option value="MGBIO">MG BIO</option>
          </Select>
          <div className="text-xs text-gray-500 mt-1">Por defecto: SEPID SA</div>
        </div>

        {/* Equipo */}
        <fieldset className="border rounded p-3">
          <legend className="px-2 font-semibold">Equipo</legend>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            {/* Tipo de equipo */}
            <div className="md:col-span-4">
              <label className="text-sm">Tipo de equipo</label>
              <Select value={tipoSel} onChange={(e) => setTipoSel(e.target.value || "")}> 
                <option value="">-- Seleccionar --</option>
                {(Array.isArray(tiposEquipo) ? tiposEquipo : []).map((t, i) => (
                  <option key={i} value={t}>
                    {t}
                  </option>
                ))}
              </Select>
            </div>

            {/* Marca (filtrada por tipo) */}
            <div className="md:col-span-2">
              <label className="text-sm">Marca</label>
              <Input list="marcas-list" value={marcaTxt} placeholder="Marca" onChange={(e) => onMarcaInput(e.target.value)} />
              <datalist id="marcas-list">
                {(tipoSel && marcasPorTipo.length ? marcasPorTipo : marcas).map((m) => (
                  <option key={m.id} value={m.nombre} />
                ))}
              </datalist>
              {marcaTxt && !marcaId && (
                <div className="text-xs text-red-600 mt-1">Elegí una marca de las sugeridas.</div>
              )}
            </div>

            {/* Modelo */}
            <div className="md:col-span-2">
              <label className="text-sm">Modelo</label>
              <Select value={form.equipo.modelo_id} onChange={onChange("equipo.modelo_id")} disabled={!marcaId || !modelos.length}>
                <option value="">{!marcaId ? "Elegí marca primero" : "Seleccioná modelo"}</option>
                {modelos.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nombre}
                  </option>
                ))}
              </Select>
            </div>

            {/* Variante (opcional) */}
            <div className="md:col-span-4">
              <label className="text-sm">Variante (opcional)</label>
              <Input list="variantes_sugeridas" value={varianteTxt} onChange={(e) => setVarianteTxt(e.target.value)} placeholder="Ej: 25, 25T, V30BT, etc." />
              <datalist id="variantes_sugeridas">
                {(varianteSugeridas || []).map((v, i) => (
                  <option key={i} value={v} />
                ))}
              </datalist>
            </div>

            {/* Técnico asignado */}
            <div className="md:col-span-2">
              <label className="text-sm">Técnico asignado</label>
              <Select value={tecnicoId ?? ""} onChange={(e) => setTecnicoId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">-- Seleccionar técnico --</option>
                {(tecnicos || []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nombre || t.email || t.id}
                  </option>
                ))}
              </Select>
            </div>
          </div>
        </fieldset>

        {/* Equipo - datos de identificación y garantías */}
        <fieldset className="border rounded p-3">
          <legend className="px-2 font-semibold">Equipo - Identificación</legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Número de serie */}
            <div className="md:col-span-2">
              <label className="text-sm">Número de serie</label>
              <Input value={form.equipo.numero_serie} onChange={onNumeroSerieChange} />
            </div>

            {/* Número interno */}
            <div className="md:col-span-2">
              <div className="flex items-center justify-between gap-2">
                <label className="text-sm">Número Interno</label>
                {mgLookup.notFound && (
                  <span className="text-xs text-amber-600">MG no encontrado</span>
                )}
              </div>
              <Input value={form.equipo.numero_interno} onChange={onNumeroInternoChange} placeholder="MG/NM/NV/CE ..." />
            </div>

            {/* Garantías */}
            <div className="flex items-center gap-2">
              <input id="gar" type="checkbox" checked={form.equipo.garantia} onChange={onChange("equipo.garantia")} />
              <label htmlFor="gar">En Garantía</label>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" checked={form.garantia_reparacion} onChange={(e) => setForm((f) => ({ ...f, garantia_reparacion: e.target.checked }))} />
              <span className="text-sm">Garantía de reparación</span>
              {garRepLoading && <span className="text-xs text-gray-500">...</span>}
              {!garRepLoading && garRepError && <span className="text-xs text-gray-400">No disponible</span>}
            </div>

            {/* Etiquetas OK */}
            <div className="md:col-span-2 flex items-center gap-2 mt-2">
              <input id="etiqok" type="checkbox" checked={!!form.etiq_garantia_ok} onChange={(e) => setForm((f) => ({ ...f, etiq_garantia_ok: !!e.target.checked }))} />
              <label htmlFor="etiqok" className="text-sm">Faja de garantía abiertas</label>
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Marcá si al ingresar el equipo la faja/etiquetas estaban en mal estado.
            </div>
          </div>
        </fieldset>

        {/* Ingreso */}
        <fieldset className="border rounded p-3">
          <legend className="px-2 font-semibold">Ingreso</legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-sm">Número de remito</label>
              <Input value={form.remito_ingreso} onChange={onChange("remito_ingreso")} placeholder="Opcional" />
            </div>
            <div>
              <label className="text-sm">Fecha de ingreso</label>
              <Input type="date" value={form.fecha_ingreso} onChange={onChange("fecha_ingreso")} />
              <div className="text-xs text-gray-500 mt-1">Si se deja vacío, se usa la fecha de hoy.</div>
            </div>
            <div>
              <label className="text-sm">Motivo</label>
              <Select value={form.motivo} onChange={onChange("motivo")} required>
                <option value="">Seleccioná motivo</option>
                {motivos.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </Select>
              {!form.motivo && <div className="text-xs text-gray-600 mt-1">Seleccioná un motivo</div>}
            </div>
            <div className="text-sm text-gray-600 self-end">
              Ubicación inicial: <b>Taller</b> (se puede modificar desde la hoja de servicio)
            </div>
            <div className="md:col-span-2">
              <label className="text-sm">Informe preliminar</label>
              <TextArea rows={3} value={form.informe_preliminar} onChange={onChange("informe_preliminar")} />
            </div>
            <div className="md:col-span-2">
              <label className="text-sm">Comentarios</label>
              <TextArea rows={3} value={form.comentarios} onChange={onChange("comentarios")} placeholder="Notas internas u observaciones del ingreso" />
            </div>

            {/* Accesorios */}
            <div className="md:col-span-2">
              <label className="text-sm font-medium">Accesorios</label>
              <div className="flex flex-wrap items-end gap-3 mb-2">
                <div className="grow min-w-[260px]">
                  <label className="block text-sm text-gray-600 mb-1">Descripción</label>
                  <input className="border rounded p-2 w-full" list="accesorios_catalogo" value={nuevoAcc.descripcion} onChange={(e) => setNuevoAcc((s) => ({ ...s, descripcion: e.target.value }))} placeholder="Escribí y elegí de la lista" />
                  <datalist id="accesorios_catalogo">
                    {(Array.isArray(accesCatalogo) ? accesCatalogo : []).map((a) => (
                      <option key={a.id} value={a.nombre} />
                    ))}
                  </datalist>
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Número de referencia</label>
                  <Input value={nuevoAcc.referencia} onChange={(e) => setNuevoAcc((s) => ({ ...s, referencia: e.target.value }))} placeholder="Opcional" />
                </div>
                <button type="button" className="bg-blue-600 text-white px-3 py-2 rounded" onClick={() => {
                  const d = (nuevoAcc.descripcion || "").trim().toLowerCase();
                  if (!d) return;
                  const acc = (accesCatalogo || []).find((a) => (a.nombre || "").trim().toLowerCase() === d);
                  if (!acc) {
                    setErr("Elegí una descripción válida de la lista");
                    return;
                  }
                  setAccItems((list) => [
                    ...list,
                    { accesorio_id: acc.id, referencia: (nuevoAcc.referencia || "").trim(), accesorio_nombre: acc.nombre },
                  ]);
                  setNuevoAcc({ descripcion: "", referencia: "" });
                }}>Agregar</button>
              </div>
              {accItems.length > 0 && (
                <ul className="list-disc pl-5 text-sm text-gray-700">
                  {accItems.map((it, i) => (
                    <li key={i}>{it.accesorio_nombre}{it.referencia ? ` (ref: ${it.referencia})` : ""}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </fieldset>

        <div className="flex gap-3">
          <button
            disabled={loading || !canSubmitCliente || !marcaId || !form.equipo.modelo_id || !form.motivo}
            className={`px-4 py-2 rounded text-white ${
              loading || !canSubmitCliente || !marcaId || !form.equipo.modelo_id || !form.motivo
                ? "bg-blue-400 cursor-not-allowed"
                : "bg-blue-600"
            }`}
          >
            {loading ? "Guardando..." : "Crear Ingreso"}
          </button>
        </div>
      </form>
    </div>
  );
}
