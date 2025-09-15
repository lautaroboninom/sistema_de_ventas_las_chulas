// web/src/pages/Login.jsx
import { useEffect, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [backendOk, setBackendOk] = useState(true);

  const nav = useNavigate();
  const loc = useLocation();
  const { login } = useAuth();

  const from = loc.state?.from?.pathname || "/";

  // Verificacion rapida del backend para diferenciar error de red vs. credenciales
  useEffect(() => {
    (async () => {
      try {
        await api.get("/api/health/");
        setBackendOk(true);
      } catch {
        setBackendOk(false);
      }
    })();
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      nav(from, { replace: true });
    } catch (e) {
      const msg = e?.message || "Credenciales invalidas";
      if (!backendOk) {
        setErr("Backend no disponible en /api. Verifica que la API este levantada (http://localhost:8000).");
      } else {
        setErr(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-md mx-auto mt-16 card">
      {!backendOk && (
        <div className="mb-3 text-sm bg-yellow-100 text-yellow-800 p-2 rounded">
          Backend no disponible.
        </div>
      )}
      <div className="h1 mb-4">Ingresar</div>
      <form className="space-y-3" onSubmit={onSubmit}>
        <input
          className="input"
          type="email"
          placeholder="...@sepid.com.ar"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />
        <input
          className="input"
          type="password"
          placeholder="Contrasena"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
        {err && <div className="text-red-600 text-sm">{err}</div>}
        <button className="btn w-full" type="submit" disabled={loading}>
          {loading ? "Ingresando..." : "Entrar"}
        </button>

        <Link to="/recuperar" className="text-sm text-blue-700 underline inline-block mt-1">
          ¿Olvidaste tu contrasena?
        </Link>
      </form>
    </div>
  );
}
