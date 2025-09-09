import { createContext, useContext, useEffect, useState } from "react";
import { postLogin, setToken } from "../lib/api";

// Normalizador local para no generar dependencia circular
function sanitizeUser(u) {
  if (!u) return null;
  const rol = String(u.rol ?? "").trim().toLowerCase();
  return { ...u, rol };
}

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("user");
    return raw ? sanitizeUser(JSON.parse(raw)) : null;
  });

  // Al montar, si hay token guardado lo cargamos en api.js
  useEffect(() => {
    const t = localStorage.getItem("token");
    if (t) setToken(t);
  }, []);

  async function login(email, password) {
    const data = await postLogin(email, password); // { token, user }
    const cleanUser = sanitizeUser(data.user);
    setToken(data.token);
    localStorage.setItem("token", data.token);
    localStorage.setItem("user", JSON.stringify(cleanUser));
    setUser(cleanUser);
  }

  function logout() {
    setToken(null);
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
  }

  return (
    <AuthCtx.Provider value={{ user, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export default AuthProvider;
