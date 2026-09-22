/**
 * CatalogIQ — HTTP Client
 *
 * Shared fetch wrapper for FastAPI backend requests.
 */

import { getToken } from "../lib/auth-storage";

const API_BASE = import.meta.env.VITE_API_URL;

if (!API_BASE) {
  throw new Error(
    "VITE_API_URL is not set. Copy ui/.env.example to ui/.env and configure it."
  );
}

export { API_BASE };

// This is a utility to perform authenticated API requests
export async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const token = getToken();
  const config = {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...options,
  };

  if (options.body instanceof FormData) {
    delete config.headers["Content-Type"];
  }

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    const message = typeof error.detail === "string"
      ? error.detail
      : `Request failed: ${response.status}`;
    throw new Error(message);
  }

  if (response.status === 204) return null;
  return response.json();
}

// This is a utility to download a binary API response as a file
export async function downloadRequest(endpoint, fallbackFilename, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const token = getToken();
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    const message = typeof error.detail === "string"
      ? error.detail
      : `Request failed: ${response.status}`;
    throw new Error(message);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^"]+)"?/i);
  const filename = filenameMatch?.[1] || fallbackFilename;

  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
