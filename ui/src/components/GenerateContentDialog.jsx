/**
 * CatalogIQ — Generate Content Dialog
 *
 * Options modal for single-product SEO content generation (tone + SEO metadata).
 */

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Sparkles, X } from "lucide-react";
import Select from "./Select";

const TONE_OPTIONS = [
  { value: "professional", label: "Professional" },
  { value: "casual", label: "Casual" },
  { value: "luxury", label: "Luxury" },
  { value: "technical", label: "Technical" },
];

/**
 * @typedef {Object} GenerateContentDialogProps
 * @property {boolean} open
 * @property {string} productTitle
 * @property {boolean} [loading]
 * @property {() => void} onCancel
 * @property {(options: { tone: string, includeSeo: boolean }) => void} onConfirm
 */

// This is a component to collect tone and SEO options before generating product content
export default function GenerateContentDialog({
  open,
  productTitle,
  loading = false,
  onCancel,
  onConfirm,
}) {
  const cancelRef = useRef(null);
  const [tone, setTone] = useState("professional");
  const [includeSeo, setIncludeSeo] = useState(true);

  useEffect(() => {
    if (!open) return undefined;

    setTone("professional");
    setIncludeSeo(true);
    cancelRef.current?.focus();

    function handleKeyDown(event) {
      if (event.key === "Escape" && !loading) {
        onCancel();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, loading, onCancel]);

  if (!open) return null;

  function handleConfirm() {
    onConfirm({ tone, includeSeo });
  }

  return createPortal(
    <div
      className="confirm-overlay"
      role="presentation"
      onClick={loading ? undefined : onCancel}
    >
      <div
        className="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="generate-content-dialog-title"
        aria-describedby="generate-content-dialog-message"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="confirm-dialog-header">
          <div className="confirm-dialog-title-row">
            <h3 id="generate-content-dialog-title">Generate SEO Content</h3>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm confirm-dialog-close"
            aria-label="Close dialog"
            onClick={onCancel}
            disabled={loading}
          >
            <X size={16} />
          </button>
        </div>

        <p id="generate-content-dialog-message" className="confirm-dialog-message">
          Generate SEO content for &ldquo;{productTitle}&rdquo;? This may overwrite
          existing generated content.
        </p>

        <div className="generate-content-dialog-fields">
          <Select
            value={tone}
            onChange={setTone}
            ariaLabel="Content generation tone"
            label="Tone"
            options={TONE_OPTIONS}
            disabled={loading}
          />
          <label className="content-gen-option">
            <input
              type="checkbox"
              checked={includeSeo}
              onChange={(event) => setIncludeSeo(event.target.checked)}
              disabled={loading}
            />
            <span>Include SEO metadata</span>
          </label>
        </div>

        <div className="confirm-dialog-actions">
          <button
            ref={cancelRef}
            type="button"
            className="btn btn-ghost"
            onClick={onCancel}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleConfirm}
            disabled={loading}
          >
            {loading ? (
              <>
                <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2, margin: 0 }} />
                Generate
              </>
            ) : (
              <>
                <Sparkles size={16} />
                Generate
              </>
            )}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
