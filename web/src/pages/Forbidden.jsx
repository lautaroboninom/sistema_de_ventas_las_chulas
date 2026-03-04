import { Link } from 'react-router-dom';

export default function Forbidden() {
  return (
    <div className="min-h-[65vh] flex items-center justify-center px-4 py-10">
      <div className="card w-full max-w-xl text-center">
        <img
          src="/branding/las-chulas-mark.svg"
          alt="Las Chulas"
          className="mx-auto mb-5 h-14 w-auto rounded-lg border border-neutral-200 object-contain"
        />
        <h1 className="h1 mb-2">Acceso denegado</h1>
        <p className="mb-6 text-sm text-neutral-600">
          No tenés permisos para acceder a esta sección.
        </p>
        <div className="flex items-center justify-center gap-3">
          <Link className="btn-secondary" to="/">Ir al inicio</Link>
          <Link className="btn" to="/login">Iniciar sesión</Link>
        </div>
      </div>
    </div>
  );
}
