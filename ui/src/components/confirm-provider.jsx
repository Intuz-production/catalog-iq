/**
 * CatalogIQ — Confirm Provider
 *
 * Renders a global confirmation dialog and exposes a promise-based confirm action.
 */

import { useState, useCallback, useRef } from "react";
import ConfirmDialog from "./ConfirmDialog";
import { ConfirmContext } from "../lib/confirm-context";

/**
 * @typedef {Object} ConfirmOptions
 * @property {string} title
 * @property {string} message
 * @property {string} [confirmLabel]
 * @property {string} [cancelLabel]
 * @property {"danger" | "primary"} [variant]
 */

// This is a component to provide global confirmation dialogs
export function ConfirmProvider({ children }) {
  const [dialogState, setDialogState] = useState(null);
  const resolverRef = useRef(null);

  const confirm = useCallback((options) => {
    return new Promise((resolve) => {
      resolverRef.current = resolve;
      setDialogState({
        title: options.title,
        message: options.message,
        confirmLabel: options.confirmLabel ?? "Confirm",
        cancelLabel: options.cancelLabel ?? "Cancel",
        variant: options.variant ?? "primary",
      });
    });
  }, []);

  function closeDialog(confirmed) {
    resolverRef.current?.(confirmed);
    resolverRef.current = null;
    setDialogState(null);
  }

  function handleConfirm() {
    closeDialog(true);
  }

  function handleCancel() {
    closeDialog(false);
  }

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      <ConfirmDialog
        open={Boolean(dialogState)}
        title={dialogState?.title ?? ""}
        message={dialogState?.message ?? ""}
        confirmLabel={dialogState?.confirmLabel ?? "Confirm"}
        cancelLabel={dialogState?.cancelLabel ?? "Cancel"}
        variant={dialogState?.variant ?? "primary"}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </ConfirmContext.Provider>
  );
}
