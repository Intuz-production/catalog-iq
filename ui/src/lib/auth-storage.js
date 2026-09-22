/**
 * CatalogIQ — Auth Token Storage
 *
 * Persists JWT access tokens in browser local storage.
 */

const TOKEN_KEY = "catalogiq_token";

// This is a utility to read the stored auth token
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

// This is a utility to persist the auth token
export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

// This is a utility to remove the stored auth token
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}
