import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { isAdmin, isJefe, isJefeVeedor, isTecnico } from "../lib/authz";
import { formatMoney, norm } from "../lib/ui-helpers";
import * as XLSX from "xlsx";
import {
  getRepuestos,
  getRepuestosConfig,
  getRepuestoDetalle,
  postRepuesto,
  patchRepuesto,
  patchRepuestosConfig,
  getRepuestosMovimientos,
  getRepuestosCambios,
  getRepuestosSubrubros,
  getRepuestosStockPermisos,
  postRepuestosStockPermiso,
  patchRepuestosStockPermiso,
  getTecnicos,
  getProveedoresExternos,
  deleteRepuesto,
} from "../lib/api";

const Input = (p) => <input {...p} className="border rounded p-2 w-full" />;

const Chip = ({ children, tone = "gray" }) => {
  const tones = {
    gray: "bg-gray-100 text-gray-700 border-gray-200",
    yellow: "bg-yellow-100 text-yellow-800 border-yellow-200",
    red: "bg-red-100 text-red-700 border-red-200",
    green: "bg-green-100 text-green-700 border-green-200",
    blue: "bg-blue-100 text-blue-700 border-blue-200",
  };
  const cls = tones[tone] || tones.gray;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs border ${cls}`}>
      {children}
    </span>
  );
};

const Tabs = ({ value, onChange, items }) => (
  <div className="border-b mb-3 flex flex-wrap gap-2">
    {items.map((it) => (
      <button
        key={it.value}
        className={`px-3 py-1.5 rounded-t ${value === it.value ? "bg-white border border-b-0" : "text-gray-600 hover:text-black"}`}
        onClick={() => onChange(it.value)}
        type="button"
      >
        {it.label}
      </button>
    ))}
  </div>
);

const formatTs = (s) => (s ? new Date(s).toLocaleString("es-AR") : "-");

const DETAIL_FIELDS = [
  "nombre",
  "tipo_articulo",
  "categoria",
  "unidad_medida",
  "marca_fabricante",
  "nro_parte",
  "ubicacion_deposito",
  "estado",
  "notas",
  "fecha_ultima_compra",
  "fecha_ultimo_conteo",
  "fecha_vencimiento",
];

const EMPTY_ADD_FORM = {
  subrubro_codigo: "",
  nombre: "",
  tipo_articulo: "",
  categoria: "",
  ubicacion_deposito: "",
  stock_on_hand: "",
  stock_min: "",
  multiplicador: "",
  costo_usd: "",
};


/**
 * Repuestos component - Manages spare parts inventory system
 * 
 * Provides comprehensive spare parts (repuestos) management including:
 * - Stock tracking with alert levels and negative stock detection
 * - Dynamic pricing based on USD exchange rate and multipliers
 * - Permission system for technicians to edit stock
 * - Supplier management with lead times and priorities
 * - Movement history and change tracking
 * - Export to CSV and Excel
 * - Configuration management for exchange rates and general multipliers
 * 
 * Role-based access control:
 * - Jefes (managers) and JefeVeedores: Full management access
 * - Tecnicos (technicians): Stock edit access if permitted (24h permissions)
 * - Admins: Cost visibility
 * 
 * Features:
 * - Search filtering by code or name
 * - Inline editing for stock, minimum stock, and multipliers
 * - Detailed view with tabs for specifications, suppliers, and movements
 * - Batch loading with pagination (500 items per page)
 * - Real-time validation and change tracking
 * - Temporary permission system (24-hour duration)
 * - Movement history per item
 * - Audit trail of name changes
 * 
 * @component
 * @returns {JSX.Element} The complete repuestos management interface
 * 
 * @requires useAuth - Authentication context hook
 * @requires useRef - React reference hook
 * @requires useState - React state management
 * @requires useEffect - React side effects
 * @requires useMemo - React memoization
 * @requires Fragment - React fragment for grouping
 * 
 * @example
 * import Repuestos from '@/pages/Repuestos';
 * 
 * export default function App() {
 *   return <Repuestos />;
 * }
 */
export default function Repuestos() {
  const { user } = useAuth();
  const canManage = isJefe(user) || isJefeVeedor(user);
  const isTech = isTecnico(user);
  const canSeeCosts = canManage || isAdmin(user);
  const canEditCost = canSeeCosts;

  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [orderBy, setOrderBy] = useState("codigo");
  const [orderDir, setOrderDir] = useState("desc");
  const [config, setConfig] = useState(null);
  const [history, setHistory] = useState([]);
  const [cfgForm, setCfgForm] = useState({ dolar_ars: "", multiplicador_general: "" });
  const [drafts, setDrafts] = useState({});
  const [detalles, setDetalles] = useState({});
  const [openId, setOpenId] = useState(null);
  const [movimientos, setMovimientos] = useState([]);
  const [movimientosOpen, setMovimientosOpen] = useState(false);
  const [movimientosLoading, setMovimientosLoading] = useState(false);
  const [cambios, setCambios] = useState([]);
  const [cambiosOpen, setCambiosOpen] = useState(false);
  const [cambiosLoading, setCambiosLoading] = useState(false);
  const [cambiosErr, setCambiosErr] = useState("");
  const [permisos, setPermisos] = useState([]);
  const [permisosLoading, setPermisosLoading] = useState(false);
  const [permisosErr, setPermisosErr] = useState("");
  const [permSaving, setPermSaving] = useState(false);
  const [permForm, setPermForm] = useState({ tecnico_id: "" });
  const [tecnicos, setTecnicos] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [subrubros, setSubrubros] = useState([]);
  const [subrubrosLoading, setSubrubrosLoading] = useState(false);
  const [subrubrosErr, setSubrubrosErr] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [cfgLoading, setCfgLoading] = useState(false);
  const [actionsOpen, setActionsOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [addSaving, setAddSaving] = useState(false);
  const [addForm, setAddForm] = useState(() => ({ ...EMPTY_ADD_FORM }));
  const actionsMenuRef = useRef(null);

  const filtered = useMemo(() => {
    const needle = norm(q);
    if (!needle) return items;
    return (items || []).filter((it) => {
      return (
        norm(it?.codigo || "").includes(needle) ||
        norm(it?.nombre || "").includes(needle)
      );
    });
  }, [q, items]);

  const activePerm = useMemo(() => {
    if (!isTech) return null;
    const uid = Number(user?.id || 0);
    if (!uid) return null;
    return (permisos || []).find((p) => Number(p?.tecnico_id) === uid) || null;
  }, [permisos, isTech, user?.id]);

  const canEditStock = canManage || !!activePerm;
  const canEditDetalle = canEditStock;
  const canDelete = canEditStock;
  const canAdd = canManage || (isTech && !!activePerm);
  const colCount = 6;

  async function loadConfig() {
    try {
      setErr("");
      const data = await getRepuestosConfig();
      const cfg = data?.config || null;
      setConfig(cfg);
      setHistory(data?.history || []);
      setCfgForm({
        dolar_ars: cfg?.dolar_ars != null ? String(cfg.dolar_ars) : "",
        multiplicador_general:
          cfg?.multiplicador_general != null
            ? String(cfg.multiplicador_general)
            : "",
      });
    } catch (e) {
      setErr(e?.message || "No se pudo cargar la configuracion");
    }
  }

  async function loadRepuestos() {
    try {
      setErr("");
      setLoading(true);
      const pageSize = 500;
      const all = [];
      let offset = 0;
      for (let i = 0; i < 50; i++) {
        const rows = await getRepuestos({
          limit: pageSize,
          offset,
          order: orderBy,
          dir: orderDir,
        });
        const batch = Array.isArray(rows) ? rows : [];
        all.push(...batch);
        if (batch.length < pageSize) break;
        offset += batch.length;
      }
      setItems(all);
    } catch (e) {
      setErr(e?.message || "No se pudo cargar repuestos");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadPermisos() {
    try {
      setPermisosErr("");
      setPermisosLoading(true);
      const rows = await getRepuestosStockPermisos();
      setPermisos(rows || []);
    } catch (e) {
      setPermisosErr(e?.message || "No se pudieron cargar permisos");
      setPermisos([]);
    } finally {
      setPermisosLoading(false);
    }
  }

  async function loadTecnicos() {
    if (!canManage) return;
    try {
      const rows = await getTecnicos();
      setTecnicos(rows || []);
    } catch {
      setTecnicos([]);
    }
  }

  async function loadProveedores() {
    if (!canManage) return;
    try {
      const rows = await getProveedoresExternos();
      setProveedores(rows || []);
    } catch {
      setProveedores([]);
    }
  }

  async function loadSubrubros() {
    if (!canAdd) return;
    try {
      setSubrubrosErr("");
      setSubrubrosLoading(true);
      const rows = await getRepuestosSubrubros();
      setSubrubros(rows || []);
    } catch (e) {
      setSubrubrosErr(e?.message || "No se pudieron cargar subrubros");
      setSubrubros([]);
    } finally {
      setSubrubrosLoading(false);
    }
  }

  function applyItemUpdate(updated) {
    if (!updated?.id) return;
    setItems((prev) =>
      prev.map((row) => {
        if (row.id !== updated.id) return row;
        const next = { ...row, ...updated };
        const stockOnHand = Number(next.stock_on_hand ?? 0);
        const stockMin = Number(next.stock_min ?? 0);
        next.stock_alerta = stockOnHand <= stockMin;
        next.stock_negativo = stockOnHand < 0;
        const multGeneral = Number(config?.multiplicador_general ?? 0);
        if (next.multiplicador != null && String(next.multiplicador) !== "") {
          next.multiplicador_aplicado = next.multiplicador;
        } else if (multGeneral) {
          next.multiplicador_aplicado = multGeneral;
        }
        return next;
      })
    );
  }

  function updateDetalleState(id, patch) {
    setDetalles((prev) => ({
      ...prev,
      [id]: {
        ...(prev[id] || {}),
        ...patch,
      },
    }));
  }

  function buildDetalleDraft(data) {
    const out = {};
    DETAIL_FIELDS.forEach((field) => {
      out[field] = data?.[field] ?? "";
    });
    out.costo_usd = data?.costo_usd != null ? String(data.costo_usd) : "";
    return out;
  }

  function buildProveedoresDraft(data) {
    return (data?.proveedores || []).map((p) => ({
      proveedor_id: p?.proveedor_id ?? "",
      proveedor_nombre: p?.proveedor_nombre ?? "",
      sku_proveedor: p?.sku_proveedor ?? "",
      lead_time_dias: p?.lead_time_dias ?? "",
      prioridad: p?.prioridad ?? "",
      ultima_compra: p?.ultima_compra ?? "",
    }));
  }

  async function loadDetalle(id) {
    updateDetalleState(id, { loading: true, error: "" });
    try {
      const data = await getRepuestoDetalle(id);
      updateDetalleState(id, {
        loading: false,
        data,
        draft: buildDetalleDraft(data),
        proveedoresDraft: buildProveedoresDraft(data),
        tab: "detalle",
        movs: [],
        movsLoading: false,
        movsError: "",
      });
    } catch (e) {
      updateDetalleState(id, {
        loading: false,
        error: e?.message || "No se pudo cargar el detalle",
      });
    }
  }

  function toggleDetalle(id) {
    setOpenId((prev) => (prev === id ? null : id));
    if (!detalles[id]?.data && !detalles[id]?.loading) {
      loadDetalle(id);
    }
  }

  async function saveDetalle(id) {
    if (!canEditDetalle && !canEditCost) return;
    const st = detalles[id];
    if (!st?.data || !st?.draft) return;
    const payload = {};
    DETAIL_FIELDS.forEach((field) => {
      const prevVal = st.data?.[field] ?? "";
      const nextRaw = st.draft?.[field] ?? "";
      const nextVal = field === "nombre" ? String(nextRaw).trim() : nextRaw;
      if (String(prevVal ?? "") !== String(nextVal ?? "")) {
        payload[field] = nextVal === "" ? null : nextVal;
      }
    });
    if (canEditCost && "costo_usd" in st.draft) {
      const prevCost = st.data?.costo_usd ?? "";
      const nextCost = st.draft?.costo_usd ?? "";
      if (String(prevCost ?? "") !== String(nextCost ?? "")) {
        payload.costo_usd = nextCost === "" ? null : nextCost;
      }
    }
    if (!Object.keys(payload).length) return;
    updateDetalleState(id, { savingDetalle: true });
    try {
      const updated = await patchRepuesto(id, payload);
      applyItemUpdate(updated);
      updateDetalleState(id, {
        savingDetalle: false,
        data: updated,
        draft: buildDetalleDraft(updated),
        proveedoresDraft: buildProveedoresDraft(updated),
      });
      setMsg("Repuesto actualizado");
    } catch (e) {
      updateDetalleState(id, { savingDetalle: false });
      setErr(e?.message || "No se pudo actualizar");
    }
  }

  async function saveProveedores(id) {
    if (!canManage) return;
    const st = detalles[id];
    const proveedoresDraft = st?.proveedoresDraft || [];
    const parseNum = (v) => (v === "" || v == null ? null : Number(v));
    const payload = {
      proveedores: proveedoresDraft
        .map((p) => ({
          proveedor_id: p.proveedor_id ? Number(p.proveedor_id) : undefined,
          proveedor_nombre: (p.proveedor_nombre || "").trim() || undefined,
          sku_proveedor: (p.sku_proveedor || "").trim() || undefined,
          lead_time_dias: parseNum(p.lead_time_dias),
          prioridad: parseNum(p.prioridad),
          ultima_compra: p.ultima_compra || undefined,
        }))
        .filter((p) => p.proveedor_id || p.proveedor_nombre),
    };
    updateDetalleState(id, { savingProveedores: true });
    try {
      const updated = await patchRepuesto(id, payload);
      applyItemUpdate(updated);
      updateDetalleState(id, {
        savingProveedores: false,
        data: updated,
        draft: buildDetalleDraft(updated),
        proveedoresDraft: buildProveedoresDraft(updated),
      });
      setMsg("Proveedores actualizados");
    } catch (e) {
      updateDetalleState(id, { savingProveedores: false });
      setErr(e?.message || "No se pudieron actualizar proveedores");
    }
  }

  async function loadMovimientosDetalle(id) {
    updateDetalleState(id, { movsLoading: true, movsError: "" });
    try {
      const rows = await getRepuestosMovimientos({ repuesto_id: id, limit: 50 });
      updateDetalleState(id, { movs: rows || [], movsLoading: false });
    } catch (e) {
      updateDetalleState(id, {
        movs: [],
        movsLoading: false,
        movsError: e?.message || "No se pudieron cargar movimientos",
      });
    }
  }

  async function enablePermiso() {
    if (!canManage) return;
    if (!permForm.tecnico_id) {
      setPermisosErr("Selecciona un tecnico");
      return;
    }
    try {
      setPermSaving(true);
      setPermisosErr("");
      await postRepuestosStockPermiso({ tecnico_id: permForm.tecnico_id });
      setPermForm({ tecnico_id: "" });
      await loadPermisos();
      setMsg("Permiso habilitado por 24h");
    } catch (e) {
      setPermisosErr(e?.message || "No se pudo habilitar permiso");
    } finally {
      setPermSaving(false);
    }
  }

  async function revokePermiso(id) {
    if (!canManage) return;
    try {
      setPermSaving(true);
      await patchRepuestosStockPermiso(id, { revoked: true });
      await loadPermisos();
      setMsg("Permiso revocado");
    } catch (e) {
      setPermisosErr(e?.message || "No se pudo revocar permiso");
    } finally {
      setPermSaving(false);
    }
  }

  useEffect(() => {
    loadConfig();
  }, []);

  useEffect(() => {
    loadRepuestos();
  }, [orderBy, orderDir]);

  useEffect(() => {
    loadPermisos();
    if (canManage) {
      loadTecnicos();
      loadProveedores();
    }
  }, [canManage, user?.id]);

  useEffect(() => {
    if (canAdd) {
      loadSubrubros();
    }
  }, [canAdd]);

  useEffect(() => {
    if (!actionsOpen) return;
    const onClick = (event) => {
      if (!actionsMenuRef.current) return;
      if (!actionsMenuRef.current.contains(event.target)) {
        setActionsOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [actionsOpen]);

  function resetAddForm() {
    setAddForm({ ...EMPTY_ADD_FORM });
  }

  function normalizeIntInput(value) {
    const raw = String(value ?? "");
    if (!raw) return "";
    const cleaned = raw.replace(/[^\d-]/g, "");
    if (!cleaned) return "";
    let sign = "";
    let rest = cleaned;
    if (cleaned.startsWith("-")) {
      sign = "-";
      rest = cleaned.slice(1);
    }
    rest = rest.replace(/-/g, "");
    return `${sign}${rest}`;
  }

  function downloadCSV(filename, rows) {
    const csv = rows
      .map((r) =>
        r
          .map((v) => {
            const s = String(v ?? "");
            if (s.includes('"') || s.includes(",") || s.includes("\n")) {
              return `"${s.replace(/"/g, '""')}"`;
            }
            return s;
          })
          .join(",")
      )
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function downloadXLSX(filename, rows, sheetName) {
    const workbook = XLSX.utils.book_new();
    const worksheet = XLSX.utils.aoa_to_sheet(rows);
    XLSX.utils.book_append_sheet(workbook, worksheet, sheetName || "Hoja1");
    const data = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
    const blob = new Blob([data], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function setCodigoOrder() {
    if (orderBy === "codigo" && orderDir === "desc") return;
    setOrderBy("codigo");
    setOrderDir("desc");
  }

  function toggleStockOrder() {
    if (orderBy !== "stock") {
      setOrderBy("stock");
      setOrderDir("desc");
      return;
    }
    setOrderDir((prev) => (prev === "desc" ? "asc" : "desc"));
  }

  function exportCambiosCSV() {
    const rows = [
      ["fecha", "accion", "codigo", "nombre_prev", "nombre_new", "usuario"],
      ...(cambios || []).map((c) => [
        formatTs(c.created_at),
        c.accion,
        c.codigo,
        c.nombre_prev,
        c.nombre_new,
        c.created_by_nombre || "",
      ]),
    ];
    downloadCSV("repuestos_cambios.csv", rows);
  }

  function exportRepuestosXLSX() {
    const numOrBlank = (value) => {
      if (value == null || value === "") return "";
      const num = Number(value);
      return Number.isNaN(num) ? value : num;
    };
    const rows = [
      [
        "codigo",
        "nombre",
        "multiplicador",
        "stock",
        "stock_min",
        ...(canSeeCosts ? ["costo_usd"] : []),
      ],
      ...(filtered || []).map((it) => [
        it.codigo || "",
        it.nombre || "",
        numOrBlank(it.multiplicador_aplicado ?? it.multiplicador ?? ""),
        numOrBlank(it.stock_on_hand ?? ""),
        numOrBlank(it.stock_min ?? ""),
        ...(canSeeCosts ? [numOrBlank(it.costo_usd ?? "")] : []),
      ]),
    ];
    downloadXLSX("repuestos_filtrados.xlsx", rows, "Repuestos");
  }

  function updateDraft(id, key, value) {
    setDrafts((prev) => ({
      ...prev,
      [id]: {
        ...(prev[id] || {}),
        [key]: value,
      },
    }));
  }

  function stopRowClick(event) {
    event.stopPropagation();
  }

  function updateDetalleDraft(id, key, value) {
    setDetalles((prev) => {
      const st = prev[id] || {};
      const draft = { ...(st.draft || {}) };
      draft[key] = value;
      return { ...prev, [id]: { ...st, draft } };
    });
  }

  function updateProveedorDraft(id, index, key, value) {
    setDetalles((prev) => {
      const st = prev[id] || {};
      const list = [...(st.proveedoresDraft || [])];
      const cur = list[index] || {};
      if (key === "proveedor_nombre") {
        list[index] = { ...cur, proveedor_id: "", proveedor_nombre: value };
      } else {
        list[index] = { ...cur, [key]: value };
      }
      return { ...prev, [id]: { ...st, proveedoresDraft: list } };
    });
  }

  function addProveedorDraft(id) {
    setDetalles((prev) => {
      const st = prev[id] || {};
      const list = [...(st.proveedoresDraft || [])];
      list.push({
        proveedor_id: "",
        proveedor_nombre: "",
        sku_proveedor: "",
        lead_time_dias: "",
        prioridad: "",
        ultima_compra: "",
      });
      return { ...prev, [id]: { ...st, proveedoresDraft: list } };
    });
  }

  function removeProveedorDraft(id, index) {
    setDetalles((prev) => {
      const st = prev[id] || {};
      const list = [...(st.proveedoresDraft || [])];
      list.splice(index, 1);
      return { ...prev, [id]: { ...st, proveedoresDraft: list } };
    });
  }

  function hasChanges(it) {
    const d = drafts[it.id];
    if (!d) return false;
    const cmp = (a, b) => String(a ?? "") !== String(b ?? "");
    if (canEditStock && "stock_on_hand" in d && cmp(d.stock_on_hand, it.stock_on_hand)) return true;
    if (canManage && "stock_min" in d && cmp(d.stock_min, it.stock_min)) return true;
    if (canManage && "multiplicador" in d && cmp(d.multiplicador, it.multiplicador)) return true;
    return false;
  }

  async function saveConfig() {
    if (!canManage) return;
    try {
      setCfgLoading(true);
      setErr("");
      setMsg("");
      await patchRepuestosConfig({
        dolar_ars: cfgForm.dolar_ars,
        multiplicador_general: cfgForm.multiplicador_general,
      });
      await loadConfig();
      await loadRepuestos();
      setMsg("Configuracion actualizada");
    } catch (e) {
      setErr(e?.message || "No se pudo actualizar configuracion");
    } finally {
      setCfgLoading(false);
    }
  }

  async function saveRow(it) {
    if (!canEditStock && !canManage) return;
    const d = drafts[it.id] || {};
    const payload = {};
    if (canEditStock && "stock_on_hand" in d) payload.stock_on_hand = d.stock_on_hand;
    if (canManage && "stock_min" in d) payload.stock_min = d.stock_min;
    if (canManage && "multiplicador" in d) {
      payload.multiplicador = d.multiplicador === "" ? null : d.multiplicador;
    }
    if (!Object.keys(payload).length) return;

    try {
      setErr("");
      setMsg("");
      const updated = await patchRepuesto(it.id, payload);
      applyItemUpdate(updated);
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[it.id];
        return next;
      });
      if (detalles[it.id]?.data) {
        updateDetalleState(it.id, {
          data: updated,
          draft: buildDetalleDraft(updated),
          proveedoresDraft: buildProveedoresDraft(updated),
        });
      }
      setMsg("Repuesto actualizado");
    } catch (e) {
      setErr(e?.message || "No se pudo actualizar");
    }
  }

  async function saveAdd() {
    if (!canAdd) return;
    const subrubroCodigo = (addForm.subrubro_codigo || "").trim();
    const nombre = (addForm.nombre || "").trim();
    if (!subrubroCodigo || !nombre) {
      setErr("Subrubro y nombre requeridos");
      return;
    }
    const payload = { subrubro_codigo: subrubroCodigo, nombre };
    if (addForm.stock_on_hand !== "") payload.stock_on_hand = addForm.stock_on_hand;
    if (canManage) {
      if (addForm.stock_min !== "") payload.stock_min = addForm.stock_min;
      if (addForm.multiplicador !== "") payload.multiplicador = addForm.multiplicador;
      if (addForm.tipo_articulo.trim()) payload.tipo_articulo = addForm.tipo_articulo.trim();
      if (addForm.categoria.trim()) payload.categoria = addForm.categoria.trim();
      if (addForm.ubicacion_deposito.trim()) {
        payload.ubicacion_deposito = addForm.ubicacion_deposito.trim();
      }
    }
    if (canEditCost && addForm.costo_usd !== "") {
      payload.costo_usd = addForm.costo_usd;
    }

    try {
      setAddSaving(true);
      setErr("");
      setMsg("");
      const created = await postRepuesto(payload);
      resetAddForm();
      setAddOpen(false);
      setActionsOpen(false);
      await loadRepuestos();
      if (created?.id) {
        setOpenId(created.id);
        updateDetalleState(created.id, {
          data: created,
          draft: buildDetalleDraft(created),
          proveedoresDraft: buildProveedoresDraft(created),
          tab: "detalle",
          movs: [],
          movsLoading: false,
          movsError: "",
        });
      }
      setMsg("Repuesto creado");
    } catch (e) {
      setErr(e?.message || "No se pudo crear repuesto");
    } finally {
      setAddSaving(false);
    }
  }

  async function loadMovimientos() {
    try {
      setErr("");
      setMovimientosLoading(true);
      setMovimientosOpen(true);
      const rows = await getRepuestosMovimientos({ limit: 100 });
      setMovimientos(rows || []);
    } catch (e) {
      setErr(e?.message || "No se pudo cargar movimientos");
      setMovimientos([]);
    } finally {
      setMovimientosLoading(false);
    }
  }

  async function loadCambios() {
    if (!canManage) return;
    try {
      setCambiosErr("");
      setCambiosLoading(true);
      setCambiosOpen(true);
      const rows = await getRepuestosCambios({ limit: 500 });
      setCambios(rows || []);
    } catch (e) {
      setCambiosErr(e?.message || "No se pudieron cargar cambios");
      setCambios([]);
    } finally {
      setCambiosLoading(false);
    }
  }

  async function handleDeleteRepuesto(id) {
    if (!canDelete) return;
    const ok = window.confirm("¿Eliminar este repuesto? Se marcara como inactivo.");
    if (!ok) return;
    try {
      setErr("");
      setMsg("");
      await deleteRepuesto(id);
      setOpenId(null);
      await loadRepuestos();
      setMsg("Repuesto eliminado");
    } catch (e) {
      setErr(e?.message || "No se pudo eliminar repuesto");
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Repuestos</h1>
      <p className="text-sm text-gray-600 mb-4">
        Stock con alerta y precios de venta basados en costo USD * dolar *
        multiplicador. El stock puede quedar negativo.
      </p>

      {err && <div className="bg-red-100 text-red-700 p-2 rounded mb-2">{err}</div>}
      {msg && <div className="bg-green-100 text-green-700 p-2 rounded mb-2">{msg}</div>}

      <div className="border rounded p-3 mb-4">
        <div className="flex flex-col md:flex-row md:items-end gap-3">
          <div className="flex-1">
            <label className="text-sm block mb-1">Dolar (ARS)</label>
            <Input
              type="number"
              step="1"
              value={cfgForm.dolar_ars}
              onChange={(e) =>
                setCfgForm((s) => ({ ...s, dolar_ars: e.target.value }))
              }
              disabled={!canManage}
            />
          </div>
          <div className="flex-1">
            <label className="text-sm block mb-1">Multiplicador general</label>
            <Input
              type="number"
              step="0.01"
              value={cfgForm.multiplicador_general}
              onChange={(e) =>
                setCfgForm((s) => ({
                  ...s,
                  multiplicador_general: e.target.value,
                }))
              }
              disabled={!canManage}
            />
          </div>
          {canManage && (
            <button
              className="px-4 py-2 rounded bg-blue-600 text-white disabled:opacity-60"
              onClick={saveConfig}
              disabled={cfgLoading}
            >
              {cfgLoading ? "Guardando..." : "Guardar"}
            </button>
          )}
        </div>
        <div className="text-xs text-gray-500 mt-2">
          Ultima actualizacion: {formatTs(config?.updated_at)}
          {config?.updated_by_nombre ? ` por ${config.updated_by_nombre}` : ""}
        </div>
        {history?.length ? (
          <div className="mt-2 text-xs text-gray-500">
            Cambios recientes: {history.slice(0, 3).map((h) => (
              <span key={h.id} className="mr-3">
                {formatTs(h.changed_at)} - {h.changed_by_nombre || "-"}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <div className="border rounded p-3 mb-4">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="font-medium">Permisos de conteo</div>
          {isTech && activePerm && (
            <Chip tone="green">Edicion habilitada hasta {formatTs(activePerm.expires_at)}</Chip>
          )}
        </div>
        {permisosErr && (
          <div className="bg-red-100 text-red-700 p-2 rounded mb-2">
            {permisosErr}
          </div>
        )}
        {canManage ? (
          <div className="space-y-3">
            <div className="flex flex-col md:flex-row md:items-end gap-3">
              <div className="flex-1">
                <label className="text-sm block mb-1">Tecnico</label>
                <select
                  className="border rounded p-2 w-full"
                  value={permForm.tecnico_id}
                  onChange={(e) =>
                    setPermForm((s) => ({ ...s, tecnico_id: e.target.value }))
                  }
                >
                  <option value="">Seleccionar tecnico</option>
                  {tecnicos.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.nombre || t.email || t.id}
                    </option>
                  ))}
                </select>
              </div>
              <button
                className="px-4 py-2 rounded bg-blue-600 text-white disabled:opacity-60"
                onClick={enablePermiso}
                disabled={permSaving || !permForm.tecnico_id}
                type="button"
              >
                {permSaving ? "Guardando..." : "Habilitar 24h"}
              </button>
            </div>
            <div className="text-xs text-gray-500">
              {permisosLoading
                ? "Cargando permisos..."
                : `${permisos.length} permiso(s) activos`}
            </div>
            <div className="overflow-auto">
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="text-left">
                    <th className="p-2">Tecnico</th>
                    <th className="p-2">Habilitado por</th>
                    <th className="p-2">Desde</th>
                    <th className="p-2">Vence</th>
                    <th className="p-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {permisos.map((p) => (
                    <tr key={p.id} className="border-t">
                      <td className="p-2">{p.tecnico_nombre || "-"}</td>
                      <td className="p-2">{p.enabled_by_nombre || "-"}</td>
                      <td className="p-2">{formatTs(p.created_at)}</td>
                      <td className="p-2">{formatTs(p.expires_at)}</td>
                      <td className="p-2 text-right">
                        <button
                          className="px-2 py-1 border rounded text-xs disabled:opacity-60"
                          type="button"
                          onClick={() => revokePermiso(p.id)}
                          disabled={permSaving}
                        >
                          Revocar
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!permisosLoading && !permisos.length && (
                    <tr>
                      <td className="p-2 text-gray-500" colSpan={5}>
                        Sin permisos activos
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="text-sm text-gray-700">
            {activePerm ? (
              <div className="flex items-center gap-2">
                <Chip tone="green">Edicion habilitada</Chip>
                <span>Vence {formatTs(activePerm.expires_at)}</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Chip>Edicion de stock no habilitada</Chip>
                <span>Contacta a un jefe para habilitar conteo.</span>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="border rounded p-3">
        <div className="flex flex-col md:flex-row md:items-center gap-3 mb-3">
          <div className="flex-1">
            <Input
              placeholder="Buscar por codigo o nombre"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div className="text-xs text-gray-500">
            {loading ? "Cargando..." : `${filtered.length} repuestos`}
          </div>
          <div className="flex items-center gap-2">
            <button
              className="px-3 py-2 border rounded text-sm"
              type="button"
              onClick={loadMovimientos}
            >
              Movimientos
            </button>
            <button
              className="px-3 py-2 border rounded text-sm"
              type="button"
              onClick={exportRepuestosXLSX}
              disabled={!filtered.length}
            >
              Exportar Excel
            </button>
            {canManage && (
              <button
                className="px-3 py-2 border rounded text-sm"
                type="button"
                onClick={loadCambios}
              >
                Cambios
              </button>
            )}
            {canAdd && (
              <div className="relative" ref={actionsMenuRef}>
                <button
                  className="px-3 py-2 border rounded text-sm"
                  type="button"
                  onClick={() => setActionsOpen((prev) => !prev)}
                >
                  Acciones
                </button>
                {actionsOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-white border rounded shadow z-10">
                    <button
                      className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50"
                      type="button"
                      onClick={() => {
                        setAddOpen(true);
                        setActionsOpen(false);
                      }}
                    >
                      Agregar repuesto
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {canAdd && addOpen && (
          <div className="border rounded p-3 bg-gray-50 mb-3">
            <div className="flex items-center justify-between mb-3">
              <div className="font-medium text-sm">Agregar repuesto</div>
              <button
                className="text-xs text-gray-500 underline"
                type="button"
                onClick={() => {
                  setAddOpen(false);
                  resetAddForm();
                }}
              >
                Cerrar
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-gray-500">Subrubro *</label>
                <select
                  className="border rounded p-2 w-full"
                  value={addForm.subrubro_codigo}
                  onChange={(e) =>
                    setAddForm((s) => ({ ...s, subrubro_codigo: e.target.value }))
                  }
                >
                  <option value="">Seleccionar subrubro</option>
                  {subrubros.map((s) => (
                    <option key={s.codigo} value={s.codigo}>
                      {s.codigo} - {s.nombre}
                    </option>
                  ))}
                </select>
                <div className="text-xs text-gray-500 mt-1">
                  Codigo se asigna automaticamente con el proximo disponible.
                </div>
                {subrubrosLoading && (
                  <div className="text-xs text-gray-500 mt-1">Cargando subrubros...</div>
                )}
                {subrubrosErr && (
                  <div className="text-xs text-red-600 mt-1">{subrubrosErr}</div>
                )}
              </div>
              <div className="md:col-span-2">
                <label className="text-xs text-gray-500">Nombre *</label>
                <Input
                  value={addForm.nombre}
                  onChange={(e) =>
                    setAddForm((s) => ({ ...s, nombre: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="text-xs text-gray-500">Stock</label>
                <input
                  type="number"
                  step="1"
                  className="border rounded p-2 w-full"
                  value={addForm.stock_on_hand}
                  onChange={(e) =>
                    setAddForm((s) => ({
                      ...s,
                      stock_on_hand: normalizeIntInput(e.target.value),
                    }))
                  }
                />
              </div>
              {canEditCost && (
                <div>
                  <label className="text-xs text-gray-500">Costo USD (opcional)</label>
                  <input
                    type="number"
                    step="0.01"
                    className="border rounded p-2 w-full"
                    value={addForm.costo_usd}
                    onChange={(e) =>
                      setAddForm((s) => ({ ...s, costo_usd: e.target.value }))
                    }
                  />
                </div>
              )}
              {canManage && (
                <>
                  <div>
                    <label className="text-xs text-gray-500">Stock min</label>
                    <input
                      type="number"
                      step="1"
                      className="border rounded p-2 w-full"
                      value={addForm.stock_min}
                      onChange={(e) =>
                        setAddForm((s) => ({
                          ...s,
                          stock_min: normalizeIntInput(e.target.value),
                        }))
                      }
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">Multiplicador</label>
                    <input
                      type="number"
                      step="0.01"
                      className="border rounded p-2 w-full"
                      value={addForm.multiplicador}
                      onChange={(e) =>
                        setAddForm((s) => ({ ...s, multiplicador: e.target.value }))
                      }
                      placeholder={
                        config?.multiplicador_general != null
                          ? String(config.multiplicador_general)
                          : ""
                      }
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">Tipo de articulo</label>
                    <Input
                      value={addForm.tipo_articulo}
                      onChange={(e) =>
                        setAddForm((s) => ({ ...s, tipo_articulo: e.target.value }))
                      }
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">Categoria</label>
                    <Input
                      value={addForm.categoria}
                      onChange={(e) =>
                        setAddForm((s) => ({ ...s, categoria: e.target.value }))
                      }
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">Ubicacion deposito</label>
                    <Input
                      value={addForm.ubicacion_deposito}
                      onChange={(e) =>
                        setAddForm((s) => ({
                          ...s,
                          ubicacion_deposito: e.target.value,
                        }))
                      }
                    />
                  </div>
                </>
              )}
            </div>
            <div className="flex justify-end gap-2 mt-3">
              <button
                className="px-3 py-2 border rounded text-sm"
                type="button"
                onClick={() => {
                  setAddOpen(false);
                  resetAddForm();
                }}
              >
                Cancelar
              </button>
              <button
                className="px-3 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-60"
                type="button"
                onClick={saveAdd}
                disabled={addSaving}
              >
                {addSaving ? "Guardando..." : "Crear repuesto"}
              </button>
            </div>
          </div>
        )}

        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="p-2 w-20 whitespace-nowrap">
                  <button
                    type="button"
                    className="hover:underline"
                    onClick={setCodigoOrder}
                  >
                    Codigo
                  </button>
                </th>
                <th className="p-2">Nombre</th>
                <th className="p-2">Mul.</th>
                <th className="p-2">
                  <button
                    type="button"
                    className="hover:underline"
                    onClick={toggleStockOrder}
                  >
                    Stock
                  </button>
                </th>
                <th className="p-2">Stock min</th>
                <th className="p-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((it) => {
                const draft = drafts[it.id] || {};
                const rowClass = it.stock_negativo
                  ? "bg-red-50"
                  : it.stock_alerta
                  ? "bg-yellow-50"
                  : "";
                const isOpen = openId === it.id;
                const detail = detalles[it.id] || {};
                const detailTab = detail.tab || "detalle";
                const detailDraft = detail.draft || {};
                const proveedoresDraft = detail.proveedoresDraft || [];
                const detailFieldsToCheck = canEditDetalle ? DETAIL_FIELDS : [];
                const detailHasChanges =
                  (canEditDetalle &&
                    detailFieldsToCheck.some((field) => {
                      const prevVal = String(detail.data?.[field] ?? "");
                      const nextRaw = String(detailDraft?.[field] ?? "");
                      const nextVal = field === "nombre" ? nextRaw.trim() : nextRaw;
                      return prevVal !== nextVal;
                    })) ||
                  (canEditCost && String(detail.data?.costo_usd ?? "") !== String(detailDraft?.costo_usd ?? ""));
                const setTab = (tab) => {
                  updateDetalleState(it.id, { tab });
                  if (
                    tab === "movimientos" &&
                    !detail.movsLoading &&
                    !(detail.movs || []).length
                  ) {
                    loadMovimientosDetalle(it.id);
                  }
                };
                return (
                  <Fragment key={it.id}>
                    <tr
                      className={`border-t ${rowClass} cursor-pointer`}
                      onClick={() => toggleDetalle(it.id)}
                    >
                      <td className="p-2 font-medium whitespace-nowrap">{it.codigo}</td>
                      <td className="p-2">
                        <div className="font-medium">{it.nombre}</div>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {it.stock_negativo && (
                            <Chip tone="red">Stock negativo</Chip>
                          )}
                          {!it.stock_negativo && it.stock_alerta && (
                            <Chip tone="yellow">Stock bajo</Chip>
                          )}
                        </div>
                      </td>
                      <td className="p-2">
                        {canManage ? (
                          <input
                            type="number"
                            step="0.01"
                            className="border rounded p-1 w-28 text-right"
                            value={
                              draft.multiplicador ??
                              (it.multiplicador ?? "")
                            }
                            onChange={(e) =>
                              updateDraft(it.id, "multiplicador", e.target.value)
                            }
                            onClick={stopRowClick}
                            placeholder={
                              it.multiplicador_aplicado != null
                                ? String(it.multiplicador_aplicado)
                                : ""
                            }
                          />
                        ) : (
                          <span>
                            {it.multiplicador_aplicado != null
                              ? it.multiplicador_aplicado
                              : "-"}
                          </span>
                        )}
                      </td>
                      <td className="p-2">
                        {canEditStock ? (
                          <input
                            type="number"
                            step="1"
                            className="border rounded p-1 w-28 text-right"
                            value={
                              draft.stock_on_hand ??
                              (it.stock_on_hand ?? "")
                            }
                            onChange={(e) =>
                              updateDraft(
                                it.id,
                                "stock_on_hand",
                                normalizeIntInput(e.target.value)
                              )
                            }
                            onClick={stopRowClick}
                          />
                        ) : (
                          <span>{it.stock_on_hand ?? "-"}</span>
                        )}
                      </td>
                      <td className="p-2">
                        {canManage ? (
                          <input
                            type="number"
                            step="1"
                            className="border rounded p-1 w-28 text-right"
                            value={draft.stock_min ?? (it.stock_min ?? "")}
                            onChange={(e) =>
                              updateDraft(
                                it.id,
                                "stock_min",
                                normalizeIntInput(e.target.value)
                              )
                            }
                            onClick={stopRowClick}
                          />
                        ) : (
                          <span>{it.stock_min ?? "-"}</span>
                        )}
                      </td>
                      <td className="p-2 text-right">
                        <div className="flex flex-wrap justify-end gap-2">
                          {(canManage || canEditStock) && (
                            <button
                              className="px-2 py-1 border rounded text-xs disabled:opacity-50"
                              onClick={(e) => {
                                stopRowClick(e);
                                saveRow(it);
                              }}
                              disabled={!hasChanges(it)}
                              type="button"
                            >
                              Guardar
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr className="border-t">
                        <td className="p-3 bg-gray-50" colSpan={colCount}>
                          {detail.loading ? (
                            <div className="text-sm text-gray-500">Cargando detalle...</div>
                          ) : detail.error ? (
                            <div className="bg-red-100 text-red-700 p-2 rounded">{detail.error}</div>
                          ) : detail.data ? (
                            <div>
                              <div className="flex items-start justify-between gap-3 mb-3">
                                <div>
                                  <div className="text-xs text-gray-500">
                                    Codigo:{" "}
                                    <span className="font-medium text-gray-800">
                                      {detail.data.codigo || it.codigo}
                                    </span>
                                  </div>
                                  <div className="text-lg font-semibold">
                                    {detail.data.nombre || it.nombre}
                                  </div>
                                  <div className="flex flex-wrap gap-1 mt-2">
                                    {detail.data.stock_negativo && (
                                      <Chip tone="red">Stock negativo</Chip>
                                    )}
                                    {!detail.data.stock_negativo &&
                                      detail.data.stock_alerta && (
                                        <Chip tone="yellow">Stock bajo</Chip>
                                      )}
                                    {detail.data.stock_permiso?.activo && (
                                      <Chip tone="green">Conteo habilitado</Chip>
                                    )}
                                  </div>
                                </div>
                                <div className="flex items-center gap-3">
                                  {canDelete && (
                                    <button
                                      className="text-xs text-red-600 underline"
                                      type="button"
                                      onClick={() => handleDeleteRepuesto(it.id)}
                                    >
                                      Eliminar
                                    </button>
                                  )}
                                  <button
                                    className="text-xs text-gray-500 underline"
                                    type="button"
                                    onClick={() => toggleDetalle(it.id)}
                                  >
                                    Cerrar
                                  </button>
                                </div>
                              </div>
                              <Tabs
                                value={detailTab}
                                onChange={setTab}
                                items={[
                                  { value: "detalle", label: "Detalle" },
                                  { value: "proveedores", label: "Proveedores" },
                                  { value: "movimientos", label: "Movimientos" },
                                ]}
                              />
                              {detailTab === "detalle" && (
                                <div className="space-y-3">
                                  {canEditDetalle && (
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                      <div className="md:col-span-2">
                                        <label className="text-xs text-gray-500">Nombre</label>
                                        <Input
                                          value={detailDraft.nombre || ""}
                                          onChange={(e) =>
                                            updateDetalleDraft(it.id, "nombre", e.target.value)
                                          }
                                          disabled={!canEditDetalle}
                                        />
                                      </div>
                                    </div>
                                  )}
                                  {canSeeCosts && (
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                      <div className="border rounded p-2 bg-white">
                                        <div className="text-xs text-gray-500">Costo USD</div>
                                        {canEditCost ? (
                                          <input
                                            type="number"
                                            step="0.01"
                                            className="border rounded p-1 w-full text-right"
                                            value={detailDraft.costo_usd || ""}
                                            onChange={(e) =>
                                              updateDetalleDraft(it.id, "costo_usd", e.target.value)
                                            }
                                          />
                                        ) : (
                                          <div className="font-medium">
                                            {formatMoney(detail.data?.costo_usd, "USD")}
                                          </div>
                                        )}
                                      </div>
                                      <div className="border rounded p-2 bg-white">
                                        <div className="text-xs text-gray-500">Multiplicador</div>
                                        <div className="font-medium">
                                          {detail.data?.multiplicador_aplicado ?? "-"}
                                        </div>
                                      </div>
                                      <div className="border rounded p-2 bg-white">
                                        <div className="text-xs text-gray-500">Precio venta</div>
                                        <div className="font-medium">
                                          {formatMoney(detail.data?.precio_venta)}
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <div>
                                      <label className="text-xs text-gray-500">Tipo de articulo</label>
                                      <Input
                                        value={detailDraft.tipo_articulo || ""}
                                        onChange={(e) =>
                                          updateDetalleDraft(it.id, "tipo_articulo", e.target.value)
                                        }
                                        disabled={!canEditDetalle}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-xs text-gray-500">Categoria</label>
                                      <Input
                                        value={detailDraft.categoria || ""}
                                        onChange={(e) =>
                                          updateDetalleDraft(it.id, "categoria", e.target.value)
                                        }
                                        disabled={!canEditDetalle}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-xs text-gray-500">Unidad de medida</label>
                                      <Input
                                        value={detailDraft.unidad_medida || ""}
                                        onChange={(e) =>
                                          updateDetalleDraft(it.id, "unidad_medida", e.target.value)
                                        }
                                        disabled={!canEditDetalle}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-xs text-gray-500">Marca / fabricante</label>
                                      <Input
                                        value={detailDraft.marca_fabricante || ""}
                                        onChange={(e) =>
                                          updateDetalleDraft(it.id, "marca_fabricante", e.target.value)
                                        }
                                        disabled={!canEditDetalle}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-xs text-gray-500">Nro parte</label>
                                      <Input
                                        value={detailDraft.nro_parte || ""}
                                        onChange={(e) =>
                                          updateDetalleDraft(it.id, "nro_parte", e.target.value)
                                        }
                                        disabled={!canEditDetalle}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-xs text-gray-500">Ubicacion deposito</label>
                                      <Input
                                        value={detailDraft.ubicacion_deposito || ""}
                                        onChange={(e) =>
                                          updateDetalleDraft(it.id, "ubicacion_deposito", e.target.value)
                                        }
                                        disabled={!canEditDetalle}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-xs text-gray-500">Estado</label>
                                      <Input
                                        value={detailDraft.estado || ""}
                                        onChange={(e) =>
                                          updateDetalleDraft(it.id, "estado", e.target.value)
                                        }
                                        disabled={!canEditDetalle}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-xs text-gray-500">Fecha ultima compra</label>
                                      <input
                                        type="date"
                                        className="border rounded p-2 w-full"
                                        value={detailDraft.fecha_ultima_compra || ""}
                                        onChange={(e) =>
                                          updateDetalleDraft(it.id, "fecha_ultima_compra", e.target.value)
                                        }
                                        disabled={!canEditDetalle}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-xs text-gray-500">Fecha ultimo conteo</label>
                                      <input
                                        type="date"
                                        className="border rounded p-2 w-full"
                                        value={detailDraft.fecha_ultimo_conteo || ""}
                                        onChange={(e) =>
                                          updateDetalleDraft(it.id, "fecha_ultimo_conteo", e.target.value)
                                        }
                                        disabled={!canEditDetalle}
                                      />
                                    </div>
                                    <div>
                                      <label className="text-xs text-gray-500">Fecha vencimiento</label>
                                      <input
                                        type="date"
                                        className="border rounded p-2 w-full"
                                        value={detailDraft.fecha_vencimiento || ""}
                                        onChange={(e) =>
                                          updateDetalleDraft(it.id, "fecha_vencimiento", e.target.value)
                                        }
                                        disabled={!canEditDetalle}
                                      />
                                    </div>
                                    <div className="md:col-span-2">
                                      <label className="text-xs text-gray-500">Notas</label>
                                      <textarea
                                        className="border rounded p-2 w-full min-h-[80px]"
                                        value={detailDraft.notas || ""}
                                        onChange={(e) =>
                                          updateDetalleDraft(it.id, "notas", e.target.value)
                                        }
                                        disabled={!canEditDetalle}
                                      />
                                    </div>
                                  </div>
                                  {(canEditDetalle || canEditCost) && (
                                    <div className="flex justify-end">
                                      <button
                                        className="px-3 py-2 border rounded text-sm disabled:opacity-60"
                                        onClick={() => saveDetalle(it.id)}
                                        disabled={!detailHasChanges || detail.savingDetalle}
                                        type="button"
                                      >
                                        {detail.savingDetalle ? "Guardando..." : "Guardar detalle"}
                                      </button>
                                    </div>
                                  )}
                                </div>
                              )}
                              {detailTab === "proveedores" && (
                                <div className="space-y-3">
                                  {!canManage && (
                                    <div className="flex flex-wrap gap-2">
                                      {(detail.data?.proveedores || []).map((p) => (
                                        <Chip key={p.id} tone="blue">{p.proveedor_nombre}</Chip>
                                      ))}
                                      {!detail.data?.proveedores?.length && (
                                        <span className="text-xs text-gray-500">Sin proveedores</span>
                                      )}
                                    </div>
                                  )}
                                  {canManage && (
                                    <>
                                      <datalist id={`prov-list-${it.id}`}>
                                        {proveedores.map((p) => (
                                          <option key={p.id} value={p.nombre} />
                                        ))}
                                      </datalist>
                                      <div className="space-y-2">
                                        {proveedoresDraft.map((p, idx) => (
                                          <div key={`${p.proveedor_id || "n"}-${idx}`} className="grid grid-cols-1 md:grid-cols-6 gap-2 items-end">
                                            <div className="md:col-span-2">
                                              <label className="text-xs text-gray-500">Proveedor</label>
                                              <input
                                                className="border rounded p-2 w-full"
                                                list={`prov-list-${it.id}`}
                                                value={p.proveedor_nombre || ""}
                                                onChange={(e) =>
                                                  updateProveedorDraft(it.id, idx, "proveedor_nombre", e.target.value)
                                                }
                                              />
                                            </div>
                                            <div>
                                              <label className="text-xs text-gray-500">SKU</label>
                                              <input
                                                className="border rounded p-2 w-full"
                                                value={p.sku_proveedor || ""}
                                                onChange={(e) =>
                                                  updateProveedorDraft(it.id, idx, "sku_proveedor", e.target.value)
                                                }
                                              />
                                            </div>
                                            <div>
                                              <label className="text-xs text-gray-500">Lead time</label>
                                              <input
                                                type="number"
                                                className="border rounded p-2 w-full"
                                                value={p.lead_time_dias || ""}
                                                onChange={(e) =>
                                                  updateProveedorDraft(it.id, idx, "lead_time_dias", e.target.value)
                                                }
                                              />
                                            </div>
                                            <div>
                                              <label className="text-xs text-gray-500">Prioridad</label>
                                              <input
                                                type="number"
                                                className="border rounded p-2 w-full"
                                                value={p.prioridad || ""}
                                                onChange={(e) =>
                                                  updateProveedorDraft(it.id, idx, "prioridad", e.target.value)
                                                }
                                              />
                                            </div>
                                            <div>
                                              <label className="text-xs text-gray-500">Ultima compra</label>
                                              <input
                                                type="date"
                                                className="border rounded p-2 w-full"
                                                value={p.ultima_compra || ""}
                                                onChange={(e) =>
                                                  updateProveedorDraft(it.id, idx, "ultima_compra", e.target.value)
                                                }
                                              />
                                            </div>
                                            <div className="md:col-span-6 flex justify-end">
                                              <button
                                                className="text-xs text-red-600 underline"
                                                type="button"
                                                onClick={() => removeProveedorDraft(it.id, idx)}
                                              >
                                                Quitar
                                              </button>
                                            </div>
                                          </div>
                                        ))}
                                        {!proveedoresDraft.length && (
                                          <div className="text-xs text-gray-500">Sin proveedores</div>
                                        )}
                                      </div>
                                      <div className="flex flex-wrap justify-between gap-2">
                                        <button
                                          className="px-3 py-2 border rounded text-sm"
                                          type="button"
                                          onClick={() => addProveedorDraft(it.id)}
                                        >
                                          Agregar proveedor
                                        </button>
                                        <button
                                          className="px-3 py-2 border rounded text-sm disabled:opacity-60"
                                          type="button"
                                          onClick={() => saveProveedores(it.id)}
                                          disabled={detail.savingProveedores}
                                        >
                                          {detail.savingProveedores ? "Guardando..." : "Guardar proveedores"}
                                        </button>
                                      </div>
                                    </>
                                  )}
                                </div>
                              )}
                              {detailTab === "movimientos" && (
                                <div>
                                  {detail.movsLoading ? (
                                    <div className="text-sm text-gray-500">Cargando movimientos...</div>
                                  ) : detail.movsError ? (
                                    <div className="bg-red-100 text-red-700 p-2 rounded">{detail.movsError}</div>
                                  ) : (
                                    <div className="overflow-auto">
                                      <table className="min-w-full text-xs">
                                        <thead>
                                          <tr className="text-left">
                                            <th className="p-2">Fecha</th>
                                            <th className="p-2">Usuario</th>
                                            <th className="p-2">Tipo</th>
                                            <th className="p-2">Qty</th>
                                            <th className="p-2">Stock prev</th>
                                            <th className="p-2">Stock nuevo</th>
                                            <th className="p-2">Nota</th>
                                          </tr>
                                        </thead>
                                        <tbody>
                                          {(detail.movs || []).map((m) => (
                                            <tr key={m.id} className="border-t">
                                              <td className="p-2">{formatTs(m.created_at)}</td>
                                              <td className="p-2">{m.created_by_nombre || "-"}</td>
                                              <td className="p-2">{m.tipo}</td>
                                              <td className="p-2">{m.qty}</td>
                                              <td className="p-2">{m.stock_prev}</td>
                                              <td className="p-2">{m.stock_new}</td>
                                              <td className="p-2">{m.nota || "-"}</td>
                                            </tr>
                                          ))}
                                          {!detail.movs?.length && (
                                            <tr>
                                              <td className="p-3 text-gray-500" colSpan={7}>
                                                Sin movimientos
                                              </td>
                                            </tr>
                                          )}
                                        </tbody>
                                      </table>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="text-sm text-gray-500">Sin detalle</div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
              {!filtered.length && (
                <tr>
                  <td className="p-3 text-gray-500" colSpan={colCount}>
                    Sin repuestos
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {movimientosOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          onClick={() => {
            setMovimientosOpen(false);
            setMovimientos([]);
          }}
        >
          <div
            className="bg-white rounded shadow-xl w-full max-w-6xl max-h-[85vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b p-3">
              <div className="font-medium">Movimientos de repuestos</div>
              <button
                className="text-xs text-gray-500 underline"
                onClick={() => {
                  setMovimientosOpen(false);
                  setMovimientos([]);
                }}
                type="button"
              >
                Cerrar
              </button>
            </div>
            <div className="overflow-auto max-h-[75vh] p-3">
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="text-left">
                    <th className="p-2">Repuesto</th>
                    <th className="p-2">Fecha</th>
                    <th className="p-2">Usuario</th>
                    <th className="p-2">Tipo</th>
                    <th className="p-2">Qty</th>
                    <th className="p-2">Stock prev</th>
                    <th className="p-2">Stock nuevo</th>
                    <th className="p-2">Nota</th>
                  </tr>
                </thead>
                <tbody>
                  {movimientos.map((m) => (
                    <tr key={m.id} className="border-t">
                      <td className="p-2">
                        <div className="font-medium">{m.codigo || "-"}</div>
                        <div className="text-gray-500">{m.nombre || "-"}</div>
                      </td>
                      <td className="p-2">{formatTs(m.created_at)}</td>
                      <td className="p-2">{m.created_by_nombre || "-"}</td>
                      <td className="p-2">{m.tipo}</td>
                      <td className="p-2">{m.qty}</td>
                      <td className="p-2">{m.stock_prev}</td>
                      <td className="p-2">{m.stock_new}</td>
                      <td className="p-2">{m.nota || "-"}</td>
                    </tr>
                  ))}
                  {movimientosLoading && (
                    <tr>
                      <td className="p-3 text-gray-500" colSpan={8}>
                        Cargando...
                      </td>
                    </tr>
                  )}
                  {!movimientosLoading && !movimientos.length && (
                    <tr>
                      <td className="p-3 text-gray-500" colSpan={8}>
                        Sin movimientos
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {cambiosOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          onClick={() => {
            setCambiosOpen(false);
            setCambios([]);
          }}
        >
          <div
            className="bg-white rounded shadow-xl w-full max-w-4xl max-h-[85vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b p-3">
              <div className="font-medium">Cambios de nombres</div>
              <div className="flex items-center gap-3">
                <button
                  className="text-xs text-gray-500 underline"
                  type="button"
                  onClick={exportCambiosCSV}
                  disabled={!cambios.length}
                >
                  Exportar CSV
                </button>
                <button
                  className="text-xs text-gray-500 underline"
                  onClick={() => {
                    setCambiosOpen(false);
                    setCambios([]);
                  }}
                  type="button"
                >
                  Cerrar
                </button>
              </div>
            </div>
            <div className="p-3 overflow-auto max-h-[75vh]">
              {cambiosErr && (
                <div className="bg-red-100 text-red-700 p-2 rounded mb-2">{cambiosErr}</div>
              )}
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="text-left">
                    <th className="p-2">Fecha</th>
                    <th className="p-2">Usuario</th>
                    <th className="p-2">Accion</th>
                    <th className="p-2">Codigo</th>
                    <th className="p-2">Nombre anterior</th>
                    <th className="p-2">Nombre nuevo</th>
                  </tr>
                </thead>
                <tbody>
                  {cambios.map((c) => (
                    <tr key={c.id} className="border-t">
                      <td className="p-2">{formatTs(c.created_at)}</td>
                      <td className="p-2">{c.created_by_nombre || "-"}</td>
                      <td className="p-2">{c.accion}</td>
                      <td className="p-2">{c.codigo || "-"}</td>
                      <td className="p-2">{c.nombre_prev || "-"}</td>
                      <td className="p-2">{c.nombre_new || "-"}</td>
                    </tr>
                  ))}
                  {cambiosLoading && (
                    <tr>
                      <td className="p-3 text-gray-500" colSpan={6}>
                        Cargando...
                      </td>
                    </tr>
                  )}
                  {!cambiosLoading && !cambios.length && (
                    <tr>
                      <td className="p-3 text-gray-500" colSpan={6}>
                        Sin cambios
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
