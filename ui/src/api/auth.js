/**
 * CatalogIQ — Auth API Client
 *
 * Authentication requests for login and current-user lookup.
 */

import { clearToken, setToken } from "../lib/auth-storage";
import { API_BASE, request } from "./http";

// This is a utility to sign in with email and password
export async function login(email, password) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);

  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Login failed");
  }

  const data = await response.json();
  setToken(data.access_token);
  return data;
}

// This is a utility to clear the stored auth session
export function logout() {
  clearToken();
}

// This is a utility to fetch the authenticated user profile
export async function fetchCurrentUser() {
  return request("/api/auth/me");
}
