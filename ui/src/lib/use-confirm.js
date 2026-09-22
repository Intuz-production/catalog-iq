/**
 * CatalogIQ — useConfirm Hook
 *
 * Shows a themed confirmation dialog before destructive or important actions.
 */

import { useContext } from "react";
import { ConfirmContext } from "./confirm-context";

// This is a hook to show confirmation dialogs before important actions
export function useConfirm() {
  const context = useContext(ConfirmContext);
  if (!context) {
    throw new Error("useConfirm must be used within ConfirmProvider");
  }
  return context;
}
