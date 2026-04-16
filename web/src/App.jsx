import { useEffect, useRef, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import Sidebar from './components/Sidebar.jsx';
import Footer from './components/Footer.jsx';
import { useAuth } from './context/AuthContext';
import {
  getRetailConfigPageSettings,
  getRetailOnlineFailedJobsSummary,
  getSystemUpdateStatus,
  postSystemUpdateCheck,
  postSystemUpdateRestart,
} from './lib/api';
import { isAdmin } from './lib/authz';
import { can, PERMISSION_CODES } from './lib/permissions';

function mergePageSettings(raw) {
  return {
    app_name: raw?.app_name || null,
    app_tagline: raw?.app_tagline || null,
    footer_legal_name: raw?.footer_legal_name || null,
    sidebar_section_title: raw?.sidebar_section_title || null,
    default_route: raw?.default_route || null,
    nav_labels: raw?.nav_labels || {},
    page_titles: raw?.page_titles || {},
  };
}

export default function App() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const menuRef = useRef(null);

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [headerMenuOpen, setHeaderMenuOpen] = useState(false);
  const [pageSettings, setPageSettings] = useState(mergePageSettings(null));
  const [onlineAlertCount, setOnlineAlertCount] = useState(0);
  const [updateStatus, setUpdateStatus] = useState(null);
  const [updateBusy, setUpdateBusy] = useState(false);
  const [restartBusy, setRestartBusy] = useState(false);
  const [updateMessage, setUpdateMessage] = useState('');

  useEffect(() => {
    setMobileMenuOpen(false);
    setHeaderMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [mobileMenuOpen]);

  useEffect(() => {
    if (!headerMenuOpen) return undefined;
    const onMouseDown = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setHeaderMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onMouseDown);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
    };
  }, [headerMenuOpen]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    (async () => {
      try {
        const row = await getRetailConfigPageSettings();
        if (!active) return;
        const next = mergePageSettings(row);
        setPageSettings(next);
        if (next.default_route) {
          window.localStorage.setItem('las_chulas_default_route', next.default_route);
        }
      } catch {
        if (active) {
          setPageSettings(mergePageSettings(null));
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [user]);

  useEffect(() => {
    if (!user) {
      setOnlineAlertCount(0);
      return undefined;
    }
    let active = true;
    const loadOnlineAlerts = async () => {
      try {
        const resp = await getRetailOnlineFailedJobsSummary({ limit: 20 });
        const count = Number(resp?.failed_total || 0);
        if (active) setOnlineAlertCount(Math.max(0, count));
      } catch {
        if (active) setOnlineAlertCount(0);
      }
    };

    loadOnlineAlerts();
    const timer = window.setInterval(loadOnlineAlerts, 45000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [user]);

  useEffect(() => {
    if (!user) {
      setUpdateStatus(null);
      setUpdateMessage('');
      setRestartBusy(false);
      return undefined;
    }

    let active = true;

    const loadStatus = async () => {
      try {
        const status = await getSystemUpdateStatus();
        if (active) setUpdateStatus(status);
      } catch {
        // dejamos el ultimo estado conocido
      }
    };

    const checkUpdates = async () => {
      try {
        const status = await postSystemUpdateCheck({ force: false });
        if (active) setUpdateStatus(status);
      } catch (err) {
        if (!active) return;
        if (err?.data && typeof err.data === 'object') {
          setUpdateStatus(err.data);
        }
      }
    };

    (async () => {
      await loadStatus();
      await checkUpdates();
    })();

    const timer = window.setInterval(checkUpdates, 15 * 60 * 1000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [user]);

  const appName = pageSettings.app_name || import.meta.env.VITE_APP_NAME || 'Las Chulas';

  useEffect(() => {
    const keyByPath = {
      '/pos': 'pos',
      '/productos': 'productos',
      '/compras': 'compras',
      '/ventas': 'ventas',
      '/promociones': 'promociones',
      '/garantias': 'garantias',
      '/inventario': 'inventario',
      '/reportes': 'reportes',
      '/online': 'online',
      '/config': 'config',
      '/config/paginas': 'config_paginas',
    };
    const key = keyByPath[location.pathname];
    const pageTitle = key ? pageSettings.page_titles?.[key] : null;
    document.title = pageTitle || appName;
  }, [location.pathname, pageSettings.page_titles, appName]);

  const hasConfigAccess = can(user, PERMISSION_CODES.PAGE_CONFIG);
  const showPendingUpdate = Boolean(updateStatus?.pending);
  const admin = isAdmin(user);

  const handleLogout = () => {
    setHeaderMenuOpen(false);
    logout();
    nav('/login');
  };

  const goToRouteFromMenu = (path) => {
    setHeaderMenuOpen(false);
    nav(path);
  };

  const handleManualUpdateCheck = async () => {
    if (!admin || updateBusy || restartBusy) return;
    setUpdateBusy(true);
    setUpdateMessage('');
    try {
      const status = await postSystemUpdateCheck({ force: true });
      setUpdateStatus(status);
      if (status?.pending) {
        setUpdateMessage('Actualizacion pendiente detectada. Se instalara al proximo inicio.');
      } else {
        setUpdateMessage('No hay nuevas actualizaciones pendientes.');
      }
    } catch (err) {
      if (err?.data && typeof err.data === 'object') {
        setUpdateStatus(err.data);
      }
      setUpdateMessage(err?.data?.last_error || err?.message || 'No se pudo buscar actualizaciones.');
    } finally {
      setUpdateBusy(false);
    }
  };

  const handleRestartForUpdate = async () => {
    if (!admin || !showPendingUpdate || updateBusy || restartBusy) return;
    const confirmed = window.confirm(
      'Se reiniciara RetailHub para aplicar la actualizacion pendiente. Deseas continuar?',
    );
    if (!confirmed) return;

    setRestartBusy(true);
    setUpdateMessage('');
    try {
      const payload = await postSystemUpdateRestart({});
      if (payload && typeof payload === 'object') {
        setUpdateStatus((prev) => ({ ...(prev || {}), ...payload }));
      }
      if (payload?.ok && payload?.scheduled) {
        setUpdateMessage('Reinicio programado. RetailHub se reiniciara en unos segundos para aplicar la actualizacion.');
      } else {
        setUpdateMessage(payload?.last_error || 'No se pudo programar el reinicio para actualizar.');
      }
    } catch (err) {
      if (err?.data && typeof err.data === 'object') {
        setUpdateStatus((prev) => ({ ...(prev || {}), ...err.data }));
      }
      setUpdateMessage(err?.data?.last_error || err?.message || 'No se pudo programar el reinicio para actualizar.');
    } finally {
      setRestartBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-30 border-b border-neutral-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
          <button
            type="button"
            aria-label="Abrir menu"
            onClick={() => setMobileMenuOpen((open) => !open)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-300 text-neutral-700 hover:bg-neutral-100 md:hidden"
          >
            <span className="block h-0.5 w-4 bg-current" />
          </button>

          <Link to="/pos" className="flex items-center gap-2.5">
            <img
              src="/branding/las-chulas-mark.svg"
              alt={appName}
              className="hidden h-9 w-auto rounded-lg border border-neutral-200 object-contain sm:block"
            />
            <span className="text-sm font-semibold uppercase tracking-[0.14em] text-neutral-800">{appName}</span>
          </Link>

          <div className="ml-auto flex items-center gap-3">
            {user ? (
              <span className="hidden rounded-full bg-neutral-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-neutral-600 md:inline">
                {user.nombre} - {user.rol}
              </span>
            ) : null}

            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => setHeaderMenuOpen((open) => !open)}
                className="relative inline-flex items-center gap-2 rounded-lg border border-neutral-300 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-neutral-700 hover:bg-neutral-100"
              >
                Menu
                {showPendingUpdate ? (
                  <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold leading-none text-white">
                    !
                  </span>
                ) : null}
              </button>

              {headerMenuOpen ? (
                <div className="absolute right-0 z-50 mt-2 w-72 overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-2xl">
                  <div className="border-b border-neutral-200 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    {user?.nombre || 'Usuario'}
                  </div>

                  {hasConfigAccess ? (
                    <div className="border-b border-neutral-200 py-1">
                      <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Configuracion</div>
                      <button
                        type="button"
                        onClick={() => goToRouteFromMenu('/config')}
                        className="block w-full px-3 py-2 text-left text-sm text-neutral-700 hover:bg-neutral-100"
                      >
                        General
                      </button>
                      <button
                        type="button"
                        onClick={() => goToRouteFromMenu('/config/paginas')}
                        className="block w-full px-3 py-2 text-left text-sm text-neutral-700 hover:bg-neutral-100"
                      >
                        Paginas
                      </button>
                    </div>
                  ) : null}

                  <div className="border-b border-neutral-200 py-1">
                    <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Actualizaciones</div>
                    <div className="px-3 py-1 text-xs text-neutral-600">
                      {showPendingUpdate
                        ? 'Actualizacion pendiente para el proximo inicio.'
                        : 'Sin actualizaciones pendientes.'}
                    </div>
                    {updateStatus?.last_error ? (
                      <div className="px-3 py-1 text-xs text-rose-700">{updateStatus.last_error}</div>
                    ) : null}
                    {admin ? (
                      <button
                        type="button"
                        disabled={updateBusy || restartBusy}
                        onClick={handleManualUpdateCheck}
                        className="mx-3 my-2 rounded-md border border-neutral-300 px-3 py-1.5 text-xs font-semibold text-neutral-700 hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {updateBusy ? 'Buscando...' : 'Buscar actualizaciones'}
                      </button>
                    ) : null}
                    {admin && showPendingUpdate ? (
                      <button
                        type="button"
                        disabled={restartBusy || updateBusy}
                        onClick={handleRestartForUpdate}
                        className="mx-3 mb-2 rounded-md border border-amber-400 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-800 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {restartBusy ? 'Programando reinicio...' : 'Reiniciar y actualizar'}
                      </button>
                    ) : null}
                    {updateMessage ? <div className="px-3 pb-2 text-xs text-neutral-600">{updateMessage}</div> : null}
                  </div>

                  <button
                    type="button"
                    onClick={handleLogout}
                    className="block w-full px-3 py-2 text-left text-sm font-semibold text-neutral-700 hover:bg-neutral-100"
                  >
                    Salir
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </header>

      <main className="flex flex-1">
        <Sidebar
          mobileOpen={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
          labels={pageSettings.nav_labels}
          sectionTitle={pageSettings.sidebar_section_title}
          onlineAlertCount={onlineAlertCount}
        />
        <div className="flex-1 p-3 md:p-6">
          {showPendingUpdate ? (
            <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              Actualizacion pendiente. Se instalara automaticamente al proximo inicio de RetailHub.
            </div>
          ) : null}
          <Outlet />
        </div>
      </main>

      <Footer legalName={pageSettings.footer_legal_name} />
    </div>
  );
}
