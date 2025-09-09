// ProtectedRoute.jsx
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children, roles }) {
  const { user } = useAuth();
  const loc = useLocation();
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  // Sin sesión real (user o token) -> login
  if (!user || !token) {
    return <Navigate to="/login" state={{ from: loc }} replace />;
  }

  // Sin permiso -> a inicio (o a una página 403 si preferís)
  if (roles && roles.length && !roles.includes(user.rol)) {
    return <Navigate to="/" replace />;
  }
  return children;
}
