/**
 * CatalogIQ — API Client
 *
 * Domain API functions for the FastAPI backend.
 */

import { request, downloadRequest } from "./http";

// ---- Products ----

export async function fetchProducts(params = {}) {
  const query = new URLSearchParams();
  if (params.skip !== undefined) query.set("skip", params.skip);
  if (params.limit !== undefined) query.set("limit", params.limit);
  if (params.status) query.set("status", params.status);
  if (params.search) query.set("search", params.search);
  if (params.category) query.set("category", params.category);
  if (params.ingestion_job_id !== undefined) {
    query.set("ingestion_job_id", params.ingestion_job_id);
  }
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_order) query.set("sort_order", params.sort_order);
  return request(`/api/products/?${query}`);
}

export async function fetchProduct(id) {
  return request(`/api/products/${id}`);
}

export async function fetchCategories(ingestionJobId) {
  const query = new URLSearchParams();
  if (ingestionJobId !== undefined && ingestionJobId !== null) {
    query.set("ingestion_job_id", ingestionJobId);
  }
  const qs = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/products/categories${qs}`);
}

export async function fetchStatuses(ingestionJobId) {
  const query = new URLSearchParams();
  if (ingestionJobId !== undefined && ingestionJobId !== null) {
    query.set("ingestion_job_id", ingestionJobId);
  }
  const qs = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/products/statuses${qs}`);
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

export async function exportWooCommerceCsv(params = {}) {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.search) query.set("search", params.search);
  if (params.category) query.set("category", params.category);
  if (params.ingestion_job_id !== undefined) {
    query.set("ingestion_job_id", params.ingestion_job_id);
  }
  const suffix = query.toString() ? `?${query}` : "";
  return downloadRequest(
    `/api/products/export/woocommerce${suffix}`,
    "catalogiq-woocommerce.csv"
  );
}

// ---- Ingestion ----

export async function downloadSampleCsv() {
  return downloadRequest("/api/ingestion/sample-csv", "sample_products.csv");
}

export async function previewCSV(file) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/api/ingestion/preview", {
    method: "POST",
    body: formData,
  });
}

export async function uploadCSV(file, columnMapping, options = {}) {
  const formData = new FormData();
  formData.append("file", file);
  if (columnMapping) {
    formData.append("column_mapping", JSON.stringify(columnMapping));
  }
  if (options.ingestionJobId != null) {
    formData.append("ingestion_job_id", String(options.ingestionJobId));
  }
  if (options.groupName != null && String(options.groupName).trim()) {
    formData.append("group_name", String(options.groupName).trim());
  }
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

export async function fetchIngestionJob(jobId) {
  return request(`/api/ingestion/jobs/${jobId}`);
}

export async function renameIngestionJob(jobId, groupName) {
  return request(`/api/ingestion/jobs/${jobId}`, {
    method: "PATCH",
    body: JSON.stringify({ group_name: groupName }),
  });
}

export async function deleteIngestionJob(jobId) {
  return request(`/api/ingestion/jobs/${jobId}`, { method: "DELETE" });
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
  if (params.ingestion_job_id !== undefined) {
    query.set("ingestion_job_id", params.ingestion_job_id);
  }
  return request(`/api/ingestion/issues?${query}`);
}

export async function resolveIssue(issueId) {
  return request(`/api/ingestion/issues/${issueId}/resolve`, { method: "PUT" });
}

export async function acceptProductIssues(productId) {
  return request("/api/ingestion/issues/accept-bulk", {
    method: "POST",
    body: JSON.stringify({ product_ids: [productId] }),
  });
}

export async function reviewIssue(issueId, action, editedValue) {
  return request(`/api/ingestion/issues/${issueId}/review`, {
    method: "PUT",
    body: JSON.stringify({
      action,
      ...(editedValue !== undefined ? { edited_value: editedValue } : {}),
    }),
  });
}

// ---- Content Generation ----

export async function generateSingleContent(productId, tone = "professional", includeSeo = true) {
  return request(
    `/api/content/generate/${productId}?tone=${tone}&include_seo=${includeSeo}`,
    { method: "POST" }
  );
}

export async function aiThought(productId, prompt) {
  return request(`/api/products/${productId}/ai-thought`, {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
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
