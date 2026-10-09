/**
 * CatalogIQ — useToast Hook
 *
 * Shows dismissible success, error, info, and warning toasts.
 */

import { useContext } from "react";
import { ToastContext } from "./toast-context";

// This is a hook to show and dismiss toast notifications
export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}
