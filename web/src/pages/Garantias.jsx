import { useState } from "react";
import { checkGarantiaFabrica } from "@/lib/api";

export default function Garantias() {
  const [marca, setMarca] = useState("");
  const [ns, setNs] = useState("");
  const [out, setOut] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

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
        Vista preliminar para verificar garantía de fábrica por número de serie en trazabilidad.
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
          {out.meta && (
            <div className="mt-2 text-gray-600">
              <div><b>Archivo:</b> {String(out.meta.file || "").replaceAll("\\\\", "\\")}</div>
              <div><b>Hoja:</b> {out.meta.sheet || "-"}</div>
              <div><b>Serie (crudo):</b> {out.meta.serial_value || "-"}</div>
            </div>
          )}
        </div>
      )}

      <div className="mt-6 text-xs text-gray-500">
        Próximamente: políticas por marca/modelo y excepciones por N/S. Ver docs/TODO_garantias.md.
      </div>
    </div>
  );
}


