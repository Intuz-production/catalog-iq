/**
 * CatalogIQ — File Product List
 *
 * Products and quality issues for one uploaded CSV file.
 */

import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Search, Download, AlertTriangle, Pencil } from "lucide-react";
import {
  fetchProducts, fetchProduct, fetchCategories, fetchStatuses, deleteProduct,
  fetchProductIssues, updateProduct,
  exportWooCommerceCsv, fetchIngestionJob, renameIngestionJob,
  fetchAllIssues, reviewIssue, acceptProductIssues,
} from "../api/client";
import ProductTable from "../components/ProductTable";
import ProductDetailDialog from "../components/ProductDetailDialog";
import QualityIssuesDialog from "../components/QualityIssuesDialog";
import Select from "../components/Select";
import { useToast } from "../lib/use-toast";
import { useConfirm } from "../lib/use-confirm";

const DEFAULT_PAGE_SIZE = 15;

const STATUS_LABELS = {
  active: "Active",
  flagged: "Flagged",
  processing: "Processing",
  draft: "Draft",
  archived: "Archived",
};

const SKIP_REASON_LABELS = {
  blank_sku: "blank SKU",
  row_error: "row error",
  invalid_row: "invalid row",
};

function formatSkipBreakdown(job) {
  const skipped = job?.skipped_rows || 0;
  if (!skipped) return null;
  const counts = job?.skip_summary?.counts || {};
  const parts = Object.entries(counts).map(
    ([reason, count]) => `${count} ${SKIP_REASON_LABELS[reason] || reason}`
  );
  if (parts.length) {
    return `${skipped} row${skipped === 1 ? "" : "s"} skipped (${parts.join(", ")})`;
  }
  return `${skipped} row${skipped === 1 ? "" : "s"} skipped`;
}

export default function Products() {
  const { jobId } = useParams();
  const ingestionJobId = Number(jobId);
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { confirm } = useConfirm();
  const [job, setJob] = useState(null);
  const [jobLoading, setJobLoading] = useState(true);
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [statuses, setStatuses] = useState(["active", "flagged"]);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [sortBy, setSortBy] = useState("updated_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [productIssues, setProductIssues] = useState([]);
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [issues, setIssues] = useState([]);
  const [fileIssuesLoading, setFileIssuesLoading] = useState(true);
  const [issueTotal, setIssueTotal] = useState(0);
  const [busyProductId, setBusyProductId] = useState(null);
  const [issuesDialogOpen, setIssuesDialogOpen] = useState(false);

  useEffect(() => {
    if (!Number.isInteger(ingestionJobId) || ingestionJobId < 1) {
      navigate("/products", { replace: true });
    }
  }, [ingestionJobId, navigate]);

  useEffect(() => {
    loadCategories();
    loadStatuses();
  }, [ingestionJobId]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery((prev) => {
        const next = searchInput.trim();
        if (prev !== next) {
          setPage(1);
        }
        return next;
      });
    }, 300);

    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    if (!Number.isInteger(ingestionJobId) || ingestionJobId < 1) return;
    loadJob();
    loadFileIssues();
  }, [ingestionJobId]);

  useEffect(() => {
    if (!Number.isInteger(ingestionJobId) || ingestionJobId < 1) return;
    loadProducts();
  }, [ingestionJobId, page, pageSize, statusFilter, categoryFilter, searchQuery, sortBy, sortOrder]);

  const isAnalyzing = job?.status === "analyzing";

  useEffect(() => {
    if (!isAnalyzing) return undefined;

    const intervalId = window.setInterval(() => {
      refreshAll();
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [isAnalyzing, ingestionJobId, page, pageSize, statusFilter, categoryFilter, searchQuery, sortBy, sortOrder]);

  // Background refetches stay silent so polling and reviews never blank the page.
  async function refreshAll() {
    await Promise.all([
      loadJob({ silent: true }),
      loadProducts({ silent: true }),
      loadFileIssues({ silent: true }),
      loadStatuses(),
    ]);
  }

  async function loadJob({ silent = false } = {}) {
    try {
      if (!silent) setJobLoading(true);
      const data = await fetchIngestionJob(ingestionJobId);
      setJob(data);
    } catch (err) {
      if (silent) return;
      setJob(null);
      showToast(err.message || "Could not load uploaded file.", "error");
      navigate("/products", { replace: true });
    } finally {
      if (!silent) setJobLoading(false);
    }
  }

  async function handleRenameGroup() {
    const current = job?.group_name || job?.filename || "";
    const nextName = window.prompt("Group name", current);
    if (nextName == null) return;
    const trimmed = nextName.trim();
    if (!trimmed) {
      showToast("Group name cannot be empty", "error");
      return;
    }
    if (trimmed === current) return;

    try {
      const updated = await renameIngestionJob(ingestionJobId, trimmed);
      setJob(updated);
      showToast("Group renamed", "success");
    } catch (err) {
      showToast(err.message || "Failed to rename group", "error");
    }
  }

  async function loadProducts({ silent = false } = {}) {
    try {
      if (!silent) setLoading(true);
      const data = await fetchProducts({
        skip: (page - 1) * pageSize,
        limit: pageSize,
        status: statusFilter || undefined,
        category: categoryFilter || undefined,
        search: searchQuery || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        ingestion_job_id: ingestionJobId,
      });
      setProducts(data.items);
      setTotal(data.total);

      const maxPage = Math.max(1, Math.ceil(data.total / pageSize));
      if (page > maxPage) {
        setPage(maxPage);
      }

      return data;
    } catch (err) {
      if (silent) return null;
      showToast(err.message || "Failed to load products", "error");
      setProducts([]);
      setTotal(0);
      return null;
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function loadCategories() {
    try {
      const cats = await fetchCategories(ingestionJobId);
      setCategories(cats);
    } catch (err) {
      showToast(err.message || "Failed to load categories", "error");
    }
  }

  async function loadStatuses() {
    try {
      const sts = await fetchStatuses(ingestionJobId);
      if (Array.isArray(sts) && sts.length > 0) {
        setStatuses(sts);
      }
    } catch {
      // Keep sensible default active/flagged
    }
  }

  async function loadFileIssues({ silent = false } = {}) {
    try {
      if (!silent) setFileIssuesLoading(true);
      const data = await fetchAllIssues({
        skip: 0,
        limit: 50,
        resolved: false,
        ingestion_job_id: ingestionJobId,
      });
      setIssues(data.items);
      setIssueTotal(data.total);
    } catch (err) {
      if (silent) return;
      setIssues([]);
      setIssueTotal(0);
      showToast(err.message || "Could not load quality issues.", "error");
    } finally {
      if (!silent) setFileIssuesLoading(false);
    }
  }

  function handleStatusFilterChange(value) {
    setStatusFilter(value);
    setPage(1);
  }

  function handleCategoryFilterChange(value) {
    setCategoryFilter(value);
    setPage(1);
  }

  function handleSort(nextSortBy, nextSortOrder) {
    setSortBy(nextSortBy);
    setSortOrder(nextSortOrder);
    setPage(1);
  }

  function handlePageSizeChange(nextPageSize) {
    setPageSize(nextPageSize);
    setPage(1);
  }

  async function handleExportWooCommerce() {
    try {
      setExporting(true);
      await exportWooCommerceCsv({
        status: statusFilter || undefined,
        category: categoryFilter || undefined,
        search: searchQuery || undefined,
        ingestion_job_id: ingestionJobId,
      });
      showToast("WooCommerce CSV downloaded", "success");
    } catch (err) {
      showToast(err.message || "Failed to export WooCommerce CSV", "error");
    } finally {
      setExporting(false);
    }
  }

  async function handleDeleteRequest(product) {
    const confirmed = await confirm({
      title: "Delete Product",
      message: `Are you sure you want to delete "${product.title}"? This action cannot be undone.`,
      confirmLabel: "Delete",
      cancelLabel: "Cancel",
      variant: "danger",
    });
    if (!confirmed) return;

    try {
      await deleteProduct(product.id);
      showToast("Product deleted", "success");
      refreshAll();
      if (selectedProduct?.id === product.id) setSelectedProduct(null);
    } catch (err) {
      showToast(err.message || "Failed to delete product", "error");
    }
  }

  async function handleViewDetails(product) {
    setSelectedProduct(product);
    setProductIssues([]);
    setIssuesLoading(true);

    try {
      const nextIssues = await fetchProductIssues(product.id);
      setProductIssues(nextIssues);
    } catch (err) {
      setProductIssues([]);
      showToast(err.message || "Failed to load product issues", "error");
    } finally {
      setIssuesLoading(false);
    }
  }

  function handleCloseDetails() {
    if (saving) return;
    setSelectedProduct(null);
    setProductIssues([]);
    setIssuesLoading(false);
  }

  async function handleSaveProduct(productId, payload) {
    try {
      setSaving(true);
      const updated = await updateProduct(productId, payload);
      showToast("Product updated and quality checks re-run", "success");
      await loadProducts({ silent: true });
      setSelectedProduct(updated);
      const nextIssues = await fetchProductIssues(productId);
      setProductIssues(nextIssues);
      await loadFileIssues({ silent: true });
    } catch (err) {
      showToast(err.message || "Failed to update product", "error");
      throw err;
    } finally {
      setSaving(false);
    }
  }

  /**
   * Reload the open product detail so Apply/Edit values show immediately.
   *
   * @param {number} productId
   * @returns {Promise<void>}
   */
  async function syncOpenProduct(productId) {
    if (selectedProduct?.id !== productId) return;
    const [updated, nextIssues] = await Promise.all([
      fetchProduct(productId),
      fetchProductIssues(productId),
    ]);
    setProductIssues(nextIssues);
    setSelectedProduct({
      ...updated,
      issue_count: nextIssues.filter((item) => !item.resolved).length,
    });
  }

  async function handleReviewIssue(issue, action, editedValue) {
    try {
      await reviewIssue(issue.id, action, editedValue);
      const labels = {
        accept: "accepted",
        edit: "saved",
        reject: "rejected",
      };
      showToast(`Issue ${labels[action] || action}.`, "success");
      await refreshAll();
      await syncOpenProduct(issue.product_id);
    } catch (err) {
      showToast(err.message || "Could not review issue.", "error");
      throw err;
    }
  }

  async function handleAcceptAllIssues(group) {
    const applicable = group.issues.filter(
      (issue) => issue.field_name && issue.suggested_value
    );
    const confirmed = await confirm({
      title: "Accept All Fixes",
      message: applicable.length
        ? `Apply ${applicable.length} suggested fix${applicable.length === 1 ? "" : "es"} for ${group.sku}?`
        : `No suggested fixes to apply for ${group.sku}.`,
      confirmLabel: "Accept all",
      cancelLabel: "Cancel",
      variant: "primary",
    });
    if (!confirmed || applicable.length === 0) return;

    try {
      setBusyProductId(group.productId);
      const result = await acceptProductIssues(group.productId);
      const skippedNote = result.skipped > 0 ? ` (${result.skipped} skipped)` : "";
      showToast(`${result.accepted} fix${result.accepted === 1 ? "" : "es"} accepted${skippedNote}.`, "success");
      await refreshAll();
      await syncOpenProduct(group.productId);
    } catch (err) {
      showToast(err.message || "Could not accept product fixes.", "error");
    } finally {
      setBusyProductId(null);
    }
  }

  async function handleIgnoreAllIssues(group) {
    const confirmed = await confirm({
      title: "Ignore All Issues",
      message: `Close all ${group.issues.length} open issue${group.issues.length === 1 ? "" : "s"} for ${group.sku} without changing the product?`,
      confirmLabel: "Ignore all",
      cancelLabel: "Cancel",
      variant: "danger",
    });
    if (!confirmed) return;

    try {
      setBusyProductId(group.productId);
      for (const issue of group.issues) {
        await reviewIssue(issue.id, "reject");
      }
      showToast(`${group.issues.length} issue${group.issues.length === 1 ? "" : "s"} ignored.`, "success");
      await refreshAll();
      await syncOpenProduct(group.productId);
    } catch (err) {
      showToast(err.message || "Could not ignore product issues.", "error");
    } finally {
      setBusyProductId(null);
    }
  }

  if (jobLoading && !job) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading file products...
      </div>
    );
  }

  return (
    <>
      <div className="animate-in">
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <button
            className="btn btn-ghost btn-sm file-products-back"
            onClick={() => navigate("/products")}
            type="button"
          >
            <ArrowLeft size={16} />
            All Groups
          </button>
          <div className="file-products-title-row">
            <h2>{job?.group_name || job?.filename || "Product Group"}</h2>
            <button
              className="btn btn-ghost btn-sm"
              onClick={handleRenameGroup}
              type="button"
              title="Rename group"
              aria-label="Rename group"
              disabled={!job}
            >
              <Pencil size={14} />
            </button>
          </div>
          <p className="file-products-meta">
            <span>
              {total} product{total === 1 ? "" : "s"} in this group
            </span>
            {job?.filename ? (
              <span title="Last uploaded CSV" style={{ color: "var(--text-muted)" }}>
                {job.filename}
              </span>
            ) : null}
            {formatSkipBreakdown(job) ? (
              <span title={formatSkipBreakdown(job)} style={{ color: "var(--accent-orange)" }}>
                {formatSkipBreakdown(job)}
              </span>
            ) : null}
            {isAnalyzing ? (
              <span className="ai-analyzing-status" aria-live="polite">
                <span
                  className="spinner"
                  aria-hidden="true"
                  style={{ width: 14, height: 14, borderWidth: 2, margin: 0 }}
                />
                AI analysis is still running
              </span>
            ) : null}
          </p>
        </div>
        <div className="page-header-actions">
          <button
            className="btn btn-ghost"
            onClick={() => setIssuesDialogOpen(true)}
            type="button"
          >
            <AlertTriangle size={16} />
            Review Issues
            {issueTotal > 0 ? (
              <span className="badge badge-high">{issueTotal}</span>
            ) : null}
          </button>
          <button
            className="btn btn-primary"
            disabled={exporting || loading || total === 0}
            onClick={handleExportWooCommerce}
            type="button"
          >
            {exporting ? (
              <>
                <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2, margin: 0 }} />
                Exporting...
              </>
            ) : (
              <>
                <Download size={16} />
                Export WooCommerce CSV
              </>
            )}
          </button>
        </div>
      </div>

      <div className="toolbar">
        <div className="search-input">
          <div style={{ position: "relative" }}>
            <Search
              size={16}
              style={{
                position: "absolute",
                left: 12,
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--text-muted)",
              }}
            />
            <input
              type="search"
              placeholder="Search by title, SKU, or brand..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              style={{ paddingLeft: 36 }}
            />
          </div>
        </div>
        <div className="filters-row">
          <Select
            value={statusFilter}
            onChange={handleStatusFilterChange}
            placeholder="All Statuses"
            ariaLabel="Filter by status"
            options={[
              { value: "", label: "All Statuses" },
              ...statuses.map((st) => ({
                value: st,
                label: STATUS_LABELS[st] || st.charAt(0).toUpperCase() + st.slice(1),
              })),
            ]}
          />
          <Select
            value={categoryFilter}
            onChange={handleCategoryFilterChange}
            placeholder="All Categories"
            ariaLabel="Filter by category"
            options={[
              { value: "", label: "All Categories" },
              ...categories.map((cat) => ({ value: cat, label: cat })),
            ]}
          />
        </div>
      </div>

      <ProductTable
        products={products}
        loading={loading}
        onDelete={handleDeleteRequest}
        onViewDetails={handleViewDetails}
        sortBy={sortBy}
        sortOrder={sortOrder}
        onSort={handleSort}
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        onPageSizeChange={handlePageSizeChange}
        emptyTitle="No products in this file"
        emptyDescription="This upload did not create or update any products that match the current filters."
      />

      </div>

      <QualityIssuesDialog
        open={issuesDialogOpen}
        onClose={() => setIssuesDialogOpen(false)}
        issues={issues}
        products={products}
        issueTotal={issueTotal}
        loading={fileIssuesLoading}
        isAnalyzing={isAnalyzing}
        busyProductId={busyProductId}
        onReview={handleReviewIssue}
        onAcceptAll={handleAcceptAllIssues}
        onIgnoreAll={handleIgnoreAllIssues}
      />

      <ProductDetailDialog
        product={selectedProduct}
        issues={productIssues}
        issuesLoading={issuesLoading}
        saving={saving}
        onClose={handleCloseDetails}
        onSave={handleSaveProduct}
        onReviewIssue={handleReviewIssue}
      />
    </>
  );
}
