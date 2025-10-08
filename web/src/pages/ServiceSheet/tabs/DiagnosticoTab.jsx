import Row from "../../../components/Row";
import IngresoPhotos from "../../../components/IngresoPhotos";
import { RESOLUCION_OPTIONS } from "../../../lib/constants";
import { postMarcarReparado } from "../../../lib/api";

export default function DiagnosticoTab({
  id,
  data,
  // accesorios
  canEditAcc,
  accesCatalogo,
  nuevoAcc,
  setNuevoAcc,
  addingAcc,
  deletingAccId,
  removeAccesorio,
  addAccesorio,
  // diagnostico/trabajos
  descripcion,
  setDescripcion,
  trabajos,
  setTrabajos,
  saveDiagYreparacion,
  savingAll,
  // fecha servicio
  fechaServStr,
  setFechaServStr,
  maxLocalNow,
  // resolucion
  canResolve,
  resolucion,
  setResolucion,
  savingResol,
  saveResolucion,
  // permisos
  actAsTech,
  // helpers
  patch,
  setErr,
  refreshIngreso,
  setShowReparadoToast,
  // fotos
  canManagePhotos,
}) {
  return (
    <div className="border rounded p-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        <div className="border rounded p-3 bg-gray-50">
          <div className="text-xs uppercase text-gray-500 mb-1">Informe preliminar</div>
          <div className="whitespace-pre-wrap">{data.informe_preliminar || "-"}</div>
        </div>
        <div className="border rounded p-3 bg-gray-50">
          <div className="text-xs uppercase text-gray-500 mb-1">Accesorios</div>
          <div>
            {Array.isArray(data.accesorios_items) && data.accesorios_items.length > 0 ? (
              <ul className="list-disc list-inside text-sm">
                {data.accesorios_items.map((it) => (
                  <li key={it.id} className="flex items-center justify-between gap-2">
                    <span>
                      {it.accesorio_nombre}
                      {it.referencia ? ` (ref: ${it.referencia})` : ""}
                    </span>
                    {canEditAcc && (
                      <button
                        className="text-red-600 text-xs"
                        onClick={() => removeAccesorio(it.id)}
                        disabled={deletingAccId === it.id}
                        type="button"
                      >
                        {deletingAccId === it.id ? "quitando..." : "quitar"}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="whitespace-pre-wrap">{data.accesorios || "-"}</div>
            )}
          </div>

          {canEditAcc && (
            <div className="mt-3 border-t pt-3">
              <div className="text-xs uppercase text-gray-500 mb-2">Agregar accesorio</div>
              <div className="flex flex-wrap items-end gap-2">
                <input
                  className="border rounded p-2 min-w-[240px]"
                  list="accesorios_catalogo"
                  placeholder="Descripcion (elegi de la lista)"
                  value={nuevoAcc.descripcion}
                  onChange={(e) => setNuevoAcc((s) => ({ ...s, descripcion: e.target.value }))}
                />
                <datalist id="accesorios_catalogo">
                  {accesCatalogo.map((a) => (
                    <option key={a.id} value={a.nombre} />
                  ))}
                </datalist>
                <input
                  className="border rounded p-2 w-40"
                  placeholder="Nro referencia (opcional)"
                  value={nuevoAcc.referencia}
                  onChange={(e) => setNuevoAcc((s) => ({ ...s, referencia: e.target.value }))}
                />
                <button
                  className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
                  onClick={addAccesorio}
                  disabled={addingAcc || !(nuevoAcc.descripcion || "").trim()}
                  type="button"
                >
                  {addingAcc ? "agregando..." : "agregar"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <h2 className="font-semibold mb-2">Descripcion del problema (diagnostico)</h2>

      <div className="flex flex-wrap items-end gap-3 mb-3">
        <div>
          <label className="block text-sm text-gray-600 mb-1">Fecha de servicio</label>
          <input
            type="datetime-local"
            className="border rounded p-2"
            value={fechaServStr}
            onChange={(e) => {
              const el = e.currentTarget;
              const v = el.value;
              setFechaServStr(v);
              if (v) setTimeout(() => el.blur(), 0);
            }}
            max={maxLocalNow}
            placeholder="YYYY-MM-DD HH:mm"
          />
        </div>

        <div className="ml-auto flex items-end gap-2">
          {canResolve && (
            <>
              <div className="min-w-[260px]">
                <label className="block text-sm text-gray-600 mb-1">Resolución de reparación</label>
                <select
                  className="border rounded p-2 w-full"
                  value={resolucion}
                  onChange={(e) => setResolucion(e.target.value)}
                  disabled={data?.estado === "entregado"}
                >
                  <option value="">-- Seleccionar --</option>
                  {RESOLUCION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
                disabled={savingResol || !resolucion}
                onClick={saveResolucion}
                type="button"
              >
                {savingResol ? "Guardando..." : "Guardar resolucion"}
              </button>
            </>
          )}

          {actAsTech && !["reparado", "liberado", "entregado"].includes(data?.estado) && (
            <button
              className="bg-emerald-600 text-white px-3 py-2 rounded"
              onClick={async () => {
                try {
                  await postMarcarReparado(id);
                  await refreshIngreso();
                  setShowReparadoToast(true);
                  setTimeout(() => setShowReparadoToast(false), 2000);
                } catch (e) {
                  setErr(e?.message || "No se pudo marcar como reparado");
                }
              }}
              type="button"
            >
              Marcar reparado
            </button>
          )}
        </div>
      </div>

      <textarea
        className="w-full border rounded p-2 min-h-[180px]"
        value={descripcion}
        onChange={(e) => setDescripcion(e.target.value)}
        placeholder="Ej.: Ingreso de agua; placa de control con oxido; valvula X no abre..."
      />

      <div className="border rounded p-4 mt-4">
        <h2 className="font-semibold mb-2">Trabajos realizados</h2>
        <textarea
          className="w-full border rounded p-2 min-h-[200px]"
          value={trabajos}
          onChange={(e) => setTrabajos(e.target.value)}
          placeholder="Ej.: Cambio de turbina; limpieza y secado; resoldado de conector; calibración; pruebas OK."
        />
        <div className="mt-2 flex items-center gap-2">
          <button
            className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
            onClick={saveDiagYreparacion}
            disabled={savingAll}
            aria-busy={savingAll ? "true" : "false"}
            type="button"
          >
            {savingAll ? "Guardando..." : "Guardar"}
          </button>
        </div>
      </div>

      <IngresoPhotos ingresoId={Number(id)} canManage={canManagePhotos} />

      <Row label="Faja de garantia Nro">
        <input
          className="border rounded p-1 w-60"
          value={data.faja_garantia || ""}
          onChange={(e) => patch({ faja_garantia: e.target.value })}
        />
      </Row>
    </div>
  );
}


