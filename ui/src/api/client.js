/**
 * CatalogIQ — API Client
 *
 * Domain API functions for the FastAPI backend.
 */

import { request } from "./http";

// ---- Products ----

export async function fetchProducts(params = {}) {
  const query = new URLSearchParams();
  if (params.skip !== undefined) query.set("skip", params.skip);
  if (params.limit !== undefined) query.set("limit", params.limit);
  if (params.status) query.set("status", params.status);
  if (params.search) query.set("search", params.search);
  if (params.category) query.set("category", params.category);
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_order) query.set("sort_order", params.sort_order);
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

export async function fetchIngestionJobs(params = {}) {
  const query = new URLSearchParams();
  if (params.skip !== undefined) query.set("skip", params.skip);
  if (params.limit !== undefined) query.set("limit", params.limit);
  if (params.status) query.set("status", params.status);
  if (params.search) query.set("search", params.search);
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_order) query.set("sort_order", params.sort_order);
  return request(`/api/ingestion/jobs?${query}`);
}

export async function fetchAllIssues(params = {}) {
  const query = new URLSearchParams();
  if (params.resolved !== undefined) query.set("resolved", params.resolved);
  if (params.skip !== undefined) query.set("skip", params.skip);
  if (params.limit !== undefined) query.set("limit", params.limit);
  if (params.search) query.set("search", params.search);
  if (params.severity) query.set("severity", params.severity);
  if (params.issue_type) query.set("issue_type", params.issue_type);
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_order) query.set("sort_order", params.sort_order);
  return request(`/api/ingestion/issues?${query}`);
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

export async function fetchProductsNeedingContent(params = {}) {
  const query = new URLSearchParams();
  if (params.skip !== undefined) query.set("skip", params.skip);
  if (params.limit !== undefined) query.set("limit", params.limit);
  if (params.search) query.set("search", params.search);
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_order) query.set("sort_order", params.sort_order);
  return request(`/api/content/needs-content?${query}`);
}

// ---- Competitors ----

let competitorConfigCache = null;

export async function fetchCompetitorConfig({ force = false } = {}) {
  if (!force && competitorConfigCache) {
    return competitorConfigCache;
  }

  competitorConfigCache = await request("/api/competitors/config");
  return competitorConfigCache;
}

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
