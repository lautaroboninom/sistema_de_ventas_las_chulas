import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getGeneralEquipos } from "../lib/api";
import { formatDateOnly as formatDateOnlyHelper, formatOS as formatOSHelper, tipoEquipoOf, resolveFechaIngreso, resolveFechaCreacion } from "../lib/ui-helpers";

export default function BuscarNS() {
  const [sp] = useSearchParams();
  const ns = (sp.get("serie") || "").trim();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const nav = useNavigate();

  useEffect(() => {
    (async () => {
      setLoading(true); setErr("");
      try {
        // Normalizar consulta: si es MG vlido (MG ####), enviarlo tal cual al back
        const mgMatch = /^mg\s*\d{4}$/i.test(String(ns || "").trim());
        const data = await getGeneralEquipos(ns ? { q: ns } : {});
        const safe = Array.isArray(data) ? data : [];
        // Filtrar por coincidencia exacta de N/S o MG y ordenar por fecha de creacion (desc)
        const needle = String(ns || "").trim();
        const compact = needle.replace(/\s+/g, "").toLowerCase();
        const onlyMatches = safe
          .filter(r => {
            const serieCompact = String(r?.numero_serie || "").trim().replace(/\s+/g, "").toLowerCase();
            const internoCompact = String(r?.numero_interno || "").trim().replace(/\s+/g, "").toLowerCase();
            if (mgMatch) {
              // Aceptar solo MG exacto (MG ####)
              const mgDigits = compact.replace(/^mg/, "");
              const mgNoSpace = `mg${mgDigits}`;
              return serieCompact === mgNoSpace || internoCompact === mgNoSpace;
            }
            // De lo contrario, buscar por N/S exacto (no interpretar como MG)
            return serieCompact === compact;
          })
          .sort((a, b) => {
            const tb = resolveFechaCreacion(b);
            const ta = resolveFechaCreacion(a);
            return (tb ? new Date(tb).getTime() : 0) - (ta ? new Date(ta).getTime() : 0);
          });
        setRows(onlyMatches);
      } catch (e) {
        setErr(e?.message || "Error cargando resultados");
      } finally { setLoading(false); }
    })();
  }, [ns]);

  const titulo = ns ? `Resultados para N/S o MG: ${ns}` : "Búsqueda por N/S o MG";

  return (
    <div className="max-w-5xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">{titulo}</h1>
      {err && <div className="bg-red-100 text-red-700 border border-red-300 p-2 rounded">{err}</div>}
      {loading ? "Cargando..." :
        rows.length === 0 ? <div className="text-sm text-gray-500">No se encontraron ingresos con ese N° de serie o MG.</div> :
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="p-2">OS</th>
                <th className="p-2">Marca</th>
                <th className="p-2">Modelo</th>
                <th className="p-2">MG</th>
                <th className="p-2">N° serie</th>
                <th className="p-2">Tipo</th>
                <th className="p-2">Fecha de ingreso</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const ingresoId = r?.id;
                return (
                  <tr
                    key={ingresoId}
                    className="border-t hover:bg-gray-50 cursor-pointer"
                    onClick={() => nav(`/ingresos/${ingresoId}`)}
                    title="Ir a la hoja de servicio"
                  >
                    <td className="p-2 underline">{formatOSHelper(r, "")}</td>
                    <td className="p-2">{r?.marca || "-"}</td>
                    <td className="p-2">{r?.modelo || "-"}</td>
                    <td className="p-2">{r?.numero_interno || "-"}</td>
                    <td className="p-2">{r?.numero_serie || "-"}</td>
                    <td className="p-2">{tipoEquipoOf(r)}</td>
                    <td className="p-2 whitespace-nowrap">{formatDateOnlyHelper(resolveFechaIngreso(r))}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="text-xs text-gray-500 mt-2">Mostrando {rows.length} ingreso(s).</div>
        </div>}
    </div>
  );
}


