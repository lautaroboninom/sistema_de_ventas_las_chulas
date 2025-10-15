export default function PresupuestoTab({
  id,
  data,
  canManagePresupuesto,
  qErr,
  qLoading,
  quote,
  abrirPdf,
  autorizadoPor,
  setAutorizadoPor,
  formaPago,
  setFormaPago,
  emitiendo,
  emitirPresupuesto,
  aprobando,
  aprobarPresupuesto,
  anulando,
  anularPresupuesto,
  marcarNoAplica,
  quitarNoAplica,
  nuevoRep,
  setNuevoRep,
  addRepuesto,
  updateItem,
  handleRemoveItem,
  manoObraStr,
  setManoObraStr,
  saveManoObra,
  money,
}) {
  const isAprobado = data.presupuesto_estado === "aprobado";
  return (
    <div className="border rounded p-4">
      <h2 className="font-semibold mb-3">Presupuesto</h2>

      {qErr && (
        <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-3">{qErr}</div>
      )}

      <div className="flex gap-3 items-end mb-4">
        <label className="block">
          <div className="text-sm text-gray-600">Autorizado por</div>
          <input className="border rounded p-2" value={autorizadoPor} onChange={(e) => setAutorizadoPor(e.target.value)} />
        </label>
        <label className="block">
          <div className="text-sm text-gray-600">Forma de pago</div>
          <input className="border rounded p-2" value={formaPago} onChange={(e) => setFormaPago(e.target.value)} />
        </label>
        {canManagePresupuesto && data.presupuesto_estado === "pendiente" && (
          <button className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60" onClick={emitirPresupuesto} disabled={emitiendo}>
            {emitiendo ? "Emitiendo..." : "Emitir presupuesto"}
          </button>
        )}
        {["presupuestado", "aprobado"].includes(data.presupuesto_estado) && (
          <button className="underline text-blue-700" onClick={abrirPdf} type="button">
            Ver/Descargar PDF
          </button>
        )}
        {canManagePresupuesto && data.presupuesto_estado === "presupuestado" && (
          <button className="bg-emerald-600 text-white px-3 py-2 rounded disabled:opacity-60" onClick={aprobarPresupuesto} disabled={aprobando} type="button">
            {aprobando ? "Aprobando..." : "Aprobar presupuesto"}
          </button>
        )}
        {canManagePresupuesto && data.presupuesto_estado === "presupuestado" && (
          <button className="bg-red-600 text-white px-3 py-2 rounded disabled:opacity-60" onClick={anularPresupuesto} disabled={anulando} type="button">
            {anulando ? "Anulando..." : "Anular presupuesto"}
          </button>
        )}
        {canManagePresupuesto && data.presupuesto_estado === "pendiente" && (
          <button className="bg-neutral-600 text-white px-3 py-2 rounded disabled:opacity-60" onClick={marcarNoAplica} disabled={emitiendo} type="button">
            {emitiendo ? "Marcando..." : "No aplica"}
          </button>
        )}
        {canManagePresupuesto && data.presupuesto_estado === "no_aplica" && (
          <button className="bg-neutral-500 text-white px-3 py-2 rounded disabled:opacity-60" onClick={quitarNoAplica} disabled={emitiendo} type="button">
            {emitiendo ? "Marcando..." : "Quitar 'No aplica'"}
          </button>
        )}
      </div>

      {qLoading || !quote ? (
        <div>Cargando...</div>
      ) : (
        <>
          {isAprobado && (
            <div className="mb-3 text-sm text-emerald-700">Presupuesto aprobado - los items y valores ya no son editables.</div>
          )}

          <h3 className="font-medium mb-2">Repuestos</h3>
          <table className="min-w-full text-sm mb-3">
            <thead>
              <tr className="text-left">
                <th className="p-2 w-28">IdRepuesto</th>
                <th className="p-2">Descripcion</th>
                <th className="p-2 w-24">Cantidad</th>
                <th className="p-2 w-36">Precio unit.</th>
                <th className="p-2 w-36 text-right">Subtotal</th>
                <th className="p-2 w-20"></th>
              </tr>
            </thead>
            <tbody>
              {quote.items
                .filter((it) => it.tipo === "repuesto")
                .map((it) => (
                  <tr key={it.id} className="border-t">
                    <td className="p-2">
                      <input
                        className="border rounded p-1 w-24"
                        value={it.repuesto_id ?? ""}
                        onChange={(e) => updateItem(it, { repuesto_id: e.target.value ? Number(e.target.value) : null })}
                        disabled={isAprobado}
                      />
                    </td>
                    <td className="p-2">
                      <input
                        className="border rounded p-1 w-full"
                        value={it.descripcion || ""}
                        onChange={(e) => updateItem(it, { descripcion: e.target.value })}
                        disabled={isAprobado}
                      />
                    </td>
                    <td className="p-2">
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        className="border rounded p-1 w-24 text-right"
                        value={it.qty}
                        onChange={(e) => updateItem(it, { qty: Number(e.target.value || 0) })}
                        disabled={isAprobado}
                      />
                    </td>
                    <td className="p-2">
                      <input
                        type="number"
                        step="0.01"
                        className="border rounded p-1 w-32 text-right"
                        value={it.precio_u}
                        onChange={(e) => updateItem(it, { precio_u: Number(e.target.value || 0) })}
                        disabled={isAprobado}
                      />
                    </td>
                    <td className="p-2 text-right">{money(it.subtotal)}</td>
                    <td className="p-2">
                      <button className="text-red-600 hover:underline" onClick={() => handleRemoveItem(it)} type="button" disabled={isAprobado}>
                        borrar
                      </button>
                    </td>
                  </tr>
                ))}

              <tr className="border-t bg-gray-50">
                <td className="p-2">
                  <input className="border rounded p-1 w-24" placeholder="(opcional)" value={nuevoRep.repuesto_id} onChange={(e) => setNuevoRep((s) => ({ ...s, repuesto_id: e.target.value }))} disabled={isAprobado} />
                </td>
                <td className="p-2">
                  <input className="border rounded p-1 w-full" placeholder="Descripcion del repuesto" value={nuevoRep.descripcion} onChange={(e) => setNuevoRep((s) => ({ ...s, descripcion: e.target.value }))} disabled={isAprobado} />
                </td>
                <td className="p-2">
                  <input type="number" step="0.01" min="0" className="border rounded p-1 w-24 text-right" value={nuevoRep.qty} onChange={(e) => setNuevoRep((s) => ({ ...s, qty: e.target.value }))} disabled={isAprobado} />
                </td>
                <td className="p-2">
                  <input type="number" step="0.01" className="border rounded p-1 w-32 text-right" placeholder="0.00" value={nuevoRep.precio_u} onChange={(e) => setNuevoRep((s) => ({ ...s, precio_u: e.target.value }))} disabled={isAprobado} />
                </td>
                <td className="p-2"></td>
                <td className="p-2">
                  <button className="bg-blue-600 text-white px-2 py-1 rounded" onClick={addRepuesto} type="button" disabled={isAprobado}>
                    agregar
                  </button>
                </td>
              </tr>
            </tbody>
          </table>

          <div className="flex items-end gap-3 mb-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Mano de obra</label>
              <input type="number" step="0.01" min="0" className="border rounded p-2 w-48 text-right" value={manoObraStr} onChange={(e) => setManoObraStr(e.target.value)} disabled={isAprobado} />
            </div>
            <button className="bg-blue-600 text-white px-3 py-2 rounded" onClick={saveManoObra} type="button" disabled={isAprobado}>
              Guardar
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div className="border rounded p-3">
              <div className="text-gray-600 text-sm">Total repuestos</div>
              <div className="text-lg font-semibold">{money(quote.tot_repuestos)}</div>
            </div>
            <div className="border rounded p-3">
              <div className="text-gray-600 text-sm">Mano de obra</div>
              <div className="text-lg font-semibold">{money(quote.mano_obra)}</div>
            </div>
            <div className="border rounded p-3">
              <div className="text-gray-600 text-sm">Subtotal</div>
              <div className="text-lg font-semibold">{money(quote.subtotal)}</div>
            </div>
            <div className="border rounded p-3">
              <div className="text-gray-600 text-sm">IVA 21%</div>
              <div className="text-lg font-semibold">{money(quote.iva_21)}</div>
            </div>
            <div className="border rounded p-3">
              <div className="text-gray-600 text-sm">Costo cliente (con IVA)</div>
              <div className="text-xl font-bold">{money(quote.total)}</div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}


