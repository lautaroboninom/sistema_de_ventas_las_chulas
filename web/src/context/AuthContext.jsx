import { createContext, useContext, useEffect, useState } from "react";
import { getAuthSession, postAuthLogout, postLogin, setToken } from "../lib/api";

// Normalizador local para no generar dependencia circular
function sanitizeUser(u) {
  if (!u) return null;
  const rol = String(u.rol ?? "").trim().toLowerCase();
  return { ...u, rol };
}

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getAuthSession();
        if (active && data?.user) {
          setUser(sanitizeUser(data.user));
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
    const data = await postLogin(email, password); // { token, user }
    const cleanUser = sanitizeUser(data.user);
    setToken(data.token);
    setUser(cleanUser);
    setLoading(false);
  }

  async function logout() {
    setToken(null);
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
    <AuthCtx.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthCtx.Provider>
  );
}

export default AuthProvider;
