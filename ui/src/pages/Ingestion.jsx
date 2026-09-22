/**
 * CatalogIQ — Products Page
 *
 * List uploaded CSV files and open each file to review its products.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileSpreadsheet,
  RefreshCw,
  Search,
  ChevronRight,
  Pencil,
  Trash2,
  Upload,
} from "lucide-react";
import { deleteIngestionJob, fetchIngestionJobs, renameIngestionJob } from "../api/client";
import PaginationBar from "../components/PaginationBar";
import Select from "../components/Select";
import SortableColumnHeader from "../components/SortableColumnHeader";
import UploadProductFeedDialog from "../components/UploadProductFeedDialog";
import { useConfirm } from "../lib/use-confirm";
import { useDebouncedValue } from "../lib/use-debounced-value";
import { useToast } from "../lib/use-toast";

const JOB_SORTABLE_COLUMNS = [
  { key: "id", label: "Job ID" },
  { key: "group_name", label: "Group Name" },
  { key: "status", label: "Status" },
  { key: "processed_rows", label: "Processed" },
  { key: "new_products", label: "Created" },
  { key: "updated_products", label: "Updated" },
  { key: "issues_found", label: "Issues" },
  { key: "started_at", label: "Date" },
];

function jobGroupLabel(job) {
  return job?.group_name || job?.filename || `Group #${job?.id}`;
}

const SKIP_REASON_LABELS = {
  blank_sku: "blank SKU",
  row_error: "row error",
  invalid_row: "invalid row",
};

function formatSkipSummary(job) {
  const skipped = job?.skipped_rows || 0;
  if (!skipped) return "";
  const counts = job?.skip_summary?.counts || {};
  const parts = Object.entries(counts).map(
    ([reason, count]) => `${count} ${SKIP_REASON_LABELS[reason] || reason}`
  );
  return parts.length ? parts.join(", ") : `${skipped} skipped`;
}
export default function Ingestion() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { confirm } = useConfirm();
  const [jobs, setJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);

  const [jobSearchInput, setJobSearchInput] = useState("");
  const jobSearchQuery = useDebouncedValue(jobSearchInput.trim(), 300);
  const [jobStatusFilter, setJobStatusFilter] = useState("");
  const [jobPage, setJobPage] = useState(1);
  const [jobPageSize, setJobPageSize] = useState(10);
  const [jobTotal, setJobTotal] = useState(0);
  const [jobSortBy, setJobSortBy] = useState("started_at");
  const [jobSortOrder, setJobSortOrder] = useState("desc");

  useEffect(() => {
    setJobPage(1);
  }, [jobSearchQuery, jobStatusFilter, jobPageSize, jobSortBy, jobSortOrder]);

  useEffect(() => {
    loadJobs();
  }, [jobPage, jobPageSize, jobSearchQuery, jobStatusFilter, jobSortBy, jobSortOrder]);

  const hasAnalyzingJob = jobs.some((job) => job.status === "analyzing");

  useEffect(() => {
    if (!hasAnalyzingJob) return undefined;

    const intervalId = window.setInterval(() => {
      loadJobs({ silent: true });
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [hasAnalyzingJob]);

  // Polling refetches stay silent so the table is not replaced by a spinner.
  async function loadJobs({ silent = false } = {}) {
    try {
      if (!silent) setJobsLoading(true);
      const data = await fetchIngestionJobs({
        skip: (jobPage - 1) * jobPageSize,
        limit: jobPageSize,
        search: jobSearchQuery || undefined,
        status: jobStatusFilter || undefined,
        sort_by: jobSortBy,
        sort_order: jobSortOrder,
      });
      setJobs(data.items);
      setJobTotal(data.total);

      const maxPage = Math.max(1, Math.ceil(data.total / jobPageSize));
      if (jobPage > maxPage) {
        setJobPage(maxPage);
      }
    } catch (err) {
      if (silent) return;
      setJobs([]);
      setJobTotal(0);
      showToast(err.message || "Failed to load ingestion jobs", "error");
    } finally {
      if (!silent) setJobsLoading(false);
    }
  }

  async function handleRefresh() {
    await loadJobs({ silent: true });
    showToast("Data refreshed", "info");
  }

  async function handleUploaded(result) {
    setJobPage(1);
    await loadJobs({ silent: true });
    if (result?.id && result.status !== "failed") {
      navigate(`/products/${result.id}`);
    }
  }

  async function handleDeleteRequest(job) {
    const label = jobGroupLabel(job);
    const confirmed = await confirm({
      title: "Delete Group",
      message:
        `Are you sure you want to delete "${label}" (#${job.id})? ` +
        "The products this group created will be deleted with it. " +
        "This action cannot be undone.",
      confirmLabel: "Delete",
      cancelLabel: "Cancel",
      variant: "danger",
    });
    if (!confirmed) return;

    try {
      await deleteIngestionJob(job.id);
      showToast("Group deleted", "success");
      await loadJobs({ silent: true });
    } catch (err) {
      showToast(err.message || "Failed to delete group", "error");
    }
  }

  async function handleRenameRequest(job) {
    const current = jobGroupLabel(job);
    const nextName = window.prompt("Group name", current);
    if (nextName == null) return;
    const trimmed = nextName.trim();
    if (!trimmed) {
      showToast("Group name cannot be empty", "error");
      return;
    }
    if (trimmed === current) return;

    try {
      await renameIngestionJob(job.id, trimmed);
      showToast("Group renamed", "success");
      await loadJobs({ silent: true });
    } catch (err) {
      showToast(err.message || "Failed to rename group", "error");
    }
  }

  function getStatusBadge(status) {
    switch (status) {
      case "completed":
        return <span className="badge badge-active">Completed</span>;
      case "completed_with_ai_errors":
        return <span className="badge badge-medium">Completed with AI Errors</span>;
      case "failed":
        return <span className="badge badge-high">Failed</span>;
      case "analyzing":
        return <span className="badge badge-medium">AI Analyzing</span>;
      case "processing":
        return <span className="badge badge-medium">Processing</span>;
      default:
        return <span className="badge badge-draft">{status}</span>;
    }
  }

  function handleJobSort(nextSortBy, nextSortOrder) {
    setJobSortBy(nextSortBy);
    setJobSortOrder(nextSortOrder);
    setJobPage(1);
  }

  const initialLoading = jobsLoading && jobs.length === 0;

  if (initialLoading) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading products...
      </div>
    );
  }

  return (
    <>
      <div className="animate-in">
        <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2>Products</h2>
            <p>Upload a CSV, then open that file to review its products</p>
          </div>
          <div className="page-header-actions">
            <button className="btn btn-ghost" onClick={handleRefresh} type="button">
              <RefreshCw size={16} />
              Refresh
            </button>
            <button className="btn btn-primary" onClick={() => setUploadOpen(true)} type="button">
              <Upload size={16} />
              Upload CSV
            </button>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3>Product Groups</h3>
          </div>

          <div className="toolbar" style={{ marginBottom: 12 }}>
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
                  placeholder="Search by group name..."
                  value={jobSearchInput}
                  onChange={(e) => setJobSearchInput(e.target.value)}
                  style={{ paddingLeft: 36 }}
                />
              </div>
            </div>
            <Select
              value={jobStatusFilter}
              onChange={(value) => {
                setJobStatusFilter(value);
                setJobPage(1);
              }}
              placeholder="All Statuses"
              ariaLabel="Filter jobs by status"
              options={[
                { value: "", label: "All Statuses" },
                { value: "completed", label: "Completed" },
                { value: "completed_with_ai_errors", label: "Completed with AI Errors" },
                { value: "analyzing", label: "AI Analyzing" },
                { value: "failed", label: "Failed" },
                { value: "processing", label: "Processing" },
                { value: "pending", label: "Pending" },
              ]}
            />
          </div>

          {jobsLoading ? (
            <div className="loading"><div className="spinner" />Loading files...</div>
          ) : jobs.length > 0 ? (
            <>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      {JOB_SORTABLE_COLUMNS.map((column) => (
                        <SortableColumnHeader
                          key={column.key}
                          columnKey={column.key}
                          label={column.label}
                          sortBy={jobSortBy}
                          sortOrder={jobSortOrder}
                          onSort={handleJobSort}
                        />
                      ))}
                      <th>Skipped</th>
                      <th>Products</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((job) => (
                      <tr
                        key={job.id}
                        className="table-row-clickable"
                        onClick={() => navigate(`/products/${job.id}`)}
                      >
                        <td style={{ fontFamily: "monospace", fontWeight: 600, color: "var(--text-secondary)" }}>
                          #{job.id}
                        </td>
                        <td
                          style={{
                            maxWidth: 220,
                            fontWeight: 500,
                          }}
                          title={job.filename ? `Last file: ${job.filename}` : undefined}
                        >
                          <div className="ingestion-group-cell">
                            <span className="ingestion-group-name">
                              {jobGroupLabel(job)}
                            </span>
                            <button
                              className="btn btn-ghost btn-sm"
                              onClick={(event) => {
                                event.stopPropagation();
                                handleRenameRequest(job);
                              }}
                              title="Rename group"
                              type="button"
                              aria-label={`Rename ${jobGroupLabel(job)}`}
                            >
                              <Pencil size={14} />
                            </button>
                          </div>
                          {job.filename && job.filename !== jobGroupLabel(job) ? (
                            <div className="ingestion-group-filename">{job.filename}</div>
                          ) : null}
                        </td>
                        <td>
                          {getStatusBadge(job.status)}
                          {job.status === "analyzing" && (
                            <div className="job-ai-progress ai-analyzing-status">
                              <span
                                className="spinner"
                                aria-hidden="true"
                                style={{ width: 12, height: 12, borderWidth: 2, margin: 0 }}
                              />
                              {job.ai_analyzed_rows || 0} analyzed
                              {job.ai_error_count > 0 ? `, ${job.ai_error_count} errors` : ""}
                            </div>
                          )}
                        </td>
                        <td>{job.processed_rows} / {job.total_rows}</td>
                        <td style={{ color: "var(--accent-green-light)" }}>
                          {job.new_products > 0 ? `+${job.new_products}` : 0}
                        </td>
                        <td style={{ color: "var(--accent-blue-light)" }}>
                          {job.updated_products}
                        </td>
                        <td style={{ color: job.issues_found > 0 ? "var(--accent-orange)" : "inherit" }}>
                          {job.issues_found}
                        </td>
                        <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                          {new Date(job.started_at).toLocaleDateString()}
                        </td>
                        <td
                          style={{
                            color: (job.skipped_rows || 0) > 0 ? "var(--accent-orange)" : "inherit",
                          }}
                          title={formatSkipSummary(job) || undefined}
                        >
                          {job.skipped_rows || 0}
                          {(job.skipped_rows || 0) > 0 && formatSkipSummary(job) ? (
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                              {formatSkipSummary(job)}
                            </div>
                          ) : null}
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: 6 }}>
                            <button
                              className="btn btn-ghost btn-sm"
                              onClick={(event) => {
                                event.stopPropagation();
                                navigate(`/products/${job.id}`);
                              }}
                              type="button"
                            >
                              Open
                              <ChevronRight size={14} />
                            </button>
                            <button
                              className="btn btn-ghost btn-sm"
                              onClick={(event) => {
                                event.stopPropagation();
                                handleDeleteRequest(job);
                              }}
                              title="Delete uploaded file"
                              style={{ color: "var(--accent-red)" }}
                              type="button"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <PaginationBar
                page={jobPage}
                pageSize={jobPageSize}
                total={jobTotal}
                onPageChange={setJobPage}
                onPageSizeChange={(size) => {
                  setJobPageSize(size);
                  setJobPage(1);
                }}
                itemLabel="files"
                pageSizeOptions={[5, 10, 15, 25]}
              />
            </>
          ) : (
            <div className="empty-state">
              <FileSpreadsheet size={40} />
              <h3>No Files Uploaded Yet</h3>
              <p>Upload a product catalog CSV to create a file and review its products.</p>
              <button className="btn btn-primary" onClick={() => setUploadOpen(true)} type="button">
                <Upload size={16} />
                Upload CSV
              </button>
            </div>
          )}
        </div>
      </div>

      <UploadProductFeedDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={handleUploaded}
      />
    </>
  );
}
