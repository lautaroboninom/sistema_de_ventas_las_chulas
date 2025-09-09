import { useState } from "react";
import { postAuthForgot } from "../lib/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");

  async function submit(e){
    e.preventDefault();
    setErr("");
    try{
      await postAuthForgot(email);
      setSent(true);
    }catch(e){ setErr(e?.message || "Error"); }
  }

  return (
    <div className="max-w-sm mx-auto mt-16 border rounded p-4">
      <h1 className="text-xl font-semibold mb-3">Recuperar contraseña</h1>
      {sent ? (
        <div className="text-sm text-gray-700">
          Si el correo existe, te enviamos un enlace para restablecer la contraseña.
          Revisá tu bandeja de entrada y el spam.
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          {err && <div className="bg-red-100 text-red-700 p-2 rounded">{err}</div>}
          <input className="border rounded p-2 w-full" placeholder="tu@sepid.com.ar"
                 value={email} onChange={e=>setEmail(e.target.value)} />
          <button className="bg-blue-600 text-white w-full p-2 rounded">Enviar enlace</button>
        </form>
      )}
    </div>
  );
}
