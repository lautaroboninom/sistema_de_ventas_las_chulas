// web/src/pages/Usuarios.jsx
import { useEffect, useMemo, useState } from "react";
import {
  getUsuarios, postUsuario, patchUsuarioActivo,
  patchUsuarioReset, patchUsuarioRolePerm, deleteUsuario,
  getRoles
} from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const Input = (p) => <input {...p} className="border rounded p-2 w-full" />;
const Select = (p) => <select {...p} className="border rounded p-2 w-full" />;
const Btn = ({variant="solid", className="", ...props}) => {
  const base = "px-3 py-2 rounded text-sm";
  const styles = variant === "solid"
    ? "bg-blue-600 text-white hover:bg-blue-700"
    : variant === "danger"
    ? "bg-red-600 text-white hover:bg-red-700"
    : "border hover:bg-gray-50";
  return <button className={`${base} ${styles} ${className}`} {...props} />;
};


export default function Usuarios() {
  const { user: yo } = useAuth();
  const soyJefe = yo?.rol === "jefe" || yo?.rol === "jefe_veedor";
  const soyAdmin = yo?.rol === "admin";

  const [rows, setRows] = useState([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [nuevo, setNuevo] = useState({ nombre:"", email:"", rol:"tecnico", password:"" });
  const [resets, setResets] = useState({}); // { [id]: "nuevaPass" }
  const [roles, setRoles] = useState([]); // [{value,label}]
  useEffect(() => {
    (async () => {
      try {
        const [us, rs] = await Promise.all([getUsuarios(), getRoles()]);
        setRows(us);
        setRoles(Array.isArray(rs) ? rs : []);
      } catch (e) {
        setErr(normalizeErr(e));
      }
    })();
  }, []);
  const roleLabel = (val) => roles.find(r => r.value === val)?.label || val;
  const load = async () => {
    setErr(""); setMsg("");
    try { setRows(await getUsuarios()); }
    catch(e){ setErr(normalizeErr(e)); }
  };

  useEffect(() => { load(); }, []);

  const onNew = (k) => (e) => setNuevo({ ...nuevo, [k]: e.target.value });

  const crear = async (e) => {
    e.preventDefault();
    try {
      await postUsuario(nuevo); // crea o actualiza si el email ya existe
      setNuevo({ nombre:"", email:"", rol:"tecnico", password:"" });
      setMsg("Usuario creado/actualizado");
      load();
    } catch(e){ setErr(normalizeErr(e)); }
  };

  const toggleActivo = async (u) => {
    try {
      await patchUsuarioActivo(u.id, !u.activo);
      setMsg(`Usuario ${!u.activo ? "activado" : "desactivado"}`);
      load();
    } catch(e){ setErr(normalizeErr(e)); }
  };

  const cambiarRol = async (u, rol) => {
    try {
      await patchUsuarioRolePerm(u.id, { rol });
      setMsg("Rol actualizado");
      load();
    } catch(e){ setErr(normalizeErr(e)); }
  };

  const togglePermIngresar = async (u) => {
    try {
      await patchUsuarioRolePerm(u.id, { perm_ingresar: !u.perm_ingresar });
      setMsg("Permiso actualizado");
      load();
    } catch(e){ setErr(normalizeErr(e)); }
  };

  const resetPw = async (u) => {
    const pw = resets[u.id] || "";
    if (!pw) { alert("Ingresá la nueva contraseña"); return; }
    try {
      await patchUsuarioReset(u.id, pw);
      setResets({ ...resets, [u.id]:"" });
      setMsg("Contraseña reiniciada");
    } catch(e){ setErr(normalizeErr(e)); }
  };

  const borrar = async (u) => {
    if (!confirm(`¿Eliminar usuario ${u.email}?`)) return;
    try { await deleteUsuario(u.id); setMsg("Usuario eliminado"); load(); }
    catch(e){ setErr(normalizeErr(e)); }
  };

  const puedeEditar = useMemo(() => soyJefe || soyAdmin, [soyJefe, soyAdmin]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">Usuarios</h1>
        <span className="text-gray-500">
          ({roleLabel(yo?.rol)})
        </span>
      </div>

      {err && <div className="bg-red-100 text-red-700 p-2 rounded">{err}</div>}
      {msg && <div className="bg-green-100 text-green-700 p-2 rounded">{msg}</div>}

      {(soyJefe || soyAdmin) && (
        <form onSubmit={crear} className="border rounded p-4 grid md:grid-cols-5 gap-3">
          <div className="md:col-span-2">
            <label className="text-sm">Nombre</label>
            <Input value={nuevo.nombre} onChange={onNew("nombre")} required />
          </div>
          <div className="md:col-span-2">
            <label className="text-sm">Email</label>
            <Input type="email" value={nuevo.email} onChange={onNew("email")} required />
          </div>
          <div>
            <label className="text-sm">Rol</label>
            <Select value={nuevo.rol} onChange={onNew("rol")}>
              {roles.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </Select>
          </div>
          <div className="md:col-span-4">
            <label className="text-sm">Contraseña (opcional)</label>
            <Input type="text" value={nuevo.password} onChange={onNew("password")}
                   placeholder="Si se completa, crea/actualiza con esta clave" />
          </div>
          <div className="md:col-span-1 self-end">
            <Btn type="submit" className="w-full">Guardar</Btn>
          </div>
        </form>
      )}

      <div className="overflow-auto border rounded">
        <table className="min-w-full">
          <thead>
            <tr className="bg-gray-50 text-left">
              <th className="p-2">ID</th>
              <th className="p-2">Nombre</th>
              <th className="p-2">Email</th>
              <th className="p-2">Rol</th>
              <th className="p-2">Perm. Ingresar</th>
              <th className="p-2">Activo</th>
              <th className="p-2">Reset Pass</th>
              <th className="p-2 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(u => (
              <tr key={u.id} className="border-t">
                <td className="p-2">{u.id}</td>
                <td className="p-2">{u.nombre}</td>
                <td className="p-2">{u.email}</td>
                <td className="p-2">
                  {soyJefe ? (
                    <Select value={u.rol} onChange={e => cambiarRol(u, e.target.value)}>
                      {roles.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                    </Select>
                  ) : (
                    <span className="px-2 py-1 rounded bg-gray-100">{roleLabel(u.rol)}</span>
                  )}
                </td>
                <td className="p-2">
                  {soyJefe && u.rol === "admin" ? (
                    <label className="inline-flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={!!u.perm_ingresar} onChange={() => togglePermIngresar(u)} />
                      <span className="text-sm">{u.perm_ingresar ? "Sí" : "No"}</span>
                    </label>
                  ) : (
                    <span className="text-sm text-gray-600">
                      {u.rol === "admin" ? (u.perm_ingresar ? "Sí" : "No") : "-"}
                    </span>
                  )}
                </td>
                <td className="p-2">
                  {puedeEditar ? (
                    <label className="inline-flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={!!u.activo} onChange={() => toggleActivo(u)} />
                      <span className="text-sm">{u.activo ? "Activo" : "Inactivo"}</span>
                    </label>
                  ) : (
                    <span className="text-sm">{u.activo ? "Activo" : "Inactivo"}</span>
                  )}
                </td>
                <td className="p-2">
                  {soyJefe ? (
                    <div className="flex items-center gap-2">
                      <Input placeholder="Nueva clave"
                             value={resets[u.id] || ""}
                             onChange={e => setResets({ ...resets, [u.id]: e.target.value })} />
                      <Btn onClick={() => resetPw(u)}>OK</Btn>
                    </div>
                  ) : <span className="text-gray-400">-</span>}
                </td>
                <td className="p-2 text-right">
                  {soyJefe ? (
                    <Btn variant="danger" onClick={() => borrar(u)}>Eliminar</Btn>
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr><td colSpan="8" className="p-4 text-center text-gray-500">Sin usuarios</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function normalizeErr(e) {
  try {
    const t = e.message || "";
    return t.startsWith("{") ? JSON.parse(t).detail || t : t;
  } catch { return e.message || "Error"; }
}
