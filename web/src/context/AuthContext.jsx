import { createContext, useContext, useEffect, useState } from "react";
import { getAuthCsrf, getAuthSession, postAuthLogout, postLogin } from "../lib/api";
import { registerFeatures } from "@/lib/features";
import { normalizePermissionsMap } from "@/lib/permissions";

// Normalizador local para no generar dependencia circular
function sanitizeUser(u) {
  if (!u) return null;
  const rol = String(u.rol ?? "").trim().toLowerCase();
  return {
    ...u,
    rol,
    permissions: normalizePermissionsMap(u.permissions),
  };
}

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refreshSession() {
    const data = await getAuthSession();
    const u = data?.user ?? data;
    if (u) {
      if (data?.features) registerFeatures(data.features);
      setUser(sanitizeUser(u));
      return sanitizeUser(u);
    }
    setUser(null);
    return null;
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        await getAuthCsrf();
        const data = await getAuthSession();
        if (!active) return;
        // La API de sesión devuelve los campos del usuario en el nivel raíz.
        // Mantener compatibilidad si alguna vez vuelve como { user, features }.
        const u = data?.user ?? data;
        if (u) {
          if (data?.features) registerFeatures(data.features);
          setUser(sanitizeUser(u));
        }
      } catch (err) {
        if (import.meta.env.DEV) {
          console.debug("Auth session bootstrap failed", err);
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function login(email, password) {
    const data = await postLogin(email, password);
    const cleanUser = sanitizeUser(data?.user);
    if (data?.features) registerFeatures(data.features);
    if (cleanUser) {
      setUser(cleanUser);
    } else {
      await refreshSession();
    }
    setLoading(false);
  }

  async function logout() {
    try {
      await postAuthLogout();
    } catch (err) {
      if (import.meta.env.DEV) {
        console.debug("Auth logout request failed", err);
      }
    } finally {
      setUser(null);
      setLoading(false);
    }
  }

  return (
    <AuthCtx.Provider value={{ user, login, logout, loading, refreshSession }}>
      {children}
    </AuthCtx.Provider>
  );
}

export default AuthProvider;

