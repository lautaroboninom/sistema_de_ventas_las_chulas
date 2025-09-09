// web/src/pages/NuevoIngreso.jsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getClientes,
  getMarcas,
  getModelosByBrand,
  getTecnicos,
  postNuevoIngreso,
  getMotivos,
  checkGarantiaReparacion,
} from "@/lib/api";

const Input = (p) => <input {...p} className="border rounded p-2 w-full" />;
const Select = (p) => <select {...p} className="border rounded p-2 w-full" />;
const TextArea = (p) => <textarea {...p} className="border rounded p-2 w-full" />;

export default function NuevoIngreso() {
  const navigate = useNavigate();

  // Catálogos
  const [marcas, setMarcas] = useState([]);
  const [motivos, setMotivos] = useState([]);
  const [modelos, setModelos] = useState([]);

  // Marca escribible
  const [marcaTxt, setMarcaTxt] = useState("");
  const [marcaId, setMarcaId] = useState(null);

  // Clientes (autocompletar)
  const [clientes, setClientes] = useState([]);
  const [selectedCliente, setSelectedCliente] = useState(null);
  const [clienteRsInput, setClienteRsInput] = useState("");
  const [clienteCodInput, setClienteCodInput] = useState("");

  // Form
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
    accesorios: "",
    garantia_reparacion: false,
  });

  // Propietario (particular) y técnico asignado
  const [propietario, setPropietario] = useState({
    nombre: "",
    contacto: "",
    doc: "",
  });
  const [tecnicos, setTecnicos] = useState([]);
  const [tecnicoId, setTecnicoId] = useState(null);

  const [loading, setLoading] = useState(false);
  const [out, setOut] = useState(null);
  const [err, setErr] = useState("");

  // Helpers cliente
  const findClienteByRS = (v) =>
    clientes.find(
      (c) =>
        (c.razon_social || "").toLowerCase() ===
        String(v).trim().toLowerCase()
    );

  const findClienteByCod = (v) =>
    clientes.find(
      (c) =>
        String(c.cod_empresa || "").toLowerCase() ===
        String(v).trim().toLowerCase()
    );

  // Devuelve el cliente válido segun los inputs (deben coincidir si ambos están completos)
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

  // check garantía de reparación por N/S (última entrada < 90 días)
  useEffect(() => {
    const ns = (form.equipo.numero_serie || "").trim();
    if (!ns) {
      setForm((f) => ({ ...f, garantia_reparacion: false }));
      return;
    }
    const h = setTimeout(async () => {
      try {
        const r = await checkGarantiaReparacion(ns);
        setForm((f) => ({ ...f, garantia_reparacion: !!r.within_90_days }));
      } catch {
        // Silencioso: si falla el check, no bloqueamos el alta
      }
    }, 400);
    return () => clearTimeout(h);
  }, [form.equipo.numero_serie]);

  const tipoEquipoSel = (() => {
    const m = modelos.find((x) => x.id === Number(form.equipo.modelo_id));
    return m?.tipo_equipo || "";
  })();

  // Carga inicial
  useEffect(() => {
    (async () => {
      try {
        const [mks, mts, cls] = await Promise.all([
          getMarcas(),
          getMotivos(),
          getClientes(),
        ]);
        setMarcas(mks);
        setMotivos(mts);
        setClientes(cls || []);
        // Técnicos activos (si hay permiso)
        try {
          const tecs = await getTecnicos(); // ya vienen solo activos y rol técnico/jefe
          setTecnicos(tecs);
        } catch {
          /* si 403, seguimos sin lista explícita */
        }
      } catch (e) {
        setErr(e.message || "Error cargando catálogos");
      }
    })();
  }, []);

  // Cuando cambia la marca válida => sincroniza form y carga modelos
  useEffect(() => {
    setForm((f) => ({
      ...f,
      equipo: { ...f.equipo, marca_id: marcaId || "", modelo_id: "" },
    }));

    if (!marcaId) {
      setModelos([]);
      return;
    }
    getModelosByBrand(marcaId)
      .then(setModelos)
      .catch((e) => setErr(e.message || "Error cargando modelos"));
  }, [marcaId]);

  // Si el modelo trae tecnico_id desde el catálogo, lo preseleccionamos
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
    const match = marcas.find(
      (m) => m.nombre.toLowerCase() === val.trim().toLowerCase()
    );
    setMarcaId(match ? match.id : null);
  }

  // Handlers cliente (autocompletado)
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

    // Validaciones mínimas de marca/modelo
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

    // Validación cliente
    const c = resolveCliente(clienteRsInput, clienteCodInput);
    if (!c?.id) {
      setLoading(false);
      setErr("Debés seleccionar un cliente válido de la lista.");
      return;
    }

    try {
      const payload = {
        cliente: { id: c.id }, // ✅ solo el id, el backend valida/usa datos reales
        equipo: {
          marca_id: Number(form.equipo.marca_id),
          modelo_id: Number(form.equipo.modelo_id),
          numero_serie: form.equipo.numero_serie.trim(),
          garantia: !!form.equipo.garantia,
          numero_interno: (form.equipo.numero_interno || "").trim(),
        },
        motivo: form.motivo,
        // 👉 NO mandamos ubicacion_id: el backend pone 'Taller'
        informe_preliminar: form.informe_preliminar,
        accesorios: form.accesorios,
        tecnico_id: tecnicoId ? Number(tecnicoId) : null,
        garantia_reparacion: !!form.garantia_reparacion,
        propietario: {
          nombre: propietario.nombre || "",
          contacto: propietario.contacto || "",
          doc: propietario.doc || "",
        },
      };

      const r = await postNuevoIngreso(payload);
      setOut(r);

      // Ir a la Hoja de servicio
      if (r?.ingreso_id) navigate(`/ingresos/${r.ingreso_id}`);

      // Reset
      setMarcaTxt("");
      setMarcaId(null);
      setModelos([]);
      setClienteRsInput("");
      setClienteCodInput("");
      setSelectedCliente(null);
      setForm({
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
        accesorios: "",
        garantia_reparacion: false,
      });
      setPropietario({ nombre: "", contacto: "", doc: "" });
      setTecnicoId(null);
    } catch (e) {
      setErr(e.message || "Error creando ingreso");
    } finally {
      setLoading(false);
    }
  };

  // Validaciones visuales de cliente
  const rsMatch = clienteRsInput ? findClienteByRS(clienteRsInput) : null;
  const codMatch = clienteCodInput ? findClienteByCod(clienteCodInput) : null;
  const clienteMismatch = rsMatch && codMatch && rsMatch.id !== codMatch.id;
  const canSubmitCliente = !!resolveCliente(clienteRsInput, clienteCodInput);

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">Nuevo Ingreso (Orden de Servicio)</h1>

      {err && (
        <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded">
          {err}
        </div>
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
              <label className="text-sm">Razón social</label>
              <Input
                list="clientes_rs"
                value={clienteRsInput}
                onChange={(e) => onClienteRsChange(e.target.value)}
                placeholder="Escribí y elegí de la lista"
                required
              />
              <datalist id="clientes_rs">
                {clientes.map((c) => (
                  <option key={c.id} value={c.razon_social} />
                ))}
              </datalist>
              {clienteRsInput && !rsMatch && (
                <div className="text-xs text-red-600 mt-1">
                  Elegí una razón social de las sugeridas.
                </div>
              )}
            </div>
            <div>
              <label className="text-sm">Código empresa</label>
              <Input
                list="clientes_cod"
                value={clienteCodInput}
                onChange={(e) => onClienteCodChange(e.target.value)}
                placeholder="Opcional: podés buscar por código"
              />
              <datalist id="clientes_cod">
                {clientes
                  .filter((c) => c.cod_empresa)
                  .map((c) => (
                    <option key={c.id} value={c.cod_empresa} />
                  ))}
              </datalist>
              {clienteCodInput && !codMatch && (
                <div className="text-xs text-red-600 mt-1">
                  Elegí un código de las sugerencias.
                </div>
              )}
            </div>
            <div>
              <label className="text-sm">Teléfono</label>
              <Input value={form.cliente.telefono} readOnly placeholder="—" />
            </div>
          </div>
          {clienteMismatch && (
            <div className="text-xs text-red-600 mt-2">
              El código no corresponde a la razón social seleccionada.
            </div>
          )}
          <p className="text-xs text-gray-600 mt-2">
            Debés seleccionar un cliente existente. Podés buscar por{" "}
            <b>Razón social</b> o por <b>Código</b>; si completás ambos, deben
            corresponder al mismo cliente.
          </p>
        </fieldset>

        {/* Equipo */}
        <fieldset className="border rounded p-3">
          <legend className="px-2 font-semibold">Equipo</legend>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            {/* Marca */}
            <div className="md:col-span-2">
              <label className="text-sm">Marca</label>
              <Input
                list="marcas-list"
                value={marcaTxt}
                placeholder="Marca"
                onChange={(e) => onMarcaInput(e.target.value)}
              />
              <datalist id="marcas-list">
                {marcas.map((m) => (
                  <option key={m.id} value={m.nombre} />
                ))}
              </datalist>
              {marcaTxt && !marcaId && (
                <div className="text-xs text-red-600 mt-1">
                  Elegí una marca de las sugeridas.
                </div>
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
                <option value="">
                  {!marcaId ? "Elegí marca primero" : "Seleccioná modelo"}
                </option>
                {modelos.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nombre}
                  </option>
                ))}
              </Select>
            </div>

            {/* TIPO DE EQUIPO - renglón completo debajo de Marca/Modelo */}
            <div className="md:col-span-4">
              <div className="text-sm text-gray-700 border rounded p-2 bg-gray-50">
                <span className="font-medium">Tipo de equipo:</span>{" "}
                {tipoEquipoSel || "—"}
              </div>
            </div>

            {/* Técnico asignado */}
            <div className="md:col-span-2">
              <label className="text-sm">Técnico asignado</label>
              <Select
                value={tecnicoId ?? ""}
                onChange={(e) =>
                  setTecnicoId(e.target.value ? Number(e.target.value) : null)
                }
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

            {/* Número de serie */}
            <div className="md:col-span-2">
              <label className="text-sm">Número de serie</label>
              <Input
                value={form.equipo.numero_serie}
                onChange={onChange("equipo.numero_serie")}
              />
            </div>

            {/* N° interno (MG) */}
            <div className="md:col-span-2">
              <label className="text-sm">N° interno (MG)</label>
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
              <label htmlFor="gar">En garantía</label>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.garantia_reparacion}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    garantia_reparacion: e.target.checked,
                  }))
                }
              />
              <span className="text-sm">Garantía de reparación</span>
            </div>
          </div>
        </fieldset>

        {/* Propietario (particular) */}
        <fieldset className="border rounded p-3">
          <legend className="px-2 font-semibold">Propietario (particular)</legend>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="text-sm">Nombre</label>
              <Input
                value={propietario.nombre}
                onChange={(e) =>
                  setPropietario((p) => ({ ...p, nombre: e.target.value }))
                }
                placeholder="Nombre y apellido"
              />
            </div>
            <div>
              <label className="text-sm">Contacto</label>
              <Input
                value={propietario.contacto}
                onChange={(e) =>
                  setPropietario((p) => ({ ...p, contacto: e.target.value }))
                }
                placeholder="Teléfono o email"
              />
            </div>
            <div>
              <label className="text-sm">Documento (DNI/CUIT)</label>
              <Input
                value={propietario.doc}
                onChange={(e) =>
                  setPropietario((p) => ({ ...p, doc: e.target.value }))
                }
                placeholder="DNI o CUIT"
              />
            </div>
          </div>
        </fieldset>

        {/* Ingreso */}
        <fieldset className="border rounded p-3">
          <legend className="px-2 font-semibold">Ingreso</legend>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-sm">Motivo</label>
              <Select value={form.motivo} onChange={onChange("motivo")}>
                <option value="">Seleccioná motivo</option>
                {motivos.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </Select>
            </div>

            {/* Ubicación removida: default Taller */}
            <div className="text-sm text-gray-600 self-end">
              Ubicación inicial: <b>Taller</b> (se puede modificar desde la hoja
              de servicio)
            </div>

            <div className="md:col-span-2">
              <label className="text-sm">Informe preliminar</label>
              <TextArea
                rows={3}
                value={form.informe_preliminar}
                onChange={onChange("informe_preliminar")}
              />
            </div>
            <div className="md:col-span-2">
              <label className="text-sm">Accesorios</label>
              <TextArea
                rows={2}
                value={form.accesorios}
                onChange={onChange("accesorios")}
              />
            </div>
          </div>
        </fieldset>

        <div className="flex gap-3">
          <button
            disabled={
              loading || !canSubmitCliente || !marcaId || !form.equipo.modelo_id
            }
            className={`px-4 py-2 rounded text-white ${
              loading ||
              !canSubmitCliente ||
              !marcaId ||
              !form.equipo.modelo_id
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
