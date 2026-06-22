/**
 * CatalogIQ — Data Issue Card Component
 *
 * Displays flagged data quality issues with severity and resolution controls.
 */

import { AlertTriangle, CheckCircle, Info, XCircle } from "lucide-react";

const SEVERITY_CONFIG = {
  critical: { icon: XCircle, className: "badge-critical", color: "var(--accent-red)" },
  high: { icon: AlertTriangle, className: "badge-high", color: "var(--accent-red-light)" },
  medium: { icon: AlertTriangle, className: "badge-medium", color: "var(--accent-orange)" },
  low: { icon: Info, className: "badge-low", color: "var(--accent-blue-light)" },
};

const ISSUE_TYPE_LABELS = {
  missing_description: "Missing Description",
  thin_content: "Thin Content",
  attribute_contradiction: "Attribute Contradiction",
  missing_attributes: "Missing Attributes",
  duplicate_title: "Duplicate Title",
  price_anomaly: "Price Anomaly",
};

export default function DataIssueCard({ issue, onResolve }) {
  const severity = SEVERITY_CONFIG[issue.severity] || SEVERITY_CONFIG.medium;
  const SeverityIcon = severity.icon;

  return (
    <div className="alert-item">
      <div
        className="alert-icon"
        style={{ background: `${severity.color}20`, color: severity.color }}
      >
        <SeverityIcon size={18} />
      </div>
      <div className="alert-content" style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span className={`badge ${severity.className}`}>
            {issue.severity}
          </span>
          <span
            style={{
              fontSize: "0.78rem",
              color: "var(--text-muted)",
              fontWeight: 500,
            }}
          >
            {ISSUE_TYPE_LABELS[issue.issue_type] || issue.issue_type}
          </span>
        </div>
        <p>{issue.description}</p>
        {(issue.expected_value || issue.actual_value) && (
          <div
            style={{
              fontSize: "0.78rem",
              color: "var(--text-muted)",
              marginTop: 6,
              display: "flex",
              gap: 16,
            }}
          >
            {issue.expected_value && (
              <span>Expected: <strong style={{ color: "var(--accent-green-light)" }}>{issue.expected_value}</strong></span>
            )}
            {issue.actual_value && (
              <span>Actual: <strong style={{ color: "var(--accent-red-light)" }}>{issue.actual_value}</strong></span>
            )}
          </div>
        )}
        <div className="alert-meta">
          Product ID: {issue.product_id} | {new Date(issue.created_at).toLocaleDateString()}
        </div>
      </div>
      {onResolve && !issue.resolved && (
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => onResolve(issue.id)}
          title="Mark as resolved"
        >
          <CheckCircle size={14} />
          Resolve
        </button>
      )}
    </div>
  );
}
