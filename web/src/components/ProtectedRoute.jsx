// ProtectedRoute.jsx
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children, roles }) {
  const { user, loading } = useAuth();
  const loc = useLocation();

  if (loading) return null;
  if (!user) {
    return <Navigate to="/login" state={{ from: loc }} replace />;
  }

  if (roles && roles.length && !roles.includes(user.rol)) {
    return <Navigate to="/403" replace />;
  }
  return children;
}
