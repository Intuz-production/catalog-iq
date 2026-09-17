/**
 * CatalogIQ — Toast Provider
 *
 * Renders a global toast stack and exposes show/dismiss actions.
 */

import { useState, useCallback, useRef } from "react";
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from "lucide-react";
import { ToastContext } from "../lib/toast-context";

const TOAST_ICONS = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warning: AlertTriangle,
};

const DEFAULT_DURATION_MS = 4000;

// This is a component to provide global toast notifications
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback((message, type = "info", duration = DEFAULT_DURATION_MS) => {
    const id = ++idRef.current;
    setToasts((prev) => [...prev, { id, message, type }]);

    if (duration > 0) {
      window.setTimeout(() => dismiss(id), duration);
    }

    return id;
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ showToast, dismiss }}>
      {children}
      <div className="toast-container" aria-live="polite">
        {toasts.map((toast) => {
          const Icon = TOAST_ICONS[toast.type] || Info;

          return (
            <div key={toast.id} className={`toast ${toast.type}`} role="alert">
              <Icon size={18} className="toast-icon" aria-hidden="true" />
              <span className="toast-message">{toast.message}</span>
              <button
                type="button"
                className="toast-close"
                aria-label="Dismiss notification"
                onClick={() => dismiss(toast.id)}
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
