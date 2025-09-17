//web\src\App.jsx
import { Link, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
//import Sidebar from "web\src\components\Sidebar.jsx"; // ⬅️ nuevo
import Sidebar from "./components/Sidebar.jsx";


export default function App() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const rol = user?.rol;
  const isJefe = rol === "jefe";
  const isAdmin = rol === "admin";
 return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b bg-white">
        <div className="max-w-7xl mx-auto px-4 h-12 flex items-center gap-6">
          <Link to="/" className="font-semibold">SEPID • Reparaciones</Link>

          {/* Tabs generales */}
          <nav className="hidden md:flex items-center gap-6">
            <Link to="/clientes" className="hover:underline">
              General por cliente
            </Link>
            <Link to="/equipos" className="hover:underline">
              General equipos
            </Link>
          </nav>

          <div className="ml-auto flex items-center gap-3">
            {(isJefe || isAdmin) && (
              <Link
                to="/ingresos/nuevo"
                className="px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700"
              >
                Nuevo Ingreso
              </Link>
            )}
            {user && (
              <span className="text-sm text-gray-500">
                {user?.nombre} · {rol}
              </span>
            )}
            <button
              onClick={() => { logout(); nav("/login"); }}
              className="px-3 py-1.5 rounded border hover:bg-gray-50"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 flex">
        <Sidebar />
        <div className="flex-1 p-6">
          <Outlet />
        </div>
      </main>

      <footer className="border-t bg-white">
        <div className="max-w-7xl mx-auto px-4 py-3 text-sm text-gray-500 flex items-center justify-between">
          <span>
            &copy; {new Date().getFullYear()} Sepid S.A. Reparaciones. Todos los derechos reservados.
          </span>
        </div>
      </footer>
    </div>
  );
}
