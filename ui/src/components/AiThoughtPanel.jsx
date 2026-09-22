/**
 * CatalogIQ — AI Thought Panel
 *
 * Lets merchants type a free-text instruction about a product; the AI proposes
 * field-level changes that can be accepted or rejected individually.
 */

import { useState, useRef, useEffect } from "react";
import { Sparkles, ChevronRight, Check, X, CheckCheck, XCircle, AlertTriangle } from "lucide-react";
import { aiThought } from "../api/client";

// WooCommerce CSV export field labels (matches woocommerce_export_service.py)
const FIELD_LABELS = {
  title: "Name (Title)",
  description: "Description",
  category: "Categories",
  brand: "Brands",
  price: "Regular Price",
  stock: "Stock",
  in_stock: "In Stock?",
  image_url: "Images (URL)",
};

function fieldLabel(field) {
  if (FIELD_LABELS[field]) return FIELD_LABELS[field];
  if (field.startsWith("attribute:")) {
    const key = field.replace("attribute:", "");
    return key.charAt(0).toUpperCase() + key.slice(1);
  }
  return field.charAt(0).toUpperCase() + field.slice(1);
}

// Maps an AI-proposed field change to a ProductUpdate-compatible payload entry.
// Only WooCommerce-exported fields are accepted; anything else is silently ignored.
const WOO_FIELD_KEYS = new Set([
  "title", "description", "category", "brand",
  "price", "stock", "in_stock", "image_url",
]);

function changeToUpdate(change) {
  const { field, after } = change;
  if (WOO_FIELD_KEYS.has(field)) {
    // Coerce numeric and boolean types that the API expects
    if (field === "price") {
      const parsed = parseFloat(after);
      return { key: "price", value: isNaN(parsed) ? null : parsed };
    }
    if (field === "stock") {
      const parsed = parseInt(after, 10);
      return { key: "stock", value: isNaN(parsed) ? null : parsed };
    }
    if (field === "in_stock") {
      return { key: "in_stock", value: after === "true" || after === true };
    }
    return { key: field, value: after };
  }
  return null; // attribute fields handled separately
}

export default function AiThoughtPanel({ product, saving, onApply, onCancel }) {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [changes, setChanges] = useState(null);
  const [accepted, setAccepted] = useState({});
  const [applying, setApplying] = useState(false);
  const textareaRef = useRef(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  async function handleGenerate(e) {
    e.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setChanges(null);
    setAccepted({});
    try {
      const result = await aiThought(product.id, trimmed);
      if (result.error && (!result.changes || result.changes.length === 0)) {
        setError(result.error);
      } else {
        setChanges(result.changes || []);
        if (result.error) setError(result.error);
        const defaults = {};
        (result.changes || []).forEach((c) => { defaults[c.field] = true; });
        setAccepted(defaults);
      }
    } catch (err) {
      setError(err.message || "AI service error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function acceptAll() {
    const next = {};
    changes.forEach((c) => { next[c.field] = true; });
    setAccepted(next);
  }

  function rejectAll() {
    const next = {};
    changes.forEach((c) => { next[c.field] = false; });
    setAccepted(next);
  }

  async function handleApply() {
    if (!changes) return;
    const selectedChanges = changes.filter((c) => accepted[c.field]);
    if (selectedChanges.length === 0) { onCancel(); return; }
    const payload = {};
    const newAttributes = { ...(product.attributes || {}) };
    let attributesChanged = false;
    for (const change of selectedChanges) {
      const mapped = changeToUpdate(change);
      if (mapped) {
        payload[mapped.key] = mapped.value;
      } else if (change.field.startsWith("attribute:")) {
        const attrKey = change.field.replace("attribute:", "");
        newAttributes[attrKey] = change.after;
        attributesChanged = true;
      }
    }
    if (attributesChanged) payload.attributes = newAttributes;
    if (Object.keys(payload).length === 0) { onCancel(); return; }
    setApplying(true);
    try {
      await onApply(payload);
    } finally {
      setApplying(false);
    }
  }

  const acceptedCount = changes ? changes.filter((c) => accepted[c.field]).length : 0;
  const isBusy = loading || applying || saving;

  return (
    <div className="ai-thought-panel">
      <div className="ai-thought-header">
        <div className="ai-thought-header-icon">
          <Sparkles size={16} />
        </div>
        <div>
          <h3 className="ai-thought-title">Give a Thought</h3>
          <p className="ai-thought-subtitle">
            Describe what you&apos;d like to change — AI will propose updates for your review.
          </p>
        </div>
      </div>

      <form className="ai-thought-form" onSubmit={handleGenerate}>
        <div className="ai-thought-prompt-wrap">
          <textarea
            ref={textareaRef}
            className="ai-thought-textarea"
            placeholder="e.g. Make the description more eco-focused and highlight the sustainable materials"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            disabled={isBusy}
            maxLength={2000}
          />
          <div className="ai-thought-prompt-meta">
            <span className="ai-thought-char-count">{prompt.length}/2000</span>
          </div>
        </div>

        <button
          type="submit"
          className="btn btn-primary ai-thought-generate-btn"
          disabled={isBusy || prompt.trim().length < 3}
        >
          {loading ? (
            <>
              <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2, margin: 0 }} />
              Thinking...
            </>
          ) : (
            <>
              <Sparkles size={15} />
              Generate Changes
            </>
          )}
        </button>
      </form>

      {error && (
        <div className="ai-thought-error">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      {changes !== null && (
        <div className="ai-thought-results">
          {changes.length === 0 ? (
            <div className="ai-thought-empty">
              <Sparkles size={24} style={{ opacity: 0.4 }} />
              <p>No changes needed based on your instruction.</p>
              <p className="ai-thought-empty-hint">Try a different prompt.</p>
            </div>
          ) : (
            <>
              <div className="ai-thought-bulk-bar">
                <span className="ai-thought-bulk-label">
                  {acceptedCount} of {changes.length} change{changes.length !== 1 ? "s" : ""} selected
                </span>
                <div className="ai-thought-bulk-actions">
                  <button type="button" className="btn btn-ghost btn-sm" onClick={acceptAll} disabled={isBusy}>
                    <CheckCheck size={13} />
                    Accept all
                  </button>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={rejectAll} disabled={isBusy}>
                    <XCircle size={13} />
                    Reject all
                  </button>
                </div>
              </div>

              <div className="ai-thought-changes">
                {changes.map((change) => {
                  const isAccepted = !!accepted[change.field];
                  return (
                    <div
                      key={change.field}
                      className={`ai-thought-change-card${isAccepted ? " is-accepted" : " is-rejected"}`}
                    >
                      <div className="ai-thought-change-header">
                        <span className="ai-thought-change-field">{fieldLabel(change.field)}</span>
                        {change.reason && (
                          <span className="ai-thought-change-reason">{change.reason}</span>
                        )}
                        <div className="ai-thought-change-actions">
                          <button
                            type="button"
                            className={`ai-thought-action-btn${isAccepted ? " is-active-accept" : ""}`}
                            onClick={() => !isBusy && setAccepted((p) => ({ ...p, [change.field]: true }))}
                            title="Accept this change"
                            disabled={isBusy}
                            aria-pressed={isAccepted}
                          >
                            <Check size={14} />
                          </button>
                          <button
                            type="button"
                            className={`ai-thought-action-btn${!isAccepted ? " is-active-reject" : ""}`}
                            onClick={() => !isBusy && setAccepted((p) => ({ ...p, [change.field]: false }))}
                            title="Reject this change"
                            disabled={isBusy}
                            aria-pressed={!isAccepted}
                          >
                            <X size={14} />
                          </button>
                        </div>
                      </div>

                      <div className="ai-thought-diff">
                        {change.before && (
                          <div className="ai-thought-diff-before">
                            <span className="ai-thought-diff-label">Before</span>
                            <p className="ai-thought-diff-text ai-thought-diff-text--before">{change.before}</p>
                          </div>
                        )}
                        <div className="ai-thought-diff-arrow">
                          <ChevronRight size={14} />
                        </div>
                        <div className="ai-thought-diff-after">
                          <span className="ai-thought-diff-label">After</span>
                          <p className="ai-thought-diff-text ai-thought-diff-text--after">{change.after}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}

      <div className="ai-thought-footer">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={isBusy}>
          Cancel
        </button>
        {changes !== null && changes.length > 0 && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleApply}
            disabled={isBusy || acceptedCount === 0}
          >
            {applying ? (
              <>
                <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2, margin: 0 }} />
                Applying...
              </>
            ) : (
              <>
                <Check size={15} />
                Apply {acceptedCount} Change{acceptedCount !== 1 ? "s" : ""}
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
