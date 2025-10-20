import { useEffect, useMemo, useState } from "react";
import { norm } from "../lib/ui-helpers";
import api, { getTiposEquipo } from "../lib/api";

const Input = (p) => <input {...p} className="border rounded p-2 w-full" />;

export default function TiposEquipo() {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [form, setForm] = useState({ nombre: "" });
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const filtered = useMemo(() => {
    const needle = norm(q);
    if (!needle) return items;
    return (items || []).filter((it) => norm(it?.nombre || "").includes(needle));
  }, [q, items]);

  async function loadTipos() {
    setErr(""); setMsg("");
    try { setItems(await getTiposEquipo()); } catch (e) { setErr(e.message || "No se pudo cargar"); setItems([]); }
  }

  useEffect(() => { loadTipos(); }, []);

  async function handleAdd(e) {
    e.preventDefault();
    const nombre = (form.nombre || "").trim();
    if (!nombre) return;
    try {
      setLoading(true);
      setErr("");
      setMsg("");
      await api.post("/api/catalogos/tipos-equipo/", { nombre });
      setForm({ nombre: "" });
      await loadTipos();
      setMsg("Tipo agregado (aparecer cuando lo uses en un modelo)");
    } catch (e) {
      setErr(e.message || "No se pudo agregar");
    } finally {
      setLoading(false);
    }
  }

  async function renameItem(it) {
    const nuevo = prompt("Nuevo nombre", it?.nombre || "");
    const nombre = (nuevo || "").trim();
    if (!nombre || nombre === it.nombre) return;
    try {
      setLoading(true);
      setErr("");
      setMsg("");
      await api.post("/api/catalogos/tipos-equipo/", { rename_from: it.nombre, nombre });
      await loadTipos();
      setMsg("Tipo renombrado");
    } catch (e) {
      setErr(e.message || "No se pudo renombrar");
    } finally {
      setLoading(false);
    }
  }

  // No hay activar/desactivar: para ocultar, eliminar (limpiar en todos los modelos)

  async function removeItem(it) {
    if (!confirm("Eliminar tipo?")) return;
    try {
      setLoading(true);
      setErr("");
      setMsg("");
      await api.del(`/api/catalogos/tipos-equipo/?nombre=${encodeURIComponent(it.nombre)}`);
      await loadTipos();
      setMsg("Eliminado");
    } catch (e) {
      setErr(e.message || "No se pudo eliminar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-3">Tipos de equipo</h1>
      {err && <div className="bg-red-100 text-red-700 p-2 rounded mb-2">{err}</div>}
      {msg && <div className="bg-green-100 text-green-700 p-2 rounded mb-2">{msg}</div>}

      <div className="mb-2">
        <Input placeholder="Buscar tipo" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      <form onSubmit={handleAdd} className="border rounded p-3 mb-3 flex gap-2 items-end">
        <div className="flex-1">
          <label className="text-sm block mb-1">Nuevo tipo</label>
          <Input
            placeholder="Nombre de tipo"
            value={form.nombre}
            onChange={(e) => setForm({ nombre: e.target.value })}
          />
        </div>
        <button
          className="px-4 py-2 rounded bg-blue-600 text-white disabled:opacity-60"
          disabled={loading || !form.nombre.trim() }
        >
          Agregar
        </button>
      </form>

      <ul className="border rounded divide-y max-h-96 overflow-auto">
        {filtered.map((it) => (
          <li key={it.id} className="p-2 flex items-center justify-between gap-3">
            <div className="flex-1">
              <div className="font-medium">{it.nombre}</div>
              <div className="text-xs text-gray-500">&nbsp;</div>
            </div>
            <div className="flex gap-2 text-xs">
              <button className="px-2 py-1 border rounded" onClick={() => renameItem(it)} disabled={loading}>
                Renombrar
              </button>
              {/* Sin activar/desactivar */}
              <button className="px-2 py-1 border rounded" onClick={() => removeItem(it)} disabled={loading}>
                Eliminar
              </button>
            </div>
          </li>
        ))}
        {!filtered.length && (
          <li className="p-3 text-center text-gray-500">
            Sin tipos
          </li>
        )}
      </ul>
    </div>
  );
}





