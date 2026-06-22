/**
 * CatalogIQ — API Client
 *
 * Centralized HTTP client for communicating with the FastAPI backend.
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Generic fetch wrapper with error handling.
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  };

  // Don't set Content-Type for FormData
  if (options.body instanceof FormData) {
    delete config.headers["Content-Type"];
  }

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }

  if (response.status === 204) return null;
  return response.json();
}

// ---- Products ----

export async function fetchProducts(params = {}) {
  const query = new URLSearchParams();
  if (params.skip) query.set("skip", params.skip);
  if (params.limit) query.set("limit", params.limit);
  if (params.status) query.set("status", params.status);
  if (params.search) query.set("search", params.search);
  if (params.category) query.set("category", params.category);
  return request(`/api/products/?${query}`);
}

export async function fetchProduct(id) {
  return request(`/api/products/${id}`);
}

export async function fetchCategories() {
  return request("/api/products/categories");
}

export async function fetchDashboardStats() {
  return request("/api/products/stats");
}

export async function updateProduct(id, data) {
  return request(`/api/products/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteProduct(id) {
  return request(`/api/products/${id}`, { method: "DELETE" });
}

export async function fetchProductIssues(id) {
  return request(`/api/products/${id}/issues`);
}

// ---- Ingestion ----

export async function uploadCSV(file) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/api/ingestion/upload", {
    method: "POST",
    body: formData,
  });
}

export async function fetchIngestionJobs(limit = 20) {
  return request(`/api/ingestion/jobs?limit=${limit}`);
}

export async function fetchAllIssues(resolved = false, limit = 100) {
  return request(`/api/ingestion/issues?resolved=${resolved}&limit=${limit}`);
}

export async function resolveIssue(issueId) {
  return request(`/api/ingestion/issues/${issueId}/resolve`, { method: "PUT" });
}

// ---- Content Generation ----

export async function generateContent(productIds, tone = "professional", includeSeo = true) {
  return request("/api/content/generate", {
    method: "POST",
    body: JSON.stringify({
      product_ids: productIds,
      tone,
      include_seo: includeSeo,
    }),
  });
}

export async function generateSingleContent(productId, tone = "professional", includeSeo = true) {
  return request(
    `/api/content/generate/${productId}?tone=${tone}&include_seo=${includeSeo}`,
    { method: "POST" }
  );
}

export async function fetchProductsNeedingContent(limit = 50) {
  return request(`/api/content/needs-content?limit=${limit}`);
}

// ---- Competitors ----

export async function triggerCompetitorScrape(productIds = null, sources = null) {
  const body = {};
  if (productIds) body.product_ids = productIds;
  if (sources) body.sources = sources;
  return request("/api/competitors/scrape", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchCompetitorPrices(params = {}) {
  const query = new URLSearchParams();
  if (params.product_id) query.set("product_id", params.product_id);
  if (params.source) query.set("source", params.source);
  if (params.limit) query.set("limit", params.limit);
  return request(`/api/competitors/prices?${query}`);
}

export async function fetchAlerts(params = {}) {
  const query = new URLSearchParams();
  if (params.acknowledged !== undefined) query.set("acknowledged", params.acknowledged);
  if (params.product_id) query.set("product_id", params.product_id);
  if (params.limit) query.set("limit", params.limit);
  return request(`/api/competitors/alerts?${query}`);
}

export async function acknowledgeAlert(alertId) {
  return request(`/api/competitors/alerts/${alertId}/acknowledge`, { method: "PUT" });
}
