/**
 * CatalogIQ — Product Detail Dialog
 *
 * Centered modal for viewing product metadata, generated content, and data issues.
 */

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X, AlertTriangle, Pencil, Sparkles } from "lucide-react";
import ContentPreview from "./ContentPreview";
import DataIssueCard from "./DataIssueCard";
import ProductEditForm from "./ProductEditForm";
import AiThoughtPanel from "./AiThoughtPanel";
import { countIssuesByField, groupIssuesByProduct } from "../lib/issue-fields";

// This is a local marker showing that open issues flag the field it sits on
function FieldFlag({ label }) {
  if (!label) return null;

  return (
    <span className="product-detail-flag" title={label} aria-label={label}>
      <AlertTriangle size={12} />
    </span>
  );
}

const STATUS_CLASSES = {
  active: "badge-active",
  draft: "badge-draft",
  flagged: "badge-flagged",
  archived: "badge-archived",
  processing: "badge-processing",
};

/**
 * @typedef {Object} ProductDetailDialogProps
 * @property {Object|null} product
 * @property {Array} [issues]
 * @property {boolean} [issuesLoading]
 * @property {boolean} [generating]
 * @property {() => void} onClose
 * @property {(productId: number) => void} onGenerateContent
 * @property {(productId: number, payload: Object) => Promise<void>} onSave
 * @property {(issue: Object, action: string, value?: string) => Promise<void>} [onReviewIssue]
 * @property {boolean} [saving]
 */

// This is a component to show product details in a centered dialog
export default function ProductDetailDialog({
  product,
  issues = [],
  issuesLoading = false,
  saving = false,
  onClose,
  onSave,
  onReviewIssue,
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const isAnalyzing =
    product?.ai_analysis_status === "pending" ||
    product?.ai_analysis_status === "analyzing";
  const openIssues = issues.filter((issue) => !issue.resolved);
  const reviewIssues = groupIssuesByProduct(
    openIssues,
    product ? [product] : [],
  )[0]?.issues || openIssues;
  const openIssueCount = product?.issue_count ?? openIssues.length;
  const flaggedFields = countIssuesByField(openIssues);
  const isBusy = saving;

  function flagLabel(fieldKey) {
    const count = flaggedFields.get(fieldKey) || 0;
    if (count === 0) return null;
    return `${count} open issue${count === 1 ? "" : "s"} flag this field`;
  }

  useEffect(() => {
    setIsEditing(false);
    setIsThinking(false);
  }, [product?.id]);

  useEffect(() => {
    if (!product) return undefined;

    function handleKeyDown(event) {
      if (event.key === "Escape" && !isBusy && !isEditing && !isThinking) {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [product, isBusy, isEditing, isThinking, onClose]);

  if (!product) return null;

  async function handleSave(payload) {
    if (!onSave) return;
    await onSave(product.id, payload);
    setIsEditing(false);
  }

  async function handleThoughtApply(payload) {
    if (!onSave) return;
    await onSave(product.id, payload);
    setIsThinking(false);
  }

  const attributeEntries = product.attributes
    ? Object.entries(product.attributes)
    : [];

  return createPortal(
    <div
      className="product-detail-overlay"
      role="presentation"
      onClick={isBusy || isEditing ? undefined : onClose}
    >
      <div
        className="product-detail-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="product-detail-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="product-detail-header">
          <div className="product-detail-header-main">
            <div className="product-detail-title-row">
              <h2 id="product-detail-title">{product.title}</h2>
              <FieldFlag label={flagLabel("title")} />
              <span
                className={`badge ${
                  isAnalyzing
                    ? "badge-processing"
                    : (STATUS_CLASSES[product.status] || "badge-draft")
                }`}
              >
                {isAnalyzing ? "Processing" : product.status}
              </span>
            </div>
            <p className="product-detail-subtitle">SKU: {product.sku}</p>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm product-detail-close"
            aria-label="Close product details"
            onClick={onClose}
            disabled={isBusy}
          >
            <X size={16} />
          </button>
        </div>

        {isEditing ? (
          <div className="product-detail-body product-detail-body-single">
            <ProductEditForm
              key={`${product.id}-${product.updated_at || ''}`}
              product={product}
              saving={saving}
              onSubmit={handleSave}
              onCancel={() => setIsEditing(false)}
            />
          </div>
        ) : isThinking ? (
          <div className="product-detail-body product-detail-body-single">
            <AiThoughtPanel
              product={product}
              saving={saving}
              onApply={handleThoughtApply}
              onCancel={() => setIsThinking(false)}
            />
          </div>
        ) : (
          <>
            <div className="product-detail-summary">
              <div className={`product-detail-meta-item${flagLabel("price") ? " is-flagged" : ""}`}>
                <span className="product-detail-meta-label">
                  Price
                  <FieldFlag label={flagLabel("price")} />
                </span>
                <span className="product-detail-meta-value">
                  {product.price
                    ? `${product.currency} ${product.price.toFixed(2)}`
                    : "N/A"}
                </span>
              </div>
              <div className={`product-detail-meta-item${flagLabel("category") ? " is-flagged" : ""}`}>
                <span className="product-detail-meta-label">
                  Category
                  <FieldFlag label={flagLabel("category")} />
                </span>
                <span className="product-detail-meta-value">{product.category || "N/A"}</span>
              </div>
              <div className={`product-detail-meta-item${flagLabel("brand") ? " is-flagged" : ""}`}>
                <span className="product-detail-meta-label">
                  Brand
                  <FieldFlag label={flagLabel("brand")} />
                </span>
                <span className="product-detail-meta-value">{product.brand || "N/A"}</span>
              </div>
              <div className="product-detail-meta-item">
                <span className="product-detail-meta-label">Open Issues</span>
                <span className="product-detail-meta-value">
                  {openIssueCount > 0 ? (
                    <span className="badge badge-high">
                      <AlertTriangle size={12} />
                      {openIssueCount}
                    </span>
                  ) : (
                    "None"
                  )}
                </span>
              </div>
              <div className="product-detail-meta-item">
                <span className="product-detail-meta-label">In Stock?</span>
                <span className="product-detail-meta-value">
                  {product.in_stock === false ? (
                    <span className="badge badge-high">Out of Stock</span>
                  ) : (
                    <span className="badge badge-active">In Stock</span>
                  )}
                </span>
              </div>
              <div className="product-detail-meta-item">
                <span className="product-detail-meta-label">Stock Qty</span>
                <span className="product-detail-meta-value">
                  {product.stock != null ? product.stock : <span style={{ color: "var(--text-muted)" }}>—</span>}
                </span>
              </div>
              {product.image_url ? (
                <div className="product-detail-meta-item product-detail-meta-full">
                  <span className="product-detail-meta-label">Image URL</span>
                  <a
                    className="product-detail-image-link"
                    href={product.image_url}
                    target="_blank"
                    rel="noreferrer"
                    title={product.image_url}
                  >
                    {product.image_url.length > 60
                      ? `${product.image_url.slice(0, 57)}...`
                      : product.image_url}
                  </a>
                </div>
              ) : null}
            </div>

            <div className="product-detail-body">
              <div className="product-detail-pane product-detail-pane-main">
                {attributeEntries.length > 0 && (
                  <section className="product-detail-section">
                    <h3 className="product-detail-section-title">
                      Attributes
                      <FieldFlag label={flagLabel("attributes")} />
                    </h3>
                    <div className="product-detail-tags">
                      {attributeEntries.map(([key, val]) => {
                        const attributeFlag = flagLabel(`attribute:${key.toLowerCase()}`);
                        return (
                          <span
                            key={key}
                            className={`product-detail-tag${attributeFlag ? " is-flagged" : ""}`}
                          >
                            <strong>{key}:</strong> {String(val)}
                            <FieldFlag label={attributeFlag} />
                          </span>
                        );
                      })}
                    </div>
                  </section>
                )}

                <section className="product-detail-section">
                  {flagLabel("description") && (
                    <p className="product-detail-flag-note">
                      <AlertTriangle size={14} />
                      {flagLabel("description")}
                    </p>
                  )}
                  <ContentPreview product={product} />
                </section>
              </div>

              <aside className="product-detail-pane product-detail-pane-side">
                <div className="product-detail-pane-header">
                  <h3 className="product-detail-section-title">Data Issues</h3>
                  {issuesLoading ? null : (
                    <span className={`badge ${openIssues.length > 0 ? "badge-high" : "badge-active"}`}>
                      {openIssues.length} Open
                    </span>
                  )}
                </div>

                <div className="product-detail-pane-content">
                  {issuesLoading ? (
                    <div className="product-detail-loading">
                      <div className="spinner" />
                      Loading issues...
                    </div>
                  ) : openIssues.length > 0 ? (
                    <div className="product-detail-issues">
                      {reviewIssues.map((issue) => (
                        <DataIssueCard
                          key={issue.id}
                          issue={issue}
                          onReview={onReviewIssue}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="product-detail-empty-issues">
                      No open data quality issues found for this product.
                    </div>
                  )}
                </div>
              </aside>
            </div>
          </>
        )}

        {isEditing || isThinking ? null : (
          <div className="product-detail-footer">
            <p className="product-detail-footer-hint">
              Accept, edit, or reject each suggested fix before exporting this file.
            </p>
            <div className="product-detail-footer-actions">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={onClose}
                disabled={isBusy}
              >
                Close
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setIsThinking(true)}
                disabled={isBusy}
                title="Give a thought — AI-powered field updates"
              >
                <Sparkles size={15} />
                Give a Thought
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setIsEditing(true)}
                disabled={isBusy}
              >
                <Pencil size={16} />
                Edit
              </button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
