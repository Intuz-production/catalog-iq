/**
 * CatalogIQ — Layout Component
 *
 * Application shell with sidebar navigation and main content area.
 */

import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  Package,
  BarChart3,
  LogOut,
} from "lucide-react";
import { useAuth } from "../lib/use-auth";
import { useToast } from "../lib/use-toast";
import { useConfirm } from "../lib/use-confirm";

const navItems = [
  { path: "/", icon: LayoutDashboard, label: "Dashboard" },
  { path: "/products", icon: Package, label: "Products" },
  // { path: "/competitors", icon: BarChart3, label: "Competitors" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { showToast } = useToast();
  const { confirm } = useConfirm();

  async function handleLogout() {
    const confirmed = await confirm({
      title: "Sign Out",
      message: "Are you sure you want to sign out of CatalogIQ?",
      confirmLabel: "Sign Out",
      cancelLabel: "Cancel",
      variant: "danger",
    });
    if (!confirmed) return;

    logout();
    showToast("Signed out successfully", "info");
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1>CatalogIQ</h1>
          <p>AI Catalog Intelligence</p>
        </div>
        <nav className="sidebar-nav">
          {navItems.map(({ path, icon: Icon, label }) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/"}
              className={({ isActive }) =>
                `nav-link ${isActive ? "active" : ""}`
              }
            >
              <Icon />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <p className="sidebar-user">{user?.full_name || user?.email}</p>
          <button className="btn btn-ghost btn-sm sidebar-logout" onClick={handleLogout} type="button">
            <LogOut size={16} />
            Sign Out
          </button>
          <p className="sidebar-version">CatalogIQ v1.0.0</p>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
