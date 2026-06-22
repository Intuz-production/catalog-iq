/**
 * CatalogIQ — Dashboard Page
 *
 * Overview with key metrics, recent issues, and recent alerts.
 */

import { useState, useEffect } from "react";
import {
  Package, AlertTriangle, Sparkles, BarChart3,
  FileText, Bell, TrendingDown,
} from "lucide-react";
import { fetchDashboardStats, fetchAllIssues, fetchAlerts } from "../api/client";
import DataIssueCard from "../components/DataIssueCard";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [issues, setIssues] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  async function loadDashboard() {
    try {
      setLoading(true);
      const [statsData, issuesData, alertsData] = await Promise.all([
        fetchDashboardStats(),
        fetchAllIssues(false, 5),
        fetchAlerts({ acknowledged: false, limit: 5 }),
      ]);
      setStats(statsData);
      setIssues(issuesData);
      setAlerts(alertsData);
    } catch (err) {
      console.error("Failed to load dashboard:", err);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading dashboard...
      </div>
    );
  }

  return (
    <div className="animate-in">
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Overview of your catalog intelligence platform</p>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card blue">
          <div className="stat-icon"><Package size={38} /></div>
          <div className="stat-label">Total Products</div>
          <div className="stat-value">{stats?.total_products || 0}</div>
        </div>
        <div className="stat-card green">
          <div className="stat-icon"><Package size={38} /></div>
          <div className="stat-label">Active Products</div>
          <div className="stat-value">{stats?.active_products || 0}</div>
        </div>
        <div className="stat-card orange">
          <div className="stat-icon"><AlertTriangle size={38} /></div>
          <div className="stat-label">Flagged Products</div>
          <div className="stat-value">{stats?.flagged_products || 0}</div>
        </div>
        <div className="stat-card red">
          <div className="stat-icon"><AlertTriangle size={38} /></div>
          <div className="stat-label">Open Issues</div>
          <div className="stat-value">{stats?.open_issues || 0}</div>
        </div>
        <div className="stat-card purple">
          <div className="stat-icon"><FileText size={38} /></div>
          <div className="stat-label">Need Content</div>
          <div className="stat-value">{stats?.products_without_description || 0}</div>
        </div>
        <div className="stat-card cyan">
          <div className="stat-icon"><Bell size={38} /></div>
          <div className="stat-label">Active Alerts</div>
          <div className="stat-value">{stats?.recent_alerts || 0}</div>
        </div>
      </div>

      {/* Two-column layout for issues and alerts */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {/* Recent Issues */}
        <div className="card">
          <div className="card-header">
            <h3>Recent Data Issues</h3>
            <span className="badge badge-high">{issues.length} open</span>
          </div>
          {issues.length > 0 ? (
            issues.map((issue) => (
              <DataIssueCard key={issue.id} issue={issue} />
            ))
          ) : (
            <div className="empty-state" style={{ padding: 32 }}>
              <p>No open data issues. Your catalog looks clean.</p>
            </div>
          )}
        </div>

        {/* Recent Alerts */}
        <div className="card">
          <div className="card-header">
            <h3>Competitor Alerts</h3>
            <span className="badge badge-medium">{alerts.length} new</span>
          </div>
          {alerts.length > 0 ? (
            alerts.map((alert) => (
              <div key={alert.id} className="alert-item">
                <div className={`alert-icon ${alert.alert_type}`}>
                  {alert.alert_type === "undercut" ? (
                    <TrendingDown size={18} />
                  ) : alert.alert_type === "out_of_stock" ? (
                    <Package size={18} />
                  ) : (
                    <BarChart3 size={18} />
                  )}
                </div>
                <div className="alert-content">
                  <p>{alert.message}</p>
                  <div className="alert-meta">
                    <span className={`badge badge-${alert.source}`}>
                      {alert.source}
                    </span>
                    {" "}{new Date(alert.created_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="empty-state" style={{ padding: 32 }}>
              <p>No active alerts. Run a competitor scrape to get started.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
