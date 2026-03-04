import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { postAuthReset } from '../lib/api';
import Footer from '../components/Footer.jsx';

export default function ResetPassword() {
  const [sp] = useSearchParams();
  const token = sp.get('t') || sp.get('token') || '';
  const nav = useNavigate();

  const [p1, setP1] = useState('');
  const [p2, setP2] = useState('');
  const [err, setErr] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) setErr('Link inválido');
  }, [token]);

  async function submit(e) {
    e.preventDefault();
    setErr('');
    if (p1.length < 8) return setErr('La contraseña debe tener al menos 8 caracteres.');
    if (p1 !== p2) return setErr('Las contraseñas no coinciden.');
    try {
      await postAuthReset(token, p1);
      setDone(true);
      setTimeout(() => nav('/login'), 1200);
    } catch (error) {
      setErr(error?.message || 'No se pudo restablecer');
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <main className="mx-auto flex w-full max-w-md flex-1 items-center px-4 py-10">
        <div className="card w-full">
          <img
            src="/branding/las-chulas-mark.svg"
            alt="Las Chulas"
            className="mb-5 h-12 w-full rounded-lg border border-neutral-200 object-contain"
          />

          <h1 className="h1 mb-3">Restablecer contraseña</h1>

          {done ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
              Listo. Ya podés iniciar sesión.
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-3">
              {err ? (
                <div className="rounded-lg border border-red-300 bg-red-50 p-2 text-sm text-red-700">
                  {err}
                </div>
              ) : null}
              <input
                type="password"
                className="input"
                placeholder="Nueva contraseña"
                value={p1}
                onChange={(e) => setP1(e.target.value)}
              />
              <input
                type="password"
                className="input"
                placeholder="Repetir contraseña"
                value={p2}
                onChange={(e) => setP2(e.target.value)}
              />
              <button className="btn w-full">Guardar</button>
            </form>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
