import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Footer from '../components/Footer.jsx';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);
  const [backendOk, setBackendOk] = useState(true);

  const appName =
    window.localStorage.getItem('las_chulas_app_name') || import.meta.env.VITE_APP_NAME || 'Las Chulas';
  const appTagline =
    window.localStorage.getItem('las_chulas_app_tagline') || 'Retail de indumentaria';
  const footerName =
    window.localStorage.getItem('las_chulas_footer_legal_name') ||
    import.meta.env.VITE_COMPANY_LEGAL ||
    appName;

  const nav = useNavigate();
  const loc = useLocation();
  const { login } = useAuth();

  const params = new URLSearchParams(loc.search || '');
  const nextParam = params.get('next');
  const from = nextParam || loc.state?.from?.pathname || '/';

  useEffect(() => {
    (async () => {
      try {
        const base = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '');
        const pingUrl = `${base}/api/ping/`;
        const res = await fetch(pingUrl, {
          method: 'GET',
          credentials: 'omit',
          cache: 'no-store',
        });
        if (!res.ok) throw new Error(`Ping failed: ${res.status}`);
        setBackendOk(true);
      } catch {
        setBackendOk(false);
      }
    })();
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setErr('');
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      nav(from, { replace: true });
    } catch (error) {
      const msg = error?.message || 'Credenciales inválidas';
      if (!backendOk) {
        setErr('Backend no disponible en /api. Verificá que la API esté levantada en http://localhost:18100.');
      } else {
        setErr(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -left-24 top-8 h-64 w-64 rounded-full bg-[#ef6f61]/20 blur-3xl" />
        <div className="absolute -right-10 top-16 h-52 w-52 rounded-full bg-[#0b0b0d]/10 blur-3xl" />
        <div className="absolute bottom-0 left-1/2 h-44 w-3/4 -translate-x-1/2 rounded-full bg-[#f1d7ca]/45 blur-3xl" />
      </div>

      <main className="mx-auto flex min-h-[calc(100vh-56px)] w-full max-w-6xl items-center px-4 py-8">
        <div className="grid w-full gap-5 lg:grid-cols-[1.1fr_1fr]">
          <section className="hidden rounded-3xl border border-neutral-200 bg-[#111111] p-8 text-neutral-50 shadow-xl lg:flex lg:flex-col lg:justify-between">
            <div className="space-y-4">
              <img
                src="/branding/las-chulas-mark.svg"
                alt={appName}
                className="h-16 w-auto rounded-xl border border-white/10 object-contain"
              />
              <h1 className="text-3xl font-bold leading-tight tracking-tight">{appName}</h1>
              <p className="max-w-md text-sm leading-relaxed text-neutral-300">
                Caja ágil, stock confiable por variantes y operación lista para ARCA y Tienda Nube.
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-neutral-200">
              Acceso para admin y empleados del local.
            </div>
          </section>

          <section className="card rounded-3xl p-6 md:p-8">
            <div className="mb-5 rounded-2xl bg-black p-3">
              <img
                src="/branding/las-chulas-mark.svg"
                alt={appName}
                className="h-14 w-full object-contain"
              />
            </div>

            {!backendOk ? (
              <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800">
                Backend no disponible.
              </div>
            ) : null}

            <h2 className="h1 mb-1">Ingreso al sistema</h2>
            <p className="mb-5 text-sm text-neutral-500">{appTagline}</p>

            <form className="space-y-3" onSubmit={onSubmit}>
              <div>
                <label className="label" htmlFor="email">Usuario</label>
                <input
                  id="email"
                  className="input"
                  type="email"
                  placeholder="Usuario o email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                />
              </div>

              <div>
                <label className="label" htmlFor="password">Contraseña</label>
                <input
                  id="password"
                  className="input"
                  type="password"
                  placeholder="********"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
              </div>

              {err ? (
                <div className="rounded-lg border border-red-300 bg-red-50 p-2 text-sm text-red-700">
                  {err}
                </div>
              ) : null}

              <button className="btn w-full" type="submit" disabled={loading}>
                {loading ? 'Ingresando...' : 'Entrar'}
              </button>

              <Link to="/recuperar" className="inline-block text-sm font-semibold text-[#d9584b] hover:text-[#be4c41]">
                ¿Olvidaste tu contraseña?
              </Link>
            </form>
          </section>
        </div>
      </main>

      <Footer legalName={footerName} />
    </div>
  );
}
