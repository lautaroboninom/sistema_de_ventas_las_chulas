// ProtectedRoute.jsx
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { canAll, canAny } from "../lib/permissions";

export default function ProtectedRoute({ children, roles, permissions, requireAll = false }) {
  const { user, loading } = useAuth();
  const loc = useLocation();

  if (loading) return null;
  if (!user) {
    return <Navigate to="/login" state={{ from: loc }} replace />;
  }

  if (roles && roles.length && !roles.includes(user.rol)) {
    return <Navigate to="/403" replace />;
  }
  if (permissions) {
    const list = Array.isArray(permissions) ? permissions : [permissions];
    const ok = requireAll ? canAll(user, list) : canAny(user, list);
    if (!ok) return <Navigate to="/403" replace />;
  }
  return children;
}
