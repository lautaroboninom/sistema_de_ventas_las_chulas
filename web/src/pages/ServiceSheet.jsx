// web/src/pages/ServiceSheet.jsx
import { useEffect, useState, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import api, {
  // ingreso / catálogos
  getIngreso, getUbicaciones, patchIngreso,
  getTecnicos, patchIngresoTecnico,
  getDerivacionesPorIngreso,
  // presupuesto
  getQuote, postQuoteItem, patchQuoteItem, deleteQuoteItem, patchQuoteResumen,
  postQuoteEmitir, postQuoteAprobar, getBlob, postQuoteAnular, postCerrarReparacion, postMarcarReparado,
  // entrega
  postEntregarIngreso,
} from "../lib/api";
import { useAuth } from "../context/AuthContext";
import {
  formatOS as formatOSHelper,
  formatDateTime as formatDateTimeHelper,
  toNum,
} from "../lib/ui-helpers";
import { canActAsTech, canRelease, hasAnyRole, ROLES } from "../lib/authz";
import { RESOLUCION, RESOLUCION_OPTIONS, resolutionLabel } from "../lib/constants";

// UI helpers
const Row = ({ label, children }) => (
  <div className="flex gap-3 py-1">
    <div className="w-40 text-gray-500">{label}</div>
    <div className="flex-1">{children}</div>
  </div>
);

const Tabs = ({ value, onChange, items }) => (
  <div className="border-b mb-4 flex gap-2">
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
);

export default function ServiceSheet() {
  const { id } = useParams();
  const { user } = useAuth(); // para ocultar/mostrar botones según rol
  const actAsTech = canActAsTech(user);
  const release = canRelease(user);

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

  // pestañas
  const [tab, setTab] = useState("principal");

  // datos generales
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  // entrega
  const [entrega, setEntrega] = useState({
    remito_salida: "",
    factura_numero: "",
    fecha_entrega: "", // datetime-local string
  });

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
  async function removeItem(it) { if (!confirm("¿Eliminar renglón?")) return; await deleteQuoteItem(id, it.id); await loadQuote(); }
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

        // técnicos
        try { setTecnicos(await getTecnicos()); } catch (_) {}

        // derivaciones
        try { setDerivs(await getDerivacionesPorIngreso(id)); } catch (_) {}
      } catch (e) {
        setErr(e?.message || "Error cargando datos");
      }
    })();
  }, [id]);

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
  const techDirty = (tecnicoId ?? null) !== (data?.asignado_a ?? null);
  async function saveTecnico() {
    if (!techDirty || tecnicoId == null) return;
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

  return (
    <div className="max-w-6xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-2">Hoja de servicio — {formatOSHelper(data, id)}</h1>

      {err && <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-4">{err}</div>}

      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          { value: "principal", label: "Principal" },
          { value: "diagnostico", label: "Diagnóstico y Reparación" },
          { value: "presupuesto", label: "Presupuesto" },
          { value: "derivaciones", label: "Derivaciones" },
        ]}
      />

      {/* PRINCIPAL */}
      {tab === "principal" && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Columna izquierda: Cliente/Equipo/Notas */}
            <div className="border rounded p-4">
              <h2 className="font-semibold mb-2">Cliente</h2>
              <Row label="Razón social">{data.razon_social}</Row>
              <Row label="Código empresa">{data.cod_empresa || "-"}</Row>
              <Row label="Teléfono">{data.telefono || "-"}</Row>

              {(data.propietario_nombre || data.propietario_contacto || data.propietario_doc) && (
                <>
                  <h2 className="font-semibold mt-4 mb-2">Propietario</h2>
                  <Row label="Nombre">{data.propietario_nombre || "-"}</Row>
                  <Row label="Contacto">{data.propietario_contacto || "-"}</Row>
                  <Row label="Documento">{data.propietario_doc || "-"}</Row>
                </>
              )}

              <h2 className="font-semibold mt-4 mb-2">Equipo</h2>
              <Row label="Marca">{data.marca}</Row>
              <Row label="Modelo">{data.modelo}</Row>
              <Row label="Tipo de equipo">{data.tipo_equipo || "-"}</Row>
              <Row label="N° serie">{data.numero_serie}</Row>
              <Row label="Garantía (fábrica)">{data.garantia ? "Sí" : "No"}</Row>
              <Row label="Garantía de reparación">
                <input
                  type="checkbox"
                  checked={!!data.garantia_reparacion}
                  onChange={(e) => patch({ garantia_reparacion: e.target.checked })}
                />
              </Row>
              <Row label="N° interno (MG)">
                <input
                  className="border rounded p-1 w-60"
                  value={data.numero_interno || ""}
                  onChange={(e) => patch({ numero_interno: e.target.value })}
                />
              </Row>

              {/* Notas justo debajo del cuadro de Equipo */}
              <h2 className="font-semibold mt-4 mb-2">Notas</h2>
              <Row label="Informe preliminar">{data.informe_preliminar || "-"}</Row>
              <Row label="Accesorios">{data.accesorios || "-"}</Row>
            </div>


            {/* Columna derecha: Estado/Asignación/Ubicación */}
            <div className="border rounded p-4">
              <h2 className="font-semibold mb-2">Estado</h2>
              <Row label="Motivo">{data.motivo}</Row>
              <Row label="Estado">{data.estado}</Row>
              <Row label="Presupuesto">{data.presupuesto_estado === "presupuestado" ? "Presupuestado" : (data.presupuesto_estado || "-")}</Row>
              <Row label="Resolución">{data.resolucion ? resolutionLabel(data.resolucion) : "-"}</Row>
              <Row label="Fecha ingreso">{formatDateTimeHelper(data.fecha_ingreso)}</Row>
              <Row label="Fecha servicio">{data.fecha_servicio ? formatDateTimeHelper(data.fecha_servicio) : "-"}</Row>

              <div className="mt-3">
                <Link to={`/ingresos/${id}/derivar`} className="bg-neutral-800 text-white px-3 py-2 rounded">Derivar a externo</Link>
              </div>

              <h2 className="font-semibold mt-4 mb-2">Asignación</h2>
              <Row label="Técnico">
                <div className="flex items-center gap-3">
                  <select
                    className="border rounded p-2"
                    value={tecnicoId ?? ""}
                    onChange={(e) => setTecnicoId(e.target.value ? Number(e.target.value) : null)}
                  >
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
                </div>
                <div className="text-xs text-gray-500 mt-1">Actual: <b>{data.asignado_a_nombre || "-"}</b></div>
              </Row>

              <h2 className="font-semibold mt-4 mb-2">Ubicación</h2>
              <div className="flex items-center gap-3">
                <select
                  className="border rounded p-2"
                  value={ubicacionId}
                  onChange={(e) => setUbicacionId(e.target.value)}
                  aria-label="Seleccionar ubicación"
                >
                  <option value="" disabled>Seleccioná la ubicación…</option>
                  {ubicaciones.map((u) => (<option key={u.id} value={String(u.id)}>{u.nombre}</option>))}
                </select>
                <button
                  className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
                  onClick={saveUbicacion}
                  disabled={savingUb || !ubDirty}
                  aria-busy={savingUb ? "true" : "false"}
                  type="button"
                >
                  {savingUb ? "Guardando..." : "Guardar"}
                </button>
              </div>
              <div className="text-xs text-gray-500 mt-1">La ubicación puede modificarse desde aquí.</div>
            </div>
          </div>

          {/* Botón de orden de salida (liberar) */}
          {release && (Boolean(data?.resolucion) || data?.estado === "listo_retiro") && (
            <button
              className="bg-neutral-800 text-white px-3 py-2 rounded mt-4"
              onClick={async () => {
                try {
                  const blob = await getBlob(`/api/ingresos/${id}/remito/`);
                  if (!(blob instanceof Blob)) throw new Error("La respuesta no fue un PDF");
                  const url = URL.createObjectURL(blob);
                  window.open(url, "_blank", "noopener");
                  setTimeout(() => URL.revokeObjectURL(url), 60_000);
                  await refreshIngreso(); // el backend suele pasar a 'listo_retiro'
                } catch (e) {
                  setErr(e?.message || "No se pudo imprimir la orden de salida");
                }
              }}
              type="button"
            >
              Imprimir orden de salida (liberar)
            </button>
          )}

          {/* Entrega final (solo cuando está listo para retirar) */}
          {data.estado === "listo_retiro" && (
            <div className="border rounded p-4 mt-4">
              <h2 className="font-semibold mb-2">Entrega</h2>
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
            </div>
          )}

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

      {/* DIAGNÓSTICO */}
      {tab === "diagnostico" && (
        <div className="border rounded p-4">
          {/* Contexto útil para diagnosticar */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
            <div className="border rounded p-3 bg-gray-50">
              <div className="text-xs uppercase text-gray-500 mb-1">Informe preliminar</div>
              <div className="whitespace-pre-wrap">{data.informe_preliminar || "-"}</div>
            </div>
            <div className="border rounded p-3 bg-gray-50">
              <div className="text-xs uppercase text-gray-500 mb-1">Accesorios</div>
              <div className="whitespace-pre-wrap">{data.accesorios || "-"}</div>
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
              {actAsTech && !["reparado","listo_retiro","entregado"].includes(data?.estado) && (
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
          />

          <div className="border rounded p-4 mt-4">
            <h2 className="font-semibold mb-2">Trabajos realizados</h2>
            <textarea
              className="w-full border rounded p-2 min-h-[200px]"
              value={trabajos}
              onChange={(e) => setTrabajos(e.target.value)}
              placeholder="Ej.: Cambio de turbina; limpieza y secado; resoldado de conector; calibración; pruebas OK…"
            />
            <div className="mt-2 flex items-center gap-2">
              <button
                className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
                onClick={saveDiagYReparacion}
                disabled={savingAll}
                aria-busy={savingAll ? "true" : "false"}
                type="button"
              >
                {savingAll ? "Guardando..." : "Guardar"}
              </button>
            </div>
          </div>

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
                        <button className="text-red-600 hover:underline" onClick={() => removeItem(it)} type="button" disabled={isAprobado}>
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
          <h2 className="font-semibold mb-2">Derivaciones</h2>
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
    </div>
  );
}
