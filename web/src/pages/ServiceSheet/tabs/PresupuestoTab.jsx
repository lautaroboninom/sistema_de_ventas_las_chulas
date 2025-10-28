import { useEffect, useState } from "react";
import { getBlob } from "../../../lib/api";
import {
  getQuote,
  postQuoteItem,
  patchQuoteItem,
  deleteQuoteItem,
  patchQuoteResumen,
  postQuoteEmitir,
  postQuoteAprobar,
  postQuoteAnular,
  postQuoteNoAplica,
  postQuoteQuitarNoAplica,
} from "../../../lib/api";

export default function PresupuestoTab({ id, data, canManagePresupuesto, money, refreshIngreso, setErr }) {
  const isAprobado = data.presupuesto_estado === "aprobado";

  const [qErr, setQErr] = useState("");
  const [qLoading, setQLoading] = useState(false);
  const [quote, setQuote] = useState(null);

  const [autorizadoPor, setAutorizadoPor] = useState("Cliente");
  const [formaPago, setFormaPago] = useState("30 F.F.");
  const [emitiendo, setEmitiendo] = useState(false);
  const [aprobando, setAprobando] = useState(false);
  const [anulando, setAnulando] = useState(false);

  const [nuevoRep, setNuevoRep] = useState({ repuesto_id: "", descripcion: "", qty: "1", precio_u: "" });
  const [manoObraStr, setManoObraStr] = useState("");

  async function loadQuote() {
    try {
      setQErr("");
      setQLoading(true);
      const q = await getQuote(id);
      setQuote(q);
      setManoObraStr(String(q?.mano_obra ?? "0"));
      setFormaPago(q?.forma_pago ?? "30 F.F.");
    } catch (e) {
      setQErr(e?.message || "No se pudo cargar el presupuesto");
      setQuote(null);
    } finally {
      setQLoading(false);
    }
  }

  useEffect(() => { loadQuote(); }, [id]);

  async function abrirPdf() {
    try {
      setQErr("");
      const blob = await getBlob(`/api/quotes/${id}/pdf/`);
      if (!(blob instanceof Blob)) throw new Error("La respuesta del API no fue un Blob.");
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      setQErr(e?.message || "No se pudo abrir el PDF del presupuesto");
    }
  }

  async function emitirPresupuesto() {
    try {
      setEmitiendo(true);
      const r = await postQuoteEmitir(id, { autorizado_por: autorizadoPor, forma_pago: formaPago });
      setQuote(r);
      if (typeof refreshIngreso === "function") await refreshIngreso();
      if (r?.pdf_url) await abrirPdf();
    } catch (e) {
      setQErr(e?.message || "No se pudo emitir el presupuesto");
    } finally {
      setEmitiendo(false);
    }
  }

  async function anularPresupuesto() {
    if (!confirm("Anular el presupuesto actual? Podrás editar y re-emitir luego.")) return;
    try {
      setAnulando(true);
      setQErr("");
      const r = await postQuoteAnular(id);
      setQuote(r);
      if (typeof refreshIngreso === "function") await refreshIngreso();
    } catch (e) {
      setQErr(e?.message || "No se pudo anular el presupuesto");
    } finally {
      setAnulando(false);
    }
  }

  async function aprobarPresupuesto() {
    try {
      setAprobando(true);
      setQErr("");
      const shouldPrint = (data?.estado || "").toLowerCase() === "reparado" &&
        window.confirm("Este equipo ya está reparado, imprimir remito de salida?");

      const r = await postQuoteAprobar(id);
      setQuote(r);
      if (shouldPrint && typeof refreshIngreso === "function") {
        try {
          const blob = await getBlob(`/api/ingresos/${id}/remito/`);
          if (!(blob instanceof Blob)) throw new Error("La respuesta no fue un PDF");
          const url = URL.createObjectURL(blob);
          window.open(url, "_blank", "noopener");
          setTimeout(() => URL.revokeObjectURL(url), 60_000);
          await refreshIngreso();
        } catch (e) {
          setQErr(e?.message || "No se pudo imprimir el remito de salida");
        }
      }
      if (typeof refreshIngreso === "function") await refreshIngreso();
    } catch (e) {
      setQErr(e?.message || "No se pudo aprobar el presupuesto");
    } finally {
      setAprobando(false);
    }
  }

  async function marcarNoAplica() {
    try {
      setQErr("");
      setEmitiendo(true);
      const r = await postQuoteNoAplica(id);
      setQuote(r);
      if (typeof refreshIngreso === "function") await refreshIngreso();
    } catch (e) {
      setQErr(e?.message || "No se pudo marcar 'No aplica'");
    } finally {
      setEmitiendo(false);
    }
  }

  async function quitarNoAplica() {
    try {
      setQErr("");
      setEmitiendo(true);
      const r = await postQuoteQuitarNoAplica(id);
      setQuote(r);
      if (typeof refreshIngreso === "function") await refreshIngreso();
    } catch (e) {
      setQErr(e?.message || "No se pudo quitar 'No aplica'");
    } finally {
      setEmitiendo(false);
    }
  }

  async function addRepuesto() {
    const qty = Number(nuevoRep.qty || 0);
    const pu  = Number(nuevoRep.precio_u || 0);
    if (!nuevoRep.descripcion.trim()) { setQErr("Descripción requerida"); return; }
    //if (qty <= 0) { setQErr("Cantidad > 0"); return; }
    if (pu < 0) { setQErr("Precio inválido"); return; }
    await postQuoteItem(id, {
      tipo: "repuesto",
      repuesto_id: nuevoRep.repuesto_id ? Number(nuevoRep.repuesto_id) : null,
      descripcion: nuevoRep.descripcion.trim(),
      qty, precio_u: pu,
    });
    setNuevoRep({ repuesto_id: "", descripcion: "", qty: "1", precio_u: "" });
    await loadQuote();
  }

  async function updateItem(it, patchRow) { await patchQuoteItem(id, it.id, patchRow); await loadQuote(); }
  async function handleRemoveItem(it) {
    if (!confirm("Eliminar renglón?")) return;
    try {
      await deleteQuoteItem(id, it.id);
      await loadQuote();
    } catch (e) {
      setQErr(e?.message || "No se pudo eliminar el renglón");
    }
  }
  async function saveManoObra() {
    const mo = Number(manoObraStr || 0);
    if (mo < 0) { setQErr("Mano de obra inválida"); return; }
    await patchQuoteResumen(id, { mano_obra: mo });
    await loadQuote();
  }

  return (
    <div className="border rounded p-4">

      <div className="border rounded p-3 mb-4 bg-gray-50">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <div className="text-sm text-gray-600">Diagnóstico</div>
            <div className="whitespace-pre-wrap">{(data?.descripcion_problema || "-")}</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Trabajos realizados</div>
            <div className="whitespace-pre-wrap">{(data?.trabajos_realizados || "-")}</div>
          </div>
        </div>
      </div>

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
            <div className="mb-3 text-sm text-emerald-700">Presupuesto aprobado - los tems y valores ya no son editables.</div>
          )}

          <h3 className="font-medium mb-2">Repuestos</h3>
          <table className="min-w-full text-sm mb-3">
            <thead>
              <tr className="text-left">
                <th className="p-2 w-28">IdRepuesto</th>
                <th className="p-2">Descripción</th>
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
                        value={it.repuesto_id || ""}
                        onChange={(e) => updateItem(it, { repuesto_id: e.target.value })}
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
                  <input className="border rounded p-1 w-full" placeholder="Descripción del repuesto" value={nuevoRep.descripcion} onChange={(e) => setNuevoRep((s) => ({ ...s, descripcion: e.target.value }))} disabled={isAprobado} />
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
              <div className="text-gray-600 text-sm">IVA 21%</div>
              <div className="text-lg font-semibold">{money(quote.iva_21)}</div>
            </div>
            <div className="border rounded p-3">
              <div className="text-gray-600 text-sm">Total</div>
              <div className="text-lg font-semibold">{money(quote.subtotal)}</div>
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





