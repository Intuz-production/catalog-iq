/**
 * CatalogIQ — Dashboard Page
 *
 * Overview with key metrics and recent issues.
 */

import { useState, useEffect } from "react";
import {
  Package, AlertTriangle, FileText, Clock, CheckCircle,
} from "lucide-react";
import { fetchDashboardStats, fetchAllIssues } from "../api/client";
import DataIssueCard from "../components/DataIssueCard";
import { useToast } from "../lib/use-toast";

export default function Dashboard() {
  const { showToast } = useToast();
  const [stats, setStats] = useState(null);
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  async function loadDashboard() {
    try {
      setLoading(true);
      const [statsData, issuesData] = await Promise.all([
        fetchDashboardStats(),
        fetchAllIssues({ resolved: false, limit: 5 }),
      ]);
      setStats(statsData);
      setIssues(issuesData.items);
    } catch (err) {
      showToast(err.message || "Failed to load dashboard", "error");
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
          <div className="stat-icon"><CheckCircle size={38} /></div>
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
          <div className="stat-icon"><Clock size={38} /></div>
          <div className="stat-label">Last Ingestion</div>
          <div className="stat-value" style={{ fontSize: "0.9rem", lineHeight: 1.3 }}>
            {stats?.last_ingestion
              ? new Date(stats.last_ingestion).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
              : "—"}
          </div>
        </div>
      </div>

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
    </div>
  );
}
