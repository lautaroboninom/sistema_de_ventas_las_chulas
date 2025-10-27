// web/src/pages/GeneralEquipos.jsx
import { useEffect, useMemo, useRef, useState } from "react";
import api, { getGeneralEquipos } from "../lib/api";
import { useSearchParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import { ingresoIdOf, formatOS, formatDateTime, norm, tipoEquipoOf, resolveFechaIngreso } from "../lib/ui-helpers";

export default function GeneralEquipos() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState("");
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const pageSize = 200;

  async function loadPage(p = 1, { reset = false } = {}) {
    try {
      if (reset) {
        setRows([]);
        setHasNext(false);
        setPage(1);
      }
      const isFirst = reset || p === 1;
      isFirst ? setLoading(true) : setLoadingMore(true);
      setErr("");

      const params = new URLSearchParams();
      const from = search.get('from') || '';
      const to = search.get('to') || '';
      const delivered = search.get('delivered') || '';
      if (delivered === '1') params.set('delivered', '1');
      if (delivered === '1' && from) params.set('from', from);
      if (delivered === '1' && to) params.set('to', to);
      params.set('page', String(p));
      params.set('page_size', String(pageSize));

      const res = await getGeneralEquipos(Object.fromEntries(params.entries()));
      const pageItems = Array.isArray(res) ? (res || []) : (res.items || []);
      const next = Array.isArray(res) ? false : !!res.has_next;

      setRows((prev) => (isFirst ? pageItems : [...prev, ...pageItems]));
      setHasNext(next);
      setPage(p);
    } catch (e) {
      setErr(e?.message || "No se pudo cargar el histórico de equipos");
      if (reset) setRows([]);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  useEffect(() => {
    loadPage(1, { reset: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search.get('from'), search.get('to'), search.get('delivered')]);

  const filtered = useMemo(() => {
    const from = search.get('from');
    const to = search.get('to');
    const delivered = search.get('delivered');
    const fromD = from ? new Date(from+"T00:00:00Z") : null;
    const toD = to ? new Date(to+"T23:59:59Z") : null;
    const needle = norm(filter);
    const base = rows.filter((row) => {
      if (delivered === '1') {
        const ent = row?.fecha_entrega ? new Date(row.fecha_entrega) : null;
        if (!ent) return false;
        if (fromD && ent < fromD) return false;
        if (toD && ent > toD) return false;
      }
      return true;
    });
    if (!needle) return base;
    return base.filter((row) => {
      const campos = [
        formatOS(row),
        row?.razon_social ?? row?.cliente ?? row?.cliente_nombre,
        row?.marca ?? row?.equipo?.marca,
        row?.modelo ?? row?.equipo?.modelo,
        row?.equipo_variante ?? row?.variante ?? row?.modelo_variante,
        tipoEquipoOf(row),
        row?.estado,
        row?.numero_serie,
        row?.numero_interno,
        row?.ubicacion_nombre,
      ];
      return campos.some((c) => norm(c).includes(needle));
    });
  }, [rows, filter]);

  const go = (row) => {
    const id = ingresoIdOf(row);
    if (!id) return;
    navigate(`/ingresos/${id}`);
  };

  const onRowKeyDown = (e, row) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      go(row);
    }
  };

  const sentinelRef = useRef(null);
  useEffect(() => {
    if (!hasNext) return;
    const el = sentinelRef.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && !loadingMore) {
          loadPage(page + 1);
        }
      }
    });
    io.observe(el);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasNext, page, loadingMore]);

  return (
    <div className="card">
      <div className="h1 mb-3">General de equipos (histórico)</div>

      {err && (
        <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-3">
          {err}
        </div>
      )}

      <div className="flex items-center gap-2 mb-3">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filtrar por OS, cliente, tipo de equipo, marca, modelo, variante, estado, serie..."
          className="border rounded p-2 w-full max-w-md"
          aria-label="Filtrar histórico"
        />
        <button
          className="btn"
          onClick={() => loadPage(1, { reset: true })}
          title="Recargar lista"
          disabled={loading}
          aria-busy={loading ? "true" : "false"}
        >
          Recargar
        </button>
      </div>

      {loading ? (
        "Cargando..."
      ) : filtered.length === 0 ? (
        <div className="text-sm text-gray-500">
          No hay resultados que coincidan con el filtro.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th scope="col" className="p-2">OS</th>
                <th scope="col" className="p-2">Cliente</th>
                <th scope="col" className="p-2">Tipo de equipo</th>
                <th scope="col" className="p-2">Marca</th>
                <th scope="col" className="p-2">Modelo</th>
                <th scope="col" className="p-2">Variante</th>
                <th scope="col" className="p-2">Estado</th>
                <th scope="col" className="p-2">N/S (serie)</th>
                <th scope="col" className="p-2">MG</th>
                <th scope="col" className="p-2">Ubicación</th>
                <th scope="col" className="p-2">Fecha ingreso</th>
                <th scope="col" className="p-2">Fecha entrega</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr
                  key={ingresoIdOf(row)}
                  onClick={() => go(row)}
                  onKeyDown={(e) => onRowKeyDown(e, row)}
                  className="hover:bg-gray-50 cursor-pointer"
                  role="link"
                  tabIndex={0}
                  aria-label={`Abrir hoja de servicio de ${formatOS(row)}`}
                  data-testid={`row-${ingresoIdOf(row)}`}
                >
                  <td className="p-2 underline">{formatOS(row)}</td>
                  <td className="p-2">
                    {row?.razon_social ?? row?.cliente ?? row?.cliente_nombre ?? "-"}
                  </td>
                  <td className="p-2">{tipoEquipoOf(row)}</td>
                  <td className="p-2">{row?.marca ?? row?.equipo?.marca ?? "-"}</td>
                  <td className="p-2">{row?.modelo ?? row?.equipo?.modelo ?? "-"}</td>
                  <td className="p-2">{row?.equipo_variante ?? row?.variante ?? row?.modelo_variante ?? "-"}</td>
                  <td className="p-2">{row?.estado ?? "-"}</td>
                  <td className="p-2">{row?.numero_serie ?? "-"}</td>
                  <td className="p-2">{row?.numero_interno ?? "-"}</td>
                  <td className="p-2">{row?.ubicacion_nombre ?? "-"}</td>
                  <td className="p-2 whitespace-nowrap">{formatDateTime(resolveFechaIngreso(row))}</td>
                  <td className="p-2 whitespace-nowrap">{formatDateTime(row?.fecha_entrega)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-xs text-gray-500 mt-2">
            Mostrando {filtered.length} de {rows.length}. {hasNext ? "Desplazá para cargar más…" : ""}
          </div>
          <div ref={sentinelRef} style={{ height: 1 }} />
          {loadingMore && (
            <div className="text-xs text-gray-500 mt-2">Cargando más…</div>
          )}
        </div>
      )}
    </div>
  );
}
