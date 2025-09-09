// web/src/pages/Login.jsx
import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const [email, setEmail] = useState("");         // vacío, solo placeholder
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const nav = useNavigate();
  const loc = useLocation();
  const { login } = useAuth();

  const from = loc.state?.from?.pathname || "/";

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      nav(from, { replace: true });
    } catch (e) {
      setErr("Usuario o contraseña inválidos");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-md mx-auto mt-16 card">
      <div className="h1 mb-4">Ingresar</div>
      <form className="space-y-3" onSubmit={onSubmit}>
        <input
          className="input"
          type="email"
          placeholder="...@sepid.com.ar"
          value={email}
          onChange={e => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
        <input
          className="input"
          type="password"
          placeholder="Contraseña"
          value={password}
          onChange={e => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
        {err && <div className="text-red-600 text-sm">{err}</div>}
        <button className="btn w-full" type="submit" disabled={loading}>
          {loading ? "Ingresando..." : "Entrar"}
        </button>

        <Link to="/recuperar" className="text-sm text-blue-700 underline inline-block mt-1">
          ¿Olvidaste tu contraseña?
        </Link>
      </form>
    </div>
  );
}
