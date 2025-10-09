// web/src/pages/ServiceSheet.jsx
import { useEffect, useState, useRef } from "react";
import { useParams, Link, useNavigate, useLocation } from "react-router-dom";
import api, {
  // ingreso / catálogos
  getIngreso, getUbicaciones, patchIngreso,
  getTecnicos, patchIngresoTecnico,
  getDerivacionesPorIngreso,
  postDerivacionDevuelto,
  // presupuesto
  getQuote, postQuoteItem, patchQuoteItem, deleteQuoteItem, patchQuoteResumen,
  postQuoteEmitir, postQuoteAprobar, getBlob, postQuoteAnular, postCerrarReparacion, postMarcarReparado,
  // entrega
  postEntregarIngreso,
  // accesorios
  getAccesoriosCatalogo, postAccesorioIngreso, deleteAccesorioIngreso,
  getIngresoHistorial,
  getGeneralEquipos,
} from "../lib/api";
import { getMarcas, getModelosByBrand, getVariantesPorMarca, checkGarantiaFabrica } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import {
  formatOS as formatOSHelper,
  formatDateTime as formatDateTimeHelper,
  resolveFechaIngreso,
  resolveFechaCreacion,
  toNum,
  catalogEquipmentLabel,
} from "../lib/ui-helpers";
import { canActAsTech, canRelease, hasAnyRole, ROLES } from "../lib/authz";
import { RESOLUCION, RESOLUCION_OPTIONS, resolutionLabel } from "../lib/constants";

import IngresoPhotos from "../components/IngresoPhotos";
import ArchivosTab from "./ServiceSheet/tabs/ArchivosTab";

// UI helpers
const Row = ({ label, children, className = "" }) => (
  <div className={`flex gap-3 py-1 ${className}`}>
    <div className="w-40 shrink-0 text-gray-500">{label}</div>
    <div className="flex-1 min-w-0 break-words">{children}</div>
  </div>
);

const Tabs = ({ value, onChange, items, extraRight }) => (
  <div className="border-b mb-4 flex items-center">
    <div className="flex gap-2">
      {items.map((it) => (
        <button
          key={it.value}
          className={`px-3 py-2 rounded-t ${
            value === it.value
              ? "bg-white border border-b-0"
              : "text-gray-600 hover:text-black"
          }`}
          onClick={() => onChange(it.value)}
          type="button"
        >
          {it.label}
        </button>
      ))}
    </div>
    <div className="ml-auto">{extraRight}</div>
  </div>
);

export default function ServiceSheet() {
  const { id } = useParams();
  const location = useLocation();
  const { user } = useAuth(); // para ocultar/mostrar botones según rol
  const navigate = useNavigate();
  const actAsTech = canActAsTech(user);
  const release = canRelease(user);
  const canEditBasics = hasAnyRole(user, [ROLES.JEFE, ROLES.JEFE_VEEDOR, ROLES.ADMIN]);
  const canAssignTecnico = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR]);
  const [editBasics, setEditBasics] = useState(false);
  const canSeeHistory = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR, ROLES.TECNICO]);
  const [formBasics, setFormBasics] = useState(null); // valores en edición local
  const [savingBasics, setSavingBasics] = useState(false);

  // Helpers datetime
  function toDatetimeLocalStr(isoOrDate) {
    if (!isoOrDate) return "";
    const d = isoOrDate instanceof Date ? isoOrDate : new Date(isoOrDate);
    const pad = (n) => String(n).padStart(2, "0");
    const yyyy = d.getFullYear();
    const mm = pad(d.getMonth() + 1);
    const dd = pad(d.getDate());
    const hh = pad(d.getHours());
    const mi = pad(d.getMinutes());
    return `${yyyy}-${mm}-${dd}T${hh}:${mi}`;
  }
  function isFutureLocal(dtLocalStr) {
    if (!dtLocalStr) return false;
    const selected = new Date(dtLocalStr);
    return selected.getTime() > Date.now();
  }

  // pesta├▒as
  const [tab, setTab] = useState("principal");
  // Permitir abrir con una pestaña preseleccionada (via navigate state)
  useEffect(() => {
    try {
      const t = location?.state?.tab;
      if (t && ["principal","diagnostico","presupuesto","derivaciones","historial"].includes(t)) {
        setTab(t);
      }
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location?.state]);

  // datos generales
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  // entrega
  const [entrega, setEntrega] = useState({
    remito_salida: "",
    factura_numero: "",
    fecha_entrega: "", // datetime-local string
  });
  const canEditEntrega = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR, ROLES.RECEPCION]);
  const [editEntrega, setEditEntrega] = useState(false);
  const [savingEntrega, setSavingEntrega] = useState(false);

  // ubicaciones
  const [ubicaciones, setUbicaciones] = useState([]);
  const [ubicacionId, setUbicacionId] = useState("");
  const [savingUb, setSavingUb] = useState(false);

  // técnicos
  const [tecnicos, setTecnicos] = useState([]);
  const [tecnicoId, setTecnicoId] = useState(null);
  const [savingTech, setSavingTech] = useState(false);

  // derivaciones
  const [derivs, setDerivs] = useState([]);
  const [fechaDevStr, setFechaDevStr] = useState(() => new Date().toISOString().slice(0,10));
  const [savingDev, setSavingDev] = useState(false);

  // accesorios (catálogo + alta/baja)
  const [accesCatalogo, setAccesCatalogo] = useState([]);
  const [nuevoAcc, setNuevoAcc] = useState({ descripcion: "", referencia: "" });
  const [addingAcc, setAddingAcc] = useState(false);
  const [deletingAccId, setDeletingAccId] = useState(null);

  // campos de técnico
  const [descripcion, setDescripcion] = useState("");
  const [trabajos, setTrabajos] = useState("");
  const [savingAll, setSavingAll] = useState(false);
  const [resolucion, setResolucion] = useState("");
  const [savingResol, setSavingResol] = useState(false);
  const [showResolToast, setShowResolToast] = useState(false);
  const [showReparadoToast, setShowReparadoToast] = useState(false);

  const canResolve = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR]);
  const [fechaServStr, setFechaServStr] = useState("");
  const maxLocalNow = toDatetimeLocalStr(new Date());

  // presupuesto
  const [quote, setQuote] = useState(null);
  const [qLoading, setQLoading] = useState(false);
  const [qErr, setQErr] = useState("");
  const [autorizadoPor, setAutorizadoPor] = useState("Cliente");
  const [formaPago, setFormaPago] = useState("30 F.F.");
  const [emitiendo, setEmitiendo] = useState(false);
  const [aprobando, setAprobando] = useState(false);
  const [anulando, setAnulando] = useState(false);
  const [nuevoRep, setNuevoRep] = useState({ repuesto_id: "", descripcion: "", qty: "1", precio_u: "" });
  const [manoObraStr, setManoObraStr] = useState("");
  const [showDiagToast, setShowDiagToast] = useState(false);
  const toastTimer = useRef(null);

  // historial de cambios
  const [hist, setHist] = useState([]);
  const [hLoading, setHLoading] = useState(false);
  const [hErr, setHErr] = useState("");

  // ingresos relacionados por N/S
  const [relatedOpen, setRelatedOpen] = useState(false);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [relatedErr, setRelatedErr] = useState("");
  const [relatedRows, setRelatedRows] = useState([]);

  // Catálogo de Equipo (para editar Marca/Modelo/Variante)
  const [marcas, setMarcas] = useState([]);
  const [marcaIdSel, setMarcaIdSel] = useState(null);
  const [modelos, setModelos] = useState([]);
  const [modeloIdSel, setModeloIdSel] = useState(null);
  const [tipoSel, setTipoSel] = useState(""); // filtro local por "tipo_equipo" del modelo
  const [varSugeridas, setVarSugeridas] = useState([]);

  function money(n) {
    if (n == null) return "-";
    const num = Number(n);
    if (Number.isNaN(num)) return String(n);
    return num.toLocaleString("es-AR", { style: "currency", currency: "ARS", minimumFractionDigits: 2 });
  }

  // helper PATCH único para campos simples
  async function patch(fields) {
    try {
      await patchIngreso(id, fields);
      setData((d) => ({ ...d, ...fields }));
      setErr("");
    } catch (e) {
      setErr(e?.message || "No se pudo guardar");
    }
  }

  async function loadQuote() {
    try {
      setQErr(""); setQLoading(true);
      const q = await getQuote(id);
      setQuote(q);
      setManoObraStr(String(q?.mano_obra ?? "0"));
      setFormaPago(q?.forma_pago ?? "30 F.F.");
    } catch (e) {
      setQErr(e?.message || "No se pudo cargar el presupuesto");
      setQuote(null);
    } finally {
      setQLoading(false);
    }
  }

  async function abrirPdf() {
    try {
      setQErr("");
      const blob = await getBlob(`/api/quotes/${id}/pdf/`);
      if (!(blob instanceof Blob)) throw new Error("La respuesta del API no fue un Blob.");
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      setQErr(e?.message || "No se pudo abrir el PDF del presupuesto");
    }
  }

  async function emitirPresupuesto() {
    try {
      setEmitiendo(true);
      const r = await postQuoteEmitir(id, { autorizado_por: autorizadoPor, forma_pago: formaPago });
      setQuote(r);
      setData(prev => ({ ...prev, presupuesto_estado: "presupuestado" }));
      if (r?.pdf_url) await abrirPdf();
    } catch (e) {
      setQErr(e?.message || "No se pudo emitir el presupuesto");
    } finally {
      setEmitiendo(false);
    }
  }

  async function anularPresupuesto() {
    if (!confirm("¿Anular el presupuesto actual? Podrás editar y re-emitir luego.")) return;
    try {
      setAnulando(true);
      setQErr("");
      const r = await postQuoteAnular(id);
      setQuote(r);
      setData((d) => ({ ...d, presupuesto_estado: r?.estado || "anulado" }));
    } catch (e) {
      setQErr(e?.message || "No se pudo anular el presupuesto");
    } finally {
      setAnulando(false);
    }
  }

  async function aprobarPresupuesto() {
    try {
      setAprobando(true);
      setQErr("");
      const r = await postQuoteAprobar(id);
      setQuote(r);
      setData((d) => ({ ...d, presupuesto_estado: "aprobado" }));
    } catch (e) {
      setQErr(e?.message || "No se pudo aprobar el presupuesto");
    } finally {
      setAprobando(false);
    }
  }

  async function saveResolucion() {
    try {
      if (!resolucion) { setErr("Seleccioná una resolución."); return; }
      setSavingResol(true);
      await postCerrarReparacion(id, { resolucion });
      await refreshIngreso();
      setShowResolToast(true);
      setTimeout(() => setShowResolToast(false), 2000);
      setErr("");
    } catch (e) {
      setErr(e?.message || "No se pudo guardar la resolución");
    } finally {
      setSavingResol(false);
    }
  }

  async function refreshIngreso() {
    try {
      const ing = await getIngreso(id);
      setData(ing);
    } catch (e) {
      setErr(e?.message || "No se pudo refrescar el ingreso");
    }
  }

  useEffect(() => { if (tab === "presupuesto") loadQuote(); }, [tab, id]);
  useEffect(() => {
    if (tab !== "historial") return;
    (async () => {
      try {
        setHErr(""); setHLoading(true);
        const rows = await getIngresoHistorial(id);
        setHist(Array.isArray(rows) ? rows : []);
      } catch (e) {
        setHErr(e?.message || "No se pudo cargar el historial");
        setHist([]);
      } finally {
        setHLoading(false);
      }
    })();
  }, [tab, id]);

  useEffect(() => {
    setRelatedOpen(false);
    setRelatedRows([]);
    setRelatedErr("");
    setRelatedLoading(false);
  }, [id]);

  useEffect(() => {
    if (!relatedOpen) return;
    const serie = (data?.numero_serie || "").trim();
    if (!serie) {
      setRelatedErr("Este equipo no tiene número de serie registrado.");
      setRelatedRows([]);
      setRelatedLoading(false);
      return;
    }
    let cancelled = false;
    setRelatedLoading(true);
    setRelatedErr("");
    (async () => {
      try {
        const rows = await getGeneralEquipos({ q: serie });
        if (cancelled) return;
        const safe = Array.isArray(rows) ? rows : [];
        const normalized = serie.toLowerCase();
        const toTs = (row) => {
          const raw = resolveFechaCreacion(row);
          if (!raw) return 0;
          const ts = new Date(raw).getTime();
          return Number.isNaN(ts) ? 0 : ts;
        };
        const filtered = safe
          .filter((row) => String(row?.numero_serie || "").trim().toLowerCase() === normalized)
          .sort((a, b) => toTs(b) - toTs(a));
        setRelatedRows(filtered);
      } catch (e) {
        if (cancelled) return;
        setRelatedErr(e?.message || "No se pudieron cargar los ingresos del equipo.");
        setRelatedRows([]);
      } finally {
        if (!cancelled) {
          setRelatedLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [relatedOpen, data?.numero_serie, id]);

  useEffect(() => {
    if (!relatedOpen) return;
    const handler = (ev) => {
      if (ev.key === "Escape") setRelatedOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [relatedOpen]);

  // Activar edición: inicializa formulario local con datos actuales
  function startEditBasics() {
    setFormBasics({
      razon_social: data?.razon_social || "",
      cod_empresa: data?.cod_empresa || "",
      telefono: data?.telefono || "",
      propietario_nombre: data?.propietario_nombre || "",
      propietario_contacto: data?.propietario_contacto || "",
      propietario_doc: data?.propietario_doc || "",
      numero_serie: data?.numero_serie || "",
      numero_interno: data?.numero_interno || "",
      remito_ingreso: data?.remito_ingreso || "",
      informe_preliminar: data?.informe_preliminar || "",
      garantia_reparacion: !!data?.garantia_reparacion,
      // Equipo adicional
      equipo_variante: data?.equipo_variante || "",
      garantia: !!data?.garantia,
    });
    setEditBasics(true);
    // Inicializar selección de Marca/Modelo/Tipo/Variante
    (async () => {
      try {
        // Cargar marcas si aún no están
        if (!marcas.length) {
          try { setMarcas(await getMarcas()); } catch { /* noop */ }
        }
        // Resolver marca actual por nombre
        const norm = (s) => (s || "").toString().trim().toLowerCase();
        const curMarcaName = norm(data?.marca);
        let curMarca = (marcas.length ? marcas : await getMarcas()).find((m) => norm(m?.nombre) === curMarcaName);
        const marcaId = curMarca?.id ?? null;
        setMarcaIdSel(marcaId);
        // Tipo de equipo mostrado actualmente (solo para filtrar modelos)
        const tipoActual = (data?.tipo_equipo_nombre || data?.tipo_equipo || "").toString();
        setTipoSel(tipoActual);
        // Cargar modelos por marca y preseleccionar el actual si coincide
        if (marcaId) {
          try {
            const list = await getModelosByBrand(marcaId);
            setModelos(list || []);
            const curModeloName = norm(data?.modelo);
            const md = (list || []).find((x) => norm(x?.nombre) === curModeloName);
            setModeloIdSel(md?.id ?? null);
          } catch { setModelos([]); setModeloIdSel(null); }
          // Cargar variantes sugeridas por marca
          try { setVarSugeridas(await getVariantesPorMarca(marcaId)); } catch { setVarSugeridas([]); }
        } else {
          setModelos([]); setModeloIdSel(null); setVarSugeridas([]);
        }
      } catch { /* noop */ }
    })();
  }

  async function saveEditBasics() {
    if (!formBasics) { setEditBasics(false); return; }
    const diff = {};
    const cmp = (a, b) => (a ?? "") !== (b ?? "");
    if (cmp(formBasics.razon_social, data?.razon_social)) diff.razon_social = formBasics.razon_social;
    if (cmp(formBasics.cod_empresa, data?.cod_empresa)) diff.cod_empresa = formBasics.cod_empresa;
    if (cmp(formBasics.telefono, data?.telefono)) diff.telefono = formBasics.telefono;
    if (cmp(formBasics.propietario_nombre, data?.propietario_nombre)) diff.propietario_nombre = formBasics.propietario_nombre;
    if (cmp(formBasics.propietario_contacto, data?.propietario_contacto)) diff.propietario_contacto = formBasics.propietario_contacto;
    if (cmp(formBasics.propietario_doc, data?.propietario_doc)) diff.propietario_doc = formBasics.propietario_doc;
    if (cmp(formBasics.numero_serie, data?.numero_serie)) diff.numero_serie = formBasics.numero_serie;
    if (cmp(formBasics.numero_interno, data?.numero_interno)) diff.numero_interno = formBasics.numero_interno;
    const remitoNuevo = (formBasics.remito_ingreso || "").trim();
    const remitoActual = (data?.remito_ingreso || "").trim();
    if (remitoNuevo !== remitoActual) diff.remito_ingreso = remitoNuevo;
    // Informe preliminar
    if (cmp(formBasics.informe_preliminar, data?.informe_preliminar)) diff.informe_preliminar = formBasics.informe_preliminar;
    if ((formBasics.garantia_reparacion ? 1 : 0) !== (data?.garantia_reparacion ? 1 : 0)) diff.garantia_reparacion = !!formBasics.garantia_reparacion;
    // Equipo: Marca / Modelo / Variante / Garantía (fábrica)
    try {
      const norm = (s) => (s || "").toString().trim().toLowerCase();
      const selMarca = marcas.find((m) => String(m.id) === String(marcaIdSel));
      if (selMarca && norm(selMarca?.nombre) !== norm(data?.marca)) {
        diff.marca_id = Number(selMarca.id);
      }
      const selModelo = modelos.find((m) => String(m.id) === String(modeloIdSel));
      if (selModelo && norm(selModelo?.nombre) !== norm(data?.modelo)) {
        diff.modelo_id = Number(selModelo.id);
      }
      const varNew = (formBasics?.equipo_variante || "").trim();
      const varOld = (data?.equipo_variante || "").trim();
      if (varNew !== varOld) diff.equipo_variante = varNew || null;
      const garNew = !!formBasics?.garantia;
      const garOld = !!data?.garantia;
      if (garNew !== garOld) diff.garantia = garNew;
    } catch { /* noop diff equipo */ }
    try {
      setSavingBasics(true);
      if (Object.keys(diff).length > 0) {
        await patch(diff);
        // Si cambia equipo (marca/modelo/variante/garantía) o identificadores (NS/MG), refrescar desde el back
        if (
          diff.marca_id != null ||
          diff.modelo_id != null ||
          diff.equipo_variante !== undefined ||
          diff.garantia !== undefined ||
          diff.numero_serie !== undefined ||
          diff.numero_interno !== undefined
        ) {
          await refreshIngreso();
        }
      }
      setEditBasics(false);
      setFormBasics(null);
    } finally {
      setSavingBasics(false);
    }
  }

  // cargar catálogo de accesorios una sola vez
  useEffect(() => {
    (async () => {
      try { setAccesCatalogo(await getAccesoriosCatalogo()); } catch (_) {}
    })();
  }, []);

  // Cargar marcas al montar (para acelerar al entrar en edición)
  useEffect(() => {
    (async () => { try { setMarcas(await getMarcas()); } catch { /* noop */ } })();
  }, []);

  // Cuando cambia marca en edición -> cargar modelos y variantes sugeridas
  useEffect(() => {
    if (!editBasics) return;
    if (!marcaIdSel) { setModelos([]); setModeloIdSel(null); setVarSugeridas([]); return; }
    (async () => {
      try {
        const list = await getModelosByBrand(marcaIdSel);
        setModelos(list || []);
      } catch { setModelos([]); }
      try { setVarSugeridas(await getVariantesPorMarca(marcaIdSel)); } catch { setVarSugeridas([]); }
      setModeloIdSel(null);
    })();
  }, [editBasics, marcaIdSel]);

  // Auto-chequeo de garantía de fábrica cuando se edita NS o cambia la marca
  useEffect(() => {
    if (!editBasics) return;
    const ns = (formBasics?.numero_serie || "").trim();
    const selMarca = marcas.find((m) => String(m.id) === String(marcaIdSel));
    const marcaName = (selMarca?.nombre || data?.marca || "").toString();
    if (!ns) {
      if (formBasics) setFormBasics((s) => ({ ...(s || {}), garantia: false }));
      return;
    }
    const h = setTimeout(async () => {
      try {
        const r = await checkGarantiaFabrica(ns, marcaName);
        const enGarantia = !!r.within_365_days;
        setFormBasics((s) => ({ ...(s || {}), garantia: enGarantia }));
      } catch { /* noop */ }
    }, 400);
    return () => clearTimeout(h);
  }, [editBasics, formBasics?.numero_serie, marcaIdSel, marcas, data?.marca]);

  const canEditAcc = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR, ROLES.TECNICO, ROLES.RECEPCION]) && data?.estado !== "entregado";

  async function addAccesorio() {
    try {
      const d = (nuevoAcc.descripcion || "").trim().toLowerCase();
      if (!d) { setErr("Escribí una descripción"); return; }
      const acc = accesCatalogo.find(a => (a.nombre || "").trim().toLowerCase() === d);
      if (!acc) { setErr("Elegí una descripción válida de la lista"); return; }
      setAddingAcc(true);
      const row = await postAccesorioIngreso(id, {
        accesorio_id: Number(acc.id),
        referencia: (nuevoAcc.referencia || "").trim() || null,
      });
      setData(d => ({ ...d, accesorios_items: [...(d?.accesorios_items || []), row] }));
      setNuevoAcc({ descripcion: "", referencia: "" });
      setErr("");
    } catch (e) {
      setErr(e?.message || "No se pudo agregar el accesorio");
    } finally {
      setAddingAcc(false);
    }
  }

  async function removeAccesorio(itemId) {
    try {
      setDeletingAccId(itemId);
      await deleteAccesorioIngreso(id, itemId);
      setData(d => ({ ...d, accesorios_items: (d?.accesorios_items || []).filter(it => it.id !== itemId) }));
      setErr("");
    } catch (e) {
      setErr(e?.message || "No se pudo quitar el accesorio");
    } finally {
      setDeletingAccId(null);
    }
  }

  async function addRepuesto() {
    const qty = Number(nuevoRep.qty || 0);
    const pu  = Number(nuevoRep.precio_u || 0);
    if (!nuevoRep.descripcion.trim()) { setQErr("Descripción requerida"); return; }
    if (qty <= 0) { setQErr("Cantidad > 0"); return; }
    if (pu < 0) { setQErr("Precio inválido"); return; }
    await postQuoteItem(id, {
      tipo: "repuesto",
      repuesto_id: nuevoRep.repuesto_id ? Number(nuevoRep.repuesto_id) : null,
      descripcion: nuevoRep.descripcion.trim(),
      qty, precio_u: pu,
    });
    setNuevoRep({ repuesto_id: "", descripcion: "", qty: "1", precio_u: "" });
    await loadQuote();
  }

  async function updateItem(it, patchRow) { await patchQuoteItem(id, it.id, patchRow); await loadQuote(); }
  async function handleRemoveItem(it) {
    if (!confirm("¿Eliminar renglón?")) return;
    try {
      await deleteQuoteItem(id, it.id);
      await loadQuote();
    } catch (e) {
      setQErr(e?.message || "No se pudo eliminar el renglón");
    }
  }
  async function removeItem(it) { if (!confirm("¿Eliminar renglónó")) return; await deleteQuoteItem(id, it.id); await loadQuote(); }
  async function saveManoObra() {
    const mo = Number(manoObraStr || 0);
    if (mo < 0) { setQErr("Mano de obra inválida"); return; }
    await patchQuoteResumen(id, { mano_obra: mo });
    await loadQuote();
  }

  // carga general
  useEffect(() => {
    (async () => {
      try {
        const [ing, ubs] = await Promise.all([getIngreso(id), getUbicaciones()]);
        setData(ing);
        setUbicaciones(ubs);
        setUbicacionId(ing?.ubicacion_id != null ? String(ing.ubicacion_id) : "");
        setTecnicoId(ing?.asignado_a ?? null);

        // inicializar campos de técnico
        setDescripcion(ing?.descripcion_problema ?? "");
        setTrabajos(ing?.trabajos_realizados ?? "");
        setResolucion(ing?.resolucion ?? "");
        setFechaServStr(toDatetimeLocalStr(ing?.fecha_servicio));
        // inicializar campos de entrega
        setEntrega({
          remito_salida: ing?.remito_salida || "",
          factura_numero: ing?.factura_numero || "",
          fecha_entrega: toDatetimeLocalStr(ing?.fecha_entrega),
        });

        // técnicos
        if (canAssignTecnico) {
          try { setTecnicos(await getTecnicos()); } catch (_) {}
        } else {
          setTecnicos([]);
        }

        // derivaciones
        try { setDerivs(await getDerivacionesPorIngreso(id)); } catch (_) {}
      } catch (e) {
        setErr(e?.message || "Error cargando datos");
      }
    })();
  }, [id, canAssignTecnico]);

  // Ubicación
  const selectedIdNum = toNum(ubicacionId);
  const currentIdNum = toNum(data?.ubicacion_id);
  const ubDirty = selectedIdNum !== null && selectedIdNum !== currentIdNum;
  async function saveUbicacion() {
    if (!ubDirty) return;
    try {
      setSavingUb(true);
      await patchIngreso(id, { ubicacion_id: selectedIdNum });
      const nuevaUb = ubicaciones.find((u) => String(u.id) === String(ubicacionId));
      setData((d) => ({ ...d, ubicacion_id: selectedIdNum, ubicacion_nombre: nuevaUb?.nombre ?? d.ubicacion_nombre }));
      setErr("");
    } catch (e) {
      setErr(e?.message || "No se pudo actualizar la ubicación");
    } finally {
      setSavingUb(false);
    }
  }

  // Técnico
  const techDirty = canAssignTecnico && (tecnicoId ?? null) !== (data?.asignado_a ?? null);
  async function saveTecnico() {
    if (!canAssignTecnico || !techDirty || tecnicoId == null) return;
    try {
      setSavingTech(true);
      await patchIngresoTecnico(id, Number(tecnicoId));
      const t = tecnicos.find((t) => String(t.id) === String(tecnicoId));
      setData((d) => ({ ...d, asignado_a: Number(tecnicoId), asignado_a_nombre: t?.nombre || d.asignado_a_nombre }));
      setErr("");
    } catch (e) {
      setErr(e?.message || "No se pudo asignar el técnico");
    } finally {
      setSavingTech(false);
    }
  }

  // Guardar diagnóstico / trabajos / fecha de servicio
  async function saveDiagYReparacion() {
    try {
      setSavingAll(true);
      const payload = {
        descripcion_problema: descripcion,
        trabajos_realizados: trabajos,
        fecha_servicio: fechaServStr || null,
      };
      const prevEstado = data?.estado;
      await patchIngreso(id, payload);
      const ing = await getIngreso(id);
      setData(ing);
      if (prevEstado !== "diagnosticado" && ing?.estado === "diagnosticado") {
        setShowDiagToast(true);
        if (toastTimer.current) clearTimeout(toastTimer.current);
        toastTimer.current = setTimeout(() => setShowDiagToast(false), 2500);
      }
      setErr("");
    } catch (e) {
      setErr(e?.message || "No se pudo guardar");
    } finally {
      setSavingAll(false);
    }
  }

  if (!data) return <div className="p-4">Cargando...</div>;
  const isAprobado = data.presupuesto_estado === "aprobado";
  const numeroSerie = (data?.numero_serie || "").trim();

  const userId = Number(user?.id || 0);
  const canManagePhotos = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR]) ||
    (user?.rol === ROLES.TECNICO && userId && data?.asignado_a === userId);
  const isTech = user?.rol === ROLES.TECNICO;
  const canEditDiag = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR]) ||
    (isTech && userId && data?.asignado_a === userId);
  const canMarkReparado = canEditDiag;

  return (
    <div className="max-w-none p-4">
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="mb-3 inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800"
      >
        Volver
      </button>
      <h1 className="text-2xl font-bold mb-2">Hoja de servicio — {formatOSHelper(data, id)} — NS {data?.numero_serie}</h1>

      {err && <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-4">{err}</div>}
      {canSeeHistory && (
        <div className="-mt-8 -mb-2 text-right">
          <button
            className={`px-3 py-2 rounded-t ${tab === 'historial' ? 'bg-white border border-b-0' : 'text-gray-600 hover:text-black'}`}
            onClick={() => setTab('historial')}
            type="button"
          >
            Historial
          </button>
        </div>
      )}

      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          { value: "principal", label: "Principal" },
          { value: "diagnostico", label: "Diagnóstico y Reparación" },
          { value: "presupuesto", label: "Presupuesto" },
          { value: "derivaciones", label: "Derivaciones" },
          { value: "archivos", label: "Archivos" },
        ]}
      />

      {/* ARCHIVOS */}
      {tab === "archivos" && (
        <ArchivosTab id={id} canManagePhotos={canManagePhotos} />
      )}


      {/* PRINCIPAL */}
      {tab === "principal" && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Columna izquierda: Cliente/Equipo/Notas */}
            <div className="border rounded p-4">
              <h2 className="font-semibold mb-2">Cliente</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
              <Row label="Razón social">
                {editBasics? (
                  <input
                    className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                    value={formBasics?.razon_social ?? ""}
                    onChange={(e) => setFormBasics(s => ({ ...s, razon_social: e.target.value }))}
                  />
                ) : (
                  data.razon_social
                )}
              </Row>
              <Row label="Código empresa">
                {editBasics ? (
                  <input
                    className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                    value={formBasics?.cod_empresa ?? ""}
                    onChange={(e) => setFormBasics(s => ({ ...s, cod_empresa: e.target.value }))}
                  />
                ) : (
                  data.cod_empresa || "-"
                )}
              </Row>
              <Row label="Teléfono">
                {editBasics ? (
                  <input
                    className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                    value={formBasics?.telefono ?? ""}
                    onChange={(e) => setFormBasics(s => ({ ...s, telefono: e.target.value }))}
                  />
                ) : (
                  data.telefono || "-"
                )}
              </Row>

              </div>
              {(editBasics || data.propietario_nombre || data.propietario_contacto || data.propietario_doc) && (
                <>
                  <h2 className="font-semibold mt-4 mb-2">Propietario</h2>
                  <Row label="Nombre">
                    {editBasics ? (
                      <input
                        className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                        value={formBasics?.propietario_nombre ?? ""}
                        onChange={(e) => setFormBasics(s => ({ ...s, propietario_nombre: e.target.value }))}
                      />
                    ) : (
                      data.propietario_nombre || "-"
                    )}
                  </Row>
                  <Row label="Contacto">
                    {editBasics ? (
                      <input
                        className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                        value={formBasics?.propietario_contacto ?? ""}
                        onChange={(e) => setFormBasics(s => ({ ...s, propietario_contacto: e.target.value }))}
                      />
                    ) : (
                      data.propietario_contacto || "-"
                    )}
                  </Row>
                  <Row label="Documento">
                    {editBasics ? (
                      <input
                        className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                        value={formBasics?.propietario_doc ?? ""}
                        onChange={(e) => setFormBasics(s => ({ ...s, propietario_doc: e.target.value }))}
                      />
                    ) : (
                      data.propietario_doc || "-"
                    )}
                  </Row>
                </>
              )}

              <h2 className="font-semibold mt-4 mb-2">Equipo</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
              <Row label="Tipo de equipo">
                {editBasics ? (
                  <select
                    className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                    value={tipoSel}
                    onChange={(e) => { setTipoSel(e.target.value); setModeloIdSel(null); }}
                  >
                    <option value="">(todos)</option>
                    {Array.from(new Set((modelos || []).map((m) => (m?.tipo_equipo || "").toString().trim().toUpperCase())))
                      .filter(Boolean)
                      .map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                  </select>
                ) : (
                  data.tipo_equipo_nombre || data.tipo_equipo || "-"
                )}
              </Row>
              <Row label="Marca">
                {editBasics ? (
                  <select
                    className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                    value={marcaIdSel == null ? "" : String(marcaIdSel)}
                    onChange={(e) => {
                      const v = e.target.value === "" ? null : Number(e.target.value);
                      setMarcaIdSel(v);
                      setModeloIdSel(null);
                    }}
                  >
                    <option value="">(sin marca)</option>
                    {(marcas || []).map((m) => (
                      <option key={m.id} value={String(m.id)}>
                        {m.nombre}
                      </option>
                    ))}
                  </select>
                ) : (
                  data.marca
                )}
              </Row>
              <Row label="Modelo">
                {editBasics ? (
                  <select
                    className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                    value={modeloIdSel == null ? "" : String(modeloIdSel)}
                    onChange={(e) => setModeloIdSel(e.target.value === "" ? null : Number(e.target.value))}
                  >
                    <option value="">(sin modelo)</option>
                    {(modelos || [])
                      .filter((m) => {
                        const norm = (s) => (s || "").toString().trim().toUpperCase();
                        return !tipoSel || norm(m?.tipo_equipo) === norm(tipoSel);
                      })
                      .map((m) => (
                        <option key={m.id} value={String(m.id)}>
                          {m.nombre}
                        </option>
                      ))}
                  </select>
                ) : (
                  data.modelo || "-"
                )}
              </Row>
              <Row label="Variante">
                {editBasics ? (
                  <>
                    <input
                      list="variantesOptions"
                      className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                      value={formBasics?.equipo_variante ?? ""}
                      onChange={(e) => setFormBasics(s => ({ ...(s || {}), equipo_variante: e.target.value }))}
                    />
                    <datalist id="variantesOptions">
                      {(varSugeridas || []).map((v, idx) => (
                        <option key={idx} value={v} />
                      ))}
                    </datalist>
                  </>
                ) : (
                  data.equipo_variante || "-"
                )}
              </Row>
              <Row label="N° serie">
                {editBasics ? (
                  <input
                    className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                    value={formBasics?.numero_serie ?? ""}
                    onChange={(e) => setFormBasics(s => ({ ...s, numero_serie: e.target.value }))}
                  />
                ) : (
                  <span>{numeroSerie || "-"}</span>
                )}
              </Row>
              <Row label="Garantía (fábrica)">
                {editBasics ? (
                  <input
                    type="checkbox"
                    checked={!!(formBasics?.garantia)}
                    onChange={(e) => setFormBasics((s) => ({ ...(s || {}), garantia: e.target.checked }))}
                  />
                ) : (
                  data.garantia ? "Sí" : "No"
                )}
              </Row>
              <Row label="N° interno (MG)">
                {editBasics ? (
                  <input
                    className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                    value={formBasics?.numero_interno || ""}
                    onChange={(e) => setFormBasics(s => ({ ...s, numero_interno: e.target.value }))}
                  />
                ) : (
                  <span>{data.numero_interno || ""}</span>
                )}
              </Row>
              <Row label="Garantía de reparación">
                {editBasics ? (
                  <input
                    type="checkbox"
                    checked={!!(formBasics?.garantia_reparacion)}
                    onChange={(e) => setFormBasics(s => ({ ...s, garantia_reparacion: e.target.checked }))}
                  />
                ) : (
                  <span>{data.garantia_reparacion ? "Sí" : "No"}</span>
                )}
              </Row>
              <Row label={"N° de remito"}>
                {editBasics ? (
                  <input
                    className="border rounded p-1 w-full bg-yellow-50 focus:bg-yellow-100"
                    value={formBasics?.remito_ingreso ?? ""}
                    onChange={(e) => setFormBasics(s => ({ ...s, remito_ingreso: e.target.value }))}
                  />
                ) : (
                  <span>{data.remito_ingreso || "-"}</span>
                )}
              </Row>

              </div>
              {/* Notas justo debajo del cuadro de Equipo */}
                <h2 className="font-semibold mt-4 mb-2">Notas</h2>
                <Row label="Informe preliminar">
                  {editBasics ? (
                    <textarea
                      className="border rounded p-2 w-full min-h-[100px] bg-yellow-50 focus:bg-yellow-100"
                      value={formBasics?.informe_preliminar ?? ""}
                      onChange={(e) => setFormBasics(s => ({ ...s, informe_preliminar: e.target.value }))}
                    />
                  ) : (
                    <div className="whitespace-pre-wrap">{data.informe_preliminar || "-"}</div>
                  )}
                </Row>
                <Row label="Accesorios">
                  {Array.isArray(data.accesorios_items) && data.accesorios_items.length > 0 ? (
                    <ul className="list-disc list-inside">
                      {data.accesorios_items.map((it) => (
                        <li key={it.id}>
                          {it.accesorio_nombre}
                          {it.referencia ? ` (ref: ${it.referencia})` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : (data.accesorios || "-")}
                </Row>
            </div>


            {/* Columna derecha: Estado/Asignación/Ubicación */}
            <div className="border rounded p-4">
              <h2 className="font-semibold mb-2">Estado</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
              <Row label="Motivo">{data.motivo}</Row>
              <Row label="Estado">{data.estado}</Row>
              <Row label="Presupuesto">{data.presupuesto_estado === "presupuestado" ? "Presupuestado" : (data.presupuesto_estado || "-")}</Row>
              <Row label="Resolución">{data.resolucion ? resolutionLabel(data.resolucion) : "-"}</Row>
              <Row label="Fecha ingreso">{formatDateTimeHelper(resolveFechaIngreso(data))}</Row>
              <Row label="Fecha servicio">{data.fecha_servicio ? formatDateTimeHelper(data.fecha_servicio) : "-"}</Row>
              </div>

              {/* Derivar a externo -> movido a pesta├▒a Derivaciones */}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
                <div>
                  <h2 className="font-semibold mb-2">Asignación</h2>
                  <div className="flex flex-col items-start gap-2">
                    {canAssignTecnico ? (
                      <>
                        <select className="border rounded p-2" value={tecnicoId ?? ""} onChange={(e) => setTecnicoId(e.target.value ? Number(e.target.value) : null)}>
                          <option value="">-- Seleccionar técnico --</option>
                          {tecnicos.map((t) => (<option key={t.id} value={t.id}>{t.nombre}</option>))}
                        </select>
                        <button
                          className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
                          onClick={saveTecnico}
                          disabled={savingTech || !techDirty || tecnicoId == null}
                          aria-busy={savingTech ? "true" : "false"}
                          type="button"
                        >
                          {savingTech ? "Guardando..." : "Guardar"}
                        </button>
                      </>
                    ) : (
                      <div className="text-sm text-gray-500">No tenés permiso para reasignar técnicos.</div>
                    )}
                    <div className="text-xs text-gray-500">Actual: <b>{data.asignado_a_nombre || "-"}</b></div>
                  </div>
                </div>
                <div>
                  <h2 className="font-semibold mb-2">Ubicación</h2>

                  <div className="flex flex-col items-start gap-2">
                    <select className="border rounded p-2" value={ubicacionId} onChange={(e) => setUbicacionId(e.target.value)} aria-label="Seleccionar ubicación">
                      <option value="" disabled>Selección la ubicación.</option>
                      {ubicaciones.map((u) => (<option key={u.id} value={String(u.id)}>{u.nombre}</option>))}
                    </select>
                    <button className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60" onClick={saveUbicacion} disabled={savingUb || !ubDirty} aria-busy={savingUb ? "true" : "false"} type="button">
                      {savingUb ? "Guardando..." : "Guardar"}
                    </button>
                  </div>
                  <div className="text-xs text-gray-500">La ubicación puede modificarse desde aquí.</div>
                </div>
                  {numeroSerie && (
                    <div className="flex justify-end mb-2 w-full">
                      <button
                        type="button"
                        onClick={() => setRelatedOpen(true)}
                        className="text-xs px-2 py-1 rounded border border-blue-600 text-blue-600 hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
                      >
                        Ver ingresos del equipo
                      </button>
                    </div>
                  )}
              </div>
            </div>
          </div>

          {/* Botón de orden de salida (liberar) */}
          {release && (Boolean(data?.resolucion) || data?.estado === "liberado") && (
            <button
              className="bg-neutral-800 text-white px-3 py-2 rounded mt-4"
              onClick={async () => {
                try {
                  const blob = await getBlob(`/api/ingresos/${id}/remito/`);
                  if (!(blob instanceof Blob)) throw new Error("La respuesta no fue un PDF");
                  const url = URL.createObjectURL(blob);
                  window.open(url, "_blank", "noopener");
                  setTimeout(() => URL.revokeObjectURL(url), 60_000);
                  await refreshIngreso(); // el backend ahora pasa a 'liberado'
                } catch (e) {
                  setErr(e?.message || "No se pudo imprimir la orden de salida");
                }
              }}
              type="button"
            >
              Imprimir orden de salida (liberar)
            </button>
          )}

          {/* Entrega: editable si está 'liberado'; si no, mostrar datos guardados */}
          <div className="border rounded p-4 mt-4">
            <h2 className="font-semibold mb-2">Entrega</h2>
            {data.estado === "liberado" ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="text-sm">Remito salida (requerido)</label>
                    <input
                      className="border rounded p-2 w-full"
                      value={entrega.remito_salida}
                      onChange={(e) => setEntrega({ ...entrega, remito_salida: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-sm">Factura (opcional)</label>
                    <input
                      className="border rounded p-2 w-full"
                      value={entrega.factura_numero}
                      onChange={(e) => setEntrega({ ...entrega, factura_numero: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-sm">Fecha entrega</label>
                    <input
                      type="datetime-local"
                      className="border rounded p-2 w-full"
                      value={entrega.fecha_entrega}
                      onChange={(e) => setEntrega({ ...entrega, fecha_entrega: e.target.value })}
                    />
                  </div>
                </div>
                <div className="mt-3">
                  <button
                    className="bg-green-600 text-white px-4 py-2 rounded"
                    onClick={async () => {
                      try {
                        if (!entrega.remito_salida.trim()) { setErr("El remito es requerido para entregar."); return; }
                        await postEntregarIngreso(id, entrega);
                        await refreshIngreso();
                      } catch (e) {
                        setErr(e?.message || "No se pudo marcar como entregado");
                      }
                    }}
                  >
                    Marcar ENTREGADO
                  </button>
                </div>
              </>
            ) : (
              <>
                {!editEntrega && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                    <div>
                      <div className="text-gray-600">Remito salida</div>
                      <div className="font-medium">{data.remito_salida || "-"}</div>
                    </div>
                    <div>
                      <div className="text-gray-600">Factura</div>
                      <div className="font-medium">{data.factura_numero || "-"}</div>
                    </div>
                    <div>
                      <div className="text-gray-600">Fecha entrega</div>
                      <div className="font-medium">{data.fecha_entrega ? formatDateTimeHelper(data.fecha_entrega) : "-"}</div>
                    </div>
                  </div>
                )}
                {canEditEntrega && !editEntrega && (
                  <div className="mt-3">
                    <button className="px-3 py-2 border rounded" type="button" onClick={() => setEditEntrega(true)}>
                      Editar entrega
                    </button>
                  </div>
                )}
                {canEditEntrega && editEntrega && (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div>
                        <label className="text-sm">Remito salida</label>
                        <input
                          className="border rounded p-2 w-full"
                          value={entrega.remito_salida}
                          onChange={(e) => setEntrega({ ...entrega, remito_salida: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="text-sm">Factura</label>
                        <input
                          className="border rounded p-2 w-full"
                          value={entrega.factura_numero}
                          onChange={(e) => setEntrega({ ...entrega, factura_numero: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="text-sm">Fecha entrega</label>
                        <input
                          type="datetime-local"
                          className="border rounded p-2 w-full"
                          value={entrega.fecha_entrega}
                          onChange={(e) => setEntrega({ ...entrega, fecha_entrega: e.target.value })}
                        />
                      </div>
                    </div>
                    <div className="mt-3 flex gap-2">
                      <button
                        className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-60"
                        disabled={savingEntrega}
                        type="button"
                        onClick={async () => {
                          try {
                            setSavingEntrega(true);
                            const payload = {
                              remito_salida: (entrega.remito_salida || "").trim(),
                              factura_numero: (entrega.factura_numero || "").trim(),
                              fecha_entrega: entrega.fecha_entrega || null,
                            };
                            await patchIngreso(id, payload);
                            await refreshIngreso();
                            setEditEntrega(false);
                            setErr("");
                          } catch (e) {
                            setErr(e?.message || "No se pudo guardar entrega");
                          } finally {
                            setSavingEntrega(false);
                          }
                        }}
                      >
                        Guardar
                      </button>
                      <button className="px-3 py-2 border rounded" type="button" onClick={() => { setEditEntrega(false); setEntrega({
                        remito_salida: data?.remito_salida || "",
                        factura_numero: data?.factura_numero || "",
                        fecha_entrega: toDatetimeLocalStr(data?.fecha_entrega),
                      }); }}>
                        Cancelar
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          {/* Alquiler */}
          <div className="border rounded p-4 mt-4">
            <h2 className="font-semibold mb-2">Alquiler</h2>
            <Row label="¿Se alquiló?">
              <input
                type="checkbox"
                checked={!!data.alquilado}
                onChange={(e) => patch({ alquilado: e.target.checked })}
              />
            </Row>
            <Row label="A quién">
              <input
                className="border rounded p-1 w-80"
                value={data.alquiler_a || ""}
                onChange={(e) => patch({ alquiler_a: e.target.value })}
              />
            </Row>
            <Row label="Remito">
              <input
                className="border rounded p-1 w-60"
                value={data.alquiler_remito || ""}
                onChange={(e) => patch({ alquiler_remito: e.target.value })}
              />
            </Row>
            <Row label="Fecha">
              <input
                type="date"
                className="border rounded p-1"
                value={(data.alquiler_fecha || "").slice(0, 10)}
                onChange={(e) => patch({ alquiler_fecha: e.target.value || null })}
              />
            </Row>
          </div>
        </>
      )}

      {/* DIAGN├ôSTICO */}
      {tab === "diagnostico" && (
        <div className="border rounded p-4">
          {!canEditDiag && (
            <div className="bg-yellow-50 border border-yellow-300 text-yellow-800 p-2 rounded mb-3">
              No tenés asignado este equipo. Podés ver, pero no editar. Pedí asignación a tu supervisor.
            </div>
          )}
          {/* Contexto útil para diagnosticar */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
            <div className="border rounded p-3 bg-gray-50">
              <div className="text-xs uppercase text-gray-500 mb-1">Informe preliminar</div>
              <div className="whitespace-pre-wrap">{data.informe_preliminar || "-"}</div>
            </div>
            <div className="border rounded p-3 bg-gray-50">
              <div className="text-xs uppercase text-gray-500 mb-1">Accesorios</div>
              <div>
                {Array.isArray(data.accesorios_items) && data.accesorios_items.length > 0 ? (
                  <ul className="list-disc list-inside text-sm">
                    {data.accesorios_items.map((it) => (
                      <li key={it.id} className="flex items-center justify-between gap-2">
                        <span>
                          {it.accesorio_nombre}
                          {it.referencia ? ` (ref: ${it.referencia})` : ""}
                        </span>
                        {canEditAcc && (
                          <button
                            className="text-red-600 text-xs"
                            onClick={() => removeAccesorio(it.id)}
                            disabled={deletingAccId === it.id}
                            type="button"
                          >
                            {deletingAccId === it.id ? "quitando..." : "quitar"}
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="whitespace-pre-wrap">{data.accesorios || "-"}</div>
                )}
              </div>

              {canEditAcc && (
                <div className="mt-3 border-t pt-3">
                  <div className="text-xs uppercase text-gray-500 mb-2">Agregar accesorio</div>
                  <div className="flex flex-wrap items-end gap-2">
                    <input
                      className="border rounded p-2 min-w-[240px]"
                      list="accesorios_catalogo"
                      placeholder="Descripción (escribí y elegí de la lista)"
                      value={nuevoAcc.descripcion}
                      onChange={(e)=> setNuevoAcc(s => ({ ...s, descripcion: e.target.value }))}
                    />
                    <datalist id="accesorios_catalogo">
                      {accesCatalogo.map(a => (
                        <option key={a.id} value={a.nombre} />
                      ))}
                    </datalist>
                    <input
                      className="border rounded p-2 w-40"
                      placeholder="N° referencia (opcional)"
                      value={nuevoAcc.referencia}
                      onChange={(e)=> setNuevoAcc(s => ({ ...s, referencia: e.target.value }))}
                    />
                      {/* Solo referencia adicional; sin campo de descripción extra */}
                    <button
                      className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
                      onClick={addAccesorio}
                      disabled={addingAcc || !(nuevoAcc.descripcion || '').trim()}
                      type="button"
                    >
                      {addingAcc ? "agregando..." : "agregar"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
          <h2 className="font-semibold mb-2">Descripción del problema (diagnóstico)</h2>

          <div className="flex flex-wrap items-end gap-3 mb-3">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Fecha de servicio</label>
              <input
                type="datetime-local"
                className="border rounded p-2"
                value={fechaServStr}
                onChange={(e) => {
                  // cierra el datepicker nativo (incluye click en "hoy")
                  const el = e.currentTarget;
                  const v = el.value;
                  setFechaServStr(v);
                  if (v) setTimeout(() => el.blur(), 0);
                }}
                max={maxLocalNow}
                placeholder="YYYY-MM-DD HH:mm"
                disabled={!canEditDiag}
              />
            </div>

            <div className="ml-auto flex items-end gap-2">
              {/* Resolución */}
              {canResolve && (
                <>
                  <div className="min-w-[260px]">
                    <label className="block text-sm text-gray-600 mb-1">Resolución de reparación</label>
                    <select
                      className="border rounded p-2 w-full"
                      value={resolucion}
                      onChange={(e) => setResolucion(e.target.value)}
                      disabled={data?.estado === "entregado"}
                    >
                      <option value="">-- Seleccionar --</option>
                      {RESOLUCION_OPTIONS.map(opt => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
                    </select>
                  </div>

                  <button
                    className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
                    disabled={savingResol || !resolucion}
                    onClick={saveResolucion}
                    type="button"
                  >
                    {savingResol ? "Guardando..." : "Guardar resolución"}
                  </button>
                </>
              )}

              {/* Marcar reparado */}
              {canMarkReparado && !["reparado","liberado","entregado"].includes(data?.estado) && (
                <button
                  className="bg-emerald-600 text-white px-3 py-2 rounded"
                  onClick={async () => {
                    try {
                      await postMarcarReparado(id);
                      await refreshIngreso();
                      setShowReparadoToast(true);
                      setTimeout(() => setShowReparadoToast(false), 2000);
                    } catch (e) {
                      setErr(e?.message || "No se pudo marcar como reparado");
                    }
                  }}
                  type="button"
                >
                  Marcar reparado
                </button>
              )}
            </div>
          </div>

          <textarea
            className="w-full border rounded p-2 min-h-[180px]"
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
            placeholder="Ej.: Ingreso de agua en turbina; placa de control con óxido; válvula X no abre..."
            disabled={!canEditDiag}
          />

          <div className="border rounded p-4 mt-4">
            <h2 className="font-semibold mb-2">Trabajos realizados</h2>
            <textarea
              className="w-full border rounded p-2 min-h-[200px]"
              value={trabajos}
              onChange={(e) => setTrabajos(e.target.value)}
              placeholder="Ej.: Cambio de turbina; limpieza y secado; resoldado de conector; calibración; pruebas OKÔÇª"
              disabled={!canEditDiag}
            />
            <div className="mt-2 flex items-center gap-2">
              <button
                className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
                onClick={saveDiagYReparacion}
                disabled={savingAll || !canEditDiag}
                aria-busy={savingAll ? "true" : "false"}
                type="button"
              >
                {savingAll ? "Guardando..." : "Guardar"}
              </button>
            </div>
          </div>

          <IngresoPhotos ingresoId={Number(id)} canManage={canManagePhotos} />

          <Row label="Faja de garantía N°">
            <input
              className="border rounded p-1 w-60"
              value={data.faja_garantia || ""}
              onChange={(e) => patch({ faja_garantia: e.target.value })}
            />
          </Row>
        </div>
      )}

      {/* PRESUPUESTO */}
      {tab === "presupuesto" && (
        <div className="border rounded p-4">
          <h2 className="font-semibold mb-3">Presupuesto</h2>

          {qErr && <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-3">{qErr}</div>}

          <div className="flex gap-3 items-end mb-4">
            <label className="block">
              <div className="text-sm text-gray-600">Autorizado por</div>
              <input className="border rounded p-2" value={autorizadoPor} onChange={(e)=>setAutorizadoPor(e.target.value)} />
            </label>
            <label className="block">
              <div className="text-sm text-gray-600">Forma de pago</div>
              <input className="border rounded p-2" value={formaPago} onChange={(e)=>setFormaPago(e.target.value)} />
            </label>
            {hasAnyRole(user, [ROLES.JEFE, ROLES.JEFE_VEEDOR]) && data.presupuesto_estado !== "presupuestado" && (
              <button className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60" onClick={emitirPresupuesto} disabled={emitiendo}>
                {emitiendo ? "Emitiendo..." : "Emitir presupuesto"}
              </button>
            )}
            {["presupuestado","aprobado"].includes(data.presupuesto_estado) && (
              <button className="underline text-blue-700" onClick={abrirPdf} type="button">Ver/Descargar PDF</button>
            )}
            {hasAnyRole(user, [ROLES.JEFE, ROLES.JEFE_VEEDOR]) && data.presupuesto_estado === "presupuestado" && (
              <button className="bg-emerald-600 text-white px-3 py-2 rounded disabled:opacity-60" onClick={aprobarPresupuesto} disabled={aprobando} type="button">
                {aprobando ? "Aprobando..." : "Aprobar presupuesto"}
              </button>
            )}
            {hasAnyRole(user, [ROLES.JEFE, ROLES.JEFE_VEEDOR]) && data.presupuesto_estado === "presupuestado" && (
              <button className="bg-red-600 text-white px-3 py-2 rounded disabled:opacity-60" onClick={anularPresupuesto} disabled={anulando} type="button">
                {anulando ? "Anulando..." : "Anular presupuesto"}
              </button>
            )}
          </div>

          {qLoading || !quote ? (
            <div>Cargando...</div>
          ) : (
            <>
              {isAprobado && <div className="mb-3 text-sm text-emerald-700">Presupuesto aprobado — los ítems y valores ya no son editables.</div>}

              {/* Repuestos */}
              <h3 className="font-medium mb-2">Repuestos</h3>
              <table className="min-w-full text-sm mb-3">
                <thead>
                  <tr className="text-left">
                    <th className="p-2 w-28">IdRepuesto</th>
                    <th className="p-2">Descripción</th>
                    <th className="p-2 w-24">Cantidad</th>
                    <th className="p-2 w-36">Precio unit.</th>
                    <th className="p-2 w-36 text-right">Subtotal</th>
                    <th className="p-2 w-20"></th>
                  </tr>
                </thead>
                <tbody>
                  {quote.items.filter(it => it.tipo === "repuesto").map((it) => (
                    <tr key={it.id} className="border-t">
                      <td className="p-2">
                        <input
                          className="border rounded p-1 w-24"
                          value={it.repuesto_id ?? ""}
                          onChange={(e) => updateItem(it, { repuesto_id: e.target.value ? Number(e.target.value) : null })}
                          disabled={isAprobado}
                        />
                      </td>
                      <td className="p-2">
                        <input
                          className="border rounded p-1 w-full"
                          value={it.descripcion || ""}
                          onChange={(e) => updateItem(it, { descripcion: e.target.value })}
                          disabled={isAprobado}
                        />
                      </td>
                      <td className="p-2">
                        <input
                          type="number" step="0.01" min="0"
                          className="border rounded p-1 w-24 text-right"
                          value={it.qty}
                          onChange={(e) => updateItem(it, { qty: Number(e.target.value || 0) })}
                          disabled={isAprobado}
                        />
                      </td>
                      <td className="p-2">
                        <input
                          type="number" step="0.01"
                          className="border rounded p-1 w-32 text-right"
                          value={it.precio_u}
                          onChange={(e) => updateItem(it, { precio_u: Number(e.target.value || 0) })}
                          disabled={isAprobado}
                        />
                      </td>
                      <td className="p-2 text-right">{money(it.subtotal)}</td>
                      <td className="p-2">
                        <button className="text-red-600 hover:underline" onClick={() => handleRemoveItem(it)} type="button" disabled={isAprobado}>
                          borrar
                        </button>
                      </td>
                    </tr>
                  ))}

                  {/* Alta rápida */}
                  <tr className="border-t bg-gray-50">
                    <td className="p-2">
                      <input className="border rounded p-1 w-24" placeholder="(opcional)"
                        value={nuevoRep.repuesto_id} onChange={(e) => setNuevoRep(s => ({ ...s, repuesto_id: e.target.value }))} disabled={isAprobado} />
                    </td>
                    <td className="p-2">
                      <input className="border rounded p-1 w-full" placeholder="Descripción del repuesto"
                        value={nuevoRep.descripcion} onChange={(e) => setNuevoRep(s => ({ ...s, descripcion: e.target.value }))} disabled={isAprobado} />
                    </td>
                    <td className="p-2">
                      <input type="number" step="0.01" min="0" className="border rounded p-1 w-24 text-right"
                        value={nuevoRep.qty} onChange={(e) => setNuevoRep(s => ({ ...s, qty: e.target.value }))} disabled={isAprobado} />
                    </td>
                    <td className="p-2">
                      <input type="number" step="0.01" className="border rounded p-1 w-32 text-right" placeholder="0.00"
                        value={nuevoRep.precio_u} onChange={(e) => setNuevoRep(s => ({ ...s, precio_u: e.target.value }))} disabled={isAprobado} />
                    </td>
                    <td className="p-2"></td>
                    <td className="p-2">
                      <button className="bg-blue-600 text-white px-2 py-1 rounded" onClick={addRepuesto} type="button" disabled={isAprobado}>
                        agregar
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>

              {/* Mano de obra */}
              <div className="flex items-end gap-3 mb-4">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Mano de obra</label>
                  <input
                    type="number" step="0.01" min="0"
                    className="border rounded p-2 w-48 text-right"
                    value={manoObraStr}
                    onChange={(e) => setManoObraStr(e.target.value)}
                    disabled={isAprobado}
                  />
                </div>
                <button className="bg-blue-600 text-white px-3 py-2 rounded" onClick={saveManoObra} type="button" disabled={isAprobado}>
                  Guardar
                </button>
              </div>

              {/* Totales */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <div className="border rounded p-3">
                  <div className="text-gray-600 text-sm">Total repuestos</div>
                  <div className="text-lg font-semibold">{money(quote.tot_repuestos)}</div>
                </div>
                <div className="border rounded p-3">
                  <div className="text-gray-600 text-sm">Mano de obra</div>
                  <div className="text-lg font-semibold">{money(quote.mano_obra)}</div>
                </div>
                <div className="border rounded p-3">
                  <div className="text-gray-600 text-sm">Subtotal</div>
                  <div className="text-lg font-semibold">{money(quote.subtotal)}</div>
                </div>
                <div className="border rounded p-3">
                  <div className="text-gray-600 text-sm">IVA 21%</div>
                  <div className="text-lg font-semibold">{money(quote.iva_21)}</div>
                </div>
                <div className="border rounded p-3">
                  <div className="text-gray-600 text-sm">Costo cliente (con IVA)</div>
                  <div className="text-xl font-bold">{money(quote.total)}</div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* DERIVACIONES */}
      {tab === "derivaciones" && (
        <div className="border rounded p-4">
          <div className="flex items-center gap-3 mb-3">
            <h2 className="font-semibold">Derivaciones</h2>
            <div className="ml-auto flex items-center gap-2">
              <Link to={`/ingresos/${id}/derivar`} className="bg-neutral-800 text-white px-3 py-2 rounded">Derivar a externo</Link>
              {/* Botón Devuelto: aplicar a la última derivación sin fecha_entrega */}
              {Array.isArray(derivs) && derivs.find(d => !d.fecha_entrega) && (
                <>
                  <input
                    type="date"
                    className="border rounded p-2"
                    value={fechaDevStr}
                    onChange={(e) => setFechaDevStr(e.target.value)}
                    aria-label="Fecha de devolución"
                  />
                  <button
                    className="bg-green-700 text-white px-3 py-2 rounded disabled:opacity-60"
                    disabled={savingDev}
                    onClick={async () => {
                      try {
                        const abierta = derivs.find(d => !d.fecha_entrega);
                        if (!abierta) return;
                        setSavingDev(true);
                        await postDerivacionDevuelto(id, abierta.id, { fecha_entrega: fechaDevStr || null });
                        // refrescar listado
                        try { setDerivs(await getDerivacionesPorIngreso(id)); } catch (_) {}
                      } catch (e) {
                        setErr(e?.message || "No se pudo marcar como devuelto");
                      } finally {
                        setSavingDev(false);
                      }
                    }}
                    type="button"
                  >
                    {savingDev ? "Guardando..." : "Devuelto"}
                  </button>
                </>
              )}
            </div>
          </div>
          {(!derivs || derivs.length === 0) ? (
            <div className="text-sm text-gray-500">No hay derivaciones.</div>
          ) : (
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left">
                  <th className="p-2">Proveedor</th>
                  <th className="p-2">Remito</th>
                  <th className="p-2">Fecha derivación</th>
                  <th className="p-2">Fecha entrega</th>
                  <th className="p-2">Estado</th>
                  <th className="p-2">Comentarios</th>
                </tr>
              </thead>
              <tbody>
                {derivs.map((d) => (
                  <tr key={d.id} className="border-t">
                    <td className="p-2">{d.proveedor || "-"}</td>
                    <td className="p-2">{d.remit_deriv || "-"}</td>
                    <td className="p-2 whitespace-nowrap">{d.fecha_deriv ? formatDateTimeHelper(d.fecha_deriv) : "-"}</td>
                    <td className="p-2 whitespace-nowrap">{d.fecha_entrega ? formatDateTimeHelper(d.fecha_entrega) : "-"}</td>
                    <td className="p-2">{d.estado || "-"}</td>
                    <td className="p-2">{d.comentarios || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {relatedOpen && (
        <div
          className="fixed inset-0 z-30 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          onClick={() => setRelatedOpen(false)}
        >
          <div
            className="bg-white rounded shadow-xl max-w-4xl w-full max-h-[80vh] overflow-y-auto p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 mb-3">
              <div>
                <h2 className="text-lg font-semibold">Ingresos del equipo</h2>
                <div className="text-sm text-gray-600">Número de serie: <span className="font-semibold">{numeroSerie || "-"}</span></div>
              </div>
              <button
                type="button"
                className="text-sm text-gray-500 hover:text-gray-900"
                onClick={() => setRelatedOpen(false)}
                aria-label="Cerrar historial de ingresos"
              >
                Cerrar
              </button>
            </div>
            {relatedLoading ? (
              <div className="text-sm text-gray-500">Cargando ingresos relacionados...</div>
            ) : relatedErr ? (
              <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded">{relatedErr}</div>
            ) : relatedRows.length === 0 ? (
              <div className="text-sm text-gray-500">No se encontraron otros ingresos con este número de serie.</div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="text-left">
                        <th className="p-2">OS</th>
                        <th className="p-2">Estado</th>
                        <th className="p-2">Presupuesto</th>
                        <th className="p-2">Fecha ingreso</th>
                        <th className="p-2">Ubicación</th>
                      </tr>
                    </thead>
                    <tbody>
                      {relatedRows.map((r) => {
                        const ingresoId = r?.id ?? r?.ingreso_id;
                        const isCurrent = ingresoId === data.id;
                        if (!ingresoId) return null;
                        return (
                          <tr
                            key={ingresoId}
                            className={`border-t hover:bg-gray-50 cursor-pointer ${isCurrent ? 'bg-blue-50' : ''}`}
                            onClick={() => {
                              setRelatedOpen(false);
                              if (ingresoId) navigate(`/ingresos/${ingresoId}`);
                            }}
                          >
                            <td className="p-2 underline">{formatOSHelper(ingresoId)}</td>
                            <td className="p-2 capitalize">{r?.estado || '-'}</td>
                            <td className="p-2 capitalize">{r?.presupuesto_estado || '-'}</td>
                            <td className="p-2 whitespace-nowrap">{formatDateTimeHelper(resolveFechaIngreso(r))}</td>
                            <td className="p-2">{r?.ubicacion_nombre || '-'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="text-xs text-gray-500 mt-2">Mostrando {relatedRows.length} ingreso(s).</div>
              </>
            )}
          </div>
        </div>
      )}

      {showDiagToast && (
        <div className="fixed right-4 top-4 bg-emerald-600 text-white px-4 py-2 rounded shadow-lg" role="status" aria-live="polite">
          Diagnosticado
        </div>
      )}
      {showResolToast && (
        <div className="fixed right-4 top-16 bg-blue-600 text-white px-4 py-2 rounded shadow-lg" role="status" aria-live="polite">
          Resolución guardada
        </div>
      )}
      {showReparadoToast && (
        <div className="fixed right-4 top-4 bg-emerald-600 text-white px-4 py-2 rounded shadow-lg" role="status">
          Marcado como reparado
        </div>
      )}

      {/* HISTORIAL */}
      {tab === "historial" && canSeeHistory && (
        <div className="border rounded p-4">
          <h2 className="font-semibold mb-2">Historial de cambios</h2>
          {hErr && <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-3">{hErr}</div>}
          {hLoading ? (
            <div className="text-sm text-gray-500">Cargando...</div>
          ) : (
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left">
                  <th className="p-2">Fecha</th>
                  <th className="p-2">Usuario</th>
                  <th className="p-2">Rol</th>
                  <th className="p-2">Entidad</th>
                  <th className="p-2">Campo</th>
                  <th className="p-2">Antes</th>
                  <th className="p-2">Despues</th>
                </tr>
              </thead>
              <tbody>
                {(hist || []).length === 0 ? (
                  <tr><td className="p-2 text-gray-500" colSpan={7}>No hay cambios registrados.</td></tr>
                ) : (
                  hist.map((r, idx) => (
                    <tr key={idx} className="border-t">
                      <td className="p-2 whitespace-nowrap">{formatDateTimeHelper(r.ts)}</td>
                      <td className="p-2">{r.user_id || '-'}</td>
                      <td className="p-2 whitespace-nowrap">{r.user_role || '-'}</td>
                      <td className="p-2">{r.table_name}</td>
                      <td className="p-2">{r.column_name}</td>
                      <td className="p-2">{r.old_value || '-'}</td>
                      <td className="p-2">{r.new_value || '-'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Botón flotante para edición básica (solo Jefe/Jefe_veedor) */}
      {canEditBasics && (
        <div className="fixed bottom-4 right-4 z-20 flex gap-2">
          {!editBasics ? (
            <button
              className="text-xs px-3 py-2 rounded shadow bg-neutral-800 text-white hover:bg-neutral-700"
              onClick={startEditBasics}
              type="button"
              title="Habilitar edición de datos"
            >
              Editar datos
            </button>
          ) : (
            <>
              <button
                className="text-xs px-3 py-2 rounded shadow bg-amber-600 text-white disabled:opacity-60"
                onClick={saveEditBasics}
                disabled={savingBasics}
                type="button"
                title="Cerrar edición y guardar cambios"
              >
                {savingBasics ? "Guardando..." : "Cerrar edición"}
              </button>
              <button
                className="text-xs px-3 py-2 rounded shadow bg-gray-200 hover:bg-gray-300"
                onClick={() => { setEditBasics(false); setFormBasics(null); }}
                type="button"
                title="Cancelar edición"
              >
                Cancelar
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}












