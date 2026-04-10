import { useEffect, useMemo, useState } from 'react';
import {
  getRetailInventarioConteos,
  getRetailInventarioConteoDetail,
  getRetailReposicionSugerida,
  postRetailInventarioConteo,
  postRetailInventarioConteoCerrar,
} from '../lib/api';

const STATUS_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'in_progress', label: 'En progreso' },
  { value: 'draft', label: 'Borrador' },
  { value: 'closed', label: 'Cerrado' },
  { value: 'cancelled', label: 'Cancelado' },
];

const SCOPE_OPTIONS = [
  { value: 'low_stock', label: 'Solo bajo stock' },
  { value: 'all', label: 'Todo el catalogo activo' },
  { value: 'custom', label: 'Seleccion manual de variantes' },
];

const intFmt = new Intl.NumberFormat('es-AR');

function errMsg(error) {
  return error?.data?.detail || error?.message || 'Ocurrio un error inesperado';
}

function statusLabel(status) {
  const value = String(status || '').toLowerCase();
  if (value === 'in_progress') return 'En progreso';
  if (value === 'closed') return 'Cerrado';
  if (value === 'cancelled') return 'Cancelado';
  if (value === 'draft') return 'Borrador';
  return value || '-';
}

function statusPillClass(status) {
  const value = String(status || '').toLowerCase();
  if (value === 'in_progress') return 'bg-blue-100 text-blue-800 border-blue-200';
  if (value === 'closed') return 'bg-emerald-100 text-emerald-800 border-emerald-200';
  if (value === 'cancelled') return 'bg-neutral-100 text-neutral-700 border-neutral-200';
  if (value === 'draft') return 'bg-amber-100 text-amber-800 border-amber-200';
  return 'bg-neutral-100 text-neutral-700 border-neutral-200';
}

function severityPillClass(value) {
  const severity = String(value || '').toLowerCase();
  if (severity === 'critical') return 'bg-rose-100 text-rose-800 border-rose-200';
  if (severity === 'high') return 'bg-orange-100 text-orange-800 border-orange-200';
  if (severity === 'medium') return 'bg-blue-100 text-blue-800 border-blue-200';
  return 'bg-neutral-100 text-neutral-700 border-neutral-200';
}

function scopeLabel(scope) {
  const value = String(scope || '').toLowerCase();
  if (value === 'low_stock') return 'Bajo stock';
  if (value === 'custom') return 'Personalizado';
  if (value === 'all') return 'Total';
  return value || '-';
}

function dateTimeLabel(value) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleString('es-AR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

function toInt(value, fallback = 0) {
  const n = Number.parseInt(String(value ?? ''), 10);
  return Number.isFinite(n) ? n : fallback;
}

function formatInt(value) {
  return intFmt.format(toInt(value, 0));
}

function formatDecimal(value, digits = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '-';
  return n.toFixed(digits);
}

function parseVariantIds(raw) {
  const tokens = String(raw || '')
    .split(/[\s,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  const unique = [];
  tokens.forEach((token) => {
    const id = Number.parseInt(token, 10);
    if (!Number.isFinite(id) || id <= 0) return;
    if (!unique.includes(id)) unique.push(id);
  });
  return unique;
}

function buildInitialItemEdits(items) {
  const map = {};
  (Array.isArray(items) ? items : []).forEach((item) => {
    const fallbackQty = item?.counted_qty != null ? item.counted_qty : item?.expected_qty;
    map[item.id] = {
      counted_qty: String(toInt(fallbackQty, 0)),
      adjustment_reason: String(item?.adjustment_reason || ''),
    };
  });
  return map;
}

export default function InventarioPage() {
  const [statusFilter, setStatusFilter] = useState('in_progress');
  const [counts, setCounts] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [itemEdits, setItemEdits] = useState({});
  const [itemSearch, setItemSearch] = useState('');

  const [loadingList, setLoadingList] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingReplenish, setLoadingReplenish] = useState(false);
  const [creating, setCreating] = useState(false);
  const [closing, setClosing] = useState(false);

  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const [form, setForm] = useState({
    scope: 'low_stock',
    reason: 'Conteo ciclico semanal',
    includeInactive: false,
    variantIds: '',
  });
  const [applyAdjustments, setApplyAdjustments] = useState(true);
  const [createIncidents, setCreateIncidents] = useState(true);

  const [replenishDays, setReplenishDays] = useState(30);
  const [replenishRows, setReplenishRows] = useState([]);

  const items = Array.isArray(detail?.items) ? detail.items : [];

  const summary = useMemo(() => {
    let countedItems = 0;
    let diffItems = 0;
    let diffUnits = 0;
    let missingReasons = 0;

    items.forEach((item) => {
      const edit = itemEdits[item.id] || {};
      const sourceQty = edit.counted_qty ?? item?.counted_qty ?? item?.expected_qty;
      const countedQty = toInt(sourceQty, Number.NaN);
      if (!Number.isFinite(countedQty)) return;
      countedItems += 1;
      const expectedQty = toInt(item?.expected_qty, 0);
      const diff = countedQty - expectedQty;
      if (diff !== 0) {
        diffItems += 1;
        diffUnits += diff;
        const reason = String(edit.adjustment_reason ?? item?.adjustment_reason ?? '').trim();
        if (applyAdjustments && !reason) {
          missingReasons += 1;
        }
      }
    });

    return {
      totalItems: items.length,
      countedItems,
      diffItems,
      diffUnits,
      missingReasons,
      completionPct: items.length ? Math.round((countedItems / items.length) * 100) : 0,
    };
  }, [items, itemEdits, applyAdjustments]);

  const filteredItems = useMemo(() => {
    const term = String(itemSearch || '').trim().toLowerCase();
    if (!term) return items;
    return items.filter((item) => {
      const haystack = `${item?.producto || ''} ${item?.sku || ''} ${item?.option_signature || ''}`.toLowerCase();
      return haystack.includes(term);
    });
  }, [items, itemSearch]);

  async function loadReplenishment() {
    setLoadingReplenish(true);
    try {
      const data = await getRetailReposicionSugerida({ days: replenishDays, limit: 40 });
      setReplenishRows(Array.isArray(data?.rows) ? data.rows : []);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoadingReplenish(false);
    }
  }

  async function loadDetail(countId, { keepMsg = true } = {}) {
    const id = Number(countId);
    if (!Number.isFinite(id) || id <= 0) {
      setDetail(null);
      setItemEdits({});
      setSelectedId(null);
      return;
    }
    setLoadingDetail(true);
    setErr('');
    if (!keepMsg) setMsg('');
    try {
      const row = await getRetailInventarioConteoDetail(id);
      setDetail(row || null);
      setItemEdits(buildInitialItemEdits(row?.items));
      setSelectedId(id);
      setItemSearch('');
      setApplyAdjustments(true);
      setCreateIncidents(true);
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoadingDetail(false);
    }
  }

  async function loadCounts(preferredId = null) {
    setLoadingList(true);
    setErr('');
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      params.limit = 80;
      const data = await getRetailInventarioConteos(params);
      const rows = Array.isArray(data?.rows) ? data.rows : [];
      setCounts(rows);

      const wanted = Number(preferredId || selectedId || 0);
      const hasWanted = rows.some((row) => Number(row.id) === wanted);
      const nextId = hasWanted ? wanted : Number(rows[0]?.id || 0);
      if (nextId > 0) {
        await loadDetail(nextId, { keepMsg: true });
      } else {
        setDetail(null);
        setSelectedId(null);
        setItemEdits({});
      }
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setLoadingList(false);
    }
  }

  useEffect(() => {
    loadCounts();
    // Carga inicial + recarga por estado.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  useEffect(() => {
    loadReplenishment();
    // Carga inicial de reposicion.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function createCount(e) {
    e.preventDefault();
    setCreating(true);
    setErr('');
    setMsg('');
    try {
      const payload = {
        scope: form.scope,
        reason: String(form.reason || '').trim() || undefined,
        include_inactive: !!form.includeInactive,
      };
      if (form.scope === 'custom') {
        const variantIds = parseVariantIds(form.variantIds);
        if (!variantIds.length) {
          setErr('Para scope personalizado, carga al menos un variant_id.');
          return;
        }
        payload.variant_ids = variantIds;
      }

      const created = await postRetailInventarioConteo(payload);
      const id = Number(created?.id || 0);
      setMsg(`Conteo ${created?.code || `#${id}`} creado.`);
      if (id > 0) {
        setDetail(created || null);
        setItemEdits(buildInitialItemEdits(created?.items));
        setSelectedId(id);
      }

      if (statusFilter !== 'in_progress') {
        setStatusFilter('in_progress');
      } else {
        await loadCounts(id);
      }
      await loadReplenishment();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setCreating(false);
    }
  }

  function updateItemEdit(itemId, patch) {
    setItemEdits((prev) => ({
      ...prev,
      [itemId]: {
        ...(prev[itemId] || {}),
        ...patch,
      },
    }));
  }

  function fillWithExpectedQty() {
    setItemEdits((prev) => {
      const next = { ...prev };
      items.forEach((item) => {
        next[item.id] = {
          ...(next[item.id] || {}),
          counted_qty: String(toInt(item.expected_qty, 0)),
          adjustment_reason: String(next[item.id]?.adjustment_reason || ''),
        };
      });
      return next;
    });
  }

  async function closeCount() {
    if (!detail) return;
    if (!['draft', 'in_progress'].includes(String(detail.status || '').toLowerCase())) {
      setErr('El conteo ya no esta abierto para cierre.');
      return;
    }

    setClosing(true);
    setErr('');
    setMsg('');
    try {
      const payloadItems = [];
      let missingReasons = 0;
      for (const item of items) {
        const edit = itemEdits[item.id] || {};
        const rawQty = edit.counted_qty ?? item?.counted_qty ?? item?.expected_qty;
        const countedQty = toInt(rawQty, Number.NaN);
        if (!Number.isFinite(countedQty) || countedQty < 0) {
          throw new Error(`Cantidad invalida para variante ${item?.variant_id || '-'}.`);
        }
        const expectedQty = toInt(item?.expected_qty, 0);
        const diffQty = countedQty - expectedQty;
        const reason = String(edit.adjustment_reason ?? item?.adjustment_reason ?? '').trim();
        if (applyAdjustments && diffQty !== 0 && !reason) {
          missingReasons += 1;
        }
        const payloadItem = {
          count_item_id: item.id,
          variant_id: item.variant_id,
          counted_qty: countedQty,
        };
        if (reason) payloadItem.adjustment_reason = reason;
        payloadItems.push(payloadItem);
      }

      if (applyAdjustments && missingReasons > 0) {
        setErr(`Faltan motivos de ajuste en ${missingReasons} filas con diferencia.`);
        return;
      }

      const row = await postRetailInventarioConteoCerrar(detail.id, {
        apply_adjustments: applyAdjustments,
        create_incidents: createIncidents,
        items: payloadItems,
      });
      setDetail(row || null);
      setItemEdits(buildInitialItemEdits(row?.items));
      setMsg(`Conteo ${row?.code || `#${detail.id}`} cerrado correctamente.`);
      await loadCounts(row?.id || detail.id);
      await loadReplenishment();
    } catch (error) {
      setErr(errMsg(error));
    } finally {
      setClosing(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <h1 className="h1">Inventario ciclico</h1>
        <p className="text-sm text-gray-600">
          Ejecuta conteos por ciclo, corrige diferencias con motivo obligatorio y deja trazabilidad para auditoria.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="space-y-4">
          <form className="card space-y-3" onSubmit={createCount}>
            <h2 className="text-lg font-semibold">Nuevo conteo</h2>
            <div>
              <label className="label">Alcance</label>
              <select
                className="input"
                value={form.scope}
                onChange={(e) => setForm((prev) => ({ ...prev, scope: e.target.value }))}
              >
                {SCOPE_OPTIONS.map((scope) => (
                  <option key={scope.value} value={scope.value}>
                    {scope.label}
                  </option>
                ))}
              </select>
            </div>
            {form.scope === 'custom' ? (
              <div>
                <label className="label">Variant IDs (coma, espacio o salto)</label>
                <textarea
                  className="input"
                  rows={3}
                  value={form.variantIds}
                  onChange={(e) => setForm((prev) => ({ ...prev, variantIds: e.target.value }))}
                  placeholder="Ej: 1201, 1202, 1203"
                />
              </div>
            ) : null}
            <div>
              <label className="label">Motivo</label>
              <input
                className="input"
                value={form.reason}
                onChange={(e) => setForm((prev) => ({ ...prev, reason: e.target.value }))}
                placeholder="Conteo de rutina"
              />
            </div>
            <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
              <input
                type="checkbox"
                checked={form.includeInactive}
                onChange={(e) => setForm((prev) => ({ ...prev, includeInactive: e.target.checked }))}
              />
              Incluir variantes inactivas
            </label>
            <button type="submit" className="btn w-full" disabled={creating}>
              {creating ? 'Creando...' : 'Iniciar conteo'}
            </button>
          </form>

          <div className="card space-y-3">
            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-[180px] flex-1">
                <label className="label">Ver conteos</label>
                <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                  {STATUS_OPTIONS.map((status) => (
                    <option key={status.value || 'all'} value={status.value}>
                      {status.label}
                    </option>
                  ))}
                </select>
              </div>
              <button type="button" className="btn-secondary !px-3 !py-2" onClick={() => loadCounts()} disabled={loadingList}>
                Recargar
              </button>
            </div>

            <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
              {loadingList ? <p className="text-sm text-gray-500">Cargando conteos...</p> : null}
              {!loadingList && !counts.length ? <p className="text-sm text-gray-500">No hay conteos para este filtro.</p> : null}
              {counts.map((row) => {
                const active = Number(row.id) === Number(selectedId);
                return (
                  <button
                    key={row.id}
                    type="button"
                    onClick={() => loadDetail(row.id, { keepMsg: true })}
                    className={`w-full rounded-lg border p-3 text-left transition ${
                      active ? 'border-[#ef6f61] bg-[#ef6f61]/10' : 'border-neutral-200 bg-white hover:border-neutral-300'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <strong className="text-sm">{row.code || `#${row.id}`}</strong>
                      <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusPillClass(row.status)}`}>
                        {statusLabel(row.status)}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-neutral-600">
                      <span>{scopeLabel(row.scope)}</span>
                      <span> · </span>
                      <span>{formatInt(row.items_counted)} / {formatInt(row.items_total)} items</span>
                    </div>
                    <div className="mt-1 text-xs text-neutral-500">
                      Dif: <strong>{formatInt(row.items_with_diff)}</strong> | Inicio: {dateTimeLabel(row.started_at)}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="space-y-4 xl:col-span-2">
          <div className="card space-y-3">
            {!detail ? (
              <p className="text-sm text-gray-500">Selecciona o crea un conteo para continuar.</p>
            ) : (
              <>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h2 className="text-lg font-semibold">Conteo {detail.code || `#${detail.id}`}</h2>
                    <p className="text-xs text-neutral-600">
                      Alcance: {scopeLabel(detail.scope)} | Estado: {statusLabel(detail.status)} | Creado por:{' '}
                      {detail.created_by_name || '-'}
                    </p>
                    <p className="text-xs text-neutral-500">
                      Inicio: {dateTimeLabel(detail.started_at)} | Cierre: {dateTimeLabel(detail.closed_at)}
                    </p>
                  </div>
                  <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${statusPillClass(detail.status)}`}>
                    {statusLabel(detail.status)}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
                  <div className="rounded border p-2">
                    <p className="text-xs text-gray-500">Items</p>
                    <strong>{formatInt(summary.totalItems)}</strong>
                  </div>
                  <div className="rounded border p-2">
                    <p className="text-xs text-gray-500">Contados</p>
                    <strong>{formatInt(summary.countedItems)}</strong>
                  </div>
                  <div className="rounded border p-2">
                    <p className="text-xs text-gray-500">Con diferencia</p>
                    <strong>{formatInt(summary.diffItems)}</strong>
                  </div>
                  <div className="rounded border p-2">
                    <p className="text-xs text-gray-500">Dif. unidades</p>
                    <strong>{formatInt(summary.diffUnits)}</strong>
                  </div>
                  <div className="rounded border p-2">
                    <p className="text-xs text-gray-500">Avance</p>
                    <strong>{formatInt(summary.completionPct)}%</strong>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                  <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
                    <input
                      type="checkbox"
                      checked={applyAdjustments}
                      onChange={(e) => setApplyAdjustments(e.target.checked)}
                      disabled={!['draft', 'in_progress'].includes(String(detail.status || '').toLowerCase())}
                    />
                    Aplicar ajustes de stock
                  </label>
                  <label className="inline-flex items-center gap-2 text-sm text-neutral-700">
                    <input
                      type="checkbox"
                      checked={createIncidents}
                      onChange={(e) => setCreateIncidents(e.target.checked)}
                      disabled={!['draft', 'in_progress'].includes(String(detail.status || '').toLowerCase())}
                    />
                    Generar incidencias por diferencias altas
                  </label>
                  <div className="text-sm text-neutral-600">
                    Motivos pendientes: <strong>{formatInt(summary.missingReasons)}</strong>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button type="button" className="btn-secondary !px-3 !py-2" onClick={fillWithExpectedQty} disabled={loadingDetail}>
                    Completar con esperado
                  </button>
                  <button
                    type="button"
                    className="btn"
                    onClick={closeCount}
                    disabled={
                      loadingDetail ||
                      closing ||
                      !['draft', 'in_progress'].includes(String(detail.status || '').toLowerCase())
                    }
                  >
                    {closing ? 'Cerrando...' : 'Cerrar conteo'}
                  </button>
                </div>

                <div className="flex flex-wrap items-end gap-2">
                  <div className="min-w-[220px] flex-1">
                    <label className="label">Buscar item (producto, sku, variante)</label>
                    <input
                      className="input"
                      value={itemSearch}
                      onChange={(e) => setItemSearch(e.target.value)}
                      placeholder="Ej: Remera M roja / SKU"
                    />
                  </div>
                  <span className="text-xs text-neutral-500">Mostrando {formatInt(filteredItems.length)} items</span>
                </div>

                <div className="max-h-[420px] overflow-auto rounded-lg border border-neutral-200">
                  <table className="min-w-full text-sm">
                    <thead className="sticky top-0 bg-neutral-50">
                      <tr className="text-left text-xs uppercase tracking-wide text-neutral-500">
                        <th className="px-2 py-2">SKU</th>
                        <th className="px-2 py-2">Producto</th>
                        <th className="px-2 py-2">Variante</th>
                        <th className="px-2 py-2">Esperado</th>
                        <th className="px-2 py-2">Contado</th>
                        <th className="px-2 py-2">Diferencia</th>
                        <th className="px-2 py-2">Motivo ajuste</th>
                      </tr>
                    </thead>
                    <tbody>
                      {loadingDetail ? (
                        <tr>
                          <td colSpan={7} className="px-3 py-4 text-sm text-gray-500">
                            Cargando detalle del conteo...
                          </td>
                        </tr>
                      ) : null}
                      {!loadingDetail && !filteredItems.length ? (
                        <tr>
                          <td colSpan={7} className="px-3 py-4 text-sm text-gray-500">
                            No hay items para mostrar.
                          </td>
                        </tr>
                      ) : null}
                      {!loadingDetail &&
                        filteredItems.map((item) => {
                          const edit = itemEdits[item.id] || {};
                          const countedValue = edit.counted_qty ?? String(item?.counted_qty ?? item?.expected_qty ?? '');
                          const countedQty = toInt(countedValue, Number.NaN);
                          const expectedQty = toInt(item.expected_qty, 0);
                          const diff = Number.isFinite(countedQty) ? countedQty - expectedQty : 0;
                          return (
                            <tr key={item.id} className="border-t align-top">
                              <td className="px-2 py-2 font-mono text-xs">{item.sku || '-'}</td>
                              <td className="px-2 py-2">{item.producto || '-'}</td>
                              <td className="px-2 py-2 text-xs text-neutral-600">{item.option_signature || '-'}</td>
                              <td className="px-2 py-2 text-right">{formatInt(expectedQty)}</td>
                              <td className="px-2 py-2">
                                <input
                                  className="input !max-w-[110px] !py-1.5 text-right"
                                  inputMode="numeric"
                                  value={countedValue}
                                  onChange={(e) => updateItemEdit(item.id, { counted_qty: e.target.value })}
                                  disabled={!['draft', 'in_progress'].includes(String(detail.status || '').toLowerCase())}
                                />
                              </td>
                              <td className="px-2 py-2 text-right">
                                <span className={diff === 0 ? 'text-neutral-700' : diff > 0 ? 'text-emerald-700' : 'text-rose-700'}>
                                  {diff > 0 ? '+' : ''}
                                  {formatInt(diff)}
                                </span>
                              </td>
                              <td className="px-2 py-2">
                                <input
                                  className="input !py-1.5"
                                  value={edit.adjustment_reason ?? item.adjustment_reason ?? ''}
                                  onChange={(e) => updateItemEdit(item.id, { adjustment_reason: e.target.value })}
                                  placeholder={diff !== 0 ? 'Motivo requerido si ajusta' : 'Sin ajuste'}
                                  disabled={!['draft', 'in_progress'].includes(String(detail.status || '').toLowerCase())}
                                />
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>

                {detail?.close_summary ? (
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                    <p>
                      Cierre aplicado: {formatInt(detail.close_summary.adjusted_items)} ajustes, diferencia total{' '}
                      {formatInt(detail.close_summary.diff_units_total)} unidades, incidencias{' '}
                      {formatInt(detail.close_summary.incidents_created)}.
                    </p>
                  </div>
                ) : null}
              </>
            )}
          </div>

          <div className="card space-y-3">
            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-[150px]">
                <label className="label">Dias de rotacion</label>
                <input
                  className="input"
                  type="number"
                  min="7"
                  max="120"
                  value={replenishDays}
                  onChange={(e) => setReplenishDays(toInt(e.target.value, 30))}
                />
              </div>
              <button type="button" className="btn-secondary !px-3 !py-2" onClick={loadReplenishment} disabled={loadingReplenish}>
                {loadingReplenish ? 'Actualizando...' : 'Actualizar reposicion'}
              </button>
            </div>

            <div className="max-h-[300px] overflow-auto rounded-lg border border-neutral-200">
              <table className="min-w-full text-sm">
                <thead className="sticky top-0 bg-neutral-50">
                  <tr className="text-left text-xs uppercase tracking-wide text-neutral-500">
                    <th className="px-2 py-2">Severidad</th>
                    <th className="px-2 py-2">Producto</th>
                    <th className="px-2 py-2">Variante</th>
                    <th className="px-2 py-2 text-right">Stock</th>
                    <th className="px-2 py-2 text-right">Min</th>
                    <th className="px-2 py-2 text-right">Sugerido</th>
                    <th className="px-2 py-2 text-right">Dias quiebre</th>
                    <th className="px-2 py-2">Proveedor</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingReplenish ? (
                    <tr>
                      <td colSpan={8} className="px-3 py-4 text-sm text-gray-500">
                        Cargando sugerencias...
                      </td>
                    </tr>
                  ) : null}
                  {!loadingReplenish && !replenishRows.length ? (
                    <tr>
                      <td colSpan={8} className="px-3 py-4 text-sm text-gray-500">
                        Sin sugerencias para los parametros elegidos.
                      </td>
                    </tr>
                  ) : null}
                  {!loadingReplenish &&
                    replenishRows.map((row) => (
                      <tr key={`${row.variant_id}-${row.supplier_id || 'na'}`} className="border-t">
                        <td className="px-2 py-2">
                          <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${severityPillClass(row.severity)}`}>
                            {String(row.severity || 'low').toUpperCase()}
                          </span>
                        </td>
                        <td className="px-2 py-2">{row.producto || '-'}</td>
                        <td className="px-2 py-2 text-xs text-neutral-600">{row.option_signature || row.sku || '-'}</td>
                        <td className="px-2 py-2 text-right">{formatInt(row.stock_on_hand)}</td>
                        <td className="px-2 py-2 text-right">{formatInt(row.stock_min)}</td>
                        <td className="px-2 py-2 text-right font-semibold">{formatInt(row.suggested_qty)}</td>
                        <td className="px-2 py-2 text-right">{formatDecimal(row.est_days_to_break, 1)}</td>
                        <td className="px-2 py-2">{row.supplier_name || '-'}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {err ? <p className="text-sm text-red-700">{err}</p> : null}
      {msg ? <p className="text-sm text-green-700">{msg}</p> : null}
    </div>
  );
}
