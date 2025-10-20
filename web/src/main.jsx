// web/src/main.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ErrorBoundary from "./components/ErrorBoundary";

import "./index.css";
import App from "./App";
import Login from "./pages/Login";
import Tecnico from "./pages/Tecnico";
import Presupuestados from "./pages/Presupuestados.jsx";
import PendientesPresupuesto from "./pages/PendientesPresupuesto.jsx";
import AdminListos from "./pages/AdminListos";
import GeneralPorCliente from "./pages/GeneralPorCliente";
import Usuarios from "./pages/Usuarios";
import NuevoIngreso from "./pages/NuevoIngreso";
import CatalogoClientes from "./pages/CatalogoClientes";
import CatalogoMarcas from "./pages/CatalogoMarcas";
import CatalogoProveedores from "./pages/CatalogoProveedores";
import TiposEquipo from "./pages/TiposEquipo.jsx";
import ProtectedRoute from "./components/ProtectedRoute";
import PendientesGeneral from "./pages/PendientesGeneral.jsx";
import Aprobados from "./pages/Aprobados.jsx";
import Reparados from "./pages/Reparados.jsx";
import GeneralEquipos from "./pages/GeneralEquipos.jsx";
import ServiceSheet from "./pages/ServiceSheet";
import PendientesPorTecnico from "./pages/PendientesPorTecnico.jsx";
import DerivarIngreso from "./pages/DerivarIngreso.jsx";
import StockAlquiler from "./pages/StockAlquiler.jsx";
import BusquedaNSCard from "./components/BusquedaNSCard.jsx";
import BusquedaAccRefCard from "./components/BusquedaAccRefCard.jsx";
import BuscarNS from "./pages/BuscarNS.jsx";
import BuscarAccesorio from "./pages/BuscarAccesorio.jsx";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Depositos from "./pages/Depositos.jsx";
import Derivados from "./pages/Derivados.jsx";
import Metricas from "./pages/Metricas.jsx";
import MetricasClientes from "./pages/MetricasClientes.jsx";
import ConfigMetricas from "./pages/ConfigMetricas.jsx";
import Garantias from "./pages/Garantias.jsx";

function NotFound() {
  return (
    <div className="p-8 text-center text-gray-600">
      Pgina no encontrada
    </div>
  );
}

const router = createBrowserRouter([
  // pblicas
  { path: "/login", element: <Login /> },
  { path: "/recuperar", element: <ForgotPassword /> },
  { path: "/restablecer", element: <ResetPassword /> },

  // privadas (layout App)
  {
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: (
          <ProtectedRoute roles={["tecnico","jefe","jefe_veedor","admin","recepcion"]}>
            <div className="p-6">
              <h1 className="text-2xl font-bold">Bienvenido </h1>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <BusquedaNSCard />
                <BusquedaAccRefCard />
              </div>
            </div>
          </ProtectedRoute>
        ),
      },

      // Operacin
      {
        path: "buscar-ns",
        element: (
          <ProtectedRoute roles={["tecnico","jefe","admin","recepcion"]}>
            <BuscarNS />
          </ProtectedRoute>
        ),
      },
      {
        path: "buscar-accesorio",
        element: (
          <ProtectedRoute roles={["tecnico","jefe","admin","recepcion"]}>
            <BuscarAccesorio />
          </ProtectedRoute>
        ),
      },
      {
        path: "tecnico",
        element: (
          <ProtectedRoute roles={["tecnico","jefe","jefe_veedor"]}>
            <Tecnico />
          </ProtectedRoute>
        ),
      },
      {
        path: "pendientes",
        element: (
          <ProtectedRoute roles={["tecnico","jefe","jefe_veedor"]}>
            <PendientesGeneral />
          </ProtectedRoute>
        ),
      },
      {
        path: "pendientes-por-tecnico",
        element: (
          <ProtectedRoute roles={["jefe","admin","jefe_veedor"]}>
            <PendientesPorTecnico />
          </ProtectedRoute>
        ),
      },
      {
        path: "pendientes-presupuesto",
        element: (
          <ProtectedRoute roles={["jefe","jefe_veedor"]}>
            <PendientesPresupuesto />
          </ProtectedRoute>
        ),
      },
      {
        path: "presupuestados",
        element: (
          <ProtectedRoute roles={["jefe","jefe_veedor"]}>
            <Presupuestados />
          </ProtectedRoute>
        ),
      },
      {
        path: "aprobados",
        element: (
          <ProtectedRoute roles={["tecnico","jefe","jefe_veedor"]}>
            <Aprobados />
          </ProtectedRoute>
        ),
      },
      {
        path: "reparados",
        element: (
          <ProtectedRoute roles={["tecnico","jefe","jefe_veedor"]}>
            <Reparados />
          </ProtectedRoute>
        ),
      },
      {
        path: "derivados",
        element: (
          <ProtectedRoute roles={["tecnico","jefe","jefe_veedor","admin","recepcion"]}>
            <Derivados />
          </ProtectedRoute>
        ),
      },
      {
        path: "listos",
        element: (
          <ProtectedRoute roles={["tecnico","jefe","jefe_veedor","admin","recepcion"]}>
            <AdminListos />
          </ProtectedRoute>
        ),
      },
      {
        path: "alquiler/stock",
        element: (
          <ProtectedRoute roles={["jefe","admin","recepcion","tecnico"]}>
            <StockAlquiler />
          </ProtectedRoute>
        ),
      },
      {
        path: "depositos",
        element: (
          <ProtectedRoute roles={["tecnico","jefe","jefe_veedor","admin","recepcion"]}>
            <Depositos />
          </ProtectedRoute>
        ),
      },

      // Tabs superiores
      {
        path: "clientes",
        element: (
          <ProtectedRoute roles={["admin","jefe","jefe_veedor","recepcion"]}>
            <GeneralPorCliente />
          </ProtectedRoute>
        ),
      },
      {
        path: "equipos",
        element: (
          <ProtectedRoute roles={["tecnico","jefe","jefe_veedor","admin","recepcion"]}>
            <GeneralEquipos />
          </ProtectedRoute>
        ),
      },

      // Nuevo ingreso
      {
        path: "ingresos/nuevo",
        element: (
          <ProtectedRoute roles={["jefe","jefe_veedor","admin"]}>
            <NuevoIngreso />
          </ProtectedRoute>
        ),
      },

      // Sistema
      {
        path: "metricas",
        element: (
          <ProtectedRoute roles={["jefe"]}>
            <Metricas />
          </ProtectedRoute>
        ),
      },
      {
        path: "metricas/clientes",
        element: (
          <ProtectedRoute roles={["jefe"]}>
            <MetricasClientes />
          </ProtectedRoute>
        ),
      },
      {
        path: "metricas/config",
        element: (
          <ProtectedRoute roles={["jefe"]}>
            <ConfigMetricas />
          </ProtectedRoute>
        ),
      },
      {
        path: "garantias",
        element: (
          <ProtectedRoute roles={["jefe","jefe_veedor","admin"]}>
            <Garantias />
          </ProtectedRoute>
        ),
      },
      {
        path: "usuarios",
        element: (
          <ProtectedRoute roles={["jefe","jefe_veedor"]}>
            <Usuarios />
          </ProtectedRoute>
        ),
      },
      {
        path: "catalogo/clientes",
        element: (
          <ProtectedRoute roles={["jefe","jefe_veedor","admin"]}>
            <CatalogoClientes />
          </ProtectedRoute>
        ),
      },
      {
        path: "catalogo/marcas",
        element: (
          <ProtectedRoute roles={["jefe","jefe_veedor","admin"]}>
            <CatalogoMarcas />
          </ProtectedRoute>
        ),
      },
      {
        path: "catalogo/tipos-equipo",
        element: (
          <ProtectedRoute roles={["jefe","jefe_veedor","admin"]}>
            <TiposEquipo />
          </ProtectedRoute>
        ),
      },
      {
        path: "catalogo/proveedores",
        element: (
          <ProtectedRoute roles={["jefe","jefe_veedor","admin"]}>
            <CatalogoProveedores />
          </ProtectedRoute>
        ),
      },

      // Hoja de servicio
      {
        path: "ingresos/:id",
        element: (
          <ProtectedRoute roles={["jefe","jefe_veedor","admin","tecnico","recepcion"]}>
            <ServiceSheet />
          </ProtectedRoute>
        ),
      },
      {
        path: "ingresos/:id/derivar",
        element: (
          <ProtectedRoute roles={["tecnico","jefe","admin"]}>
            <DerivarIngreso />
          </ProtectedRoute>
        ),
      },
    ],
  },

  // 404
  { path: "*", element: <NotFound /> },
]);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>
);

// Limpieza de Service Workers/caches antiguos para evitar mezclar bundles
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  // Intentar desregistrar cualquier SW previo y limpiar caches de app
  try {
    navigator.serviceWorker.getRegistrations?.().then((regs) => {
      regs?.forEach((r) => r.unregister().catch(() => {}));
    });
    if (window.caches && caches.keys) {
      caches.keys().then((keys) => keys.forEach((k) => caches.delete(k)));
    }
  } catch (_) {}
}

// Registrar Service Worker (opcional): habilitar solo si VITE_SW=1 en build
if (import.meta.env.PROD && import.meta.env.VITE_SW === '1' && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // silenciosamente ignoramos errores de registro
    });
  });
}

