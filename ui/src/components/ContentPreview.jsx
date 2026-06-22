/**
 * CatalogIQ — Content Preview Component
 *
 * Displays generated product descriptions with SEO metadata.
 */

import { Copy, Check, Tag, Search } from "lucide-react";
import { useState } from "react";

export default function ContentPreview({ product }) {
  const [copied, setCopied] = useState(false);

  const description = product.generated_description || product.description;

  if (!description) {
    return (
      <div className="content-preview" style={{ color: "var(--text-muted)", fontStyle: "italic" }}>
        No content generated yet. Click "Generate" to create an SEO description.
      </div>
    );
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(description);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <h4 style={{ fontSize: "0.9rem", fontWeight: 600 }}>
          {product.generated_description ? "Generated Description" : "Original Description"}
        </h4>
        <button className="btn btn-ghost btn-sm" onClick={handleCopy}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="content-preview">{description}</div>

      {(product.seo_title || product.seo_keywords) && (
        <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
          {product.seo_title && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Search size={14} style={{ color: "var(--accent-blue-light)", flexShrink: 0 }} />
              <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                SEO Title:
              </span>
              <span style={{ fontSize: "0.85rem", fontWeight: 500 }}>{product.seo_title}</span>
            </div>
          )}
          {product.seo_keywords && (
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
              <Tag size={14} style={{ color: "var(--accent-purple)", flexShrink: 0, marginTop: 2 }} />
              <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                Keywords:
              </span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {product.seo_keywords.split(",").map((kw, i) => (
                  <span
                    key={i}
                    style={{
                      padding: "2px 8px",
                      background: "rgba(139, 92, 246, 0.12)",
                      borderRadius: 50,
                      fontSize: "0.75rem",
                      color: "var(--accent-purple)",
                      fontWeight: 500,
                    }}
                  >
                    {kw.trim()}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
