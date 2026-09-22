/**
 * CatalogIQ — Auth Provider
 *
 * Bootstraps auth state and exposes login/logout actions to the app.
 */

import { useEffect, useState } from "react";
import { fetchCurrentUser, login as apiLogin, logout as apiLogout } from "../../api/auth";
import { clearToken, getToken } from "../../lib/auth-storage";
import { AuthContext } from "../../lib/auth-context";

// This is a component to provide auth state and login/logout actions
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function bootstrapAuth() {
      if (!getToken()) {
        setLoading(false);
        return;
      }

      try {
        const currentUser = await fetchCurrentUser();
        setUser(currentUser);
      } catch {
        clearToken();
        setUser(null);
      } finally {
        setLoading(false);
      }
    }

    bootstrapAuth();
  }, []);

  async function login(email, password) {
    await apiLogin(email, password);
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
  }

  function logout() {
    apiLogout();
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        isAuthenticated: Boolean(user),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
