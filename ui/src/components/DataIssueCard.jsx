/**
 * CatalogIQ — Data Issue Card Component
 *
 * Displays flagged data quality issues with severity and resolution controls.
 */

import { useState } from "react";
import { AlertTriangle, ArrowRight, CheckCircle, Info, Pencil, X, XCircle } from "lucide-react";
import { formatFieldLabel } from "../lib/issue-fields";

const SEVERITY_CONFIG = {
  critical: { icon: XCircle, className: "badge-critical", color: "var(--accent-red)" },
  high: { icon: AlertTriangle, className: "badge-high", color: "var(--accent-red-light)" },
  medium: { icon: AlertTriangle, className: "badge-medium", color: "var(--accent-orange)" },
  low: { icon: Info, className: "badge-low", color: "var(--accent-blue-light)" },
};

/**
 * Say what is wrong in one plain sentence instead of naming the detector.
 *
 * @param {string} issueType Stored issue type.
 * @param {string} fieldName Readable field name, such as "Color".
 * @param {boolean} hasSuggestion Whether the issue carries a suggested value.
 * @returns {string} Headline shown at the top of the card.
 */
function buildHeadline(issueType, fieldName, hasSuggestion) {
  switch (issueType) {
    case "missing_description":
      return "Description is missing";
    case "thin_content":
      return "Description is too short";
    case "attribute_contradiction":
      return `${fieldName} does not match the title or description`;
    case "attribute_not_in_copy":
      return `${fieldName} is missing from the title and description`;
    case "missing_attributes":
      return "Key attributes are missing";
    case "duplicate_title":
      return "Title is already used by another product";
    case "price_anomaly":
      return "Price needs a check";
    default:
      return hasSuggestion
        ? `A better ${fieldName.toLowerCase()} is suggested`
        : `${fieldName} needs a review`;
  }
}

/**
 * Seed the editor with the proposed (new) value, never the old/diagnostic text.
 *
 * @param {object} issue
 * @returns {string}
 */
function getEditableSeed(issue) {
  if (issue.suggested_value) return issue.suggested_value;
  if (issue.expected_value) return issue.expected_value;
  return "";
}

// This is a component to display and review a catalog quality issue
export default function DataIssueCard({ issue, onResolve, onReview }) {
  const severity = SEVERITY_CONFIG[issue.severity] || SEVERITY_CONFIG.medium;
  const SeverityIcon = severity.icon;
  // Legacy soft finding: attribute exists but is absent from copy. Ignore only —
  // Accept/Edit would wrongly rewrite the attribute instead of title/description.
  const isIgnoreOnly = issue.issue_type === "attribute_not_in_copy";
  const isEditableField =
    !isIgnoreOnly &&
    (["title", "description", "category", "brand", "price"].includes(issue.field_name) ||
      issue.field_name?.startsWith("attributes.") ||
      ["color", "size", "material", "weight", "upc"].includes(issue.field_name));
  const [isEditing, setIsEditing] = useState(false);
  const [editedValue, setEditedValue] = useState(() => getEditableSeed(issue));
  const [isSaving, setIsSaving] = useState(false);
  // Headlines read better with the bare field name ("Color", not "Attribute: Color").
  const fieldLabel = formatFieldLabel(issue.field_name).replace(/^Attribute:\s*/, "");
  const hasSuggestion = Boolean(issue.suggested_value);
  const headline = buildHeadline(issue.issue_type, fieldLabel, hasSuggestion);
  // Long copy fields read better stacked than side-by-side.
  const isLongTextField =
    issue.field_name === "description" || issue.field_name === "title";
  // "Now" is the current product value; fall back to expected when actual is a diagnostic note.
  const currentValue = hasSuggestion
    ? (issue.actual_value || issue.expected_value)
    : (issue.expected_value || issue.actual_value);
  const metaParts = [
    issue.suggestion_source ? (issue.suggestion_source === "ai" ? "Found by AI" : "Found by rule") : null,
    `Product ${issue.product_id}`,
    new Date(issue.created_at).toLocaleDateString(),
  ].filter(Boolean);

  async function handleReview(action, value) {
    try {
      setIsSaving(true);
      await onReview(issue, action, value);
      setIsEditing(false);
    } catch {
      // The parent reports the API error and keeps the editor open.
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="alert-item issue-card" style={{ "--issue-accent": severity.color }}>
      <div
        className="alert-icon"
        style={{ background: `${severity.color}20`, color: severity.color }}
      >
        <SeverityIcon size={18} />
      </div>
      <div className="alert-content" style={{ flex: 1 }}>
        <div className="issue-card-header">
          <span className="issue-card-title">{headline}</span>
          <span className={`badge ${severity.className}`}>
            {issue.severity}
          </span>
        </div>
        <p className="issue-card-description">{issue.description}</p>
        {issue.field_name ? (
          <span className="issue-field-chip">{fieldLabel}</span>
        ) : null}
        {isEditing ? (
          <div className="issue-editor">
            <span>New {fieldLabel.toLowerCase()}</span>
            <textarea
              aria-label={`Edit value for ${issue.field_name || "issue"}`}
              onChange={(event) => setEditedValue(event.target.value)}
              rows={isLongTextField ? 6 : 3}
              value={editedValue}
            />
          </div>
        ) : null}
        {!isEditing && hasSuggestion && !isIgnoreOnly ? (
          <div
            className={
              isLongTextField ? "issue-change issue-change-stacked" : "issue-change"
            }
          >
            <div className="issue-change-side">
              <span>Now</span>
              <p>{currentValue || "Empty"}</p>
            </div>
            <ArrowRight className="issue-change-arrow" size={16} aria-hidden="true" />
            <div className="issue-change-side issue-change-next">
              <span>Change to</span>
              <p>{issue.suggested_value}</p>
            </div>
          </div>
        ) : null}
        <div className="issue-card-footer">
          <div className="alert-meta">{metaParts.join(" · ")}</div>
          {onReview && !issue.resolved ? (
            <div className="issue-review-actions">
              {isEditing ? (
                <>
                  <button
                    className="btn btn-success btn-sm"
                    disabled={isSaving}
                    onClick={() => handleReview("edit", editedValue)}
                    type="button"
                  >
                    <CheckCircle size={14} />
                    Save
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={isSaving}
                    onClick={() => setIsEditing(false)}
                    type="button"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <>
                  {!isIgnoreOnly && hasSuggestion ? (
                    <button
                      className="btn btn-success btn-sm"
                      disabled={isSaving}
                      onClick={() => handleReview("accept")}
                      type="button"
                    >
                      <CheckCircle size={14} />
                      Apply this fix
                    </button>
                  ) : null}
                  {isEditableField ? (
                    <button
                      className="btn btn-ghost btn-sm"
                      disabled={isSaving}
                      onClick={() => {
                        setEditedValue(getEditableSeed(issue));
                        setIsEditing(true);
                      }}
                      type="button"
                    >
                      <Pencil size={14} />
                      {hasSuggestion ? "Edit fix" : "Write my own"}
                    </button>
                  ) : null}
                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={isSaving}
                    onClick={() => handleReview("reject")}
                    title="Close this issue without changing the product"
                    type="button"
                  >
                    <X size={14} />
                    Ignore
                  </button>
                </>
              )}
            </div>
          ) : null}
        </div>
      </div>
      {onResolve && !issue.resolved ? (
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => onResolve(issue)}
          title="Mark as resolved"
          type="button"
        >
          <CheckCircle size={14} />
          Resolve
        </button>
      ) : null}
    </div>
  );
}
