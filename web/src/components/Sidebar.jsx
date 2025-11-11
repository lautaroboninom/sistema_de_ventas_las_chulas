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
  if (p === "/pendientes") return "amber";
  if (p === "/pendientes-por-tecnico") return "amber";
  if (p === "/pendientes-presupuesto") return "lime";
  if (p === "/aprobados") return "green";
  if (p === "/derivados") return "blue";
  if (p === "/reparados") return "gray";
  if (p === "/listos") return "indigo";
  if (p === "/alquiler/stock") return "cyan";
  if (p === "/depositos") return "black";
  return null;
}

const LinkItem = ({ to, children, variant }) => (
  <NavLink
    to={to}
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

export default function Sidebar() {
  const { user } = useAuth();
  if (!user) return null;

  const jefe = isJefe(user);
  const jefeVeedor = isJefeVeedor(user);
  const admin = isAdmin(user);
  const recep = isRecepcion(user);
  const techLike = canActAsTech(user);
  const showSistema = jefe || admin || jefeVeedor;
  const showUsuarios = jefe;

  return (
    <aside className="w-50 shrink-0 border-r bg-white hidden md:block text-sm">
      <div className="p-3 text-xs text-gray-500">Menú</div>
      <div className="px-3 pb-3 space-y-2">
        <div>
          <div className="text-xs uppercase text-gray-400 px-1 mb-1">Equipos</div>

          {(jefe || jefeVeedor) && (
            <LinkItem to="/pendientes">Pendientes General</LinkItem>
          )}

          {jefe && (
            <LinkItem to="/pendientes-por-tecnico">Pendientes por técnico</LinkItem>
          )}

          {techLike && !jefeVeedor && (
            <LinkItem to="/tecnico" variant="amber">Mis pendientes</LinkItem>
          )}
          {(jefe || jefeVeedor) && <LinkItem to="/pendientes-presupuesto">Pendientes de Presupuesto</LinkItem>}
          {(jefe || jefeVeedor) && <LinkItem to="/presupuestados">Presupuestados</LinkItem>}
          {techLike && (
            <LinkItem to="/aprobados" variant="green">Aprobados</LinkItem>
          )}
          {(techLike || admin || recep) && (
            <LinkItem to="/derivados" variant="blue">Derivados</LinkItem>
          )}
          {techLike && (
            <LinkItem to="/reparados" variant="gray">Reparados</LinkItem>
          )}

          <LinkItem to="/listos">Liberados</LinkItem>
          <LinkItem to="/alquiler/stock">Stock de Alquiler</LinkItem>
          <LinkItem to="/depositos">Depósitos</LinkItem>
        </div>

        <div className="pt-2">
          {showSistema && (
            <>
              <div className="text-xs uppercase text-gray-400 px-1 mb-1">Sistema</div>
              {jefe && <LinkItem to="/metricas">Métricas</LinkItem>}
              {showUsuarios && <LinkItem to="/usuarios">Usuarios</LinkItem>}
              <LinkItem to="/catalogo/clientes">Clientes</LinkItem>
              <LinkItem to="/catalogo/tipos-equipo">Tipos de equipo</LinkItem>
              <LinkItem to="/catalogo/accesorios">Accesorios</LinkItem>
              <LinkItem to="/catalogo/marcas">Marcas &amp; Modelos</LinkItem>
              <LinkItem to="/catalogo/proveedores">Proveedores externos</LinkItem>
              <LinkItem to="/garantias">Garantías</LinkItem>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
