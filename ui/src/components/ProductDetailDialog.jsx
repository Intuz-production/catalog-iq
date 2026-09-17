/**
 * CatalogIQ — Product Detail Dialog
 *
 * Centered modal for viewing product metadata, generated content, and data issues.
 */

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X, Sparkles, AlertTriangle, Pencil } from "lucide-react";
import ContentPreview from "./ContentPreview";
import DataIssueCard from "./DataIssueCard";
import ProductEditForm from "./ProductEditForm";

const STATUS_CLASSES = {
  active: "badge-active",
  draft: "badge-draft",
  flagged: "badge-flagged",
  archived: "badge-archived",
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
 * @property {boolean} [saving]
 */

// This is a component to show product details in a centered dialog
export default function ProductDetailDialog({
  product,
  issues = [],
  issuesLoading = false,
  generating = false,
  saving = false,
  onClose,
  onGenerateContent,
  onSave,
}) {
  const [isEditing, setIsEditing] = useState(false);
  const openIssues = issues.filter((issue) => !issue.resolved);
  const isBusy = generating || saving;

  useEffect(() => {
    setIsEditing(false);
  }, [product?.id]);

  useEffect(() => {
    if (!product) return undefined;

    function handleKeyDown(event) {
      if (event.key === "Escape" && !isBusy && !isEditing) {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [product, isBusy, isEditing, onClose]);

  if (!product) return null;

  async function handleSave(payload) {
    if (!onSave) return;
    await onSave(product.id, payload);
    setIsEditing(false);
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
              <span className={`badge ${STATUS_CLASSES[product.status] || "badge-draft"}`}>
                {product.status}
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

        <div className="product-detail-body">
          {isEditing ? (
            <ProductEditForm
              key={product.id}
              product={product}
              saving={saving}
              onSubmit={handleSave}
              onCancel={() => setIsEditing(false)}
            />
          ) : (
            <>
          <div className="product-detail-meta-grid">
            <div className="product-detail-meta-item">
              <span className="product-detail-meta-label">Price</span>
              <span className="product-detail-meta-value">
                {product.price
                  ? `${product.currency} ${product.price.toFixed(2)}`
                  : "N/A"}
              </span>
            </div>
            <div className="product-detail-meta-item">
              <span className="product-detail-meta-label">Category</span>
              <span className="product-detail-meta-value">{product.category || "N/A"}</span>
            </div>
            <div className="product-detail-meta-item">
              <span className="product-detail-meta-label">Brand</span>
              <span className="product-detail-meta-value">{product.brand || "N/A"}</span>
            </div>
            <div className="product-detail-meta-item">
              <span className="product-detail-meta-label">Issues</span>
              <span className="product-detail-meta-value">
                {(product.issue_count ?? openIssues.length) > 0 ? (
                  <span className="badge badge-high">
                    <AlertTriangle size={12} />
                    {product.issue_count ?? openIssues.length}
                  </span>
                ) : (
                  "None"
                )}
              </span>
            </div>
          </div>

          {attributeEntries.length > 0 && (
            <section className="product-detail-section">
              <h3 className="product-detail-section-title">Attributes</h3>
              <div className="product-detail-tags">
                {attributeEntries.map(([key, val]) => (
                  <span key={key} className="product-detail-tag">
                    <strong>{key}:</strong> {String(val)}
                  </span>
                ))}
              </div>
            </section>
          )}

          <section className="product-detail-section">
            <ContentPreview product={product} />
          </section>

          <section className="product-detail-section">
            <div className="product-detail-section-header">
              <h3 className="product-detail-section-title">
                Data Issues
                {!issuesLoading && openIssues.length > 0 && (
                  <span className="product-detail-count">({openIssues.length})</span>
                )}
              </h3>
            </div>

            {issuesLoading ? (
              <div className="product-detail-loading">
                <div className="spinner" />
                Loading issues...
              </div>
            ) : openIssues.length > 0 ? (
              <div className="product-detail-issues">
                {openIssues.map((issue) => (
                  <DataIssueCard key={issue.id} issue={issue} />
                ))}
              </div>
            ) : (
              <div className="product-detail-empty-issues">
                No open data quality issues found for this product.
              </div>
            )}
          </section>
            </>
          )}
        </div>

        <div className="product-detail-footer">
          {isEditing ? null : (
            <>
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
            onClick={() => setIsEditing(true)}
            disabled={isBusy}
          >
            <Pencil size={16} />
            Edit
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onGenerateContent(product.id)}
            disabled={isBusy}
          >
            {generating ? (
              <>
                <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2, margin: 0 }} />
                Generating...
              </>
            ) : (
              <>
                <Sparkles size={16} />
                {product.generated_description ? "Regenerate SEO Content" : "Generate SEO Content"}
              </>
            )}
          </button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
