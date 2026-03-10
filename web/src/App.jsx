import { useEffect, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import Sidebar from './components/Sidebar.jsx';
import Footer from './components/Footer.jsx';
import { useAuth } from './context/AuthContext';
import { getRetailConfigPageSettings } from './lib/api';

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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [pageSettings, setPageSettings] = useState(mergePageSettings(null));

  useEffect(() => {
    setMobileMenuOpen(false);
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

  const appName = pageSettings.app_name || import.meta.env.VITE_APP_NAME || 'Las Chulas';

  useEffect(() => {
    const keyByPath = {
      '/pos': 'pos',
      '/productos': 'productos',
      '/compras': 'compras',
      '/ventas': 'ventas',
      '/promociones': 'promociones',
      '/garantias': 'garantias',
      '/reportes': 'reportes',
      '/online': 'online',
      '/config': 'config',
      '/config/paginas': 'config_paginas',
    };
    const key = keyByPath[location.pathname];
    const pageTitle = key ? pageSettings.page_titles?.[key] : null;
    document.title = pageTitle || appName;
  }, [location.pathname, pageSettings.page_titles, appName]);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-30 border-b border-neutral-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
          <button
            type="button"
            aria-label="Abrir menú"
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
            <button
              onClick={() => {
                logout();
                nav('/login');
              }}
              className="btn-secondary !px-3 !py-1.5 !text-xs"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      <main className="flex flex-1">
        <Sidebar
          mobileOpen={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
          labels={pageSettings.nav_labels}
          sectionTitle={pageSettings.sidebar_section_title}
        />
        <div className="flex-1 p-3 md:p-6">
          <Outlet />
        </div>
      </main>

      <Footer legalName={pageSettings.footer_legal_name} />
    </div>
  );
}
