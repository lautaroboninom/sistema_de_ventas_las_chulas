import { useEffect, useState } from "react";
import { getClientes, postCliente, deleteCliente } from "../lib/api";

const Input = (p) => <input {...p} className="border rounded p-2 w-full" />;

export default function CatalogoClientes() {
  const [rows, setRows] = useState([]);
  const [f, setF] = useState({ razon_social:"", cod_empresa:"", telefono:"" });
  const [err, setErr] = useState(""); const [msg, setMsg] = useState("");

  const load = async () => {
    setErr(""); setMsg("");
    try { setRows(await getClientes()); } catch(e){ setErr(e.message); }
  };
  useEffect(() => { load(); }, []);

  const on = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const add = async (e) => {
    e.preventDefault();
    try { await postCliente(f); setF({ razon_social:"", cod_empresa:"", telefono:"" }); setMsg("Cliente agregado"); load(); }
    catch(e){ setErr(e.message); }
  };

  const del = async (id) => {
    if (!confirm("¿Eliminar cliente?")) return;
    try { await deleteCliente(id); load(); } catch(e){ setErr(e.message); }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Clientes</h1>
      {err && <div className="bg-red-100 text-red-700 p-2 rounded">{err}</div>}
      {msg && <div className="bg-green-100 text-green-700 p-2 rounded">{msg}</div>}

      <form onSubmit={add} className="border rounded p-3 grid grid-cols-1 md:grid-cols-3 gap-3">
        <div><label className="text-sm">Razón social</label><Input value={f.razon_social} onChange={on("razon_social")} required/></div>
        <div><label className="text-sm">Código empresa</label><Input value={f.cod_empresa} onChange={on("cod_empresa")} required/></div>
        <div><label className="text-sm">Teléfono</label><Input value={f.telefono} onChange={on("telefono")}/></div>
        <div className="md:col-span-3"><button className="bg-blue-600 text-white px-4 py-2 rounded">Agregar</button></div>
      </form>

      <table className="w-full border">
        <thead><tr className="bg-gray-50">
          <th className="p-2 text-left">ID</th><th className="p-2 text-left">Razón social</th><th className="p-2 text-left">Código</th><th className="p-2 text-left">Teléfono</th><th></th>
        </tr></thead>
        <tbody>
          {rows.map(c => (
            <tr key={c.id} className="border-t">
              <td className="p-2">{c.id}</td>
              <td className="p-2">{c.razon_social}</td>
              <td className="p-2">{c.cod_empresa}</td>
              <td className="p-2">{c.telefono || "-"}</td>
              <td className="p-2 text-right">
                <button onClick={() => del(c.id)} className="px-3 py-1 border rounded">Eliminar</button>
              </td>
            </tr>
          ))}
          {!rows.length && <tr><td colSpan="5" className="p-3 text-center text-gray-500">Sin clientes</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
