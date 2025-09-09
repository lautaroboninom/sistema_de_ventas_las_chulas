import { useEffect, useState } from "react";
import { getProveedoresExternos, postProveedorExterno, deleteProveedorExterno } from "../lib/api";

const Input = (p) => <input {...p} className="border rounded p-2 w-full" />;

export default function CatalogoProveedores() {
  const [rows, setRows] = useState([]);
  const [f, setF] = useState({ nombre:"", contacto:"" });
  const [err, setErr] = useState(""); const [msg, setMsg] = useState("");

  const load = async () => {
    setErr(""); setMsg("");
    try { setRows(await getProveedoresExternos()); } catch(e){ setErr(e.message); }
  };
  useEffect(() => { load(); }, []);

  const on = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const add = async (e) => {
    e.preventDefault();
    try { await postProveedorExterno(f); setF({ nombre:"", contacto:"" }); setMsg("Proveedor agregado"); load(); }
    catch(e){ setErr(e.message); }
  };

  const del = async (id) => {
    if (!confirm("¿Eliminar proveedor externo?")) return;
    try { await deleteProveedorExterno(id); load(); } catch(e){ setErr(e.message); }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Proveedores Externos</h1>
      {err && <div className="bg-red-100 text-red-700 p-2 rounded">{err}</div>}
      {msg && <div className="bg-green-100 text-green-700 p-2 rounded">{msg}</div>}

      <form onSubmit={add} className="border rounded p-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div><label className="text-sm">Nombre</label><Input value={f.nombre} onChange={on("nombre")} required/></div>
        <div><label className="text-sm">Contacto</label><Input value={f.contacto} onChange={on("contacto")} /></div>
        <div className="md:col-span-2"><button className="bg-blue-600 text-white px-4 py-2 rounded">Agregar</button></div>
      </form>

      <table className="w-full border">
        <thead><tr className="bg-gray-50">
          <th className="p-2 text-left">ID</th><th className="p-2 text-left">Nombre</th><th className="p-2 text-left">Contacto</th><th></th>
        </tr></thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.id} className="border-t">
              <td className="p-2">{r.id}</td>
              <td className="p-2">{r.nombre}</td>
              <td className="p-2">{r.contacto || "-"}</td>
              <td className="p-2 text-right"><button className="px-3 py-1 border rounded" onClick={() => del(r.id)}>Eliminar</button></td>
            </tr>
          ))}
          {!rows.length && <tr><td colSpan="4" className="p-3 text-center text-gray-500">Sin proveedores</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
