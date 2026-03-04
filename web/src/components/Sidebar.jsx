import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { can, PERMISSION_CODES } from '../lib/permissions';

const DEFAULT_LABELS = {
  pos: 'POS',
  productos: 'Productos',
  compras: 'Compras',
  ventas: 'Ventas',
  garantias: 'Cambios y devoluciones',
  reportes: 'Reportes',
  online: 'Online',
  config_general: 'Config general',
  config_paginas: 'Config páginas',
};

const LinkItem = ({ to, children, onClick }) => (
  <NavLink
    to={to}
    onClick={onClick}
    className={({ isActive }) =>
      `block rounded-xl border-l-4 px-3 py-2.5 text-sm font-semibold tracking-wide transition ${
        isActive
          ? 'border-[#ef6f61] bg-[#ef6f61]/10 text-[#111111]'
          : 'border-transparent text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900'
      }`
    }
  >
    {children}
  </NavLink>
);

export default function Sidebar({ mobileOpen = false, onClose, labels = {}, sectionTitle = 'Operaciones' }) {
  const { user } = useAuth();
  if (!user) return null;

  const navLabels = { ...DEFAULT_LABELS, ...(labels || {}) };

  const canPos = can(user, PERMISSION_CODES.PAGE_POS);
  const canProductos = can(user, PERMISSION_CODES.PAGE_PRODUCTOS);
  const canCompras = can(user, PERMISSION_CODES.PAGE_COMPRAS);
  const canVentas = can(user, PERMISSION_CODES.PAGE_VENTAS);
  const canReportes = String(user?.rol || '').toLowerCase() === 'admin';
  const canOnline = can(user, PERMISSION_CODES.PAGE_ONLINE);
  const canConfig = can(user, PERMISSION_CODES.PAGE_CONFIG);

  const handleNavigate = () => {
    if (onClose) onClose();
  };

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-black/40 md:hidden ${mobileOpen ? 'block' : 'hidden'}`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        id="app-sidebar"
        className={`fixed inset-y-0 left-0 z-50 w-72 transform border-r border-neutral-200 bg-white text-sm shadow-xl transition-transform duration-200 ease-out md:static md:w-60 md:translate-x-0 md:shadow-none ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-14 items-center justify-between border-b border-neutral-200 px-3 md:hidden">
          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500">Menú</span>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-300 text-neutral-700 hover:bg-neutral-100"
            aria-label="Cerrar menú"
          >
            X
          </button>
        </div>

        <div className="hidden border-b border-neutral-200 p-3 md:block">
          <img
            src="/branding/las-chulas-mark.svg"
            alt="Las Chulas"
            className="h-12 w-full rounded-lg border border-neutral-200 object-contain"
          />
          <div className="mt-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-neutral-500">
            {sectionTitle || 'Operaciones'}
          </div>
        </div>

        <div className="space-y-1 p-3">
          {canPos ? <LinkItem to="/pos" onClick={handleNavigate}>{navLabels.pos}</LinkItem> : null}
          {canProductos ? <LinkItem to="/productos" onClick={handleNavigate}>{navLabels.productos}</LinkItem> : null}
          {canCompras ? <LinkItem to="/compras" onClick={handleNavigate}>{navLabels.compras}</LinkItem> : null}
          {canVentas ? <LinkItem to="/ventas" onClick={handleNavigate}>{navLabels.ventas}</LinkItem> : null}
          {canVentas ? <LinkItem to="/garantias" onClick={handleNavigate}>{navLabels.garantias}</LinkItem> : null}
          {canReportes ? <LinkItem to="/reportes" onClick={handleNavigate}>{navLabels.reportes}</LinkItem> : null}
          {canOnline ? <LinkItem to="/online" onClick={handleNavigate}>{navLabels.online}</LinkItem> : null}
          {canConfig ? <LinkItem to="/config" onClick={handleNavigate}>{navLabels.config_general}</LinkItem> : null}
          {canConfig ? <LinkItem to="/config/paginas" onClick={handleNavigate}>{navLabels.config_paginas}</LinkItem> : null}
        </div>
      </aside>
    </>
  );
}
