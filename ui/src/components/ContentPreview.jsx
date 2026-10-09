/**
 * CatalogIQ — Content Preview Component
 *
 * Displays generated product descriptions with SEO metadata and quality hints.
 */

import { Copy, Check, Tag, Search, AlertTriangle } from "lucide-react";
import { useState } from "react";

/**
 * @typedef {Object} ContentPreviewProps
 * @property {Object} product
 * @property {string[]} [warnings]
 * @property {number} [wordCount]
 */

// This is a component to preview generated SEO product content
export default function ContentPreview({ product, warnings = [], wordCount = null }) {
  const [copied, setCopied] = useState(false);

  const description = product.generated_description || product.description;
  const resolvedWordCount = wordCount ?? (description ? description.split(/\s+/).filter(Boolean).length : 0);
  const seoTitleLength = product.seo_title ? product.seo_title.length : 0;

  if (!description) {
    return (
      <div className="content-preview content-preview-empty">
        No description available yet. SEO content is generated automatically during file analysis.
      </div>
    );
  }

  function handleCopy() {
    navigator.clipboard.writeText(description);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="content-preview-panel">
      <div className="content-preview-header">
        <div>
          <h4 className="content-preview-title">
            {product.generated_description ? "Generated Description" : "Original Description"}
          </h4>
          <span className="content-preview-meta">{resolvedWordCount} words</span>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={handleCopy}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      <div className="content-preview">{description}</div>

      {(product.seo_title || product.seo_keywords) && (
        <div className="content-preview-seo">
          {product.seo_title && (
            <div className="content-preview-seo-row">
              <Search size={14} className="content-preview-seo-icon" />
              <span className="content-preview-seo-label">SEO Title</span>
              <span className="content-preview-seo-value">{product.seo_title}</span>
              <span className={`badge ${seoTitleLength > 60 ? "badge-medium" : "badge-low"}`}>
                {seoTitleLength}/60
              </span>
            </div>
          )}
          {product.seo_keywords && (
            <div className="content-preview-seo-row content-preview-seo-row-keywords">
              <Tag size={14} className="content-preview-seo-icon" />
              <span className="content-preview-seo-label">Keywords</span>
              <div className="content-preview-keyword-list">
                {product.seo_keywords.split(",").map((kw, index) => (
                  <span key={index} className="content-preview-keyword">
                    {kw.trim()}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {warnings.length > 0 && (
        <div className="content-preview-warnings">
          {warnings.map((warning) => (
            <div key={warning} className="content-preview-warning">
              <AlertTriangle size={14} />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
