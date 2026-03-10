import React from 'react';
import ReactDOM from 'react-dom/client';
import { Navigate, createBrowserRouter, RouterProvider } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ErrorBoundary from './components/ErrorBoundary';

import './index.css';
import App from './App';
import Login from './pages/Login';
import Forbidden from './pages/Forbidden.jsx';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import ProtectedRoute from './components/ProtectedRoute';
import Pos from './pages/Pos.jsx';
import Productos from './pages/Productos.jsx';
import Compras from './pages/Compras.jsx';
import Ventas from './pages/Ventas.jsx';
import Promociones from './pages/Promociones.jsx';
import Garantias from './pages/Garantias.jsx';
import Reportes from './pages/Reportes.jsx';
import Online from './pages/Online.jsx';
import ConfigGeneral from './pages/ConfigGeneral.jsx';
import ConfigPaginas from './pages/ConfigPaginas.jsx';
import { PERMISSION_CODES } from './lib/permissions';

function resolveInitialRoute() {
  const saved = window.localStorage.getItem('las_chulas_default_route') || '/pos';
  const allowed = new Set(['/pos', '/productos', '/compras', '/ventas', '/promociones', '/garantias', '/online', '/config']);
  return allowed.has(saved) ? saved : '/pos';
}

function NotFound() {
  return <div className="p-8 text-center text-gray-600">Página no encontrada</div>;
}

if (import.meta.env.VITE_SW !== '1' && 'serviceWorker' in navigator) {
  navigator.serviceWorker
    .getRegistrations()
    .then((regs) => regs.forEach((reg) => reg.unregister()))
    .catch(() => {});
}

const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  { path: '/recuperar', element: <ForgotPassword /> },
  { path: '/403', element: <Forbidden /> },
  { path: '/restablecer', element: <ResetPassword /> },
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Navigate to={resolveInitialRoute()} replace /> },
      {
        path: 'pos',
        element: (
          <ProtectedRoute permissions={PERMISSION_CODES.PAGE_POS}>
            <Pos />
          </ProtectedRoute>
        ),
      },
      {
        path: 'productos',
        element: (
          <ProtectedRoute permissions={PERMISSION_CODES.PAGE_PRODUCTOS}>
            <Productos />
          </ProtectedRoute>
        ),
      },
      {
        path: 'compras',
        element: (
          <ProtectedRoute permissions={PERMISSION_CODES.PAGE_COMPRAS}>
            <Compras />
          </ProtectedRoute>
        ),
      },
      {
        path: 'ventas',
        element: (
          <ProtectedRoute permissions={PERMISSION_CODES.PAGE_VENTAS}>
            <Ventas />
          </ProtectedRoute>
        ),
      },
      {
        path: 'promociones',
        element: (
          <ProtectedRoute permissions={PERMISSION_CODES.PAGE_PROMOCIONES}>
            <Promociones />
          </ProtectedRoute>
        ),
      },
      {
        path: 'garantias',
        element: (
          <ProtectedRoute permissions={PERMISSION_CODES.PAGE_VENTAS}>
            <Garantias />
          </ProtectedRoute>
        ),
      },
      {
        path: 'reportes',
        element: (
          <ProtectedRoute roles={['admin']}>
            <Reportes />
          </ProtectedRoute>
        ),
      },
      {
        path: 'online',
        element: (
          <ProtectedRoute permissions={PERMISSION_CODES.PAGE_ONLINE}>
            <Online />
          </ProtectedRoute>
        ),
      },
      {
        path: 'config',
        element: (
          <ProtectedRoute permissions={PERMISSION_CODES.PAGE_CONFIG}>
            <ConfigGeneral />
          </ProtectedRoute>
        ),
      },
      {
        path: 'config/paginas',
        element: (
          <ProtectedRoute permissions={PERMISSION_CODES.PAGE_CONFIG}>
            <ConfigPaginas />
          </ProtectedRoute>
        ),
      },
    ],
  },
  { path: '*', element: <NotFound /> },
]);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
