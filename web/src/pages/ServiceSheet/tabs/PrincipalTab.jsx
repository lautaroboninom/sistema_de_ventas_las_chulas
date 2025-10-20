import Row from "../../../components/Row";
import { useMemo, useState, useEffect } from "react";
import { formatDateTime as formatDateTimeHelper, resolveFechaIngreso } from "../../../lib/ui-helpers";
import { resolutionLabel } from "../../../lib/constants";
import { getBlob, postEntregarIngreso, patchIngreso, checkGarantiaFabrica, patchIngresoTecnico, postSolicitarAsignacion } from "../../../lib/api";

export default function PrincipalTab(props) {
  const {
    id,
    data,
    release,
    numeroSerie,
    // basics edit
    editBasics,
    formBasics,
    setFormBasics,
    marcas,
    marcaIdSel,
    setMarcaIdSel,
    modelos,
    modeloIdSel,
    setModeloIdSel,
    variantes,
    // ubicacion/tecnico
    ubicaciones,
    ubicacionId,
    setUbicacionId,
    // savingUb,
    // saveUbicacion,
    // ubDirty,
    tecnicos,
    tecnicoId,
    setTecnicoId,
    // saveTecnico,
    // savingTech,
    // techDirty,
    canAssignTecnico,
    isTech,
    userId,
    // entrega
    canEditEntrega,
    editEntrega,
    setEditEntrega,
    entrega,
    setEntrega,
    savingEntrega,
    setSavingEntrega,
    // callbacks and helpers
    patch,
    refreshIngreso,
    setErr,
    setRelatedOpen,
    toDatetimeLocalStr,
  } = props;

  // Estados/dirty locales (encapsulados en el tab)
  const [savingTech, setSavingTech] = useState(false);
  const [savingUb, setSavingUb] = useState(false);
  const [mailEnviado, setMailEnviado] = useState(false);
  const [solicitando, setSolicitando] = useState(false);
  const techDirty = Boolean(canAssignTecnico && (tecnicoId ?? null) !== (data?.asignado_a ?? null));
  const _selUb = (ubicacionId ? Number(ubicacionId) : null);
  const _curUb = (data?.ubicacion_id ?? null);
  const ubDirty = _selUb !== null && _selUb !== _curUb;
  // Labels auxiliares (evitar expresiones JSX complejas)
  const pendingLabel = (() => {
    if (data?.tecnico_solicitado_nombre) return `Solicitud de asignación pendiente: ${data.tecnico_solicitado_nombre}`;
    if (data?.tecnico_solicitado_id) return `Solicitud de asignación pendiente (ID ${data.tecnico_solicitado_id})`;
    return "Solicitud de asignación pendiente";
  })();
  const otherTechLabel = (() => {
    const name = data?.tecnico_solicitado_nombre;
    const id = data?.tecnico_solicitado_id;
    const quien = name ? name : (id ? `ID ${id}` : "otro técnico");
    return `Ya hay una solicitud pendiente para ${quien}.`;
  })();

  async function saveTecnico() {
    if (!canAssignTecnico || !techDirty || tecnicoId == null) return;
    try {
      setSavingTech(true);
      await patchIngresoTecnico(id, Number(tecnicoId));
      await refreshIngreso();
      setErr("");
    } catch (e) {
      setErr(e?.message || "No se pudo asignar el técnico");
    } finally {
      setSavingTech(false);
    }
  }

  async function saveUbicacion() {
    if (!ubDirty) return;
    try {
      setSavingUb(true);
      await patch({ ubicacion_id: _selUb });
      setErr("");
    } catch (e) {
      setErr(e?.message || "No se pudo actualizar la ubicacion");
    } finally {
      setSavingUb(false);
    }
  }

  // Auto-chequeo de garanta de fbrica cuando se edita N/S
  useEffect(() => {
    if (!editBasics) return;
    const ns = (formBasics?.numero_serie || "").trim();
    const marcaName = (formBasics?.marca || data?.marca || "").toString();
    if (!ns) {
      if (formBasics) setFormBasics((s) => ({ ...(s || {}), garantia: false }));
      return;
    }
    const h = setTimeout(async () => {
      try {
        const r = await checkGarantiaFabrica(ns, marcaName);
        const enGarantia = !!r.within_365_days;
        setFormBasics((s) => ({ ...(s || {}), garantia: enGarantia }));
      } catch {
        /* noop */
      }
    }, 400);
    return () => clearTimeout(h);
  }, [editBasics, formBasics?.numero_serie, formBasics?.marca, data?.marca]);

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Columna izquierda: Cliente/Equipo/Notas */}
        <div className="border rounded p-4">
          <h2 className="font-semibold mb-2">Cliente</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
            <Row label="Razn social">
              {editBasics ? (
                <input
                  className="border rounded p-1 w-64"
                  value={formBasics?.razon_social ?? ""}
                  onChange={(e) => setFormBasics((s) => ({ ...s, razon_social: e.target.value }))}
                />
              ) : (
                data.razon_social
              )}
            </Row>
            <Row label="Cdigo empresa">
              {editBasics ? (
                <input
                  className="border rounded p-1 w-40"
                  value={formBasics?.cod_empresa ?? ""}
                  onChange={(e) => setFormBasics((s) => ({ ...s, cod_empresa: e.target.value }))}
                />
              ) : (
                data.cod_empresa || "-"
              )}
            </Row>
            <Row label="Telfono">
              {editBasics ? (
                <input
                  className="border rounded p-1 w-48"
                  value={formBasics?.telefono ?? ""}
                  onChange={(e) => setFormBasics((s) => ({ ...s, telefono: e.target.value }))}
                />
              ) : (
                data.telefono || "-"
              )}
            </Row>
          </div>

          {(editBasics || data.propietario_nombre || data.propietario_contacto || data.propietario_doc) && (
            <>
              <h2 className="font-semibold mt-4 mb-2">Propietario</h2>
              <Row label="Nombre">
                {editBasics ? (
                  <input
                    className="border rounded p-1 w-64"
                    value={formBasics?.propietario_nombre ?? ""}
                    onChange={(e) => setFormBasics((s) => ({ ...s, propietario_nombre: e.target.value }))}
                  />
                ) : (
                  data.propietario_nombre || "-"
                )}
              </Row>
              <Row label="Contacto">
                {editBasics ? (
                  <input
                    className="border rounded p-1 w-64"
                    value={formBasics?.propietario_contacto ?? ""}
                    onChange={(e) => setFormBasics((s) => ({ ...s, propietario_contacto: e.target.value }))}
                  />
                ) : (
                  data.propietario_contacto || "-"
                )}
              </Row>
              <Row label="Documento">
                {editBasics ? (
                  <input
                    className="border rounded p-1 w-64"
                    value={formBasics?.propietario_doc ?? ""}
                    onChange={(e) => setFormBasics((s) => ({ ...s, propietario_doc: e.target.value }))}
                  />
                ) : (
                  data.propietario_doc || "-"
                )}
              </Row>
            </>
          )}

          <h2 className="font-semibold mt-4 mb-2">Equipo</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
            {(() => {
              const tiposDisponibles = useMemo(() => {
                const norm = (s) => (s || "").toString().trim().toUpperCase();
                const set = new Set();
                (modelos || []).forEach((m) => {
                  const t = norm(m?.tipo_equipo);
                  if (t) set.add(t);
                });
                return Array.from(set);
              }, [modelos]);
              const [tipoSel, setTipoSel] = useState(() => {
                const raw = (data?.tipo_equipo_nombre || data?.tipo_equipo || "").toString().trim().toUpperCase();
                return raw || "";
              });
              useEffect(() => {
                const raw = (data?.tipo_equipo_nombre || data?.tipo_equipo || "").toString().trim().toUpperCase();
                if (!tipoSel && raw) setTipoSel(raw);
                // eslint-disable-next-line react-hooks/exhaustive-deps
              }, [data?.tipo_equipo, data?.tipo_equipo_nombre]);
              const modelosFiltrados = useMemo(() => {
                const norm = (s) => (s || "").toString().trim().toUpperCase();
                const all = modelos || [];
                if (!tipoSel) return all;
                return all.filter((m) => norm(m?.tipo_equipo) === tipoSel);
              }, [modelos, tipoSel]);
              return (
                <>
                  <Row label="Tipo de equipo">
                    {editBasics ? (
                      <select
                        className="border rounded p-1 w-60"
                        value={tipoSel}
                        onChange={(e) => {
                          setTipoSel(e.target.value);
                          setModeloIdSel(null);
                        }}
                      >
                        <option value="">(todos)</option>
                        {tiposDisponibles.map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    ) : (
                      data.tipo_equipo_nombre || data.tipo_equipo || "-"
                    )}
                  </Row>
                  {/* Marca / Modelo */}
                  <Row label="Marca">
                    {editBasics ? (
                      <select
                        className="border rounded p-1 w-60"
                        value={marcaIdSel == null ? "" : String(marcaIdSel)}
                        onChange={(e) => { const v = e.target.value === "" ? null : Number(e.target.value); setMarcaIdSel(v); setModeloIdSel(null); }}
                      >
                        <option value="">(sin marca)</option>
                        {(marcas || []).map((m) => (
                          <option key={m.id} value={String(m.id)}>
                            {m.nombre}
                          </option>
                        ))}
                      </select>
                    ) : (
                      data.marca
                    )}
                  </Row>
                  <Row label="Modelo">
                    {editBasics ? (
                      <select
                        className="border rounded p-1 w-60"
                        value={modeloIdSel == null ? "" : String(modeloIdSel)}
                        onChange={(e) => setModeloIdSel(e.target.value === "" ? null : Number(e.target.value))}
                      >
                        <option value="">(sin modelo)</option>
                        {(modelosFiltrados || []).map((m) => (
                          <option key={m.id} value={String(m.id)}>
                            {m.nombre}
                          </option>
                        ))}
                      </select>
                    ) : (
                      data.modelo || "-"
                    )}
                  </Row>
                </>
              );
            })()}
            <Row label="Variante">
              {editBasics ? (
                <>
                  <input
                    list="variantesOptions"
                    className="border rounded p-1 w-60"
                    value={formBasics?.equipo_variante ?? ""}
                    onChange={(e) => setFormBasics((f) => ({ ...(f || {}), equipo_variante: e.target.value }))}
                  />
                  <datalist id="variantesOptions">
                    {(variantes || []).map((v, idx) => (
                      <option key={idx} value={v} />
                    ))}
                  </datalist>
                </>
              ) : (
                data.equipo_variante || "-"
              )}
            </Row>
            <Row label={"N serie"}>
              {editBasics ? (
                <input
                  className="border rounded p-1 w-60"
                  value={formBasics?.numero_serie ?? ""}
                  onChange={(e) => setFormBasics((s) => ({ ...s, numero_serie: e.target.value }))}
                />
              ) : (
                <span>{numeroSerie || "-"}</span>
              )}
            </Row>
            <Row label="Garanta (fbrica)">
              {editBasics ? (
                <input
                  type="checkbox"
                  checked={!!(formBasics?.garantia)}
                  onChange={(e) => setFormBasics((s) => ({ ...(s || {}), garantia: e.target.checked }))}
                />
              ) : (
                <span>{data.garantia ? "Sí" : "No"}</span>
              )}
            </Row>
            <Row label="Garanta de reparacin">
              {editBasics ? (
                <input
                  type="checkbox"
                  checked={!!(formBasics?.garantia_reparacion)}
                  onChange={(e) => setFormBasics((s) => ({ ...(s || {}), garantia_reparacion: e.target.checked }))}
                />
              ) : (
                <span>{data?.garantia_reparacion ? "Sí" : "No"}</span>
              )}
            </Row>
            <Row label={"N interno (MG)"}>
              {editBasics ? (
                <input
                  className="border rounded p-1 w-60"
                  value={formBasics?.numero_interno || ""}
                  onChange={(e) => setFormBasics((s) => ({ ...s, numero_interno: e.target.value }))}
                />
              ) : (
                <span>{data.numero_interno || ""}</span>
              )}
            </Row>
            <Row label={"N de remito"}>
              {editBasics ? (
                <input
                  className="border rounded p-1 w-60"
                  value={formBasics?.remito_ingreso ?? ""}
                  onChange={(e) => setFormBasics((s) => ({ ...s, remito_ingreso: e.target.value }))}
                />
              ) : (
                <span>{data.remito_ingreso || "-"}</span>
              )}
            </Row>
          </div>
          {/* Notas */}
          <h2 className="font-semibold mt-4 mb-2">Notas</h2>
          <Row label="Informe preliminar">
            {editBasics ? (
              <textarea
                className="border rounded p-2 w-full min-h-[100px]"
                value={formBasics?.informe_preliminar ?? ""}
                onChange={(e) => setFormBasics((s) => ({ ...s, informe_preliminar: e.target.value }))}
              />
            ) : (
              <div className="whitespace-pre-wrap">{data.informe_preliminar || "-"}</div>
            )}
          </Row>
          <Row label="Accesorios">
            {Array.isArray(data.accesorios_items) && data.accesorios_items.length > 0 ? (
              <ul className="list-disc list-inside">
                {data.accesorios_items.map((it) => (
                  <li key={it.id}>
                    {it.accesorio_nombre}
                    {it.referencia ? ` (ref: ${it.referencia})` : ""}
                  </li>
                ))}
              </ul>
            ) : (
              data.accesorios || "-"
            )}
          </Row>
        </div>

        {/* Columna derecha: Estado/Asignacin/ubicacion */}
        <div className="border rounded p-4">
          <h2 className="font-semibold mb-2">Estado</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
            <Row label="Motivo">{data.motivo}</Row>
            <Row label="Estado">{data.estado}</Row>
            <Row label="Presupuesto">
              {(() => {
                const v = data.presupuesto_estado;
                if (!v) return "-";
                if (v === "presupuestado") return "Presupuestado";
                if (v === "no_aplica") return "No aplica";
                try {
                  const s = String(v);
                  return s.charAt(0).toUpperCase() + s.slice(1);
                } catch (_) {
                  return String(v);
                }
              })()}
            </Row>
            <Row label="Resolución">{data.resolucion ? resolutionLabel(data.resolucion) : "-"}</Row>
            <Row label="Fecha ingreso">{formatDateTimeHelper(resolveFechaIngreso(data))}</Row>
            <Row label="Fecha servicio">{data.fecha_servicio ? formatDateTimeHelper(data.fecha_servicio) : "-"}</Row>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
            <div>
              <h2 className="font-semibold mb-2">Asignación</h2>
              <div className="flex flex-col items-start gap-2">
                {canAssignTecnico ? (
                  <>
                    <select
                      className="border rounded p-2"
                      value={tecnicoId ?? ""}
                      onChange={(e) => setTecnicoId(e.target.value ? Number(e.target.value) : null)}
                    >
                      <option value="">-- Seleccionar técnico --</option>
                      {tecnicos.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.nombre}
                        </option>
                      ))}
                    </select>
                    <button
                      className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
                      onClick={saveTecnico}
                      disabled={savingTech || !techDirty || tecnicoId == null}
                      aria-busy={savingTech ? "true" : "false"}
                      type="button"
                    >
                      {savingTech ? "Guardando..." : "Guardar"}
                    </button>
                    {(data?.tecnico_solicitado_id && data?.tecnico_solicitado_id !== (data?.asignado_a ?? null)) && (
                      <div className="text-xs text-amber-700 mt-1">{pendingLabel}</div>
                    )}
                  </>
                ) : (
                  <div className="text-sm text-gray-500">
                    {mailEnviado && (<div className="text-xs text-emerald-700">Se envió el mail</div>)}
                    <div>No tenés permiso para reasignar técnicos.</div>
                    {isTech && (data?.estado || "") !== "entregado" && Number(userId || 0) > 0 && (
                      <div className="mt-2">
                        {data?.asignado_a === userId ? (
                          <div className="text-xs text-gray-600">Ya estás asignado a este ingreso.</div>
                        ) : data?.tecnico_solicitado_id === userId ? (
                          <div className="text-xs text-amber-700">Solicitud de asignación enviada</div>
                        ) : data?.tecnico_solicitado_id ? (
                          <div className="text-xs text-gray-600">{otherTechLabel}</div>
                        ) : (
                          <button hidden={mailEnviado}
                            className="bg-neutral-800 text-white px-3 py-2 rounded disabled:opacity-60"
                            disabled={solicitando}
                            onClick={async () => {
                              try {
                                setSolicitando(true);
                                await postSolicitarAsignacion(id);
                                await refreshIngreso();
                                setMailEnviado(true);
                                setErr("");
                              } catch (e) {
                                setErr(e?.message || "No se pudo solicitar la asignación");
                              } finally {
                                setSolicitando(false);
                              }
                            }}
                            type="button"
                          >
                            {solicitando ? "Enviando..." : "Solicitar asignación"}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
                <div className="text-xs text-gray-500">
                  Actual: <b>{data.asignado_a_nombre || "-"}</b>
                </div>
              </div>
            </div>
            <div>
              <h2 className="font-semibold mb-2">Ubicación</h2>
              <div className="flex flex-col items-start gap-2">
                <select
                  className="border rounded p-2"
                  value={ubicacionId}
                  onChange={(e) => setUbicacionId(e.target.value)}
                  aria-label="Seleccionar ubicación"
                >
                  <option value="" disabled>
                    Seleccione la ubicación.
                  </option>
                  {ubicaciones.map((u) => (
                    <option key={u.id} value={String(u.id)}>
                      {u.nombre}
                    </option>
                  ))}
                </select>
                <button
                  className="bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-60"
                  onClick={saveUbicacion}
                  disabled={savingUb || !ubDirty}
                  aria-busy={savingUb ? "true" : "false"}
                  type="button"
                >
                  {savingUb ? "Guardando..." : "Guardar"}
                </button>
              </div>
              <div className="text-xs text-gray-500">La ubicación puede modificarse desde aquí.</div>
            </div>
            {numeroSerie && (
              <div className="flex justify-end mb-2 w-full">
                <button
                  type="button"
                  onClick={() => setRelatedOpen(true)}
                  className="text-xs px-2 py-1 rounded border border-blue-600 text-blue-600 hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  Ver ingresos del equipo
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Botón de orden de salida (liberar) */}
      {release && (Boolean(data?.resolucion) || data?.estado === "liberado") && (
        <button
          className="bg-neutral-800 text-white px-3 py-2 rounded mt-4"
          onClick={async () => {
            try {
              const blob = await getBlob(`/api/ingresos/${id}/remito/`);
              if (!(blob instanceof Blob)) throw new Error("La respuesta no fue un PDF");
              const url = URL.createObjectURL(blob);
              window.open(url, "_blank", "noopener");
              setTimeout(() => URL.revokeObjectURL(url), 60_000);
              await refreshIngreso();
                                setMailEnviado(true);
            } catch (e) {
              setErr(e?.message || "No se pudo imprimir la orden de salida");
            }
          }}
          type="button"
        >
          Imprimir orden de salida (liberar)
        </button>
      )}

      {/* Entrega */}
      <div className="border rounded p-4 mt-4">
        <h2 className="font-semibold mb-2">Entrega</h2>
        {data.estado === "liberado" ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="text-sm">Remito salida (requerido)</label>
                <input
                  className="border rounded p-2 w-full"
                  value={entrega.remito_salida}
                  onChange={(e) => setEntrega({ ...entrega, remito_salida: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm">Factura (opcional)</label>
                <input
                  className="border rounded p-2 w-full"
                  value={entrega.factura_numero}
                  onChange={(e) => setEntrega({ ...entrega, factura_numero: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm">Fecha entrega</label>
                <input
                  type="datetime-local"
                  className="border rounded p-2 w-full"
                  value={entrega.fecha_entrega}
                  onChange={(e) => setEntrega({ ...entrega, fecha_entrega: e.target.value })}
                />
              </div>
            </div>
            <div className="mt-3">
              <button
                className="bg-green-600 text-white px-4 py-2 rounded"
                onClick={async () => {
                  try {
                    if (!entrega.remito_salida.trim()) {
                      setErr("El remito es requerido para entregar.");
                      return;
                    }
                    await postEntregarIngreso(id, entrega);
                    await refreshIngreso();
                                setMailEnviado(true);
                  } catch (e) {
                    setErr(e?.message || "No se pudo marcar como entregado");
                  }
                }}
              >
                Marcar ENTREGADO
              </button>
            </div>
          </>
        ) : (
          <>
            {!editEntrega && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                <div>
                  <div className="text-gray-600">Remito salida</div>
                  <div className="font-medium">{data.remito_salida || "-"}</div>
                </div>
                <div>
                  <div className="text-gray-600">Factura</div>
                  <div className="font-medium">{data.factura_numero || "-"}</div>
                </div>
                <div>
                  <div className="text-gray-600">Fecha entrega</div>
                  <div className="font-medium">{data.fecha_entrega ? formatDateTimeHelper(data.fecha_entrega) : "-"}</div>
                </div>
              </div>
            )}
            {canEditEntrega && !editEntrega && (
              <div className="mt-3">
                <button className="px-3 py-2 border rounded" type="button" onClick={() => setEditEntrega(true)}>
                  Editar entrega
                </button>
              </div>
            )}
            {canEditEntrega && editEntrega && (
              <>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="text-sm">Remito salida</label>
                    <input
                      className="border rounded p-2 w-full"
                      value={entrega.remito_salida}
                      onChange={(e) => setEntrega({ ...entrega, remito_salida: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-sm">Factura</label>
                    <input
                      className="border rounded p-2 w-full"
                      value={entrega.factura_numero}
                      onChange={(e) => setEntrega({ ...entrega, factura_numero: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-sm">Fecha entrega</label>
                    <input
                      type="datetime-local"
                      className="border rounded p-2 w-full"
                      value={entrega.fecha_entrega}
                      onChange={(e) => setEntrega({ ...entrega, fecha_entrega: e.target.value })}
                    />
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  <button
                    className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-60"
                    disabled={savingEntrega}
                    type="button"
                    onClick={async () => {
                      try {
                        setSavingEntrega(true);
                        const payload = {
                          remito_salida: (entrega.remito_salida || "").trim(),
                          factura_numero: (entrega.factura_numero || "").trim(),
                          fecha_entrega: entrega.fecha_entrega || null,
                        };
                        await patchIngreso(id, payload);
                        await refreshIngreso();
                                setMailEnviado(true);
                        setEditEntrega(false);
                        setErr("");
                      } catch (e) {
                        setErr(e?.message || "No se pudo guardar entrega");
                      } finally {
                        setSavingEntrega(false);
                      }
                    }}
                  >
                    Guardar
                  </button>
                  <button
                    className="px-3 py-2 border rounded"
                    type="button"
                    onClick={() => {
                      setEditEntrega(false);
                      setEntrega({
                        remito_salida: data?.remito_salida || "",
                        factura_numero: data?.factura_numero || "",
                        fecha_entrega: toDatetimeLocalStr(data?.fecha_entrega),
                      });
                    }}
                  >
                    Cancelar
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* Alquiler */}
      <div className="border rounded p-4 mt-4">
        <h2 className="font-semibold mb-2">Alquiler</h2>
        <Row label="Se alquil?">
          <input type="checkbox" checked={!!data.alquilado} onChange={(e) => patch({ alquilado: e.target.checked })} />
        </Row>
        <Row label="A quin?">
          <input className="border rounded p-1 w-80" value={data.alquiler_a || ""} onChange={(e) => patch({ alquiler_a: e.target.value })} />
        </Row>
        <Row label="Remito">
          <input className="border rounded p-1 w-60" value={data.alquiler_remito || ""} onChange={(e) => patch({ alquiler_remito: e.target.value })} />
        </Row>
        <Row label="Fecha">
          <input
            type="date"
            className="border rounded p-1"
            value={(data.alquiler_fecha || "").slice(0, 10)}
            onChange={(e) => patch({ alquiler_fecha: e.target.value || null })}
          />
        </Row>
      </div>
    </>
  );
}












