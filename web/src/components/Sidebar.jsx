import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  canActAsTech,
  isJefe,
  isAdmin,
  isRecepcion,
  isJefeVeedor,
} from "../lib/authz";

const VARIANT_BORDER = {
  amber: "border-amber-500",
  green: "border-emerald-500",
  lime: "border-lime-500",
  blue: "border-blue-500",
  indigo: "border-indigo-500",
  cyan: "border-cyan-500",
  black: "border-black",
  gray: "border-gray-400",
};

function variantOfPath(to) {
  const p = String(to || "");
  if (p === "/tecnico") return "amber";
  if (p === "/pendientes") return "gray";
  if (p === "/pendientes-por-tecnico") return "amber";
  if (p === "/pendientes-presupuesto") return "amber";
  if (p === "/presupuestados") return "lime";
  if (p === "/aprobados") return "lime";
  if (p === "/derivados") return "cyan";
  if (p === "/reparados") return "lime";
  if (p === "/listos") return "green";
  if (p === "/alquiler/stock") return "indigo";
  if (p === "/depositos") return "black";
  return null;
}

const LinkItem = ({ to, children, variant, onClick }) => (
  <NavLink
    to={to}
    onClick={onClick}
    className={({ isActive }) => {
      const base = "block px-3 py-2 rounded hover:bg-gray-50 border-l-4";
      const active = isActive ? " bg-gray-100 font-semibold" : "";
      const v = variant || variantOfPath(to);
      const border = v ? VARIANT_BORDER[v] || "border-gray-200" : "border-transparent";
      return `${base} ${border}${active}`;
    }}
  >
    {children}
  </NavLink>
);

export default function Sidebar({ mobileOpen = false, onClose }) {
  const { user } = useAuth();
  if (!user) return null;

  const rol = user?.rol;
  const jefe = isJefe(user);
  const jefeVeedor = isJefeVeedor(user);
  const admin = isAdmin(user);
  const recep = isRecepcion(user);
  const techLike = canActAsTech(user);
  const showSistemaLinks = jefe || admin || jefeVeedor;
  const showRepuestos = jefe || admin || jefeVeedor || techLike;
  const showSistema = showSistemaLinks || showRepuestos;
  const showUsuarios = jefe || jefeVeedor;
  const handleNavigate = () => {
    if (onClose) onClose();
  };
  const linkProps = onClose ? { onClick: handleNavigate } : {};

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-black/40 md:hidden ${mobileOpen ? "block" : "hidden"}`}
        onClick={onClose}
        aria-hidden="true"
      ></div>
      <aside
        id="app-sidebar"
        className={`fixed inset-y-0 left-0 z-50 w-72 transform border-r bg-white text-sm overflow-y-auto shadow-lg transition-transform duration-200 ease-out md:static md:w-50 md:translate-x-0 md:shadow-none md:block ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex h-12 items-center justify-between border-b px-3 md:hidden">
          <span className="text-sm text-gray-600">Menú</span>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded border border-gray-200 text-gray-700 hover:bg-gray-50"
            aria-label="Cerrar menú"
            >
            X
          </button>
        </div>

        {user && (
          <div className="border-b px-3 py-2 text-xs text-gray-500 md:hidden">
            {user?.nombre} {rol}
          </div>
        )}

        <div className="p-3 text-xs text-gray-500 hidden md:block">Menú</div>
        <div className="px-3 pb-3 space-y-2">
          <div className="md:hidden">
            <div className="text-xs uppercase text-gray-400 px-1 mb-1">General</div>
            <LinkItem to="/clientes" {...linkProps}>
              General por cliente
            </LinkItem>
            <LinkItem to="/ingresos/historico" {...linkProps}>
              Histórico ingresos
            </LinkItem>
            {(jefe || admin || jefeVeedor) && (
              <LinkItem to="/equipos" {...linkProps}>
                Equipos
              </LinkItem>
            )}
          </div>

          <div>
            <div className="text-xs uppercase text-gray-400 px-1 mb-1">Equipos</div>

            {techLike && (
              <LinkItem to="/pendientes" {...linkProps}>Pendientes General</LinkItem>
            )}

            {jefe && (
              <LinkItem to="/pendientes-por-tecnico" {...linkProps}>Pendientes por técnico</LinkItem>
            )}

            {techLike && !jefeVeedor && (
              <LinkItem to="/tecnico" {...linkProps}>Mis pendientes</LinkItem>
            )}
            {(jefe || jefeVeedor) && <LinkItem to="/pendientes-presupuesto" {...linkProps}>Pendientes de Presupuesto</LinkItem>}
            {(jefe || jefeVeedor) && <LinkItem to="/presupuestados" {...linkProps}>Presupuestados</LinkItem>}
            {techLike && (
              <LinkItem to="/aprobados" {...linkProps}>Aprobados</LinkItem>
            )}
            {techLike && (
              <LinkItem to="/reparados" {...linkProps}>Reparados</LinkItem>
            )}

            {(techLike || admin || recep) && (
              <LinkItem to="/derivados" {...linkProps}>Derivados</LinkItem>
            )}
            <LinkItem to="/listos" {...linkProps}>Liberados</LinkItem>
            <LinkItem to="/alquiler/stock" {...linkProps}>Stock de Alquiler</LinkItem>
            <LinkItem to="/depositos" {...linkProps}>Depósitos/Bajas</LinkItem>
            {!showSistemaLinks && techLike && (
              <LinkItem to="/equipos" {...linkProps}>Equipos</LinkItem>
            )}
          </div>

          <div className="pt-2">
            {showSistema && (
              <>
                <div className="text-xs uppercase text-gray-400 px-1 mb-1">Sistema</div>
                {(jefe || jefeVeedor) && <LinkItem to="/metricas" {...linkProps}>Métricas</LinkItem>}
                {showUsuarios && <LinkItem to="/usuarios" {...linkProps}>Usuarios</LinkItem>}
                {showSistemaLinks && <LinkItem to="/catalogo/clientes" {...linkProps}>Clientes</LinkItem>}
                {showSistemaLinks && <LinkItem to="/catalogo/tipos-equipo" {...linkProps}>Tipos de equipo</LinkItem>}
                {showSistemaLinks && <LinkItem to="/catalogo/accesorios" {...linkProps}>Accesorios</LinkItem>}
                {showSistemaLinks && <LinkItem to="/catalogo/repuestos" {...linkProps}>Repuestos</LinkItem>}
                {showSistemaLinks && <LinkItem to="/catalogo/marcas" {...linkProps}>Marcas &amp; Modelos</LinkItem>}
                {showSistemaLinks && <LinkItem to="/catalogo/proveedores" {...linkProps}>Proveedores externos</LinkItem>}
                {showSistemaLinks && <LinkItem to="/garantias" {...linkProps}>Garantías</LinkItem>}
                {showSistemaLinks && <LinkItem to="/equipos" {...linkProps}>Equipos</LinkItem>}
                {!showSistemaLinks && showRepuestos && <LinkItem to="/catalogo/repuestos" {...linkProps}>Repuestos</LinkItem>}
              </>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}

