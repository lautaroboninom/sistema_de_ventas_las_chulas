import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getGeneralEquipos } from "../lib/api";
import { formatDateTime as formatDateTimeHelper, formatOS as formatOSHelper, tipoEquipoOf } from "../lib/ui-helpers";

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
        const data = await getGeneralEquipos(ns ? { q: ns } : {});
        const safe = Array.isArray(data) ? data : [];
        // Filtrar por coincidencia exacta de N/S y ordenar por fecha de ingreso (desc)
        const onlyNS = safe
          .filter(r => String(r?.numero_serie || "").trim() === ns)
          .sort((a,b)=> new Date(b?.fecha_ingreso||0) - new Date(a?.fecha_ingreso||0));
        setRows(onlyNS);
      } catch (e) {
        setErr(e?.message || "Error cargando resultados");
      } finally { setLoading(false); }
    })();
  }, [ns]);

  const titulo = ns ? `Resultados para N/S: ${ns}` : "Búsqueda por N/S";

  return (
    <div className="max-w-5xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">{titulo}</h1>
      {err && <div className="bg-red-100 text-red-700 border border-red-300 p-2 rounded">{err}</div>}
      {loading ? "Cargando..." :
        rows.length === 0 ? <div className="text-sm text-gray-500">No se encontraron ingresos con ese N° de serie.</div> :
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th className="p-2">OS</th>
                <th className="p-2">Marca</th>
                <th className="p-2">Modelo</th>
                <th className="p-2">Tipo</th>
                <th className="p-2">Fecha de ingreso</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const ingresoId = r?.id ?? r?.ingreso_id;
                return (
                  <tr
                    key={ingresoId}
                    className="border-t hover:bg-gray-50 cursor-pointer"
                    onClick={() => nav(`/ingresos/${ingresoId}`)}
                    title="Ir a la hoja de servicio"
                  >
                    <td className="p-2 underline">{formatOSHelper(r, ingresoId)}</td>
                    <td className="p-2">{r?.marca || "-"}</td>
                    <td className="p-2">{r?.modelo || "-"}</td>
                    <td className="p-2">{tipoEquipoOf(r)}</td>
                    <td className="p-2 whitespace-nowrap">{formatDateTimeHelper(r?.fecha_ingreso)}</td>
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
