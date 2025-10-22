// web/src/pages/NuevoIngreso.jsx (reconstruido)
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
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
} from "@/lib/api";

const Input = (p) => <input {...p} className={`border rounded p-2 w-full ${p.className || ""}`} />;
const Select = (p) => <select {...p} className={`border rounded p-2 w-full ${p.className || ""}`} />;
const TextArea = (p) => <textarea {...p} className={`border rounded p-2 w-full ${p.className || ""}`} />;

export default function NuevoIngreso() {
  const navigate = useNavigate();

  // Catálogos base
  const [marcas, setMarcas] = useState([]);
  const [motivos, setMotivos] = useState([]);
  const [modelos, setModelos] = useState([]);

  // Marca escribible + tipo
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

  // Variante (opcional)
  const [varianteTxt, setVarianteTxt] = useState("");
  const [varianteSugeridas, setVarianteSugeridas] = useState([]);
  // Catálogo (tipos/modelos) para sugerir variantes
  const [catTipoId, setCatTipoId] = useState(null);
  const [catModelos, setCatModelos] = useState([]);

  // Form principal
  const [form, setForm] = useState({
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
    fecha_ingreso: "", // opcional: si viene vaca, se usar hoy() en el backend
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

  // Helpers de clientes
  const findClienteByRS = (v) =>
    clientes.find((c) => (c.razon_social || "").toLowerCase() === String(v).trim().toLowerCase());
  const findClienteByCod = (v) =>
    clientes.find((c) => String(c.cod_empresa || "").toLowerCase() === String(v).trim().toLowerCase());

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
    if (c) {
      setSelectedCliente(c);
      setForm((f) => ({
        ...f,
        cliente: {
          id: c.id,
          razon_social: c.razon_social,
          cod_empresa: c.cod_empresa || "",
          telefono: c.telefono || "",
        },
      }));
    } else {
      setSelectedCliente(null);
      setForm((f) => ({
        ...f,
        cliente: {
          id: null,
          razon_social: rsVal || "",
          cod_empresa: codVal || "",
          telefono: "",
        },
      }));
    }
  }

  // Garantía de reparación (por N/S o N interno MG) - debounce 400ms
  useEffect(() => {
    const ns = (form.equipo.numero_serie || "").trim();
    const mg = (form.equipo.numero_interno || "").trim();
    if (!ns && !mg) {
      setForm((f) => ({ ...f, garantia_reparacion: false }));
      return;
    }
    const h = setTimeout(async () => {
      try {
        const r = await checkGarantiaReparacion(ns, mg);
        setForm((f) => ({ ...f, garantia_reparacion: !!r.within_90_days }));
      } catch {
        /* noop */
      }
    }, 400);
    return () => clearTimeout(h);
  }, [form.equipo.numero_serie, form.equipo.numero_interno]);

  // Garantía de fbrica (por N/S en Excels) - debounce 400ms
  useEffect(() => {
    const ns = (form.equipo.numero_serie || "").trim();
    const marcaSel = (() => {
      const m = marcas.find((x) => x.id === (marcaId || form.equipo.marca_id));
      return m?.nombre || "";
    })();
    if (!ns) {
      // Si no hay N/S, no marcar
      setForm((f) => ({ ...f, equipo: { ...f.equipo, garantia: false } }));
      return;
    }
    const h = setTimeout(async () => {
      try {
        const r = await checkGarantiaFabrica(ns, marcaSel);
        const enGarantia = !!r.within_365_days;
        setForm((f) => ({ ...f, equipo: { ...f.equipo, garantia: enGarantia } }));
      } catch {
        /* noop */
      }
    }, 400);
    return () => clearTimeout(h);
  }, [form.equipo.numero_serie, marcaId, form.equipo.marca_id, marcas]);

  const tipoEquipoSel = useMemo(() => {
    const m = modelos.find((x) => x.id === Number(form.equipo.modelo_id));
    return m?.tipo_equipo || "";
  }, [modelos, form.equipo.modelo_id]);

  // Carga inicial
  useEffect(() => {
    (async () => {
      try {
        const [mks, mts, cls, accs, tps] = await Promise.all([
          getMarcas(),
          getMotivos(),
          getClientes(),
          getAccesoriosCatalogo(),
          getTiposEquipo(),
        ]);
        setMarcas(mks || []);
        setMotivos(mts || []);
        setClientes(cls || []);
        setAccesCatalogo(accs || []);
        const list = (tps || [])
          .map((t) => t?.nombre || t?.label || t?.name || t?.value || t)
          .map(String)
          .filter(Boolean);
        setTiposEquipo(Array.from(new Set(list)));
        try {
          const tecs = await getTecnicos();
          setTecnicos(tecs || []);
        } catch {}
      } catch (e) {
        setErr(e?.message || "Error cargando Catálogos");
      }
    })();
  }, []);

  // Cambio de marca
  useEffect(() => {
    setForm((f) => ({
      ...f,
      equipo: { ...f.equipo, marca_id: marcaId || "", modelo_id: "" },
    }));

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
          // si el modelo seleccionado no pertenece al filtro, limpiarlo
          const currentId = (form?.equipo?.modelo_id ?? "").toString();
          const exists = filtered.some((x) => String(x.id) === currentId);
          if (!exists) {
            setForm((f) => ({ ...f, equipo: { ...f.equipo, modelo_id: "" } }));
          }
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

  // Variantes desde Catálogo segn modelo interno seleccionado
  useEffect(() => {
    const m = modelos.find((x) => x.id === Number(form.equipo.modelo_id));
    if (!m || !marcaId || !catTipoId) {
      setVarianteTxt("");
      setVarianteSugeridas([]);
      return;
    }
    const needle = (m.nombre || "").trim().toUpperCase();
    const cmatch = (catModelos || []).filter((cm) => {
      const a = (cm.name || "").trim().toUpperCase();
      const alias = (cm.alias || "").trim().toUpperCase();
      return (
        a === needle ||
        a.includes(needle) ||
        needle.includes(a) ||
        (alias && (alias === needle || needle.includes(alias) || alias.includes(needle)))
      );
    });
    if (cmatch.length !== 1) {
      setVarianteSugeridas([]);
      setVarianteTxt("");
      return;
    }
    const cm = cmatch[0];
    (async () => {
      try {
        const vars = await getCatalogVariantes(marcaId, catTipoId, cm.id);
        const names = (vars || [])
          .filter((v) => v && v.name)
          .map((v) => v.name);
        setVarianteSugeridas(names);
        if (names.length === 1) setVarianteTxt(names[0]);
      } catch {
        setVarianteSugeridas([]);
      }
    })();
  }, [form.equipo.modelo_id, modelos, marcaId, catTipoId, catModelos]);

  // Si el modelo define técnico por defecto
  useEffect(() => {
    const m = modelos.find((x) => x.id === Number(form.equipo.modelo_id));
    if (m?.tecnico_id) setTecnicoId(m.tecnico_id);
  }, [form.equipo.modelo_id, modelos]);

  // Fallback: técnico por marca si el modelo no define
  useEffect(() => {
    const m = modelos.find((x) => x.id === Number(form.equipo.modelo_id));
    if (m?.tecnico_id) {
      setTecnicoId(m.tecnico_id);
    } else {
      const marcaObj = marcas.find((x) => x.id === marcaId);
      if (marcaObj?.tecnico_id) setTecnicoId(marcaObj.tecnico_id);
    }
  }, [form.equipo.modelo_id, modelos, marcaId, marcas]);

  const onChange = (path) => (e) => {
    const v = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((prev) => {
      const copy = structuredClone(prev);
      const parts = path.split(".");
      let obj = copy;
      for (let i = 0; i < parts.length - 1; i++) obj = obj[parts[i]];
      obj[parts.at(-1)] = v;
      return copy;
    });
  };

  function onMarcaInput(val) {
    setMarcaTxt(val);
    const pool = tipoSel ? (marcasPorTipo.length ? marcasPorTipo : marcas) : marcas;
    const match = pool.find((m) => (m.nombre || "").toLowerCase() === val.trim().toLowerCase());
    setMarcaId(match ? match.id : null);
  }

  // Cambio de tipo => filtra marcas
  useEffect(() => {
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

    if (!form.equipo.marca_id) {
      setLoading(false);
      setErr("Seleccioná una marca válida de la lista.");
      return;
    }
    if (!form.equipo.modelo_id) {
      setLoading(false);
      setErr("Seleccioná un modelo.");
      return;
    }

    const c = resolveCliente(clienteRsInput, clienteCodInput);
    if (!c?.id) {
      setLoading(false);
      setErr("Debés seleccionar un cliente válido de la lista.");
      return;
    }

    try {
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
        ...(form.fecha_ingreso ? { fecha_ingreso: form.fecha_ingreso } : {}),
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
      };

      const r = await postNuevoIngreso(payload);
      setOut(r);
      if (r?.ingreso_id) navigate(`/ingresos/${r.ingreso_id}`);

      // Reset bsico
      setMarcaTxt("");
      setMarcaId(null);
      setModelos([]);
      setClienteRsInput("");
      setClienteCodInput("");
      setSelectedCliente(null);
      setForm({
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
    } catch (e2) {
      setErr(e2?.message || "Error creando ingreso");
    } finally {
      setLoading(false);
    }
  };

  const rsMatch = clienteRsInput ? findClienteByRS(clienteRsInput) : null;
  const codMatch = clienteCodInput ? findClienteByCod(clienteCodInput) : null;
  const clienteMismatch = rsMatch && codMatch && rsMatch.id !== codMatch.id;
  const canSubmitCliente = !!resolveCliente(clienteRsInput, clienteCodInput);

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">Nuevo Ingreso (Orden de Servicio)</h1>

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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="text-sm">Razn social</label>
              <Input
                list="clientes_rs"
                value={clienteRsInput}
                onChange={(e) => onClienteRsChange(e.target.value)}
                placeholder="Escrib y eleg de la lista"
                required
              />
              <datalist id="clientes_rs">
                {(Array.isArray(clientes) ? clientes : []).map((c) => (
                  <option key={c.id} value={c.razon_social} />
                ))}
              </datalist>
              {clienteRsInput && !rsMatch && (
                <div className="text-xs text-red-600 mt-1">Eleg una razn social de las sugeridas.</div>
              )}
            </div>
            <div>
              <label className="text-sm">Cdigo empresa</label>
              <Input
                list="clientes_cod"
                value={clienteCodInput}
                onChange={(e) => onClienteCodChange(e.target.value)}
                placeholder="Opcional: pods buscar por cdigo"
              />
              <datalist id="clientes_cod">
                {(Array.isArray(clientes) ? clientes : [])
                  .filter((c) => c.cod_empresa)
                  .map((c) => (
                    <option key={c.id} value={c.cod_empresa} />
                  ))}
              </datalist>
              {clienteCodInput && !codMatch && (
                <div className="text-xs text-red-600 mt-1">Eleg un cdigo de las sugerencias.</div>
              )}
            </div>
            <div>
              <label className="text-sm">Telfono</label>
              <Input value={form.cliente.telefono} readOnly placeholder="-" />
            </div>
          </div>
          {clienteMismatch && (
            <div className="text-xs text-red-600 mt-2">
              El cdigo no corresponde a la razn social seleccionada.
            </div>
          )}
          <p className="text-xs text-gray-600 mt-2">
            Debés seleccionar un cliente existente. Pods buscar por <b>Razn social</b> o por
            <b> Cdigo</b>; si complets ambos, deben corresponder al mismo cliente.
          </p>
        </fieldset>

        {/* Empresa a facturar */}
        <div className="border rounded p-3">
          <label className="text-sm">Empresa a facturar</label>
          <Select
            value={empresaFact}
            onChange={(e) => setEmpresaFact((e.target.value || "SEPID").toUpperCase())}
          >
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
              <Input
                list="marcas-list"
                value={marcaTxt}
                placeholder="Marca"
                onChange={(e) => onMarcaInput(e.target.value)}
              />
              <datalist id="marcas-list">
                {(tipoSel && marcasPorTipo.length ? marcasPorTipo : marcas).map((m) => (
                  <option key={m.id} value={m.nombre} />
                ))}
              </datalist>
              {marcaTxt && !marcaId && (
                <div className="text-xs text-red-600 mt-1">Eleg una marca de las sugeridas.</div>
              )}
            </div>

            {/* Modelo */}
            <div className="md:col-span-2">
              <label className="text-sm">Modelo</label>
              <Select
                value={form.equipo.modelo_id}
                onChange={onChange("equipo.modelo_id")}
                disabled={!marcaId || !modelos.length}
              >
                <option value="">{!marcaId ? "Eleg marca primero" : "Seleccion modelo"}</option>
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
              <Input
                list="variantes_sugeridas"
                value={varianteTxt}
                onChange={(e) => setVarianteTxt(e.target.value)}
                placeholder="Ej: 25, 25T, V30BT, etc."
              />
              <datalist id="variantes_sugeridas">
                {(varianteSugeridas || []).map((v, i) => (
                  <option key={i} value={v} />
                ))}
              </datalist>
            </div>

            {/* técnico asignado */}
            <div className="md:col-span-2">
              <label className="text-sm">técnico asignado</label>
              <Select
                value={tecnicoId ?? ""}
                onChange={(e) => setTecnicoId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">-- Seleccionar técnico --</option>
                {tecnicos.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nombre}
                  </option>
                ))}
              </Select>
              <div className="text-xs text-gray-600 mt-1">
                Si el modelo tiene técnico por defecto, se completa solo.
              </div>
            </div>

            {/* Nmero de serie */}
            <div className="md:col-span-2">
              <label className="text-sm">Nmero de serie</label>
              <Input value={form.equipo.numero_serie} onChange={onChange("equipo.numero_serie")} />
            </div>

            {/* N interno (MG) */}
            <div className="md:col-span-2">
              <label className="text-sm">N interno (MG)</label>
              <Input
                value={form.equipo.numero_interno}
                onChange={onChange("equipo.numero_interno")}
                placeholder="MG ..."
              />
            </div>

            {/* Garantías */}
            <div className="flex items-center gap-2">
              <input
                id="gar"
                type="checkbox"
                checked={form.equipo.garantia}
                onChange={onChange("equipo.garantia")}
              />
              <label htmlFor="gar">En Garantía</label>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.garantia_reparacion}
                onChange={(e) => setForm((f) => ({ ...f, garantia_reparacion: e.target.checked }))}
              />
              <span className="text-sm">Garantía de reparación</span>
            </div>
          </div>
        </fieldset>

        {/* Ingreso */}
        <fieldset className="border rounded p-3">
          <legend className="px-2 font-semibold">Ingreso</legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-sm">N de remito</label>
              <Input
                value={form.remito_ingreso}
                onChange={onChange("remito_ingreso")}
                placeholder="Opcional"
              />
            </div>
            <div>
              <label className="text-sm">Fecha de ingreso</label>
              <Input
                type="date"
                value={form.fecha_ingreso}
                onChange={onChange("fecha_ingreso")}
              />
              <div className="text-xs text-gray-500 mt-1">Si se deja vaco, se usa la fecha de hoy.</div>
            </div>
            <div>
              <label className="text-sm">Motivo</label>
              <Select value={form.motivo} onChange={onChange("motivo")}>
                <option value="">Seleccion motivo</option>
                {motivos.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="text-sm text-gray-600 self-end">
              Ubicacin inicial: <b>Taller</b> (se puede modificar desde la hoja de servicio)
            </div>
            <div className="md:col-span-2">
              <label className="text-sm">Informe preliminar</label>
              <TextArea rows={3} value={form.informe_preliminar} onChange={onChange("informe_preliminar")} />
            </div>

            <div className="md:col-span-2">
              <label className="text-sm">Comentarios</label>
              <TextArea
                rows={3}
                value={form.comentarios}
                onChange={onChange("comentarios")}
                placeholder="Notas internas u observaciones del ingreso"
              />
            </div>

            {/* Accesorios */}
            <div className="md:col-span-2">
              <label className="text-sm font-medium">Accesorios</label>
              <div className="flex flex-wrap items-end gap-3 mb-2">
                <div className="grow min-w-[260px]">
                  <label className="block text-sm text-gray-600 mb-1">Descripcin</label>
                  <input
                    className="border rounded p-2 w-full"
                    list="accesorios_catalogo"
                    value={nuevoAcc.descripcion}
                    onChange={(e) => setNuevoAcc((s) => ({ ...s, descripcion: e.target.value }))}
                    placeholder="Escrib y eleg de la lista"
                  />
                  <datalist id="accesorios_catalogo">
                    {(Array.isArray(accesCatalogo) ? accesCatalogo : []).map((a) => (
                      <option key={a.id} value={a.nombre} />
                    ))}
                  </datalist>
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">N referencia</label>
                  <Input
                    value={nuevoAcc.referencia}
                    onChange={(e) => setNuevoAcc((s) => ({ ...s, referencia: e.target.value }))}
                    placeholder="Opcional"
                  />
                </div>
                <button
                  type="button"
                  className="bg-blue-600 text-white px-3 py-2 rounded"
                  onClick={() => {
                    const d = (nuevoAcc.descripcion || "").trim().toLowerCase();
                    if (!d) return;
                    const acc = accesCatalogo.find(
                      (a) => (a.nombre || "").trim().toLowerCase() === d
                    );
                    if (!acc) {
                      setErr("Eleg una descripcin válida de la lista");
                      return;
                    }
                    setAccItems((list) => [
                      ...list,
                      {
                        accesorio_id: acc.id,
                        referencia: (nuevoAcc.referencia || "").trim(),
                        accesorio_nombre: acc.nombre,
                      },
                    ]);
                    setNuevoAcc({ descripcion: "", referencia: "" });
                  }}
                >
                  agregar
                </button>
              </div>
              {accItems.length === 0 ? (
                <div className="text-sm text-gray-500">Sin accesorios cargados.</div>
              ) : (
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left">
                      <th className="p-2">Descripcin</th>
                      <th className="p-2">N referencia</th>
                      <th className="p-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {(Array.isArray(accItems) ? accItems : []).map((it, idx) => (
                      <tr key={idx} className="border-t">
                        <td className="p-2">
                          {it.accesorio_nombre ||
                            accesCatalogo.find((a) => String(a.id) === String(it.accesorio_id))?.nombre ||
                            it.accesorio_id}
                        </td>
                        <td className="p-2">{it.referencia || "-"}</td>
                        <td className="p-2">
                          <button
                            type="button"
                            className="text-red-600"
                            onClick={() => {
                              setAccItems((list) => list.filter((_, i) => i !== idx));
                            }}
                          >
                            quitar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </fieldset>

        <div className="flex gap-3">
          <button
            disabled={loading || !canSubmitCliente || !marcaId || !form.equipo.modelo_id}
            className={`px-4 py-2 rounded text-white ${
              loading || !canSubmitCliente || !marcaId || !form.equipo.modelo_id
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


