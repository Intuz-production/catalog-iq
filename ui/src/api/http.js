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
