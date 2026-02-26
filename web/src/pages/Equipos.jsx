import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Tabs from "../components/Tabs";
import {
  getCatalogModelos,
  getCatalogTipos,
  getCatalogVariantes,
  getDevices,
  getMarcas,
  getMarcasPorTipo,
  getModelosByBrand,
  getTiposEquipo,
  postDeviceDirectCreate,
  patchDeviceIdentificadores,
  postDevicesMerge,
  postDevicePreventivoPlan,
  patchDevicePreventivoPlan,
  postDevicePreventivoRevision,
  getPreventivosAgenda,
  getPreventivosClientes,
  postCustomerPreventivoPlan,
  patchCustomerPreventivoPlan,
  getCustomerPreventivoRevisiones,
  postCustomerPreventivoRevision,
  getPreventivoRevision,
  postPreventivoRevisionItem,
  patchPreventivoRevisionItem,
  postPreventivoRevisionCerrar,
  postCliente,
} from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { isAdmin, isJefe, isJefeVeedor } from "../lib/authz";

const TAB_ITEMS = [
  { value: "equipos", label: "Equipos" },
  { value: "preventivos", label: "Mantenimientos preventivos" },
  { value: "instituciones", label: "Instituciones" },
];

const PERIODICIDAD_UNIDADES = [
  { value: "dias", label: "Dias" },
  { value: "meses", label: "Meses" },
  { value: "anios", label: "Anios" },
];

const ITEM_STATES = [
  { value: "pendiente", label: "Pendiente" },
  { value: "ok", label: "OK" },
  { value: "retirado", label: "Retirado" },
  { value: "no_controlado", label: "No controlado" },
];

function todayISO() {
  const now = new Date();
  const mm = `${now.getMonth() + 1}`.padStart(2, "0");
  const dd = `${now.getDate()}`.padStart(2, "0");
  return `${now.getFullYear()}-${mm}-${dd}`;
}

function fmtDate(v) {
  if (!v) return "-";
  const s = String(v);
  if (s.includes("T")) return s.slice(0, 10);
  return s;
}

function estadoClass(estado) {
  if (estado === "vencido") return "bg-red-100 text-red-800";
  if (estado === "proximo") return "bg-amber-100 text-amber-800";
  if (estado === "sin_plan") return "bg-slate-100 text-slate-700";
  return "bg-emerald-100 text-emerald-800";
}

function estadoLabel(estado) {
  if (estado === "vencido") return "Vencido";
  if (estado === "proximo") return "Proximo";
  if (estado === "sin_plan") return "Sin plan";
  if (estado === "al_dia") return "Al dia";
  return estado || "-";
}

function PreventivoBadge({ estado, dias }) {
  return (
    <span className={`px-2 py-1 text-xs rounded ${estadoClass(estado)}`}>
      {estadoLabel(estado)}
      {typeof dias === "number" ? ` (${dias})` : ""}
    </span>
  );
}

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
          Equipo #{row.id} - Marca: {row.marca || "-"}, Modelo: {row.modelo || "-"}
        </div>
        {err && <div className="bg-red-100 text-red-800 border border-red-300 rounded p-2 mb-3">{err}</div>}
        <div className="space-y-3">
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Numero de serie</div>
            <input
              type="text"
              value={ns}
              onChange={(e) => setNs(e.target.value)}
              className="border rounded p-2 w-full"
              disabled={!canEdit || saving}
            />
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Numero interno (MG)</div>
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
          <button className="px-3 py-1.5 rounded border" onClick={onClose} disabled={saving}>
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
                  if (ctype === "NS_DUPLICATE") setErr("El numero de serie ya esta asignado a otro equipo.");
                  else if (ctype === "MG_DUPLICATE") setErr("El numero interno ya esta asignado a otro equipo.");
                  else setErr(e?.message || "No se pudo guardar.");
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

function PreventivoPlanModal({ title, initialPlan, onClose, onSubmit, saving = false, error = "" }) {
  const [form, setForm] = useState({
    periodicidad_valor: "",
    periodicidad_unidad: "meses",
    aviso_anticipacion_dias: "30",
    ultima_revision_fecha: "",
    proxima_revision_fecha: "",
    activa: true,
    observaciones: "",
  });

  useEffect(() => {
    setForm({
      periodicidad_valor: initialPlan?.periodicidad_valor != null ? String(initialPlan.periodicidad_valor) : "",
      periodicidad_unidad: initialPlan?.periodicidad_unidad || "meses",
      aviso_anticipacion_dias:
        initialPlan?.aviso_anticipacion_dias != null
          ? String(initialPlan.aviso_anticipacion_dias)
          : "30",
      ultima_revision_fecha: initialPlan?.ultima_revision_fecha || "",
      proxima_revision_fecha: initialPlan?.proxima_revision_fecha || "",
      activa: initialPlan?.activa == null ? true : !!initialPlan.activa,
      observaciones: initialPlan?.observaciones || "",
    });
  }, [initialPlan]);

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded shadow-lg w-full max-w-xl p-4">
        <div className="text-lg font-semibold mb-2">{title}</div>
        {error && <div className="bg-red-100 border border-red-300 text-red-800 rounded p-2 mb-3">{error}</div>}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Periodicidad valor</div>
            <input
              type="number"
              min="1"
              className="border rounded p-2 w-full"
              value={form.periodicidad_valor}
              onChange={(e) => update("periodicidad_valor", e.target.value)}
              disabled={saving}
            />
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Unidad</div>
            <select
              className="border rounded p-2 w-full"
              value={form.periodicidad_unidad}
              onChange={(e) => update("periodicidad_unidad", e.target.value)}
              disabled={saving}
            >
              {PERIODICIDAD_UNIDADES.map((u) => (
                <option key={u.value} value={u.value}>{u.label}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Aviso (dias)</div>
            <input
              type="number"
              min="0"
              className="border rounded p-2 w-full"
              value={form.aviso_anticipacion_dias}
              onChange={(e) => update("aviso_anticipacion_dias", e.target.value)}
              disabled={saving}
            />
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Ultima revision</div>
            <input
              type="date"
              className="border rounded p-2 w-full"
              value={form.ultima_revision_fecha}
              onChange={(e) => update("ultima_revision_fecha", e.target.value)}
              disabled={saving}
            />
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Proxima revision</div>
            <input
              type="date"
              className="border rounded p-2 w-full"
              value={form.proxima_revision_fecha}
              onChange={(e) => update("proxima_revision_fecha", e.target.value)}
              disabled={saving}
            />
          </label>
          <label className="block md:flex md:items-end">
            <span className="inline-flex items-center gap-2 text-sm mt-7 md:mt-0">
              <input
                type="checkbox"
                checked={!!form.activa}
                onChange={(e) => update("activa", e.target.checked)}
                disabled={saving}
              />
              Plan activo
            </span>
          </label>
        </div>
        <label className="block mt-3">
          <div className="text-sm text-gray-700 mb-1">Observaciones</div>
          <textarea
            className="border rounded p-2 w-full min-h-20"
            value={form.observaciones}
            onChange={(e) => update("observaciones", e.target.value)}
            disabled={saving}
          />
        </label>
        <div className="flex justify-end gap-2 mt-4">
          <button className="px-3 py-1.5 rounded border" onClick={onClose} disabled={saving}>Cancelar</button>
          <button
            className="px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            onClick={() => onSubmit({
              periodicidad_valor: Number(form.periodicidad_valor || 0),
              periodicidad_unidad: form.periodicidad_unidad,
              aviso_anticipacion_dias: Number(form.aviso_anticipacion_dias || 0),
              ultima_revision_fecha: form.ultima_revision_fecha || null,
              proxima_revision_fecha: form.proxima_revision_fecha || null,
              activa: !!form.activa,
              observaciones: form.observaciones || "",
            })}
            disabled={saving}
          >
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}

function DeviceRevisionModal({ row, onClose, onSubmit, saving = false, error = "" }) {
  const [form, setForm] = useState({
    fecha_realizada: todayISO(),
    estado_item: "ok",
    motivo_no_control: "",
    ubicacion_detalle: "",
    accesorios_cambiados: false,
    accesorios_detalle: "",
    notas: "",
    arrastrar_proxima: true,
    resumen: "",
  });

  useEffect(() => {
    setForm({
      fecha_realizada: todayISO(),
      estado_item: "ok",
      motivo_no_control: "",
      ubicacion_detalle: "",
      accesorios_cambiados: false,
      accesorios_detalle: "",
      notas: "",
      arrastrar_proxima: true,
      resumen: "",
    });
  }, [row?.id]);

  const update = (key, value) => {
    setForm((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "estado_item" && value === "retirado") next.arrastrar_proxima = false;
      return next;
    });
  };

  if (!row) return null;
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded shadow-lg w-full max-w-xl p-4">
        <div className="text-lg font-semibold mb-2">Registrar revision de equipo</div>
        <div className="text-sm text-gray-600 mb-3">
          Equipo #{row.id} - {row.marca || "-"} {row.modelo || ""}
        </div>
        {error && <div className="bg-red-100 border border-red-300 text-red-800 rounded p-2 mb-3">{error}</div>}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Fecha realizada</div>
            <input type="date" className="border rounded p-2 w-full" value={form.fecha_realizada} onChange={(e) => update("fecha_realizada", e.target.value)} />
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Estado</div>
            <select className="border rounded p-2 w-full" value={form.estado_item} onChange={(e) => update("estado_item", e.target.value)}>
              {ITEM_STATES.filter((s) => s.value !== "pendiente").map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </label>
          {form.estado_item === "no_controlado" && (
            <label className="block md:col-span-2">
              <div className="text-sm text-gray-700 mb-1">Motivo no control</div>
              <input
                type="text"
                className="border rounded p-2 w-full"
                value={form.motivo_no_control}
                onChange={(e) => update("motivo_no_control", e.target.value)}
              />
            </label>
          )}
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Ubicacion</div>
            <input type="text" className="border rounded p-2 w-full" value={form.ubicacion_detalle} onChange={(e) => update("ubicacion_detalle", e.target.value)} />
          </label>
          <label className="block md:flex md:items-end">
            <span className="inline-flex items-center gap-2 text-sm mt-7 md:mt-0">
              <input type="checkbox" checked={!!form.accesorios_cambiados} onChange={(e) => update("accesorios_cambiados", e.target.checked)} />
              Accesorios cambiados
            </span>
          </label>
          {form.accesorios_cambiados && (
            <label className="block md:col-span-2">
              <div className="text-sm text-gray-700 mb-1">Detalle accesorios</div>
              <input
                type="text"
                className="border rounded p-2 w-full"
                value={form.accesorios_detalle}
                onChange={(e) => update("accesorios_detalle", e.target.value)}
              />
            </label>
          )}
          <label className="block md:col-span-2">
            <div className="text-sm text-gray-700 mb-1">Resumen</div>
            <input type="text" className="border rounded p-2 w-full" value={form.resumen} onChange={(e) => update("resumen", e.target.value)} />
          </label>
          <label className="block md:col-span-2">
            <div className="text-sm text-gray-700 mb-1">Notas</div>
            <textarea className="border rounded p-2 w-full min-h-16" value={form.notas} onChange={(e) => update("notas", e.target.value)} />
          </label>
          <label className="block md:col-span-2">
            <span className="inline-flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!form.arrastrar_proxima} onChange={(e) => update("arrastrar_proxima", e.target.checked)} />
              Arrastrar a proxima revision
            </span>
          </label>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button className="px-3 py-1.5 rounded border" onClick={onClose} disabled={saving}>Cancelar</button>
          <button
            className="px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            onClick={() => onSubmit(form)}
            disabled={saving}
          >
            Guardar revision
          </button>
        </div>
      </div>
    </div>
  );
}

function AddInstitutionModal({ onClose, onSubmit, saving = false, error = "" }) {
  const [form, setForm] = useState({
    razon_social: "",
    cod_empresa: "",
    telefono: "",
    telefono_2: "",
    email: "",
  });

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded shadow-lg w-full max-w-xl p-4">
        <div className="text-lg font-semibold mb-2">Agregar institucion</div>
        {error && <div className="bg-red-100 border border-red-300 text-red-800 rounded p-2 mb-3">{error}</div>}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="block md:col-span-2">
            <div className="text-sm text-gray-700 mb-1">Razon social *</div>
            <input className="border rounded p-2 w-full" value={form.razon_social} onChange={(e) => update("razon_social", e.target.value)} />
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Codigo empresa *</div>
            <input className="border rounded p-2 w-full" value={form.cod_empresa} onChange={(e) => update("cod_empresa", e.target.value)} />
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Telefono</div>
            <input className="border rounded p-2 w-full" value={form.telefono} onChange={(e) => update("telefono", e.target.value)} />
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Telefono 2</div>
            <input className="border rounded p-2 w-full" value={form.telefono_2} onChange={(e) => update("telefono_2", e.target.value)} />
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Email</div>
            <input className="border rounded p-2 w-full" value={form.email} onChange={(e) => update("email", e.target.value)} />
          </label>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button className="px-3 py-1.5 rounded border" onClick={onClose} disabled={saving}>Cancelar</button>
          <button
            className="px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            onClick={() => onSubmit(form)}
            disabled={saving}
          >
            Crear institucion
          </button>
        </div>
      </div>
    </div>
  );
}

function AddPreventivoEquipoModal({ onClose, onSelect, onCreateManaged }) {
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const runSearch = async () => {
    const term = (search || "").trim();
    if (!term) {
      setErr("Ingresa un criterio para buscar (N/S, MG, cliente, marca o modelo).");
      setRows([]);
      return;
    }
    try {
      setLoading(true);
      setErr("");
      const res = await getDevices({
        q: term,
        page: 1,
        page_size: 30,
        sort: "-id",
      });
      const items = Array.isArray(res) ? res : (res.items || []);
      setRows(items);
      if (!items.length) {
        setErr("No se encontraron equipos en la lista actual.");
      }
    } catch (e) {
      setErr(e?.message || "No se pudieron buscar equipos.");
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded shadow-lg w-full max-w-5xl p-4">
        <div className="text-lg font-semibold mb-2">Agregar equipo a preventivos</div>
        <div className="text-sm text-gray-600 mb-3">
          Selecciona un equipo existente para configurarle plan preventivo.
        </div>

        {err && <div className="bg-red-100 border border-red-300 text-red-800 rounded p-2 mb-3">{err}</div>}

        <div className="flex flex-wrap items-center gap-2 mb-3">
          <input
            type="text"
            className="border rounded p-2 w-full max-w-xl"
            placeholder="Buscar por N/S, MG, cliente, marca, modelo..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") runSearch(); }}
          />
          <button className="btn" onClick={runSearch} disabled={loading}>
            Buscar
          </button>
          <button className="px-3 py-1.5 rounded border hover:bg-gray-50" onClick={onCreateManaged}>
            Crear equipo sin ingreso
          </button>
        </div>

        <div className="border rounded overflow-x-auto max-h-[50vh]">
          {loading ? (
            <div className="text-sm text-gray-500 p-3">Buscando...</div>
          ) : rows.length === 0 ? (
            <div className="text-sm text-gray-500 p-3">Sin resultados.</div>
          ) : (
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left bg-gray-50">
                  <th className="p-2">ID</th>
                  <th className="p-2">Cliente</th>
                  <th className="p-2">N/S</th>
                  <th className="p-2">MG</th>
                  <th className="p-2">Marca</th>
                  <th className="p-2">Modelo</th>
                  <th className="p-2">Accion</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t">
                    <td className="p-2 font-mono text-xs">{row.id}</td>
                    <td className="p-2">{row.last_customer_nombre || row.customer_nombre || "-"}</td>
                    <td className="p-2">{row.numero_serie || "-"}</td>
                    <td className="p-2">{row.numero_interno || "-"}</td>
                    <td className="p-2">{row.marca || "-"}</td>
                    <td className="p-2">{row.modelo || "-"}</td>
                    <td className="p-2">
                      <button
                        className="px-2 py-1 rounded border text-xs hover:bg-gray-50"
                        onClick={() => onSelect(row)}
                      >
                        Configurar plan
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <button className="px-3 py-1.5 rounded border" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

function AddManagedDeviceModal({ onClose, onSubmit, customers = [], saving = false, error = "" }) {
  const [form, setForm] = useState({
    customer_id: "",
    tipo_equipo: "",
    marca_id: "",
    modelo_id: "",
    variante: "",
    numero_serie: "",
    numero_interno: "",
    alquilado: false,
    alquiler_customer_id: "",
    alquiler_a: "",
  });
  const [tiposEquipo, setTiposEquipo] = useState([]);
  const [marcas, setMarcas] = useState([]);
  const [marcasPorTipo, setMarcasPorTipo] = useState([]);
  const [modelos, setModelos] = useState([]);
  const [varianteSugeridas, setVarianteSugeridas] = useState([]);
  const [marcaTxt, setMarcaTxt] = useState("");
  const [marcaId, setMarcaId] = useState(null);
  const [catTipoId, setCatTipoId] = useState(null);
  const [catModelos, setCatModelos] = useState([]);
  const [catalogErr, setCatalogErr] = useState("");

  const update = (key, value) =>
    setForm((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "alquilado" && !value) {
        next.alquiler_customer_id = "";
        next.alquiler_a = "";
      }
      if (key === "alquiler_customer_id") {
        const selected = (customers || []).find((c) => String(c.customer_id) === String(value));
        next.alquiler_a = selected?.razon_social || "";
      }
      return next;
    });
  const tipoSel = (form.tipo_equipo || "").trim();

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        setCatalogErr("");
        const [marcasRows, tiposRows] = await Promise.all([getMarcas(), getTiposEquipo()]);
        if (!active) return;
        setMarcas(Array.isArray(marcasRows) ? marcasRows : []);
        const tipoList = (Array.isArray(tiposRows) ? tiposRows : [])
          .map((t) => t?.nombre || t?.label || t?.name || t?.value || t)
          .map(String)
          .map((s) => s.trim())
          .filter(Boolean);
        setTiposEquipo(Array.from(new Set(tipoList)));
      } catch (e) {
        if (!active) return;
        setCatalogErr(e?.message || "No se pudieron cargar catalogos de equipo.");
        setMarcas([]);
        setTiposEquipo([]);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setMarcaTxt("");
    setMarcaId(null);
    setModelos([]);
    setCatTipoId(null);
    setCatModelos([]);
    setVarianteSugeridas([]);
    setForm((prev) => ({
      ...prev,
      marca_id: "",
      modelo_id: "",
      variante: "",
    }));
    if (!tipoSel) {
      setMarcasPorTipo([]);
      return () => {
        active = false;
      };
    }
    (async () => {
      try {
        const rows = await getMarcasPorTipo(tipoSel);
        if (!active) return;
        setMarcasPorTipo(Array.isArray(rows) ? rows : []);
      } catch {
        if (!active) return;
        setMarcasPorTipo([]);
      }
    })();
    return () => {
      active = false;
    };
  }, [tipoSel]);

  useEffect(() => {
    let active = true;
    setForm((prev) => ({
      ...prev,
      marca_id: marcaId ? String(marcaId) : "",
      modelo_id: "",
      variante: "",
    }));
    setModelos([]);
    setCatTipoId(null);
    setCatModelos([]);
    setVarianteSugeridas([]);
    if (!marcaId) {
      return () => {
        active = false;
      };
    }
    (async () => {
      try {
        const rows = await getModelosByBrand(marcaId);
        if (!active) return;
        const list = Array.isArray(rows) ? rows : [];
        const norm = (s) => (s || "").toString().trim().toUpperCase();
        const filtered = tipoSel ? list.filter((m) => norm(m?.tipo_equipo) === norm(tipoSel)) : list;
        setModelos(filtered);

        const tiposBrand = await getCatalogTipos(marcaId);
        if (!active) return;
        const match = (Array.isArray(tiposBrand) ? tiposBrand : []).find(
          (t) => (t?.name || "").trim().toUpperCase() === (tipoSel || "").trim().toUpperCase()
        );
        const tId = match?.id ?? null;
        setCatTipoId(tId);
        if (tId) {
          const mods = await getCatalogModelos(marcaId, tId);
          if (!active) return;
          setCatModelos(Array.isArray(mods) ? mods : []);
        } else {
          setCatModelos([]);
        }
      } catch (e) {
        if (!active) return;
        setCatalogErr(e?.message || "No se pudieron cargar modelos.");
        setModelos([]);
        setCatTipoId(null);
        setCatModelos([]);
        setVarianteSugeridas([]);
      }
    })();
    return () => {
      active = false;
    };
  }, [marcaId, tipoSel]);

  useEffect(() => {
    let active = true;
    const selectedModel = (modelos || []).find((x) => String(x.id) === String(form.modelo_id));
    if (!selectedModel || !marcaId || !catTipoId) {
      setVarianteSugeridas([]);
      return () => {
        active = false;
      };
    }

    const needle = (selectedModel?.nombre || "").trim().toUpperCase();
    const cmatch = (catModelos || []).filter((cm) => {
      const a = (cm?.name || "").trim().toUpperCase();
      const alias = (cm?.alias || "").trim().toUpperCase();
      return (
        a === needle ||
        a.includes(needle) ||
        needle.includes(a) ||
        (alias && (alias === needle || needle.includes(alias) || alias.includes(needle)))
      );
    });
    if (cmatch.length !== 1) {
      setVarianteSugeridas([]);
      return () => {
        active = false;
      };
    }

    (async () => {
      try {
        const vars = await getCatalogVariantes(marcaId, catTipoId, cmatch[0].id);
        if (!active) return;
        const names = (Array.isArray(vars) ? vars : []).filter((v) => v?.name).map((v) => v.name);
        setVarianteSugeridas(names);
        if (!String(form.variante || "").trim() && names.length === 1) {
          setForm((prev) => ({ ...prev, variante: names[0] }));
        }
      } catch {
        if (!active) return;
        setVarianteSugeridas([]);
      }
    })();
    return () => {
      active = false;
    };
  }, [form.modelo_id, form.variante, modelos, marcaId, catTipoId, catModelos]);

  const onMarcaInput = (value) => {
    setMarcaTxt(value);
    const pool = tipoSel ? (marcasPorTipo.length ? marcasPorTipo : marcas) : marcas;
    const match = (pool || []).find(
      (m) => (m?.nombre || "").toLowerCase() === String(value || "").trim().toLowerCase()
    );
    setMarcaId(match ? Number(match.id) : null);
  };

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded shadow-lg w-full max-w-xl p-4">
        <div className="text-lg font-semibold mb-2">Agregar equipo al sistema</div>
        <div className="text-sm text-gray-600 mb-3">
          Este alta registra el equipo en inventario sin generar ingreso ni remito.
        </div>
        {error && <div className="bg-red-100 border border-red-300 text-red-800 rounded p-2 mb-3">{error}</div>}
        {catalogErr && <div className="bg-amber-100 border border-amber-300 text-amber-900 rounded p-2 mb-3">{catalogErr}</div>}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="block md:col-span-2">
            <div className="text-sm text-gray-700 mb-1">Institucion / Cliente *</div>
            <select
              className="border rounded p-2 w-full"
              value={form.customer_id}
              onChange={(e) => update("customer_id", e.target.value)}
              disabled={saving}
            >
              <option value="">Selecciona una institucion</option>
              {customers.map((c) => (
                <option key={c.customer_id} value={c.customer_id}>
                  {c.razon_social} {c.cod_empresa ? `(${c.cod_empresa})` : ""}
                </option>
              ))}
            </select>
          </label>

          <label className="block md:col-span-2">
            <div className="text-sm text-gray-700 mb-1">Tipo de equipo</div>
            <select
              className="border rounded p-2 w-full"
              value={form.tipo_equipo}
              onChange={(e) => update("tipo_equipo", e.target.value || "")}
              disabled={saving}
            >
              <option value="">-- Seleccionar --</option>
              {(tiposEquipo || []).map((t, i) => (
                <option key={`${t}-${i}`} value={t}>{t}</option>
              ))}
            </select>
          </label>

          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Marca *</div>
            <input
              list="managed-device-marcas-list"
              className="border rounded p-2 w-full"
              value={marcaTxt}
              onChange={(e) => onMarcaInput(e.target.value)}
              placeholder="Marca"
              disabled={saving}
            />
            <datalist id="managed-device-marcas-list">
              {(tipoSel && marcasPorTipo.length ? marcasPorTipo : marcas).map((m) => (
                <option key={m.id} value={m.nombre} />
              ))}
            </datalist>
            {marcaTxt && !marcaId && (
              <div className="text-xs text-red-600 mt-1">Elegi una marca de las sugeridas.</div>
            )}
          </label>

          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Modelo *</div>
            <select
              className="border rounded p-2 w-full"
              value={form.modelo_id}
              onChange={(e) => update("modelo_id", e.target.value)}
              disabled={!marcaId || !modelos.length || saving}
            >
              <option value="">{!marcaId ? "Elegi marca primero" : "Selecciona modelo"}</option>
              {modelos.map((m) => (
                <option key={m.id} value={m.id}>{m.nombre}</option>
              ))}
            </select>
          </label>

          <label className="block md:col-span-2">
            <div className="text-sm text-gray-700 mb-1">Variante / detalle</div>
            <input
              list="managed-device-variantes-list"
              className="border rounded p-2 w-full"
              value={form.variante}
              onChange={(e) => update("variante", e.target.value)}
              disabled={saving}
            />
            <datalist id="managed-device-variantes-list">
              {(varianteSugeridas || []).map((v, i) => (
                <option key={`${v}-${i}`} value={v} />
              ))}
            </datalist>
          </label>

          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Numero de serie</div>
            <input
              className="border rounded p-2 w-full"
              value={form.numero_serie}
              onChange={(e) => update("numero_serie", e.target.value)}
              disabled={saving}
            />
          </label>
          <label className="block">
            <div className="text-sm text-gray-700 mb-1">Numero interno (MG)</div>
            <input
              className="border rounded p-2 w-full"
              value={form.numero_interno}
              onChange={(e) => update("numero_interno", e.target.value)}
              disabled={saving}
            />
          </label>

          <label className="block md:col-span-2">
            <span className="inline-flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={!!form.alquilado}
                onChange={(e) => update("alquilado", e.target.checked)}
                disabled={saving}
              />
              Equipo alquilado
            </span>
          </label>
          {form.alquilado && (
            <label className="block md:col-span-2">
              <div className="text-sm text-gray-700 mb-1">Alquilado a (cliente) *</div>
              <select
                className="border rounded p-2 w-full"
                value={form.alquiler_customer_id}
                onChange={(e) => update("alquiler_customer_id", e.target.value)}
                disabled={saving}
              >
                <option value="">Selecciona cliente</option>
                {customers.map((c) => (
                  <option key={c.customer_id} value={c.customer_id}>
                    {c.razon_social} {c.cod_empresa ? `(${c.cod_empresa})` : ""}
                  </option>
                ))}
              </select>
              {!customers.length && (
                <div className="text-xs text-amber-700 mt-1">
                  No hay clientes cargados para seleccionar.
                </div>
              )}
            </label>
          )}
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <button className="px-3 py-1.5 rounded border" onClick={onClose} disabled={saving}>
            Cancelar
          </button>
          <button
            className="px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            onClick={() => onSubmit(form)}
            disabled={saving}
          >
            Guardar equipo
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Equipos() {
  const { user } = useAuth();
  const canEdit = isJefe(user) || isJefeVeedor(user) || isAdmin(user);
  const canPlanEdit = isJefe(user) || isJefeVeedor(user) || isAdmin(user);
  const canRevisionMutate = isJefe(user) || isJefeVeedor(user) || isAdmin(user) || user?.rol === "tecnico";
  const nav = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const tabParam = (searchParams.get("tab") || "equipos").toLowerCase();
  const initialTab = tabParam === "mantenimientos-preventivos" ? "preventivos" : tabParam;
  const [activeTab, setActiveTab] = useState(TAB_ITEMS.some((t) => t.value === initialTab) ? initialTab : "equipos");

  const updateSearchParam = (key, value) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value == null || value === "") next.delete(key);
      else next.set(key, String(value));
      return next;
    }, { replace: true });
  };

  useEffect(() => {
    updateSearchParam("tab", activeTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const highlightId = searchParams.get("device_id");

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [err, setErr] = useState("");
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [qDebounced, setQDebounced] = useState(searchParams.get("q") || "");
  const [editRow, setEditRow] = useState(null);
  const [reloadDevicesKey, setReloadDevicesKey] = useState(0);
  const [sort, setSort] = useState("-id");

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

  const [planModalCtx, setPlanModalCtx] = useState(null);
  const [planSaving, setPlanSaving] = useState(false);
  const [planErr, setPlanErr] = useState("");

  const [deviceRevisionCtx, setDeviceRevisionCtx] = useState(null);
  const [deviceRevisionSaving, setDeviceRevisionSaving] = useState(false);
  const [deviceRevisionErr, setDeviceRevisionErr] = useState("");

  const [agendaLoading, setAgendaLoading] = useState(false);
  const [agendaErr, setAgendaErr] = useState("");
  const [agendaItems, setAgendaItems] = useState([]);
  const [agendaCounts, setAgendaCounts] = useState({ total: 0, vencido: 0, proximo: 0, sin_plan: 0, al_dia: 0 });
  const [agendaEstado, setAgendaEstado] = useState("");
  const [agendaQ, setAgendaQ] = useState("");
  const [agendaCustomerId, setAgendaCustomerId] = useState("");

  const [institucionesLoading, setInstitucionesLoading] = useState(false);
  const [institucionesErr, setInstitucionesErr] = useState("");
  const [instituciones, setInstituciones] = useState([]);
  const [selectedInstitucionId, setSelectedInstitucionId] = useState(searchParams.get("institucion_id") || "");
  const [instRevisionesLoading, setInstRevisionesLoading] = useState(false);
  const [instRevisionesErr, setInstRevisionesErr] = useState("");
  const [instRevisiones, setInstRevisiones] = useState([]);
  const [instPlan, setInstPlan] = useState(null);

  const [addInstitutionOpen, setAddInstitutionOpen] = useState(false);
  const [addInstitutionSaving, setAddInstitutionSaving] = useState(false);
  const [addInstitutionErr, setAddInstitutionErr] = useState("");
  const [addPreventivoEquipoOpen, setAddPreventivoEquipoOpen] = useState(false);
  const [addManagedDeviceOpen, setAddManagedDeviceOpen] = useState(false);
  const [addManagedDeviceSaving, setAddManagedDeviceSaving] = useState(false);
  const [addManagedDeviceErr, setAddManagedDeviceErr] = useState("");
  const [addManagedDeviceContext, setAddManagedDeviceContext] = useState("general");

  const [revisionOpenId, setRevisionOpenId] = useState(null);
  const [revisionLoading, setRevisionLoading] = useState(false);
  const [revisionErr, setRevisionErr] = useState("");
  const [revisionData, setRevisionData] = useState(null);
  const [savingItemId, setSavingItemId] = useState(null);
  const [newItemName, setNewItemName] = useState("");
  const [closeRevisionForm, setCloseRevisionForm] = useState({ fecha_realizada: todayISO(), resumen: "" });
  const [closingRevision, setClosingRevision] = useState(false);

  const pageSize = 100;

  useEffect(() => {
    const timer = setTimeout(() => setQDebounced(q), 300);
    return () => clearTimeout(timer);
  }, [q]);

  const selectedInstitucion = useMemo(
    () => instituciones.find((it) => String(it.customer_id) === String(selectedInstitucionId)) || null,
    [instituciones, selectedInstitucionId]
  );

  const mergedInstPlan = selectedInstitucion?.plan || instPlan || null;

  const sortedInstituciones = useMemo(
    () => [...instituciones].sort((a, b) => String(a?.razon_social || "").localeCompare(String(b?.razon_social || ""))),
    [instituciones]
  );

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

  const selectMergeEquipo2 = (row) => {
    setMergeEquipo2(row);
    const nsDefault = mergeEquipo1?.numero_serie ? "equipo1" : (row?.numero_serie ? "equipo2" : "equipo1");
    const mgDefault = mergeEquipo1?.numero_interno ? "equipo1" : (row?.numero_interno ? "equipo2" : "equipo1");
    setMergeNsChoice(nsDefault);
    setMergeMgChoice(mgDefault);
    setMergeStep(2);
    setMergeErr("");
  };

  const mergeNsFinal = mergeNsChoice === "equipo1" ? (mergeEquipo1?.numero_serie || "") : (mergeEquipo2?.numero_serie || "");
  const mergeMgFinal = mergeMgChoice === "equipo1" ? (mergeEquipo1?.numero_interno || "") : (mergeEquipo2?.numero_interno || "");
  const mergeNsFinalValue = (mergeNsFinal || "").trim();
  const mergeMgFinalValue = (mergeMgFinal || "").trim();
  const canSubmitMerge = !!mergeEquipo1 && !!mergeEquipo2 && !!mergeNsFinalValue && !mergeSaving;

  async function loadDevices(p = 1, { reset = false } = {}) {
    try {
      if (reset) {
        setRows([]);
        setPage(1);
        setHasNext(false);
      }
      const isFirst = reset || p === 1;
      isFirst ? setLoading(true) : setLoadingMore(true);
      setErr("");
      const qEffective = (qDebounced || "").trim();
      const query = {
        page: p,
        page_size: pageSize,
        q: qEffective || undefined,
        propio: searchParams.get("propio") || undefined,
        alquilado: searchParams.get("alquilado") || undefined,
        sort: sort || undefined,
      };
      const res = await getDevices(query);
      const items = Array.isArray(res) ? res : (res.items || []);
      const next = Array.isArray(res) ? false : !!res.has_next;

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

  async function loadAgenda() {
    try {
      setAgendaLoading(true);
      setAgendaErr("");
      const params = {
        scope: "device",
        only_with_plan: 1,
        estado: agendaEstado || undefined,
        customer_id: agendaCustomerId || undefined,
        q: agendaQ || undefined,
      };
      const res = await getPreventivosAgenda(params);
      const items = (res?.items || []).filter((it) => (it?.scope_type || "device") === "device");
      const counts = { total: items.length, vencido: 0, proximo: 0, sin_plan: 0, al_dia: 0 };
      items.forEach((it) => {
        const estado = it?.preventivo_estado;
        if (estado === "vencido") counts.vencido += 1;
        else if (estado === "proximo") counts.proximo += 1;
        else if (estado === "sin_plan") counts.sin_plan += 1;
        else if (estado === "al_dia") counts.al_dia += 1;
      });
      setAgendaItems(items);
      setAgendaCounts(counts);
    } catch (e) {
      setAgendaErr(e?.message || "No se pudo cargar la agenda de preventivos.");
      setAgendaItems([]);
      setAgendaCounts({ total: 0, vencido: 0, proximo: 0, sin_plan: 0, al_dia: 0 });
    } finally {
      setAgendaLoading(false);
    }
  }

  async function loadInstituciones() {
    try {
      setInstitucionesLoading(true);
      setInstitucionesErr("");
      const res = await getPreventivosClientes();
      setInstituciones(res?.items || []);
    } catch (e) {
      setInstitucionesErr(e?.message || "No se pudieron cargar las instituciones.");
      setInstituciones([]);
    } finally {
      setInstitucionesLoading(false);
    }
  }

  async function loadInstitucionRevisiones(customerId) {
    if (!customerId) {
      setInstPlan(null);
      setInstRevisiones([]);
      return;
    }
    try {
      setInstRevisionesLoading(true);
      setInstRevisionesErr("");
      const res = await getCustomerPreventivoRevisiones(customerId);
      setInstPlan(res?.plan || null);
      setInstRevisiones(res?.items || []);
    } catch (e) {
      setInstRevisionesErr(e?.message || "No se pudo cargar el historial de revisiones.");
      setInstPlan(null);
      setInstRevisiones([]);
    } finally {
      setInstRevisionesLoading(false);
    }
  }

  async function openRevision(revisionId) {
    if (!revisionId) return;
    try {
      setRevisionOpenId(revisionId);
      setRevisionLoading(true);
      setRevisionErr("");
      const res = await getPreventivoRevision(revisionId);
      setRevisionData({ revision: res?.revision || null, items: res?.items || [] });
      setCloseRevisionForm({
        fecha_realizada: res?.revision?.fecha_realizada || todayISO(),
        resumen: res?.revision?.resumen || "",
      });
    } catch (e) {
      setRevisionErr(e?.message || "No se pudo cargar la revision.");
      setRevisionData(null);
    } finally {
      setRevisionLoading(false);
    }
  }

  async function startOrContinueInstitutionRevision(customerId) {
    if (!customerId) return;
    try {
      const current = instituciones.find((it) => String(it.customer_id) === String(customerId));
      const draftFromList = current?.borrador_revision_id;
      const draftFromHistory = (instRevisiones || []).find((it) => it.estado === "borrador")?.id;
      const draftId = draftFromList || draftFromHistory;
      if (draftId) {
        await openRevision(draftId);
        return;
      }
      const res = await postCustomerPreventivoRevision(customerId, {});
      const revId = res?.revision?.id;
      await loadInstituciones();
      await loadInstitucionRevisiones(customerId);
      if (revId) await openRevision(revId);
    } catch (e) {
      setInstRevisionesErr(e?.message || "No se pudo iniciar la revision institucional.");
    }
  }

  const sentinelRef = useRef(null);
  useEffect(() => {
    if (!hasNext || activeTab !== "equipos") return;
    const el = sentinelRef.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && !loadingMore) loadDevices(page + 1);
      }
    });
    io.observe(el);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasNext, page, loadingMore, activeTab]);

  useEffect(() => {
    if (activeTab === "equipos") loadDevices(1, { reset: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, reloadDevicesKey, sort, qDebounced, searchParams.get("propio"), searchParams.get("alquilado")]);

  useEffect(() => {
    if (activeTab !== "preventivos") return;
    const timer = setTimeout(() => {
      loadAgenda();
    }, 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, agendaEstado, agendaCustomerId, agendaQ]);

  useEffect(() => {
    if (activeTab === "instituciones" || activeTab === "preventivos") loadInstituciones();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  useEffect(() => {
    if (!addManagedDeviceOpen) return;
    if (sortedInstituciones.length > 0 || institucionesLoading) return;
    loadInstituciones();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addManagedDeviceOpen, sortedInstituciones.length, institucionesLoading]);

  useEffect(() => {
    updateSearchParam("institucion_id", selectedInstitucionId || "");
    if (!selectedInstitucionId) {
      setInstPlan(null);
      setInstRevisiones([]);
      return;
    }
    if (activeTab === "instituciones") loadInstitucionRevisiones(selectedInstitucionId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedInstitucionId, activeTab]);

  const openDevicePlanModal = (row) => {
    setPlanErr("");
    setPlanModalCtx({
      scope: "device",
      id: row.id,
      title: `Configurar preventivo - Equipo #${row.id}`,
      isEdit: !!row.preventivo_plan_id,
      initialPlan: row.preventivo_plan_id
        ? {
            periodicidad_valor: row.preventivo_periodicidad_valor,
            periodicidad_unidad: row.preventivo_periodicidad_unidad,
            aviso_anticipacion_dias: row.preventivo_aviso_dias,
            ultima_revision_fecha: row.preventivo_ultima_revision,
            proxima_revision_fecha: row.preventivo_proxima_revision,
            activa: true,
            observaciones: "",
          }
        : null,
    });
  };

  const openCustomerPlanModal = (inst) => {
    setPlanErr("");
    const plan = inst?.plan || null;
    setPlanModalCtx({
      scope: "customer",
      id: inst?.customer_id,
      title: `Plan institucional - ${inst?.razon_social || "Institucion"}`,
      isEdit: !!plan?.id,
      initialPlan: plan,
    });
  };

  const savePlan = async (payload) => {
    if (!planModalCtx) return;
    try {
      setPlanSaving(true);
      setPlanErr("");
      if (planModalCtx.scope === "device") {
        if (planModalCtx.isEdit) await patchDevicePreventivoPlan(planModalCtx.id, payload);
        else await postDevicePreventivoPlan(planModalCtx.id, payload);
        setReloadDevicesKey(Date.now());
      } else {
        if (planModalCtx.isEdit) await patchCustomerPreventivoPlan(planModalCtx.id, payload);
        else await postCustomerPreventivoPlan(planModalCtx.id, payload);
        await loadInstituciones();
        if (selectedInstitucionId) await loadInstitucionRevisiones(selectedInstitucionId);
      }
      setPlanModalCtx(null);
      if (activeTab === "preventivos") loadAgenda();
    } catch (e) {
      setPlanErr(e?.message || "No se pudo guardar el plan preventivo.");
    } finally {
      setPlanSaving(false);
    }
  };

  const saveDeviceRevision = async (form) => {
    if (!deviceRevisionCtx) return;
    try {
      setDeviceRevisionSaving(true);
      setDeviceRevisionErr("");
      await postDevicePreventivoRevision(deviceRevisionCtx.id, form);
      setDeviceRevisionCtx(null);
      setReloadDevicesKey(Date.now());
      if (activeTab === "preventivos") loadAgenda();
    } catch (e) {
      setDeviceRevisionErr(e?.message || "No se pudo registrar la revision.");
    } finally {
      setDeviceRevisionSaving(false);
    }
  };

  const onSelectExistingPreventivoDevice = (row) => {
    setAddPreventivoEquipoOpen(false);
    openDevicePlanModal(row);
  };

  const onCreateManagedDevice = async (form) => {
    if (!form?.customer_id) {
      setAddManagedDeviceErr("Debes seleccionar una institucion.");
      return;
    }
    if (!form?.marca_id) {
      setAddManagedDeviceErr("Debes seleccionar una marca valida.");
      return;
    }
    if (!form?.modelo_id) {
      setAddManagedDeviceErr("Debes seleccionar un modelo.");
      return;
    }
    if (!(form?.numero_serie || "").trim() && !(form?.numero_interno || "").trim()) {
      setAddManagedDeviceErr("Debes cargar numero de serie o numero interno.");
      return;
    }
    let alquilerA = "";
    if (form?.alquilado) {
      if (!form?.alquiler_customer_id) {
        setAddManagedDeviceErr("Debes seleccionar a que cliente esta alquilado el equipo.");
        return;
      }
      const alquilerCustomer = sortedInstituciones.find(
        (c) => String(c.customer_id) === String(form.alquiler_customer_id)
      );
      if (!alquilerCustomer?.razon_social) {
        setAddManagedDeviceErr("El cliente seleccionado para alquiler no es valido.");
        return;
      }
      alquilerA = String(alquilerCustomer.razon_social || "").trim();
    }
    try {
      setAddManagedDeviceSaving(true);
      setAddManagedDeviceErr("");
      const res = await postDeviceDirectCreate({
        customer_id: Number(form.customer_id),
        tipo_equipo: (form.tipo_equipo || "").trim(),
        marca_id: Number(form.marca_id),
        model_id: Number(form.modelo_id),
        variante: (form.variante || "").trim(),
        numero_serie: (form.numero_serie || "").trim(),
        numero_interno: (form.numero_interno || "").trim(),
        alquilado: !!form.alquilado,
        alquiler_a: alquilerA,
      });
      const created = res?.device || null;
      setAddManagedDeviceOpen(false);
      setAddPreventivoEquipoOpen(false);
      await loadDevices(1, { reset: true });
      await loadAgenda();
      if (created?.id && addManagedDeviceContext === "preventivos") {
        openDevicePlanModal(created);
      } else if (created?.id) {
        updateSearchParam("device_id", created.id);
        setActiveTab("equipos");
      }
      setAddManagedDeviceContext("general");
    } catch (e) {
      setAddManagedDeviceErr(e?.message || "No se pudo crear el equipo sin ingreso.");
    } finally {
      setAddManagedDeviceSaving(false);
    }
  };

  const runMergeSearch = async () => {
    const term = (mergeSearch || "").trim();
    if (!term) {
      setMergeSearchResults([]);
      setMergeSearchErr("Ingresa un N/S o numero interno para buscar.");
      return;
    }
    try {
      setMergeSearching(true);
      setMergeSearchErr("");
      const res = await getDevices({ q: term, page: 1, page_size: 20, sort: "id" });
      const items = Array.isArray(res) ? res : (res.items || []);
      const filtered = items.filter((item) => item.id !== mergeEquipo1?.id);
      setMergeSearchResults(filtered);
      if (!filtered.length) setMergeSearchErr("No hay resultados para esa busqueda.");
    } catch (e) {
      setMergeSearchErr(e?.message || "No se pudo buscar el equipo.");
      setMergeSearchResults([]);
    } finally {
      setMergeSearching(false);
    }
  };

  const selectedInstState = selectedInstitucion?.preventivo_estado || mergedInstPlan?.preventivo_estado || "sin_plan";
  const selectedInstDraftId = selectedInstitucion?.borrador_revision_id || (instRevisiones || []).find((r) => r.estado === "borrador")?.id;

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="h1">Equipos</div>
          <p className="text-sm text-gray-600">
            Gestion de equipos, mantenimientos preventivos e instituciones.
          </p>
        </div>
        {canEdit && (
          <button
            className="btn"
            onClick={() => {
              setAddManagedDeviceErr("");
              setAddManagedDeviceContext("general");
              setAddManagedDeviceOpen(true);
            }}
          >
            Agregar equipo
          </button>
        )}
      </div>

      <Tabs value={activeTab} onChange={setActiveTab} items={TAB_ITEMS} />

      {activeTab === "equipos" && (
        <>
          {err && <div className="bg-red-100 border border-red-300 text-red-800 p-2 rounded mb-3">{err}</div>}

          <div className="flex flex-wrap items-center gap-2 mb-3">
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Buscar por N/S, MG, cliente, marca, modelo..."
              className="border rounded p-2 w-full max-w-md"
            />
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
                    <SortableTh label="Ultimo cliente/Dueno" field="cliente" sort={sort} setSort={setSort} />
                    <SortableTh label="N/S" field="ns" sort={sort} setSort={setSort} />
                    <SortableTh label="MG" field="mg" sort={sort} setSort={setSort} />
                    <SortableTh label="Marca" field="marca" sort={sort} setSort={setSort} />
                    <SortableTh label="Modelo" field="modelo" sort={sort} setSort={setSort} />
                    <SortableTh label="Ubicacion" field="ubicacion" sort={sort} setSort={setSort} />
                    <th className="p-2">Alquiler</th>
                    <th className="p-2">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const isHighlight = highlightId && String(highlightId) === String(row.id);
                    return (
                      <tr key={row.id} className={`hover:bg-gray-50 ${isHighlight ? "bg-amber-50" : ""}`}>
                        <td className="p-2 font-mono text-xs">{row.id}</td>
                        <td className="p-2"><PropiedadBadge row={row} /></td>
                        <td className="p-2">
                          <div className="font-medium">{row.last_customer_nombre || row.customer_nombre || "-"}</div>
                          {row.last_ingreso_id ? <div className="text-xs text-gray-500">Ultimo ingreso #{row.last_ingreso_id}</div> : null}
                          {row.es_propietario_mg && <div className="text-xs text-gray-500">Dueno base (propio MG/BIO)</div>}
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
                              button={({ toggle }) => (
                                <button onClick={toggle} className="px-2 py-1 rounded hover:bg-gray-100" aria-label="Acciones">
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
                Mostrando {rows.length} {hasNext ? "(hay mas, baja para cargar...)" : ""}
              </div>
              <div ref={sentinelRef} style={{ height: 1 }} />
              {loadingMore && <div className="text-xs text-gray-500 mt-2">Cargando mas...</div>}
            </div>
          )}
        </>
      )}

      {activeTab === "preventivos" && (
        <>
          {agendaErr && <div className="bg-red-100 border border-red-300 text-red-800 p-2 rounded mb-3">{agendaErr}</div>}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
            <div className="border rounded p-3 bg-red-50"><div className="text-xs text-gray-600">Vencidos</div><div className="text-xl font-semibold text-red-700">{agendaCounts.vencido || 0}</div></div>
            <div className="border rounded p-3 bg-amber-50"><div className="text-xs text-gray-600">Proximos</div><div className="text-xl font-semibold text-amber-700">{agendaCounts.proximo || 0}</div></div>
            <div className="border rounded p-3 bg-slate-50"><div className="text-xs text-gray-600">Sin plan</div><div className="text-xl font-semibold text-slate-700">{agendaCounts.sin_plan || 0}</div></div>
            <div className="border rounded p-3 bg-emerald-50"><div className="text-xs text-gray-600">Total</div><div className="text-xl font-semibold text-emerald-700">{agendaCounts.total || 0}</div></div>
          </div>

          <div className="flex flex-wrap items-center gap-2 mb-3">
            <select className="border rounded p-2" value={agendaEstado} onChange={(e) => setAgendaEstado(e.target.value)}>
              <option value="">Estado: todos</option>
              <option value="vencido">Vencido</option>
              <option value="proximo">Proximo</option>
              <option value="sin_plan">Sin plan</option>
              <option value="al_dia">Al dia</option>
            </select>
            <select className="border rounded p-2" value={agendaCustomerId} onChange={(e) => setAgendaCustomerId(e.target.value)}>
              <option value="">Institucion: todas</option>
              {sortedInstituciones.map((inst) => (
                <option key={inst.customer_id} value={inst.customer_id}>{inst.razon_social}</option>
              ))}
            </select>
            <input
              type="text"
              className="border rounded p-2 w-full max-w-md"
              value={agendaQ}
              onChange={(e) => setAgendaQ(e.target.value)}
              placeholder="Buscar por cliente, codigo, marca, modelo, N/S"
            />
            {canPlanEdit && (
              <button
                className="btn"
                onClick={() => {
                  setAddManagedDeviceErr("");
                  setAddPreventivoEquipoOpen(true);
                }}
              >
                Sumar preventivo
              </button>
            )}
          </div>

          {agendaLoading ? (
            "Cargando agenda..."
          ) : agendaItems.length === 0 ? (
            <div className="text-sm text-gray-500">Sin resultados.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left">
                    <th className="p-2">Cliente</th>
                    <th className="p-2">Equipo</th>
                    <th className="p-2">Proxima</th>
                    <th className="p-2">Estado</th>
                    <th className="p-2">Accion</th>
                  </tr>
                </thead>
                <tbody>
                  {agendaItems.map((item, idx) => (
                    <tr key={`${item.plan_id || "sp"}-${item.device_id || idx}-${idx}`} className="border-t">
                      <td className="p-2">{item.customer_nombre || "-"}</td>
                      <td className="p-2">{item.equipo_label || `${item.marca || ""} ${item.modelo || ""}`.trim() || "-"}</td>
                      <td className="p-2">{fmtDate(item.proxima_revision_fecha)}</td>
                      <td className="p-2"><PreventivoBadge estado={item.preventivo_estado} dias={item.preventivo_dias_restantes} /></td>
                      <td className="p-2">
                        {item.plan_id ? (
                          <button
                            className="px-2 py-1 rounded border text-xs hover:bg-gray-50"
                            onClick={() => {
                              const row =
                                rows.find((r) => String(r.id) === String(item.device_id)) || {
                                  id: item.device_id,
                                  marca: item.marca,
                                  modelo: item.modelo,
                                  preventivo_plan_id: item.plan_id,
                                };
                              setDeviceRevisionCtx(row);
                            }}
                          >
                            Registrar revision
                          </button>
                        ) : (
                          <div className="flex items-center gap-1">
                            {canPlanEdit && (
                              <button
                                className="px-2 py-1 rounded border text-xs hover:bg-gray-50"
                                onClick={() =>
                                  openDevicePlanModal({
                                    id: item.device_id,
                                    marca: item.marca,
                                    modelo: item.modelo,
                                    preventivo_plan_id: null,
                                  })
                                }
                              >
                                Configurar plan
                              </button>
                            )}
                            <button className="px-2 py-1 rounded border text-xs hover:bg-gray-50" onClick={() => setActiveTab("equipos")}>
                              Ir a equipo
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {activeTab === "instituciones" && (
        <>
          {institucionesErr && <div className="bg-red-100 border border-red-300 text-red-800 p-2 rounded mb-3">{institucionesErr}</div>}
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="text-sm">Institucion:</span>
            <select className="border rounded p-2 min-w-72" value={selectedInstitucionId} onChange={(e) => setSelectedInstitucionId(e.target.value)}>
              <option value="">Elegi una institucion</option>
              {sortedInstituciones.map((inst) => (
                <option key={inst.customer_id} value={inst.customer_id}>
                  {inst.razon_social} {inst.cod_empresa ? `(${inst.cod_empresa})` : ""}
                </option>
              ))}
            </select>
            {canPlanEdit && (
              <button className="btn" onClick={() => { setAddInstitutionErr(""); setAddInstitutionOpen(true); }}>
                Agregar institucion
              </button>
            )}
          </div>

          {!selectedInstitucionId ? (
            <div className="text-sm text-gray-500">Selecciona una institucion para ver su plan y revisiones.</div>
          ) : (
            <>
              {selectedInstState === "vencido" || selectedInstState === "proximo" || selectedInstDraftId ? (
                <div className="border rounded p-3 mb-3 bg-amber-50 border-amber-200 flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm text-amber-900">
                    {selectedInstDraftId
                      ? "Hay una revision institucional en borrador pendiente de cierre."
                      : "Esta institucion requiere actualizacion de revision preventiva."}
                  </div>
                  {canRevisionMutate && (
                    <button
                      className="px-3 py-1.5 rounded bg-amber-600 text-white hover:bg-amber-700"
                      onClick={() => {
                        if (selectedInstDraftId) openRevision(selectedInstDraftId);
                        else startOrContinueInstitutionRevision(selectedInstitucionId);
                      }}
                    >
                      {selectedInstDraftId ? "Continuar revision pendiente" : "Actualizar revision ahora"}
                    </button>
                  )}
                </div>
              ) : null}

              <div className="border rounded p-3 mb-3">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <div className="font-medium">Plan preventivo institucional</div>
                  <div className="flex items-center gap-2">
                    {canPlanEdit && (
                      <button className="px-2 py-1 rounded border text-xs hover:bg-gray-50" onClick={() => openCustomerPlanModal(selectedInstitucion)}>
                        {mergedInstPlan ? "Editar plan" : "Crear plan"}
                      </button>
                    )}
                    {canRevisionMutate && mergedInstPlan && (
                      <>
                        <button className="px-2 py-1 rounded border text-xs hover:bg-gray-50" onClick={() => startOrContinueInstitutionRevision(selectedInstitucionId)}>
                          Nueva revision
                        </button>
                        <button className="px-2 py-1 rounded border text-xs hover:bg-gray-50" onClick={() => startOrContinueInstitutionRevision(selectedInstitucionId)}>
                          Actualizar revision ahora
                        </button>
                      </>
                    )}
                  </div>
                </div>
                {!mergedInstPlan ? (
                  <div className="text-sm text-gray-500">Sin plan activo.</div>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                    <div><div className="text-xs text-gray-500">Periodicidad</div><div>{mergedInstPlan.periodicidad_valor} {mergedInstPlan.periodicidad_unidad}</div></div>
                    <div><div className="text-xs text-gray-500">Ultima</div><div>{fmtDate(mergedInstPlan.ultima_revision_fecha)}</div></div>
                    <div><div className="text-xs text-gray-500">Proxima</div><div>{fmtDate(mergedInstPlan.proxima_revision_fecha)}</div></div>
                    <div><div className="text-xs text-gray-500">Aviso</div><div>{mergedInstPlan.aviso_anticipacion_dias} dias</div></div>
                    <div><div className="text-xs text-gray-500">Estado</div><div><PreventivoBadge estado={selectedInstState} dias={selectedInstitucion?.preventivo_dias_restantes || mergedInstPlan?.preventivo_dias_restantes} /></div></div>
                  </div>
                )}
              </div>

              {instRevisionesErr && <div className="bg-red-100 border border-red-300 text-red-800 p-2 rounded mb-3">{instRevisionesErr}</div>}

              <div className="border rounded p-3 mb-3">
                <div className="font-medium mb-2">Historial de revisiones</div>
                {instRevisionesLoading ? (
                  "Cargando revisiones..."
                ) : instRevisiones.length === 0 ? (
                  <div className="text-sm text-gray-500">Sin revisiones.</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="text-left">
                          <th className="p-2">ID</th>
                          <th className="p-2">Estado</th>
                          <th className="p-2">Programada</th>
                          <th className="p-2">Realizada</th>
                          <th className="p-2">Items</th>
                          <th className="p-2">Accion</th>
                        </tr>
                      </thead>
                      <tbody>
                        {instRevisiones.map((rev) => (
                          <tr key={rev.id} className="border-t">
                            <td className="p-2">#{rev.id}</td>
                            <td className="p-2">{rev.estado}</td>
                            <td className="p-2">{fmtDate(rev.fecha_programada)}</td>
                            <td className="p-2">{fmtDate(rev.fecha_realizada)}</td>
                            <td className="p-2">{rev.total_items || 0}</td>
                            <td className="p-2">
                              <button className="px-2 py-1 rounded border text-xs hover:bg-gray-50" onClick={() => openRevision(rev.id)}>
                                {rev.estado === "borrador" ? "Continuar" : "Ver"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {revisionOpenId && (
                <div className="border rounded p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <div className="font-medium">Editor revision #{revisionOpenId}</div>
                    <button className="px-2 py-1 rounded border text-xs hover:bg-gray-50" onClick={() => { setRevisionOpenId(null); setRevisionData(null); }}>
                      Cerrar editor
                    </button>
                  </div>
                  {revisionErr && <div className="bg-red-100 border border-red-300 text-red-800 p-2 rounded mb-2">{revisionErr}</div>}
                  {revisionLoading || !revisionData ? (
                    "Cargando revision..."
                  ) : (
                    <>
                      <div className="text-sm text-gray-600 mb-3">
                        Estado: <b>{revisionData.revision?.estado}</b> | Programada: {fmtDate(revisionData.revision?.fecha_programada)} | Realizada: {fmtDate(revisionData.revision?.fecha_realizada)}
                      </div>

                      <div className="overflow-x-auto">
                        <table className="min-w-full text-xs">
                          <thead>
                            <tr className="text-left">
                              <th className="p-2">Item</th>
                              <th className="p-2">Estado</th>
                              <th className="p-2">Motivo no control</th>
                              <th className="p-2">Ubicacion</th>
                              <th className="p-2">Acc. cambiados</th>
                              <th className="p-2">Detalle accesorios</th>
                              <th className="p-2">Observaciones</th>
                              <th className="p-2">Arrastrar proxima</th>
                              <th className="p-2">Guardar</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(revisionData.items || []).map((item) => (
                              <tr key={item.id} className="border-t">
                                <td className="p-2 min-w-56">{item.equipo_snapshot || "-"}</td>
                                <td className="p-2">
                                  <select
                                    className="border rounded p-1"
                                    value={item.estado_item || "pendiente"}
                                    disabled={revisionData.revision?.estado !== "borrador"}
                                    onChange={(e) => {
                                      const val = e.target.value;
                                      setRevisionData((prev) => ({
                                        ...prev,
                                        items: prev.items.map((it) =>
                                          it.id === item.id ? { ...it, estado_item: val, arrastrar_proxima: val === "retirado" ? false : it.arrastrar_proxima } : it
                                        ),
                                      }));
                                    }}
                                  >
                                    {ITEM_STATES.map((st) => <option key={st.value} value={st.value}>{st.label}</option>)}
                                  </select>
                                </td>
                                <td className="p-2">
                                  <input
                                    className="border rounded p-1 w-44"
                                    value={item.motivo_no_control || ""}
                                    disabled={revisionData.revision?.estado !== "borrador"}
                                    onChange={(e) =>
                                      setRevisionData((prev) => ({
                                        ...prev,
                                        items: prev.items.map((it) => (it.id === item.id ? { ...it, motivo_no_control: e.target.value } : it)),
                                      }))
                                    }
                                  />
                                </td>
                                <td className="p-2"><input className="border rounded p-1 w-36" value={item.ubicacion_detalle || ""} disabled={revisionData.revision?.estado !== "borrador"} onChange={(e) => setRevisionData((prev) => ({ ...prev, items: prev.items.map((it) => it.id === item.id ? { ...it, ubicacion_detalle: e.target.value } : it) }))} /></td>
                                <td className="p-2 text-center"><input type="checkbox" checked={!!item.accesorios_cambiados} disabled={revisionData.revision?.estado !== "borrador"} onChange={(e) => setRevisionData((prev) => ({ ...prev, items: prev.items.map((it) => it.id === item.id ? { ...it, accesorios_cambiados: e.target.checked } : it) }))} /></td>
                                <td className="p-2"><input className="border rounded p-1 w-44" value={item.accesorios_detalle || ""} disabled={revisionData.revision?.estado !== "borrador"} onChange={(e) => setRevisionData((prev) => ({ ...prev, items: prev.items.map((it) => it.id === item.id ? { ...it, accesorios_detalle: e.target.value } : it) }))} /></td>
                                <td className="p-2"><input className="border rounded p-1 w-44" value={item.notas || ""} disabled={revisionData.revision?.estado !== "borrador"} onChange={(e) => setRevisionData((prev) => ({ ...prev, items: prev.items.map((it) => it.id === item.id ? { ...it, notas: e.target.value } : it) }))} /></td>
                                <td className="p-2 text-center"><input type="checkbox" checked={!!item.arrastrar_proxima} disabled={revisionData.revision?.estado !== "borrador"} onChange={(e) => setRevisionData((prev) => ({ ...prev, items: prev.items.map((it) => it.id === item.id ? { ...it, arrastrar_proxima: e.target.checked } : it) }))} /></td>
                                <td className="p-2">
                                  <button
                                    className="px-2 py-1 rounded border text-xs hover:bg-gray-50 disabled:opacity-50"
                                    disabled={revisionData.revision?.estado !== "borrador" || savingItemId === item.id}
                                    onClick={async () => {
                                      try {
                                        setSavingItemId(item.id);
                                        const payload = {
                                          estado_item: item.estado_item,
                                          motivo_no_control: item.motivo_no_control || "",
                                          ubicacion_detalle: item.ubicacion_detalle || "",
                                          accesorios_cambiados: !!item.accesorios_cambiados,
                                          accesorios_detalle: item.accesorios_detalle || "",
                                          notas: item.notas || "",
                                          arrastrar_proxima: !!item.arrastrar_proxima,
                                          equipo_snapshot: item.equipo_snapshot || "",
                                          serie_snapshot: item.serie_snapshot || "",
                                          interno_snapshot: item.interno_snapshot || "",
                                          orden: item.orden || 1,
                                        };
                                        const res = await patchPreventivoRevisionItem(revisionOpenId, item.id, payload);
                                        setRevisionData((prev) => ({
                                          ...prev,
                                          items: prev.items.map((it) => (it.id === item.id ? { ...it, ...(res?.item || {}) } : it)),
                                        }));
                                      } catch (e) {
                                        setRevisionErr(e?.message || "No se pudo guardar item.");
                                      } finally {
                                        setSavingItemId(null);
                                      }
                                    }}
                                  >
                                    Guardar
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {revisionData.revision?.estado === "borrador" && (
                        <>
                          <div className="flex flex-wrap items-center gap-2 mt-3">
                            <input
                              type="text"
                              className="border rounded p-2 w-full max-w-md"
                              placeholder="Nuevo item libre (equipo/item)"
                              value={newItemName}
                              onChange={(e) => setNewItemName(e.target.value)}
                            />
                            <button
                              className="px-3 py-1.5 rounded border hover:bg-gray-50"
                              onClick={async () => {
                                const txt = (newItemName || "").trim();
                                if (!txt) return;
                                try {
                                  await postPreventivoRevisionItem(revisionOpenId, { equipo_snapshot: txt, estado_item: "pendiente", arrastrar_proxima: true });
                                  setNewItemName("");
                                  await openRevision(revisionOpenId);
                                } catch (e) {
                                  setRevisionErr(e?.message || "No se pudo agregar item.");
                                }
                              }}
                            >
                              Agregar item
                            </button>
                          </div>

                          <div className="border rounded p-3 mt-3 bg-gray-50">
                            <div className="font-medium mb-2">Cerrar revision</div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                              <label className="block">
                                <div className="text-xs text-gray-600 mb-1">Fecha realizada</div>
                                <input type="date" className="border rounded p-2 w-full" value={closeRevisionForm.fecha_realizada} onChange={(e) => setCloseRevisionForm((prev) => ({ ...prev, fecha_realizada: e.target.value }))} />
                              </label>
                              <label className="block">
                                <div className="text-xs text-gray-600 mb-1">Resumen</div>
                                <input type="text" className="border rounded p-2 w-full" value={closeRevisionForm.resumen} onChange={(e) => setCloseRevisionForm((prev) => ({ ...prev, resumen: e.target.value }))} />
                              </label>
                            </div>
                            <div className="flex justify-end mt-3">
                              <button
                                className="px-3 py-1.5 rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
                                disabled={closingRevision}
                                onClick={async () => {
                                  try {
                                    setClosingRevision(true);
                                    await postPreventivoRevisionCerrar(revisionOpenId, {
                                      fecha_realizada: closeRevisionForm.fecha_realizada || todayISO(),
                                      resumen: closeRevisionForm.resumen || "",
                                    });
                                    await openRevision(revisionOpenId);
                                    await loadInstituciones();
                                    if (selectedInstitucionId) await loadInstitucionRevisiones(selectedInstitucionId);
                                    if (activeTab === "preventivos") await loadAgenda();
                                  } catch (e) {
                                    setRevisionErr(e?.message || "No se pudo cerrar la revision.");
                                  } finally {
                                    setClosingRevision(false);
                                  }
                                }}
                              >
                                Cerrar revision
                              </button>
                            </div>
                          </div>
                        </>
                      )}
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}

      {editRow && (
        <EditModal row={editRow} canEdit={canEdit} onClose={() => setEditRow(null)} onSaved={() => setReloadDevicesKey(Date.now())} />
      )}

      {planModalCtx && (
        <PreventivoPlanModal
          title={planModalCtx.title}
          initialPlan={planModalCtx.initialPlan}
          onClose={() => setPlanModalCtx(null)}
          onSubmit={savePlan}
          saving={planSaving}
          error={planErr}
        />
      )}

      {deviceRevisionCtx && (
        <DeviceRevisionModal
          row={deviceRevisionCtx}
          onClose={() => setDeviceRevisionCtx(null)}
          onSubmit={saveDeviceRevision}
          saving={deviceRevisionSaving}
          error={deviceRevisionErr}
        />
      )}

      {addInstitutionOpen && (
        <AddInstitutionModal
          onClose={() => setAddInstitutionOpen(false)}
          saving={addInstitutionSaving}
          error={addInstitutionErr}
          onSubmit={async (form) => {
            if (!form.razon_social.trim() || !form.cod_empresa.trim()) {
              setAddInstitutionErr("Razon social y codigo empresa son requeridos.");
              return;
            }
            try {
              setAddInstitutionSaving(true);
              setAddInstitutionErr("");
              await postCliente({
                razon_social: form.razon_social.trim(),
                cod_empresa: form.cod_empresa.trim(),
                telefono: form.telefono.trim() || null,
                telefono_2: form.telefono_2.trim() || null,
                email: form.email.trim() || null,
              });
              setAddInstitutionOpen(false);
              await loadInstituciones();
            } catch (e) {
              setAddInstitutionErr(e?.message || "No se pudo crear la institucion.");
            } finally {
              setAddInstitutionSaving(false);
            }
          }}
        />
      )}

      {addPreventivoEquipoOpen && (
        <AddPreventivoEquipoModal
          onClose={() => setAddPreventivoEquipoOpen(false)}
          onSelect={onSelectExistingPreventivoDevice}
          onCreateManaged={() => {
            setAddManagedDeviceErr("");
            setAddManagedDeviceContext("preventivos");
            setAddPreventivoEquipoOpen(false);
            setAddManagedDeviceOpen(true);
          }}
        />
      )}

      {addManagedDeviceOpen && (
        <AddManagedDeviceModal
          customers={sortedInstituciones}
          onClose={() => setAddManagedDeviceOpen(false)}
          onSubmit={onCreateManagedDevice}
          saving={addManagedDeviceSaving}
          error={addManagedDeviceErr}
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
                <button className="px-3 py-1.5 rounded border text-sm hover:bg-gray-50" onClick={() => setMergeStep(1)} disabled={mergeSaving}>
                  Cambiar equipo 2
                </button>
              )}
            </div>

            {mergeErr && <div className="bg-red-100 text-red-800 border border-red-300 rounded p-2 mb-3">{mergeErr}</div>}

            {mergeStep === 1 ? (
              <div className="space-y-3">
                <div className="text-sm">
                  <div className="text-gray-700">Equipo 1</div>
                  <div className="text-gray-900 font-medium">#{mergeEquipo1.id} - NS: {mergeEquipo1.numero_serie || "-"} - MG: {mergeEquipo1.numero_interno || "-"}</div>
                </div>
                <label className="block">
                  <div className="text-sm text-gray-700 mb-1">Buscar equipo 2 (N/S o MG)</div>
                  <div className="flex items-center gap-2">
                    <input type="text" value={mergeSearch} onChange={(e) => setMergeSearch(e.target.value)} className="border rounded p-2 w-full" placeholder="Ej: MG 1234 o NS 00123" disabled={mergeSearching} onKeyDown={(e) => { if (e.key === "Enter") runMergeSearch(); }} />
                    <button className="btn" onClick={runMergeSearch} disabled={mergeSearching}>Buscar</button>
                  </div>
                </label>
                {mergeSearchErr && <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">{mergeSearchErr}</div>}
                <div className="border rounded overflow-auto max-h-72">
                  {mergeSearching ? "Buscando..." : mergeSearchResults.map((row) => (
                    <div key={row.id} className="p-2 border-t flex items-center justify-between">
                      <div className="text-xs">#{row.id} - NS: {row.numero_serie || "-"} - MG: {row.numero_interno || "-"}</div>
                      <button className="px-2 py-1 rounded border text-xs" onClick={() => selectMergeEquipo2(row)}>Seleccionar</button>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-4 text-sm">
                {mergeEquipo2 ? (
                  <>
                    <div className="border rounded p-3">
                      <div className="text-sm font-medium mb-2">N/S final</div>
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="merge-ns"
                          value="equipo1"
                          checked={mergeNsChoice === "equipo1"}
                          onChange={() => setMergeNsChoice("equipo1")}
                        />
                        Equipo 1: {mergeEquipo1?.numero_serie || "(vacio)"}
                      </label>
                      <label className="flex items-center gap-2 mt-2">
                        <input
                          type="radio"
                          name="merge-ns"
                          value="equipo2"
                          checked={mergeNsChoice === "equipo2"}
                          onChange={() => setMergeNsChoice("equipo2")}
                        />
                        Equipo 2: {mergeEquipo2?.numero_serie || "(vacio)"}
                      </label>
                    </div>
                    <div className="border rounded p-3">
                      <div className="text-sm font-medium mb-2">MG final</div>
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="merge-mg"
                          value="equipo1"
                          checked={mergeMgChoice === "equipo1"}
                          onChange={() => setMergeMgChoice("equipo1")}
                        />
                        Equipo 1: {mergeEquipo1?.numero_interno || "(vacio)"}
                      </label>
                      <label className="flex items-center gap-2 mt-2">
                        <input
                          type="radio"
                          name="merge-mg"
                          value="equipo2"
                          checked={mergeMgChoice === "equipo2"}
                          onChange={() => setMergeMgChoice("equipo2")}
                        />
                        Equipo 2: {mergeEquipo2?.numero_interno || "(vacio)"}
                      </label>
                    </div>
                  </>
                ) : (
                  <div>Selecciona equipo 2.</div>
                )}
              </div>
            )}

            <div className="flex justify-between items-center mt-4">
              <button className="px-3 py-1.5 rounded border" onClick={resetMergeState} disabled={mergeSaving}>Cancelar</button>
              {mergeStep === 2 && (
                <button
                  className="px-3 py-1.5 rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
                  disabled={!canSubmitMerge}
                  onClick={async () => {
                    try {
                      setMergeSaving(true);
                      setMergeErr("");
                      await postDevicesMerge({
                        target_id: mergeEquipo1.id,
                        source_id: mergeEquipo2.id,
                        numero_serie: mergeNsFinalValue,
                        numero_interno: mergeMgFinalValue,
                      });
                      resetMergeState();
                      setReloadDevicesKey(Date.now());
                    } catch (e) {
                      setMergeErr(e?.message || "No se pudo unificar.");
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
    else if (isDesc) setSort("id");
    else setSort(field);
  };
  return (
    <th className="p-2 cursor-pointer select-none" onClick={next}>
      <span className="inline-flex items-center gap-1">
        {label}
        {isAsc && <span aria-label="asc">^</span>}
        {isDesc && <span aria-label="desc">v</span>}
      </span>
    </th>
  );
}
