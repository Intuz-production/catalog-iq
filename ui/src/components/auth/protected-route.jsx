/**
 * CatalogIQ — Protected Route
 *
 * Blocks unauthenticated access to dashboard routes.
 */

import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../../lib/use-auth";

// This is a component to guard routes behind authentication
export default function ProtectedRoute() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
