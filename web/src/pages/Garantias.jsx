import { useEffect, useMemo, useState } from "react";
import {
  checkGarantiaFabrica,
  listWarrantyRules,
  createWarrantyRule,
  deleteWarrantyRule,
  patchWarrantyRule,
  getMarcas,
  getModelosByBrand,
} from "@/lib/api";

export default function Garantias() {
  const [marca, setMarca] = useState("");
  const [ns, setNs] = useState("");
  const [out, setOut] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  // Excepciones
  const [marcas, setMarcas] = useState([]);
  const [marcaId, setMarcaId] = useState("");
  const [modelos, setModelos] = useState([]);
  const [modeloId, setModeloId] = useState("");
  const [rules, setRules] = useState([]);
  const [ruleDays, setRuleDays] = useState(365);
  const [ruleNotas, setRuleNotas] = useState("");
  const [busyRule, setBusyRule] = useState(false);
  const [modelNames, setModelNames] = useState({}); // { model_id: nombre }
  const [loadedBrands, setLoadedBrands] = useState(new Set());

  useEffect(() => {
    (async () => {
      try {
        const ms = await getMarcas();
        setMarcas(ms || []);
      } catch {}
      try {
        const rs = await listWarrantyRules({ activo: 1 });
        setRules(Array.isArray(rs) ? rs : []);
      } catch {}
    })();
  }, []);

  useEffect(() => {
    (async () => {
      if (!marcaId) {
        setModelos([]);
        return;
      }
      try {
        const mods = await getModelosByBrand(marcaId);
        setModelos(mods || []);
      } catch {}
    })();
  }, [marcaId]);
  // Resolver nombres de modelos para cada brand_id de las reglas
  useEffect(() => {
    (async () => {
      if (!Array.isArray(rules) || rules.length === 0) return;
      const distinctBrands = Array.from(new Set(rules.map(r => r.brand_id).filter(Boolean)));
      const toLoad = distinctBrands.filter(bid => !loadedBrands.has(bid));
      if (toLoad.length === 0) return;
      const newModelNames = { ...modelNames };
      const newLoaded = new Set(loadedBrands);
      for (const bid of toLoad) {
        try {
          const mods = await getModelosByBrand(bid);
          (mods || []).forEach(m => { if (m?.id) newModelNames[m.id] = m.nombre || String(m.id); });
          newLoaded.add(bid);
        } catch {}
      }
      setModelNames(newModelNames);
      setLoadedBrands(newLoaded);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(rules)]);

  async function probe(e) {
    e?.preventDefault?.();
    setLoading(true);
    setErr("");
    setOut(null);
    try {
      const r = await checkGarantiaFabrica(ns.trim(), marca.trim());
      setOut(r || null);
    } catch (e) {
      setErr(e?.message || "Error consultando garantía");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-3">Garantías</h1>
      <p className="text-sm text-gray-600 mb-4">
        Por defecto todas las garantías son de 1 año. Configure aquí las excepciones por marca/modelo.
      </p>
      <form className="flex flex-wrap items-end gap-3 mb-4" onSubmit={probe}>
        <div>
          <label className="block text-sm mb-1">Marca (opcional)</label>
          <input
            className="border rounded p-2 w-64"
            value={marca}
            onChange={(e) => setMarca(e.target.value)}
            placeholder="YUWELL, BMC, etc"
          />
        </div>
        <div>
          <label className="block text-sm mb-1">Número de serie</label>
          <input
            className="border rounded p-2 w-64"
            value={ns}
            onChange={(e) => setNs(e.target.value)}
            placeholder="20810302"
          />
        </div>
        <div>
          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-50"
          >
            {loading ? "Consultando..." : "Verificar"}
          </button>
        </div>
      </form>

      {err && <div className="text-red-600 text-sm mb-2">{err}</div>}
      {out && (
        <div className="border rounded p-3 text-sm">
          <div>
            <b>Dentro de 365 días:</b> {out.within_365_days ? "Sí" : "No"}
          </div>
          <div>
            <b>Fecha de venta:</b> {out.fecha_venta || "-"}
          </div>
          {out.garantia_vence && (
            <div>
              <b>Vence:</b> {out.garantia_vence}
            </div>
          )}
          {out.meta && (
            <div className="mt-2 text-gray-600">
              <div><b>Archivo:</b> {String(out.meta.file || "").replaceAll("\\\\", "\\")}</div>
              <div><b>Hoja:</b> {out.meta.sheet || "-"}</div>
              <div><b>Serie (crudo):</b> {out.meta.serial_value || "-"}</div>
            </div>
          )}
        </div>
      )}

      {/* Excepciones */}
      <div className="mt-8">
        <h2 className="font-semibold mb-2">Excepciones de garantía</h2>
        <div className="text-xs text-gray-600 mb-3">Las nuevas reglas requieren rol de administrador.</div>
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <div>
            <label className="block text-sm mb-1">Marca</label>
            <select className="border rounded p-2 w-64" value={marcaId} onChange={(e) => { setMarcaId(e.target.value); setModeloId(""); }}>
              <option value="">-- Seleccione --</option>
              {(marcas || []).map(m => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm mb-1">Modelo</label>
            <select className="border rounded p-2 w-64" value={modeloId} onChange={(e) => setModeloId(e.target.value)} disabled={!marcaId}>
              <option value="">-- (opcional) --</option>
              {(modelos || []).map(m => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm mb-1">Duración (días)</label>
            <input className="border rounded p-2 w-40" type="number" min={1} value={ruleDays} onChange={(e) => setRuleDays(Number(e.target.value || 0))} />
          </div>
          <div>
            <label className="block text-sm mb-1">Notas</label>
            <input className="border rounded p-2 w-64" value={ruleNotas} onChange={(e) => setRuleNotas(e.target.value)} />
          </div>
          <div>
            <button disabled={busyRule || !ruleDays || (!marcaId && !modeloId)} onClick={async () => {
              try {
                setBusyRule(true);
                const payload = { days: ruleDays };
                if (marcaId) payload.brand_id = Number(marcaId);
                if (modeloId) payload.model_id = Number(modeloId);
                if (ruleNotas) payload.notas = ruleNotas;
                await createWarrantyRule(payload);
                const rs = await listWarrantyRules({ activo: 1 });
                setRules(Array.isArray(rs) ? rs : []);
                setRuleNotas("");
              } catch (e) {
                alert(e?.message || "Error creando regla");
              } finally {
                setBusyRule(false);
              }
            }} className="bg-green-600 text-white px-3 py-2 rounded disabled:opacity-50">Agregar</button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="p-2">ID</th>
                <th className="p-2">Marca</th>
                <th className="p-2">Modelo</th>
                <th className="p-2">Días</th>
                <th className="p-2">Notas</th>
                <th className="p-2">Activo</th>
                <th className="p-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {(rules || []).map(r => (
                <tr key={r.id} className="border-t">
                  <td className="p-2">{r.id}</td>
                  <td className="p-2">{(marcas.find(m => m.id === r.brand_id)?.nombre) || (r.brand_id || "-")}</td>
                  <td className="p-2">{(r.model_id ? (modelNames[r.model_id] || r.model_id) : "-")}</td>
                  <td className="p-2">
                    <input
                      type="number"
                      min={1}
                      className="border rounded p-1 w-24"
                      value={r.days}
                      onChange={(e) => setRules(prev => prev.map(rr => rr.id === r.id ? { ...rr, days: Number(e.target.value || 0) } : rr))}
                    />
                  </td>
                  <td className="p-2">
                    <input
                      className="border rounded p-1 w-56"
                      value={r.notas || ""}
                      onChange={(e) => setRules(prev => prev.map(rr => rr.id === r.id ? { ...rr, notas: e.target.value } : rr))}
                    />
                  </td>
                  <td className="p-2">
                    <input
                      type="checkbox"
                      checked={!!r.activo}
                      onChange={async (e) => {
                        const checked = !!e.target.checked;
                        setRules(prev => prev.map(rr => rr.id === r.id ? { ...rr, activo: checked } : rr));
                        try {
                          await patchWarrantyRule(r.id, { activo: checked });
                          const rs = await listWarrantyRules({ activo: 1 });
                          setRules(Array.isArray(rs) ? rs : []);
                        } catch (err) {
                          alert(err?.message || "Error guardando activo");
                        }
                      }}
                    />
                  </td>
                  <td className="p-2">
                    <button
                      className="text-blue-600 underline mr-3"
                      onClick={async () => {
                        try {
                          await patchWarrantyRule(r.id, { days: Number(r.days || 0), notas: r.notas || "", activo: !!r.activo });
                          const rs = await listWarrantyRules({ activo: 1 });
                          setRules(Array.isArray(rs) ? rs : []);
                        } catch (e) {
                          alert(e?.message || "Error guardando regla");
                        }
                      }}
                    >Guardar</button>
                    <button className="text-red-600 underline" onClick={async () => {
                      if (!confirm("¿Eliminar (desactivar) regla?")) return;
                      try {
                        await deleteWarrantyRule(r.id);
                        const rs = await listWarrantyRules({ activo: 1 });
                        setRules(Array.isArray(rs) ? rs : []);
                      } catch (e) {
                        alert(e?.message || "Error eliminando regla");
                      }
                    }}>Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
