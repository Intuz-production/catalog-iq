/**
 * CatalogIQ — Confirm Dialog
 *
 * Accessible confirmation modal for destructive or important actions.
 */

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, X } from "lucide-react";

/**
 * @typedef {Object} ConfirmDialogProps
 * @property {boolean} open
 * @property {string} title
 * @property {string} message
 * @property {string} [confirmLabel]
 * @property {string} [cancelLabel]
 * @property {"danger" | "primary"} [variant]
 * @property {boolean} [loading]
 * @property {() => void} onConfirm
 * @property {() => void} onCancel
 */

// This is a component to show a themed confirmation dialog
export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "primary",
  loading = false,
  onConfirm,
  onCancel,
}) {
  const cancelRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

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

  const confirmClassName = variant === "danger" ? "btn btn-danger" : "btn btn-primary";

  return createPortal(
    <div
      className="confirm-overlay"
      role="presentation"
      onClick={loading ? undefined : onCancel}
    >
      <div
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="confirm-dialog-header">
          <div className="confirm-dialog-title-row">
            {variant === "danger" && (
              <span className="confirm-dialog-icon confirm-dialog-icon-danger" aria-hidden="true">
                <AlertTriangle size={18} />
              </span>
            )}
            <h3 id="confirm-dialog-title">{title}</h3>
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

        <p id="confirm-dialog-message" className="confirm-dialog-message">
          {message}
        </p>

        <div className="confirm-dialog-actions">
          <button
            ref={cancelRef}
            type="button"
            className="btn btn-ghost"
            onClick={onCancel}
            disabled={loading}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={confirmClassName}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? (
              <>
                <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2, margin: 0 }} />
                {confirmLabel}
              </>
            ) : (
              confirmLabel
            )}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
