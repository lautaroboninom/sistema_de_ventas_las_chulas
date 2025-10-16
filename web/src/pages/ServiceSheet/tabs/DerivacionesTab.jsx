import { Link } from "react-router-dom";
import { formatDateTime as formatDateTimeHelper } from "../../../lib/ui-helpers";

export default function DerivacionesTab({
  id,
  derivs,
  fechaDevStr,
  setFechaDevStr,
  savingDev,
  onMarcarDevuelto,
}) {
  const hayDerivAbierta = Array.isArray(derivs) && derivs.find(d => !d.fecha_entrega);
  return (
    <div className="border rounded p-4"> 
      <div className="flex items-center gap-3 mb-3">
        <h2 className="font-semibold">Derivaciones</h2>
        <div className="ml-auto flex items-center gap-2">
          <Link to={`/ingresos/${id}/derivar`} className="bg-neutral-800 text-white px-3 py-2 rounded">Derivar a externo</Link>
          {hayDerivAbierta && (
            <>
              <input
                type="date"
                className="border rounded p-2"
                value={fechaDevStr}
                onChange={(e) => setFechaDevStr(e.target.value)}
                aria-label="Fecha de devolución"
              />
              <button
                className="bg-green-700 text-white px-3 py-2 rounded disabled:opacity-60"
                disabled={savingDev}
                onClick={onMarcarDevuelto}
                type="button"
              >
                {savingDev ? "Guardando..." : "Devuelto"}
              </button>
            </>
          )}
        </div>
      </div>

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
  );
}

