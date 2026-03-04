import { useState } from 'react';
import { postAuthForgot } from '../lib/api';
import Footer from '../components/Footer.jsx';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState('');
  const [sending, setSending] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr('');
    if (sending) return;
    setSending(true);
    try {
      await postAuthForgot(email);
      setSent(true);
    } catch (error) {
      setErr(error?.message || 'Error al enviar');
    } finally {
      setSending(false);
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

          <h1 className="h1 mb-3">Recuperar contraseña</h1>

          {sent ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
              Si el correo existe, enviamos un enlace para restablecer la contraseña.
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-3">
              {err ? (
                <div className="rounded-lg border border-red-300 bg-red-50 p-2 text-sm text-red-700">
                  {err}
                </div>
              ) : null}

              <div>
                <label className="label" htmlFor="email">Email</label>
                <input
                  id="email"
                  className="input"
                  placeholder="tu@empresa.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                />
              </div>

              <button type="submit" disabled={sending || !email.trim()} className="btn w-full">
                {sending ? 'Enviando...' : 'Enviar enlace'}
              </button>
            </form>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
