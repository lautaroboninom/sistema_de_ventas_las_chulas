import { useEffect, useState } from "react";
import { getProveedoresExternos, postProveedorExterno, deleteProveedorExterno } from "../lib/api";

const Input = (p) => <input {...p} className="border rounded p-2 w-full" />;
const TextArea = (p) => <textarea {...p} className="border rounded p-2 w-full" />;

const initialForm = { nombre:"", contacto:"", telefono:"", email:"", direccion:"", notas:"" };

export default function CatalogoProveedores() {
  const [rows, setRows] = useState([]);
  const [f, setF] = useState(initialForm);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const load = async (preserveMsg = false) => {
    setErr("");
    if (!preserveMsg) setMsg("");
    try {
      const data = await getProveedoresExternos();
      setRows(data);
      return data;
    } catch (e) {
      setErr(e.message);
      return [];
    }
  };

  useEffect(() => { load(); }, []);

  const on = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const add = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      const payload = Object.fromEntries(
        Object.entries(f).map(([k, v]) => [k, typeof v === "string" ? v.trim() : v])
      );
      if (payload.email) payload.email = payload.email.toLowerCase();
      const res = await postProveedorExterno(payload);
      setF(initialForm);
      await load(true);
      if (res?.created) {
        setMsg("Proveedor agregado");
      } else if (res?.updated) {
        setMsg("Proveedor actualizado");
      } else {
        setMsg("Proveedor guardado");
      }
    } catch (e) {
      setErr(e.message);
    }
  };

  const del = async (id) => {
    if (!confirm("Eliminar proveedor externo?")) return;
    setErr("");
    try {
      await deleteProveedorExterno(id);
      await load(true);
      setMsg("Proveedor eliminado");
    } catch (e) {
      setErr(e.message);
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Proveedores Externos</h1>
      {err && <div className="bg-red-100 text-red-700 p-2 rounded">{err}</div>}
      {msg && <div className="bg-green-100 text-green-700 p-2 rounded">{msg}</div>}

      <form onSubmit={add} className="border rounded p-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className="text-sm">Nombre</label>
          <Input value={f.nombre} onChange={on("nombre")} required />
        </div>
        <div>
          <label className="text-sm">Contacto</label>
          <Input value={f.contacto} onChange={on("contacto")} />
        </div>
        <div>
          <label className="text-sm">Teléfono</label>
          <Input value={f.telefono} onChange={on("telefono")} />
        </div>
        <div>
          <label className="text-sm">Email</label>
          <Input type="email" value={f.email} onChange={on("email")} />
        </div>
        <div className="md:col-span-2">
          <label className="text-sm">Dirección</label>
          <Input value={f.direccion} onChange={on("direccion")} />
        </div>
        <div className="md:col-span-2">
          <label className="text-sm">Notas</label>
          <TextArea rows={3} value={f.notas} onChange={on("notas")} />
        </div>
        <div className="md:col-span-2">
          <button className="bg-blue-600 text-white px-4 py-2 rounded">Guardar</button>
        </div>
      </form>

      <table className="w-full border">
        <thead>
          <tr className="bg-gray-50 text-left">
            <th className="p-2">ID</th>
            <th className="p-2">Nombre</th>
            <th className="p-2">Contacto</th>
            <th className="p-2">Teléfono</th>
            <th className="p-2">Email</th>
            <th className="p-2">Dirección</th>
            <th className="p-2">Notas</th>
            <th className="p-2 text-right"></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t">
              <td className="p-2 align-top">{r.id}</td>
              <td className="p-2 align-top">{r.nombre}</td>
              <td className="p-2 align-top">{r.contacto || "-"}</td>
              <td className="p-2 align-top">{r.telefono || "-"}</td>
              <td className="p-2 align-top">{r.email || "-"}</td>
              <td className="p-2 align-top">{r.direccion || "-"}</td>
              <td className="p-2 align-top whitespace-pre-line">{r.notas || "-"}</td>
              <td className="p-2 text-right align-top">
                <button className="px-3 py-1 border rounded text-xs" onClick={() => del(r.id)}>
                  Eliminar
                </button>
              </td>
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan="8" className="p-3 text-center text-gray-500">
                Sin proveedores
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}


