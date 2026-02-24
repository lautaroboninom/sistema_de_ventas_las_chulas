//web\src\App.jsx
import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
//import Sidebar from "web\src\components\Sidebar.jsx"; //  nuevo
import Sidebar from "./components/Sidebar.jsx";
import Footer from "./components/Footer.jsx";
import useRouteUiState from "./hooks/useRouteUiState";


export default function App() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const rol = user?.rol;
  const isJefe = rol === "jefe";
  const isJefeVeedor = rol === "jefe_veedor";
  const isAdmin = rol === "admin";
  const isTecnico = rol === "tecnico";

  useRouteUiState();

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileMenuOpen]);

  useEffect(() => {
    if (!mobileMenuOpen) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mobileMenuOpen]);

 return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b bg-white">
        <div className="max-w-7xl mx-auto px-4 h-12 flex items-center">
          <button
            type="button"
            aria-label="Abrir menu"
            aria-controls="app-sidebar"
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen((open) => !open)}
            className="mr-3 inline-flex h-8 w-8 items-center justify-center rounded border border-gray-200 text-gray-700 hover:bg-gray-50 md:hidden"
          >
            <span className="sr-only">Abrir menu</span>
            <span className="flex flex-col gap-1">
              <span className="block h-0.5 w-4 bg-current"></span>
              <span className="block h-0.5 w-4 bg-current"></span>
              <span className="block h-0.5 w-4 bg-current"></span>
            </span>
          </button>

          <Link to="/" className="font-semibold">SEPID  Reparaciones</Link>

          {/* Tabs generales */}
          <nav className="hidden md:flex items-center gap-6 ml-6">
            <Link to="/clientes" className="hover:underline">
              General por cliente
            </Link>
            <Link to="/ingresos/historico" className="hover:underline">
              Histórico ingresos
            </Link>
            {(isJefe || isAdmin || isJefeVeedor || isTecnico) && (
              <Link to="/equipos" className="hover:underline">
                Equipos
              </Link>
            )}
          </nav>

          <div className="ml-auto flex items-center gap-2 md:gap-3">
            {(isJefe || isAdmin || isJefeVeedor) && (
              <Link
                to="/ingresos/nuevo"
                className="px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 text-xs md:text-sm"
              >
                Nuevo Ingreso
              </Link>
            )}
            {user && (
              <span className="hidden md:inline text-sm text-gray-500">
                {user?.nombre}  {rol}
              </span>
            )}
            <button
              onClick={() => { logout(); nav("/login"); }}
              className="px-2.5 py-1.5 rounded border hover:bg-gray-50 text-xs md:text-sm md:px-3"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 flex">
        <Sidebar
          mobileOpen={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
        />
        <div className="flex-1 p-3 md:p-6">
          <Outlet />
        </div>
      </main>

      <Footer />
    </div>
  );
}
