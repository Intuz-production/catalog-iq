/**
 * CatalogIQ — Layout Component
 *
 * Application shell with sidebar navigation and main content area.
 */

import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  Package,
  Upload,
  Sparkles,
  BarChart3,
} from "lucide-react";

const navItems = [
  { path: "/", icon: LayoutDashboard, label: "Dashboard" },
  { path: "/products", icon: Package, label: "Products" },
  { path: "/ingestion", icon: Upload, label: "Data Ingestion" },
  { path: "/content", icon: Sparkles, label: "Content Generator" },
  { path: "/competitors", icon: BarChart3, label: "Competitors" },
];

export default function Layout() {
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
        <div style={{ padding: "16px 24px", borderTop: "1px solid var(--border-color)" }}>
          <p style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
            CatalogIQ v1.0.0
          </p>
        </div>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
