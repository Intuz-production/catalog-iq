/**
 * CatalogIQ — Quality Issues Dialog
 *
 * Modal reviewer for open quality issues on one uploaded file. Shows a single
 * loader until AI analysis finishes and the issue list is ready.
 */

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, Check, X } from "lucide-react";
import DataIssueCard from "./DataIssueCard";
import { groupIssuesByProduct } from "../lib/issue-fields";

/**
 * @param {object} issue
 * @returns {boolean}
 */
function isLowPolishIssue(issue) {
  return issue?.issue_type === "ai_inferred" && issue?.severity === "low";
}

/**
 * @typedef {Object} QualityIssuesDialogProps
 * @property {boolean} open
 * @property {() => void} onClose
 * @property {object[]} issues
 * @property {object[]} products
 * @property {number} issueTotal
 * @property {boolean} loading
 * @property {boolean} isAnalyzing
 * @property {number|null} busyProductId
 * @property {(issue: object, action: string, editedValue?: string) => Promise<void>} onReview
 * @property {(group: object) => Promise<void>} onAcceptAll
 * @property {(group: object) => Promise<void>} onIgnoreAll
 */

// This is a component to review file quality issues in a centered dialog
export default function QualityIssuesDialog({
  open,
  onClose,
  issues,
  products,
  issueTotal,
  loading,
  isAnalyzing,
  busyProductId,
  onReview,
  onAcceptAll,
  onIgnoreAll,
}) {
  const isWaiting = loading;
  const isBusy = busyProductId !== null;
  const [showPolish, setShowPolish] = useState(false);

  useEffect(() => {
    if (!open) {
      setShowPolish(false);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;

    function handleKeyDown(event) {
      if (event.key === "Escape" && !isBusy) {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, isBusy, onClose]);

  const polishCount = useMemo(
    () => issues.filter(isLowPolishIssue).length,
    [issues]
  );

  const visibleIssues = useMemo(() => {
    if (showPolish) return issues;
    return issues.filter((issue) => !isLowPolishIssue(issue));
  }, [issues, showPolish]);

  const visibleTotal = showPolish
    ? issueTotal
    : Math.max(0, issueTotal - polishCount);

  if (!open) return null;

  const groups = groupIssuesByProduct(visibleIssues, products);

  return createPortal(
    <div
      className="product-detail-overlay"
      role="presentation"
      onClick={isBusy ? undefined : onClose}
    >
      <div
        className="product-detail-dialog quality-issues-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="quality-issues-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="product-detail-header">
          <div className="product-detail-header-main">
            <div className="product-detail-title-row">
              <h2 id="quality-issues-title">Quality Issues</h2>
              {!isWaiting && (
                <span className={`badge ${visibleTotal > 0 ? "badge-high" : "badge-active"}`}>
                  {visibleTotal} Open
                </span>
              )}
            </div>
            <p className="product-detail-subtitle">
              Grouped by product. Apply a fix, write your own value, or ignore
              to leave the product unchanged.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm product-detail-close"
            aria-label="Close quality issues"
            disabled={isBusy}
            onClick={onClose}
          >
            <X size={16} />
          </button>
        </div>

        <div className="quality-issues-dialog-body">
          {isWaiting ? (
            <div className="quality-issues-dialog-loading">
              <div className="spinner" />
              <p>Loading quality issues...</p>
            </div>
          ) : (
            <>
              {isAnalyzing ? (
                <div className="quality-issues-analyzing-banner">
                  <span
                    className="spinner"
                    aria-hidden="true"
                    style={{ width: 14, height: 14, borderWidth: 2, flexShrink: 0 }}
                  />
                  AI analysis in progress — more issues may appear as products are processed.
                </div>
              ) : null}
              {polishCount > 0 ? (
                <label className="quality-issues-polish-toggle">
                  <input
                    type="checkbox"
                    checked={showPolish}
                    onChange={(event) => setShowPolish(event.target.checked)}
                    disabled={isBusy}
                  />
                  Show polish suggestions ({polishCount})
                </label>
              ) : null}
              {visibleTotal > 0 ? (
                <>
                  {visibleTotal > visibleIssues.length ? (
                    <p className="rewrite-review-limit">
                      Showing the first {visibleIssues.length} open issues.
                    </p>
                  ) : null}
                  <div className="ingestion-issue-list">
                    {groups.map((group) => {
                      const hasApplicableFixes = group.issues.some(
                        (issue) => issue.field_name && issue.suggested_value
                      );
                      return (
                        <section className="rewrite-product" key={group.productId}>
                          <div className="rewrite-product-header">
                            <div>
                              <strong>{group.sku}</strong>
                              {group.title ? <small>{group.title}</small> : null}
                            </div>
                            <div className="rewrite-product-actions">
                              <span className="badge badge-medium">
                                {group.issues.length}{" "}
                                {group.issues.length === 1 ? "Issue" : "Issues"}
                              </span>
                              <button
                                className="btn btn-success btn-sm"
                                disabled={isBusy || !hasApplicableFixes}
                                onClick={() => onAcceptAll(group)}
                                type="button"
                              >
                                <Check size={14} />
                                Accept all
                              </button>
                              <button
                                className="btn btn-ghost btn-sm"
                                disabled={isBusy}
                                onClick={() => onIgnoreAll(group)}
                                type="button"
                              >
                                <X size={14} />
                                Ignore all
                              </button>
                            </div>
                          </div>
                          {group.issues.map((issue) => (
                            <DataIssueCard
                              key={issue.id}
                              issue={issue}
                              onReview={onReview}
                            />
                          ))}
                        </section>
                      );
                    })}
                  </div>
                </>
              ) : (
                <div className="empty-state rewrite-review-empty">
                  <AlertTriangle size={40} />
                  <h3>{isAnalyzing ? "Analyzing..." : "No Open Quality Issues"}</h3>
                  <p>
                    {isAnalyzing
                      ? "Issues will appear here as AI analysis completes."
                      : polishCount > 0 && !showPolish
                      ? "Only low-severity polish suggestions remain. Turn on Show polish suggestions to review them."
                      : "Rule and AI flags for this file are clear, or already reviewed."}
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
