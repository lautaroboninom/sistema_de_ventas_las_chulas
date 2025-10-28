// web/src/pages/ServiceSheet.jsx (container)
import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  getIngreso, getUbicaciones, patchIngreso,
  getTecnicos,
  getAccesoriosCatalogo,
  getIngresoHistorial,
  getGeneralEquipos,
} from "../lib/api";
import { getMarcas, getModelosByBrand, getVariantesPorMarca, checkGarantiaFabrica, patchModeloTipoEquipo } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import {
  formatOS as formatOSHelper,
  formatDateTime as formatDateTimeHelper,
  resolveFechaIngreso,
  resolveFechaCreacion,
} from "../lib/ui-helpers";
import { canActAsTech, canRelease, hasAnyRole, ROLES } from "../lib/authz";
import ArchivosTab from "./ServiceSheet/tabs/ArchivosTab";
import HistorialTab from "./ServiceSheet/tabs/HistorialTab";
import PresupuestoTab from "./ServiceSheet/tabs/PresupuestoTab";
import DiagnosticoTab from "./ServiceSheet/tabs/DiagnosticoTab";
import PrincipalTab from "./ServiceSheet/tabs/PrincipalTab";
import DerivacionesTab from "./ServiceSheet/tabs/DerivacionesTab";

const Tabs = ({ value, onChange, items, extraRight }) => (
  <div className="border-b mb-4 flex items-center">
    <div className="flex gap-2">
      {items.map((it) => (
        <button
          key={it.value}
          className={`px-3 py-2 rounded-t ${value === it.value ? "bg-white border border-b-0" : "text-gray-600 hover:text-black"}`}
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
  const { user } = useAuth();
  const navigate = useNavigate();

  const actAsTech = canActAsTech(user);
  const release = canRelease(user);
  const canEditBasics = hasAnyRole(user, [ROLES.JEFE, ROLES.JEFE_VEEDOR, ROLES.ADMIN]);
  const canAssignTecnico = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR]);
  const canManagePresupuesto = hasAnyRole(user, [ROLES.JEFE, ROLES.JEFE_VEEDOR]);
  const canSeeHistory = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR, ROLES.TECNICO]);

  // pestañas
  const [tab, setTab] = useState("principal");
  useEffect(() => {
    try {
      const t = location?.state?.tab;
      if (t && ["principal","diagnostico","presupuesto","derivaciones","historial"].includes(t)) setTab(t);
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location?.state]);

  // Leer tab/tecnico_id desde el querystring (enlaces del mail)
  useEffect(() => {
    try {
      const search = location?.search || "";
      if (!search) return;
      const sp = new URLSearchParams(search);
      const t = (sp.get("tab") || "").trim();
      if (t && ["principal","diagnostico","presupuesto","derivaciones","historial"].includes(t)) {
        setTab(t);
      }
      if (canAssignTecnico) {
        const tid = (sp.get("tecnico_id") || "").trim();
        if (tid) {
          const n = Number(tid);
          if (!Number.isNaN(n)) { setTecnicoIdQS(n); setTecnicoId(n); }
        }
      }
    } catch {}
  }, [location?.search, canAssignTecnico]);

  // datos generales
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  // entrega
  const [entrega, setEntrega] = useState({ remito_salida: "", factura_numero: "", fecha_entrega: "" });
  const canEditEntrega = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR, ROLES.RECEPCION]);
  const [editEntrega, setEditEntrega] = useState(false);
  const [savingEntrega, setSavingEntrega] = useState(false);

  // ubicaciones
  const [ubicaciones, setUbicaciones] = useState([]);
  const [ubicacionId, setUbicacionId] = useState("");

  // tcnicos
  const [tecnicos, setTecnicos] = useState([]);
  const [tecnicoId, setTecnicoId] = useState(null);
  const [tecnicoIdQS, setTecnicoIdQS] = useState(null);

  // accesorios
  const [accesCatalogo, setAccesCatalogo] = useState([]);
  const [nuevoAcc, setNuevoAcc] = useState({ descripcion: "", referencia: "" });

  // Diagnóstico (texto/fecha) mantenidos en el contenedor
  const [descripcion, setDescripcion] = useState("");
  const [trabajos, setTrabajos] = useState("");
  const [resolucion, setResolucion] = useState("");
  const [fechaServStr, setFechaServStr] = useState("");
  const [showReparadoToast, setShowReparadoToast] = useState(false);
  const [savingDiag, setSavingDiag] = useState(false);
  const canResolve = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR]);
  const toDatetimeLocalStr = (isoOrDate) => {
    if (!isoOrDate) return "";
    const d = isoOrDate instanceof Date ? isoOrDate : new Date(isoOrDate);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const maxLocalNow = toDatetimeLocalStr(new Date());

  // historial de cambios
  const [hist, setHist] = useState([]);
  const [hLoading, setHLoading] = useState(false);
  const [hErr, setHErr] = useState("");

  // ingresos relacionados por N/S
  const [relatedOpen, setRelatedOpen] = useState(false);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [relatedErr, setRelatedErr] = useState("");
  const [relatedRows, setRelatedRows] = useState([]);

  // Catlogo de Equipo (para editar Marca/Modelo/Variante)
  const [marcas, setMarcas] = useState([]);
  const [marcaIdSel, setMarcaIdSel] = useState(null);
  const [modelos, setModelos] = useState([]);
  const [modeloIdSel, setModeloIdSel] = useState(null);
  const [tipoSel, setTipoSel] = useState("");
  const [varSugeridas, setVarSugeridas] = useState([]);

  // edición bsica
  const [editBasics, setEditBasics] = useState(false);
  const [formBasics, setFormBasics] = useState(null);
  const [savingBasics, setSavingBasics] = useState(false);

  function money(n) {
    if (n == null) return "-";
    const num = Number(n);
    if (Number.isNaN(num)) return String(n);
    return num.toLocaleString("es-AR", { style: "currency", currency: "ARS", minimumFractionDigits: 2 });
  }

  // PATCH helper
  async function patch(fields) {
    try {
      await patchIngreso(id, fields);
      setData((d) => ({ ...d, ...fields }));
      setErr("");
    } catch (e) {
      setErr(e?.message || "No se pudo guardar");
    }
  }

  async function refreshIngreso(params) {
    try {
      const ing = await getIngreso(id, params || undefined);
      setData(ing);
    } catch (e) {
      setErr(e?.message || "No se pudo refrescar el ingreso");
    }
  }

  // cargar historial solo cuando se selecciona la pestaña
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

  // limpiar modal relacionados al cambiar id
  useEffect(() => {
    setRelatedOpen(false);
    setRelatedRows([]);
    setRelatedErr("");
    setRelatedLoading(false);
  }, [id]);

  // cargar relacionados cuando se abre el modal
  useEffect(() => {
    if (!relatedOpen) return;
    const serie = (data?.numero_serie || "").trim();
    if (!serie) {
      setRelatedErr("Este equipo no tiene Número de serie registrado.");
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
        if (!cancelled) setRelatedLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [relatedOpen, data?.numero_serie, id]);

  // close modal with Escape
  useEffect(() => {
    if (!relatedOpen) return;
    const handler = (ev) => { if (ev.key === "Escape") setRelatedOpen(false); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [relatedOpen]);

  // Activar edición bsica
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
      comentarios: data?.comentarios || "",
      garantia_reparacion: !!data?.garantia_reparacion,
      equipo_variante: data?.equipo_variante || "",
      garantia: !!data?.garantia,
    });
    setEditBasics(true);
    (async () => {
      try {
        if (!marcas.length) { try { setMarcas(await getMarcas()); } catch {} }
        const norm = (s) => (s || "").toString().trim().toLowerCase();
        const curMarcaName = norm(data?.marca);
        let curMarca = (marcas.length ? marcas : await getMarcas()).find((m) => norm(m?.nombre) === curMarcaName);
        const marcaId = curMarca?.id ?? null;
        setMarcaIdSel(marcaId);
        const tipoActual = (data?.tipo_equipo_nombre || data?.tipo_equipo || "").toString().trim().toUpperCase();
        setTipoSel(tipoActual);
        if (marcaId) {
          try {
            const list = await getModelosByBrand(marcaId);
            setModelos(list || []);
            const curModeloName = norm(data?.modelo);
            const md = (list || []).find((x) => norm(x?.nombre) === curModeloName);
            setModeloIdSel(md?.id ?? null);
          } catch { setModelos([]); setModeloIdSel(null); }
          try { setVarSugeridas(await getVariantesPorMarca(marcaId)); } catch { setVarSugeridas([]); }
        } else {
          setModelos([]); setModeloIdSel(null); setVarSugeridas([]);
        }
      } catch {}
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
    if (cmp(formBasics.informe_preliminar, data?.informe_preliminar)) diff.informe_preliminar = formBasics.informe_preliminar;
    if (cmp(formBasics.comentarios, data?.comentarios)) diff.comentarios = formBasics.comentarios;
    if ((formBasics.garantia_reparacion ? 1 : 0) !== (data?.garantia_reparacion ? 1 : 0)) diff.garantia_reparacion = !!formBasics.garantia_reparacion;
    try {
      const norm = (s) => (s || "").toString().trim().toLowerCase();
      const selMarca = marcas.find((m) => String(m.id) === String(marcaIdSel));
      if (selMarca && norm(selMarca?.nombre) !== norm(data?.marca)) diff.marca_id = Number(selMarca.id);
      const selModelo = modelos.find((m) => String(m.id) === String(modeloIdSel));
      if (selModelo && norm(selModelo?.nombre) !== norm(data?.modelo)) diff.modelo_id = Number(selModelo.id);
      const varNew = (formBasics?.equipo_variante || "").trim();
      const varOld = (data?.equipo_variante || "").trim();
      if (varNew !== varOld) diff.equipo_variante = varNew || null;
      const garNew = !!formBasics?.garantia;
      const garOld = !!data?.garantia;
      if (garNew !== garOld) diff.garantia = garNew;
    } catch {}
    try {
      setSavingBasics(true);
      if (Object.keys(diff).length > 0) {
        await patch(diff);
      }

      // Persistir Tipo de equipo en el modelo asociado si cambi
      try {
        const tipoNuevo = (tipoSel || "").toString().trim();
        const tipoActual = (data?.tipo_equipo_nombre || data?.tipo_equipo || "").toString().trim();
        // Determinar modelo/marca efectivos (nuevo seleccionado o actuales)
        const selModelo = modelos.find((m) => String(m.id) === String(modeloIdSel));
        const modeloIdEfectivo = selModelo ? Number(selModelo.id) : (data?.model_id != null ? Number(data.model_id) : null);
        const marcaIdEfectivo = marcaIdSel != null ? Number(marcaIdSel) : (data?.marca_id != null ? Number(data.marca_id) : null);
        if (modeloIdEfectivo && marcaIdEfectivo && (tipoNuevo || tipoActual) && tipoNuevo.toUpperCase() !== (tipoActual || "").toUpperCase()) {
          await patchModeloTipoEquipo(marcaIdEfectivo, modeloIdEfectivo, { tipo_equipo: tipoNuevo });
        }
      } catch {}

      // Refrescar si hubo cambios relevantes o si pudo haber cambiado el tipo
      if (
        Object.keys(diff).length > 0 ||
        (tipoSel || "").toString().trim().toUpperCase() !== (data?.tipo_equipo || "").toString().trim().toUpperCase()
      ) {
        await refreshIngreso();
      }
      setEditBasics(false);
      setFormBasics(null);
    } finally {
      setSavingBasics(false);
    }
  }

  // cargar catlogos base
  useEffect(() => { (async () => { try { setAccesCatalogo(await getAccesoriosCatalogo()); } catch {} })(); }, []);
  useEffect(() => { (async () => { try { setMarcas(await getMarcas()); } catch {} })(); }, []);
  useEffect(() => {
    if (!editBasics) return;
    if (!marcaIdSel) { setModelos([]); setModeloIdSel(null); setVarSugeridas([]); return; }
    (async () => {
      try { setModelos(await getModelosByBrand(marcaIdSel) || []); } catch { setModelos([]); }
      try { setVarSugeridas(await getVariantesPorMarca(marcaIdSel)); } catch { setVarSugeridas([]); }
      setModeloIdSel(null);
    })();
  }, [editBasics, marcaIdSel]);
  useEffect(() => {
    if (!editBasics) return;
    const ns = (formBasics?.numero_serie || "").trim();
    const selMarca = marcas.find((m) => String(m.id) === String(marcaIdSel));
    const marcaName = (selMarca?.nombre || data?.marca || "").toString();
    if (!ns) { if (formBasics) setFormBasics((s) => ({ ...(s || {}), garantia: false })); return; }
    const h = setTimeout(async () => {
      try {
        const r = await checkGarantiaFabrica(ns, marcaName);
        const enGarantia = !!r.within_365_days;
        setFormBasics((s) => ({ ...(s || {}), garantia: enGarantia }));
      } catch {}
    }, 400);
    return () => clearTimeout(h);
  }, [editBasics, formBasics?.numero_serie, marcaIdSel, marcas, data?.marca]);

  // carga general
  useEffect(() => {
    (async () => {
      try {
        const [ing, ubs] = await Promise.all([getIngreso(id, { strong: 1 }), getUbicaciones()]);
        setData(ing);
        setUbicaciones(ubs);
        setUbicacionId(ing?.ubicacion_id != null ? String(ing.ubicacion_id) : "");
        if (canAssignTecnico) {
          if (tecnicoIdQS != null) {
            setTecnicoId(Number(tecnicoIdQS));
          } else if (ing?.tecnico_solicitado_id && ing?.tecnico_solicitado_id !== (ing?.asignado_a ?? null)) {
            setTecnicoId(ing.tecnico_solicitado_id);
          } else {
            setTecnicoId(ing?.asignado_a ?? null);
          }
        } else {
          setTecnicoId(ing?.asignado_a ?? null);
        }
        // inicializar campos de tcnico
        setDescripcion(ing?.descripcion_problema ?? "");
        setTrabajos(ing?.trabajos_realizados ?? "");
        setResolucion(ing?.resolucion ?? "");
        setFechaServStr(toDatetimeLocalStr(ing?.fecha_servicio));
        // entrega
        setEntrega({
          remito_salida: ing?.remito_salida || "",
          factura_numero: ing?.factura_numero || "",
          fecha_entrega: toDatetimeLocalStr(ing?.fecha_entrega),
        });
        // tcnicos
        if (canAssignTecnico) { try { setTecnicos(await getTecnicos()); } catch {} } else { setTecnicos([]); }
      } catch (e) {
        setErr(e?.message || "Error cargando datos");
      }
    })();
  }, [id, canAssignTecnico, tecnicoIdQS]);

  // Auto-guardado de diagnóstico y trabajos (con debounce)
  useEffect(() => {
    if (!data) return;
    // respetar permisos de edición
    const isTech = user?.rol === ROLES.TECNICO;
    const userId = Number(user?.id || 0);
    const canEditDiagLocal = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR]) || (isTech && userId && data?.asignado_a === userId);
    if (!canEditDiagLocal) return;
    if (data?.estado === "entregado") return;

    const curDesc = data?.descripcion_problema ?? "";
    const curTrab = data?.trabajos_realizados ?? "";
    const curFechaStr = toDatetimeLocalStr(data?.fecha_servicio);

    const payload = {};
    if (descripcion !== curDesc) payload.descripcion_problema = descripcion;
    if (trabajos !== curTrab) payload.trabajos_realizados = trabajos;
    if ((fechaServStr || "") !== (curFechaStr || "")) payload.fecha_servicio = (fechaServStr || "").trim() || null;

    if (Object.keys(payload).length === 0) return;

    const h = setTimeout(async () => {
      try {
        setSavingDiag(true);
        await patch(payload);
        setErr("");
      } catch (e) {
        setErr(e?.message || "No se pudo guardar");
      } finally {
        setSavingDiag(false);
      }
    }, 700);

    return () => clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [descripcion, trabajos, fechaServStr, data, user]);

  if (!data) return <div className="p-4">Cargando...</div>;
  const isAprobado = data.presupuesto_estado === "aprobado";
  const numeroSerie = (data?.numero_serie || "").trim();
  const userId = Number(user?.id || 0);
  const canManagePhotos = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR]) || (user?.rol === ROLES.TECNICO && userId);
  const isTech = user?.rol === ROLES.TECNICO;
  const canEditDiag = hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR]) || (isTech && userId && data?.asignado_a === userId);
  const canMarkReparado = canEditDiag;

  return (
    <div className="max-w-none p-4">
      <button type="button" onClick={() => navigate(-1)} className="mb-3 inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800">
        Volver
      </button>
      <div className="grid grid-cols-2 items-center mb-2">
        <h1 className="text-2xl font-bold">
          Hoja de servicio - OS: {formatOSHelper(data, id)} - NS: {data?.numero_interno || data?.numero_serie}
        </h1>

        {numeroSerie && (
          <button
            type="button"
            onClick={() => setRelatedOpen(true)}
            className="justify-self-end text-xs px-2 py-1 rounded border border-blue-600 text-blue-600 hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            Ver ingresos del equipo
          </button>
        )}
      </div>
      <div className="text-sm text-gray-700 mb-3">{(data?.tipo_equipo_nombre || data?.tipo_equipo || "-").toString()} - {(data?.marca || "-").toString()} - {(data?.modelo || "-").toString()} {(data?.equipo_variante || "").toString()}</div>
      

      {err && <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-4">{err}</div>}
      {canSeeHistory && (
        <div className="-mt-8 -mb-3 text-right">
          <button className={`px-3 py-2 rounded-t ${tab === 'historial' ? 'bg-white border border-b-0' : 'text-gray-600 hover:text-black'}`} onClick={() => setTab('historial')} type="button">
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
      {tab === "archivos" && (<ArchivosTab id={id} canManagePhotos={canManagePhotos} />)}

      {/* PRINCIPAL */}
      {tab === "principal" && (
        <PrincipalTab
          id={id}
          data={data}
          release={release}
          numeroSerie={numeroSerie}
          editBasics={editBasics}
          formBasics={formBasics}
          setFormBasics={setFormBasics}
          marcas={marcas}
          marcaIdSel={marcaIdSel}
          setMarcaIdSel={setMarcaIdSel}
          modelos={modelos}
          modeloIdSel={modeloIdSel}
          setModeloIdSel={setModeloIdSel}
          tipoSel={tipoSel}
          setTipoSel={setTipoSel}
          variantes={varSugeridas}
          ubicaciones={ubicaciones}
          ubicacionId={ubicacionId}
          setUbicacionId={setUbicacionId}
          tecnicos={tecnicos}
          tecnicoId={tecnicoId}
          setTecnicoId={setTecnicoId}
          canAssignTecnico={canAssignTecnico}
          isTech={isTech}
          userId={userId}
          canEditEntrega={canEditEntrega}
          editEntrega={editEntrega}
          setEditEntrega={setEditEntrega}
          entrega={entrega}
          setEntrega={setEntrega}
          savingEntrega={savingEntrega}
          setSavingEntrega={setSavingEntrega}
          patch={patch}
          refreshIngreso={refreshIngreso}
          setErr={setErr}
          setRelatedOpen={setRelatedOpen}
          toDatetimeLocalStr={toDatetimeLocalStr}
        />
      )}

      {/* Diagnóstico */}
      {tab === "diagnostico" && (
        <DiagnosticoTab
          id={id}
          data={data}
          canEditAcc={hasAnyRole(user, [ROLES.JEFE, ROLES.ADMIN, ROLES.JEFE_VEEDOR, ROLES.TECNICO, ROLES.RECEPCION]) && data?.estado !== "entregado"}
          accesCatalogo={accesCatalogo}
          nuevoAcc={nuevoAcc}
          setNuevoAcc={setNuevoAcc}
          descripcion={descripcion}
          setDescripcion={setDescripcion}
          trabajos={trabajos}
          setTrabajos={setTrabajos}
          fechaServStr={fechaServStr}
          setFechaServStr={setFechaServStr}
          maxLocalNow={maxLocalNow}
          canResolve={canResolve}
          resolucion={resolucion}
          setResolucion ={setResolucion}
          actAsTech={actAsTech}
          canEditDiag={canEditDiag}
          canMarkReparado={canMarkReparado}
          patch={patch}
          setErr={setErr}
          refreshIngreso={refreshIngreso}
          setShowReparadoToast={setShowReparadoToast}
          savingDiag={savingDiag}
          canManagePhotos={canManagePhotos}
        />
      )}

      {/* PRESUPUESTO */}
      {tab === "presupuesto" && (
        <PresupuestoTab
          id={id}
          data={data}
          canManagePresupuesto={canManagePresupuesto}
          money={money}
          refreshIngreso={refreshIngreso}
          setErr={setErr}
        />
      )}

      {/* DERIVACIONES */}
      {tab === "derivaciones" && (
        <DerivacionesTab id={id} setErr={setErr} refreshIngreso={refreshIngreso} />
      )}

      {relatedOpen && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true" onClick={() => setRelatedOpen(false)}>
          <div className="bg-white rounded shadow-xl max-w-4xl w-full max-h-[80vh] overflow-y-auto p-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3 mb-3">
              <div>
                <h2 className="text-lg font-semibold">Ingresos del equipo</h2>
                <div className="text-sm text-gray-600">Número de serie: <span className="font-semibold">{numeroSerie || "-"}</span></div>
              </div>
              <button type="button" className="text-sm text-gray-500 hover:text-gray-900" onClick={() => setRelatedOpen(false)} aria-label="Cerrar historial de ingresos">Cerrar</button>
            </div>
            {relatedLoading ? (
              <div className="text-sm text-gray-500">Cargando ingresos relacionados...</div>
            ) : relatedErr ? (
              <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded">{relatedErr}</div>
            ) : relatedRows.length === 0 ? (
              <div className="text-sm text-gray-500">No se encontraron otros ingresos con este Número de serie.</div>
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
                          <tr key={ingresoId} className={`border-t hover:bg-gray-50 cursor-pointer ${isCurrent ? 'bg-blue-50' : ''}`} onClick={() => { setRelatedOpen(false); if (ingresoId) navigate(`/ingresos/${ingresoId}`); }}>
                            <td className="p-2 underline">{formatOSHelper(ingresoId)}</td>
                            <td className="p-2 capitalize">{r?.estado || '-'}</td>
                            <td className="p-2">{(() => {
                              const v = r?.presupuesto_estado;
                              if (!v) return '-';
                              if (v === 'presupuestado') return 'Presupuestado';
                              if (v === 'no_aplica') return 'No aplica';
                              try { const s = String(v); return s.charAt(0).toUpperCase() + s.slice(1); } catch { return String(v); }
                            })()}</td>
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

      {showReparadoToast && (
        <div className="fixed right-4 top-4 bg-emerald-600 text-white px-4 py-2 rounded shadow-lg" role="status">
          Marcado como reparado
        </div>
      )}

      {/* HISTORIAL */}
      {tab === "historial" && canSeeHistory && (
        <HistorialTab hErr={hErr} hLoading={hLoading} hist={hist} />
      )}

      {/* Botón flotante para edición bsica */}
      {canEditBasics && (
        <div className="fixed bottom-4 right-4 z-20 flex gap-2">
          {!editBasics ? (
            <button className="text-xs px-3 py-2 rounded shadow bg-neutral-800 text-white hover:bg-neutral-700" onClick={startEditBasics} type="button" title="Habilitar edición de datos">
              Editar datos
            </button>
          ) : (
            <>
              <button className="text-xs px-3 py-2 rounded shadow bg-amber-600 text-white disabled:opacity-60" onClick={saveEditBasics} disabled={savingBasics} type="button" title="Cerrar edición y guardar cambios">
                {savingBasics ? "Guardando..." : "Cerrar edición"}
              </button>
              <button className="text-xs px-3 py-2 rounded shadow bg-gray-200 hover:bg-gray-300" onClick={() => { setEditBasics(false); setFormBasics(null); }} type="button" title="Cancelar edición">
                Cancelar
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
