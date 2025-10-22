import { formatDateTime as formatDateTimeHelper } from "../../../lib/ui-helpers";

export default function HistorialTab({ hErr, hLoading, hist }) {
  return (
    <div className="border rounded p-4">
      <h2 className="font-semibold mb-2">Historial de cambios</h2>
      {hErr && <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-3">{hErr}</div>}
      {hLoading ? (
        <div className="text-sm text-gray-500">Cargando...</div>
      ) : (
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left">
              <th className="p-2">Fecha</th>
              <th className="p-2">Usuario</th>
              <th className="p-2">Rol</th>
              <th className="p-2">Entidad</th>
              <th className="p-2">Campo</th>
              <th className="p-2">Antes</th>
              <th className="p-2">Después</th>
            </tr>
          </thead>
          <tbody>
            {(hist || []).length === 0 ? (
              <tr>
                <td className="p-2 text-gray-500" colSpan={7}>
                  No hay cambios registrados.
                </td>
              </tr>
            ) : (
              hist.map((r, idx) => (
                <tr key={idx} className="border-t">
                  <td className="p-2 whitespace-nowrap">{formatDateTimeHelper(r.ts)}</td>
                  <td className="p-2">{r.user_id || '-'}</td>
                  <td className="p-2 whitespace-nowrap">{r.user_role || '-'}</td>
                  <td className="p-2">{r.table_name}</td>
                  <td className="p-2">{r.column_name}</td>
                  <td className="p-2">{r.old_value || '-'}</td>
                  <td className="p-2">{r.new_value || '-'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}







