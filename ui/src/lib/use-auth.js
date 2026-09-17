/**
 * CatalogIQ — useAuth Hook
 *
 * Reads auth state and actions from AuthProvider.
 */

import { useContext } from "react";
import { AuthContext } from "./auth-context";

// This is a hook to access auth state and login/logout actions
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
