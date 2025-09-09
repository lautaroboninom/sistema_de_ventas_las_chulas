// web/src/pages/GeneralPorCliente.jsx
import { useEffect, useMemo, useState } from "react";
import api, { getClientes } from "../lib/api";
import { useNavigate } from "react-router-dom";
import { ingresoIdOf, formatOS, formatDateTime, norm } from "../lib/ui-helpers";



export default function GeneralPorCliente() {
  const [clientes, setClientes] = useState([]);
  const [loadingClientes, setLoadingClientes] = useState(true);
  const [errClientes, setErrClientes] = useState("");

  const [sel, setSel] = useState("");
  const [rows, setRows] = useState([]);
  const [loadingRows, setLoadingRows] = useState(false);
  const [errRows, setErrRows] = useState("");
  const [filter, setFilter] = useState("");

  const navigate = useNavigate();

  // Cargar listado de clientes
  useEffect(() => {
    (async () => {
      try {
        setErrClientes("");
        setLoadingClientes(true);
        const data = await getClientes(); // /api/catalogos/clientes/
        setClientes(Array.isArray(data) ? data : []);
      } catch (e) {
        setErrClientes(e?.message || "No se pudieron cargar los clientes");
        setClientes([]);
      } finally {
        setLoadingClientes(false);
      }
    })();
  }, []);

  // Buscar ingresos del cliente seleccionado
  async function buscar() {
    if (!sel) return;
    try {
      setErrRows("");
      setLoadingRows(true);
      const data = await api.get(`/api/clientes/${sel}/general/`);
      const list = Array.isArray(data) ? data : [];
      // Si necesitás ordenar por fecha de ingreso (recientes primero):
      list.sort((a, b) => {
        const da = new Date(a?.fecha_ingreso ?? 0).getTime();
        const db = new Date(b?.fecha_ingreso ?? 0).getTime();
        return db - da;
      });
      setRows(list);
    } catch (e) {
      setErrRows(e?.message || "No se pudo cargar el general del cliente");
      setRows([]);
    } finally {
      setLoadingRows(false);
    }
  }

  const filtered = useMemo(() => {
    const needle = norm(filter);
    if (!needle) return rows;
    return rows.filter((row) => {
      const campos = [
        formatOS(row),
        row?.marca ?? row?.equipo?.marca,
        row?.modelo ?? row?.equipo?.modelo,
        row?.estado,
        row?.presupuesto_estado,
        row?.numero_serie,
        row?.ubicacion_nombre ?? String(row?.ubicacion_id ?? ""),
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

  return (
    <div className="card">
      <div className="h1 mb-3">General por cliente</div>

      {/* Errores de clientes */}
      {errClientes && (
        <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-3">
          {errClientes}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <select
          className="input"
          value={sel}
          onChange={(e) => setSel(e.target.value)}
          disabled={loadingClientes}
          aria-label="Elegir cliente"
        >
          <option value="">{loadingClientes ? "Cargando clientes…" : "-- Elegí cliente --"}</option>
          {clientes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.razon_social ?? c.nombre ?? `Cliente ${c.id}`}
            </option>
          ))}
        </select>
        <button
          className="btn"
          onClick={buscar}
          disabled={!sel || loadingRows}
          aria-busy={loadingRows ? "true" : "false"}
          title={!sel ? "Elegí un cliente para buscar" : "Buscar ingresos del cliente"}
        >
          Buscar
        </button>
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filtrar resultados por OS, equipo, serie, estado…"
          className="border rounded p-2 w-full max-w-md"
          aria-label="Filtrar resultados"
        />
      </div>

      {/* Errores de la búsqueda */}
      {errRows && (
        <div className="bg-red-100 border border-red-300 text-red-700 p-2 rounded mb-3">
          {errRows}
        </div>
      )}

      {loadingRows ? (
        "Cargando…"
      ) : rows.length === 0 && sel ? (
        <div className="text-sm text-gray-500">No hay resultados para este cliente.</div>
      ) : rows.length === 0 ? (
        <div className="text-sm text-gray-500">
          Elegí un cliente y presioná <span className="font-medium">Buscar</span>.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left">
                <th scope="col" className="p-2">OS</th>
                <th scope="col" className="p-2">Equipo</th>
                <th scope="col" className="p-2">Serie</th>
                <th scope="col" className="p-2">Estado</th>
                <th scope="col" className="p-2">Presupuesto</th>
                <th scope="col" className="p-2">Ubicación</th>
                <th scope="col" className="p-2">Fecha ingreso</th>
                <th scope="col" className="p-2">Último cambio</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr
                  key={ingresoIdOf(row)}
                  onClick={() => go(row)}
                  onKeyDown={(e) => onRowKeyDown(e, row)}
                  className="hover:bg-gray-50 cursor-pointer border-t"
                  role="link"
                  tabIndex={0}
                  aria-label={`Abrir hoja de servicio de ${formatOS(row)}`}
                  data-testid={`row-${ingresoIdOf(row)}`}
                >
                  <td className="p-2 underline">{formatOS(row)}</td>
                  <td className="p-2">
                    {(row?.marca ?? row?.equipo?.marca ?? "-") +
                      " " +
                      (row?.modelo ?? row?.equipo?.modelo ?? "")}
                  </td>
                  <td className="p-2">{row?.numero_serie ?? "-"}</td>
                  <td className="p-2">{row?.estado ?? "-"}</td>
                  <td className="p-2">{row?.presupuesto_estado ?? "-"}</td>
                  <td className="p-2">{row?.ubicacion_nombre ?? row?.ubicacion_id ?? "-"}</td>
                  <td className="p-2 whitespace-nowrap">{formatDateTime(row?.fecha_ingreso)}</td>
                  <td className="p-2 whitespace-nowrap">
                    {formatDateTime(
                      row?.fecha_actualizacion ??
                        row?.fecha_estado ??
                        row?.fecha_reparado ??
                        row?.fecha_aprobacion
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-xs text-gray-500 mt-2">
            Mostrando {filtered.length} de {rows.length}.
          </div>
        </div>
      )}
    </div>
  );
}
