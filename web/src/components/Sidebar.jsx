import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  canActAsTech,
  isJefe,
  isAdmin,
  isRecepcion,
} from "../lib/authz";

const LinkItem = ({ to, children }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      `block px-3 py-2 rounded hover:bg-gray-100 ${
        isActive ? "bg-gray-100 font-semibold" : ""
      }`
    }
  >
    {children}
  </NavLink>
);

export default function Sidebar() {
  const { user } = useAuth();
  if (!user) return null;

  // Usar SIEMPRE helpers centralizados (normalizan el rol)
  const jefe = isJefe(user);
  const admin = isAdmin(user);
  const recep = isRecepcion(user);
  const techLike = canActAsTech(user); // tecnico | jefe | jefe_veedor

  return (
    <aside className="w-64 shrink-0 border-r bg-white hidden md:block">
      <div className="p-3 text-sm text-gray-500">Menú</div>
      <div className="px-3 pb-3 space-y-2">
        <div>
          <div className="text-xs uppercase text-gray-400 px-1 mb-1">Equipos</div>

          {jefe && (
            <>
              <LinkItem to="/pendientes">Pendientes General</LinkItem>
              <LinkItem to="/pendientes-por-tecnico">Pendientes por técnico</LinkItem>
            </>
          )}

          {techLike && <LinkItem to="/tecnico">Mis pendientes</LinkItem>}
          {techLike && <LinkItem to="/pendientes-presupuesto">Pendientes de Presupuesto</LinkItem>}
          {techLike && <LinkItem to="/presupuestados">Presupuestados</LinkItem>}
          {techLike && <LinkItem to="/aprobados">Aprobados p/Reparar</LinkItem>}
          {techLike && <LinkItem to="/reparados">Reparados</LinkItem>}
          {(techLike || admin || recep) && <LinkItem to="/derivados">Derivados</LinkItem>}

          <LinkItem to="/listos">Liberados</LinkItem>
          <LinkItem to="/alquiler/stock">Stock de Alquiler</LinkItem>
          <LinkItem to="/depositos">Depósitos</LinkItem>
        </div>

        <div className="pt-2">
          {(jefe || admin) && (
            <>
              <div className="text-xs uppercase text-gray-400 px-1 mb-1">Sistema</div>
              {jefe && <LinkItem to="/usuarios">Usuarios</LinkItem>}
              <>
                <LinkItem to="/catalogo/clientes">Clientes</LinkItem>
                <LinkItem to="/catalogo/marcas">Marcas &amp; Modelos</LinkItem>
                <LinkItem to="/catalogo/proveedores">Proveedores externos</LinkItem>
              </>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
