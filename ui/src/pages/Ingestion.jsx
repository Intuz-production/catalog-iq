/**
 * CatalogIQ — Ingestion Page
 *
 * Ingest raw CSV supplier data, view recent job history,
 * and review/resolve flagged data quality issues.
 */

import { useState, useEffect, useRef } from "react";
import {
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  RefreshCw,
  Info,
  Search,
} from "lucide-react";
import {
  uploadCSV,
  fetchIngestionJobs,
  fetchAllIssues,
  resolveIssue
} from "../api/client";
import DataIssueCard from "../components/DataIssueCard";
import PaginationBar from "../components/PaginationBar";
import Select from "../components/Select";
import SortableColumnHeader from "../components/SortableColumnHeader";
import { useDebouncedValue } from "../lib/use-debounced-value";
import { useToast } from "../lib/use-toast";
import { useConfirm } from "../lib/use-confirm";

const JOB_SORTABLE_COLUMNS = [
  { key: "id", label: "Job ID" },
  { key: "filename", label: "File Name" },
  { key: "status", label: "Status" },
  { key: "processed_rows", label: "Processed" },
  { key: "new_products", label: "Created" },
  { key: "updated_products", label: "Updated" },
  { key: "issues_found", label: "Issues" },
  { key: "started_at", label: "Date" },
];

export default function Ingestion() {
  const { showToast } = useToast();
  const { confirm } = useConfirm();
  const [jobs, setJobs] = useState([]);
  const [issues, setIssues] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [issuesLoading, setIssuesLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const [jobSearchInput, setJobSearchInput] = useState("");
  const jobSearchQuery = useDebouncedValue(jobSearchInput.trim(), 300);
  const [jobStatusFilter, setJobStatusFilter] = useState("");
  const [jobPage, setJobPage] = useState(1);
  const [jobPageSize, setJobPageSize] = useState(10);
  const [jobTotal, setJobTotal] = useState(0);
  const [jobSortBy, setJobSortBy] = useState("started_at");
  const [jobSortOrder, setJobSortOrder] = useState("desc");

  const [issueSearchInput, setIssueSearchInput] = useState("");
  const issueSearchQuery = useDebouncedValue(issueSearchInput.trim(), 300);
  const [issueSeverityFilter, setIssueSeverityFilter] = useState("");
  const [issueTypeFilter, setIssueTypeFilter] = useState("");
  const [issuePage, setIssuePage] = useState(1);
  const [issuePageSize, setIssuePageSize] = useState(10);
  const [issueTotal, setIssueTotal] = useState(0);
  const [issueSortBy, setIssueSortBy] = useState("created_at");
  const [issueSortOrder, setIssueSortOrder] = useState("desc");

  useEffect(() => {
    setJobPage(1);
  }, [jobSearchQuery, jobStatusFilter, jobPageSize, jobSortBy, jobSortOrder]);

  useEffect(() => {
    setIssuePage(1);
  }, [issueSearchQuery, issueSeverityFilter, issueTypeFilter, issuePageSize, issueSortBy, issueSortOrder]);

  useEffect(() => {
    loadJobs();
  }, [jobPage, jobPageSize, jobSearchQuery, jobStatusFilter, jobSortBy, jobSortOrder]);

  useEffect(() => {
    loadIssues();
  }, [issuePage, issuePageSize, issueSearchQuery, issueSeverityFilter, issueTypeFilter, issueSortBy, issueSortOrder]);

  async function loadJobs() {
    try {
      setJobsLoading(true);
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
      setJobs([]);
      setJobTotal(0);
      showToast(err.message || "Failed to load ingestion jobs", "error");
    } finally {
      setJobsLoading(false);
    }
  }

  async function loadIssues() {
    try {
      setIssuesLoading(true);
      const data = await fetchAllIssues({
        resolved: false,
        skip: (issuePage - 1) * issuePageSize,
        limit: issuePageSize,
        search: issueSearchQuery || undefined,
        severity: issueSeverityFilter || undefined,
        issue_type: issueTypeFilter || undefined,
        sort_by: issueSortBy,
        sort_order: issueSortOrder,
      });
      setIssues(data.items);
      setIssueTotal(data.total);

      const maxPage = Math.max(1, Math.ceil(data.total / issuePageSize));
      if (issuePage > maxPage) {
        setIssuePage(maxPage);
      }
    } catch (err) {
      setIssues([]);
      setIssueTotal(0);
      showToast(err.message || "Failed to load quality issues", "error");
    } finally {
      setIssuesLoading(false);
    }
  }

  async function handleRefresh() {
    await Promise.all([loadJobs(), loadIssues()]);
    showToast("Data refreshed", "info");
  }

  function handleDrag(e) {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }

  async function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await processUploadedFile(e.dataTransfer.files[0]);
    }
  }

  async function handleFileSelect(e) {
    if (e.target.files && e.target.files[0]) {
      await processUploadedFile(e.target.files[0]);
    }
  }

  async function processUploadedFile(file) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      showToast("Unsupported file type. Please upload a CSV file.", "error");
      return;
    }

    const confirmed = await confirm({
      title: "Upload Product Feed",
      message: `Upload "${file.name}" and start the ingestion pipeline? This will create or update products in your catalog.`,
      confirmLabel: "Upload",
      cancelLabel: "Cancel",
      variant: "primary",
    });
    if (!confirmed) {
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    try {
      setUploading(true);
      showToast(`Uploading ${file.name}...`, "info");
      const result = await uploadCSV(file);

      if (result.status === "completed") {
        showToast(`Successfully processed: ${result.processed_rows} rows`, "success");
      } else if (result.status === "failed") {
        showToast(`Ingestion failed: ${result.error_message || "Unknown error"}`, "error");
      } else {
        showToast("CSV file uploaded for processing", "info");
      }

      setJobPage(1);
      setIssuePage(1);
      await Promise.all([loadJobs(), loadIssues()]);
    } catch (err) {
      showToast(err.message || "Failed to upload CSV file", "error");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleResolveIssue(issue) {
    const confirmed = await confirm({
      title: "Resolve Data Issue",
      message: `Mark this issue as resolved?\n\n${issue.description}`,
      confirmLabel: "Resolve",
      cancelLabel: "Cancel",
      variant: "primary",
    });
    if (!confirmed) return;

    try {
      await resolveIssue(issue.id);
      showToast("Issue marked as resolved", "success");
      await loadIssues();
    } catch (err) {
      showToast(err.message || "Failed to resolve issue", "error");
    }
  }

  function getStatusBadge(status) {
    switch (status) {
      case "completed":
        return <span className="badge badge-active">Completed</span>;
      case "failed":
        return <span className="badge badge-high">Failed</span>;
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

  function handleIssueSortChange(value) {
    const [nextSortBy, nextSortOrder] = value.split(":");
    setIssueSortBy(nextSortBy);
    setIssueSortOrder(nextSortOrder);
    setIssuePage(1);
  }

  const initialLoading = jobsLoading && issuesLoading && jobs.length === 0 && issues.length === 0;

  if (initialLoading) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading ingestion platform...
      </div>
    );
  }

  return (
    <div className="animate-in">
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2>Data Ingestion</h2>
          <p>Import raw product data from supplier CSVs and normalize attributes</p>
        </div>
        <button className="btn btn-ghost" onClick={handleRefresh} disabled={uploading}>
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 24 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="card">
            <div className="card-header">
              <h3>Upload Product Feed</h3>
            </div>

            <div
              className={`upload-zone ${dragActive ? "dragover" : ""}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{ position: "relative" }}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept=".csv"
                style={{ display: "none" }}
                disabled={uploading}
              />
              {uploading ? (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                  <div className="spinner" style={{ width: 42, height: 42 }} />
                  <p style={{ fontWeight: 600 }}>Processing Ingestion Pipeline...</p>
                  <p className="upload-hint">Running product data normalization & cleaning</p>
                </div>
              ) : (
                <>
                  <Upload size={48} style={{ color: "var(--accent-blue-light)" }} />
                  <p style={{ fontWeight: 500, fontSize: "1.05rem", marginTop: 8 }}>
                    Drag & drop your supplier CSV here, or <span style={{ color: "var(--accent-blue-light)" }}>browse</span>
                  </p>
                  <p className="upload-hint">Supported file format: CSV (.csv) up to 10MB</p>
                </>
              )}
            </div>

            <div
              style={{
                marginTop: 20,
                padding: 16,
                background: "var(--bg-secondary)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-color)",
                fontSize: "0.82rem"
              }}
            >
              <h4 style={{ color: "var(--text-secondary)", fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                <Info size={14} /> Expected CSV Structure
              </h4>
              <p style={{ color: "var(--text-muted)", marginBottom: 10 }}>
                The CSV parser accepts columns mapping to standard attributes. Recommended fields include:
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {["sku *", "title *", "description", "price", "category", "brand", "specifications / specs"].map((field) => (
                  <span
                    key={field}
                    style={{
                      padding: "3px 8px",
                      background: "var(--bg-input)",
                      borderRadius: "var(--radius-sm)",
                      fontFamily: "monospace",
                      color: field.includes("*") ? "var(--accent-orange)" : "var(--text-secondary)"
                    }}
                  >
                    {field}
                  </span>
                ))}
              </div>
              <p style={{ color: "var(--text-muted)", fontSize: "0.76rem", marginTop: 10 }}>
                * Asterisk indicates required fields. Other fields will be automatically cleaned and stored in the product's structured JSON attributes.
              </p>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h3>Ingestion History</h3>
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
                    placeholder="Search by filename..."
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
                  { value: "failed", label: "Failed" },
                  { value: "processing", label: "Processing" },
                  { value: "pending", label: "Pending" },
                ]}
              />
            </div>

            {jobsLoading ? (
              <div className="loading"><div className="spinner" />Loading jobs...</div>
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
                      </tr>
                    </thead>
                    <tbody>
                      {jobs.map((job) => (
                        <tr key={job.id}>
                          <td style={{ fontFamily: "monospace", fontWeight: 600, color: "var(--text-secondary)" }}>
                            #{job.id}
                          </td>
                          <td
                            style={{
                              maxWidth: 160,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                              fontWeight: 500
                            }}
                            title={job.filename}
                          >
                            {job.filename}
                          </td>
                          <td>{getStatusBadge(job.status)}</td>
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
                  itemLabel="jobs"
                  pageSizeOptions={[5, 10, 15, 25]}
                />
              </>
            ) : (
              <div className="empty-state">
                <FileSpreadsheet size={40} />
                <h3>No Ingestion Jobs Yet</h3>
                <p>Upload a product catalog CSV to start the ingestion pipeline.</p>
              </div>
            )}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="card" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
            <div className="card-header" style={{ marginBottom: 12 }}>
              <h3>Open Quality Issues</h3>
              <span className={`badge ${issueTotal > 0 ? "badge-high" : "badge-active"}`}>
                {issueTotal} Flagged
              </span>
            </div>

            <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: 12 }}>
              Review contradiction flags and missing catalog details flagged during CSV normalization.
            </p>

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
                    placeholder="Search issues, SKU, or title..."
                    value={issueSearchInput}
                    onChange={(e) => setIssueSearchInput(e.target.value)}
                    style={{ paddingLeft: 36 }}
                  />
                </div>
              </div>
              <Select
                value={issueSeverityFilter}
                onChange={(value) => {
                  setIssueSeverityFilter(value);
                  setIssuePage(1);
                }}
                placeholder="All Severities"
                ariaLabel="Filter issues by severity"
                options={[
                  { value: "", label: "All Severities" },
                  { value: "critical", label: "Critical" },
                  { value: "high", label: "High" },
                  { value: "medium", label: "Medium" },
                  { value: "low", label: "Low" },
                ]}
              />
              <Select
                value={issueTypeFilter}
                onChange={(value) => {
                  setIssueTypeFilter(value);
                  setIssuePage(1);
                }}
                placeholder="All Issue Types"
                ariaLabel="Filter issues by type"
                options={[
                  { value: "", label: "All Issue Types" },
                  { value: "missing_description", label: "Missing Description" },
                  { value: "thin_content", label: "Thin Content" },
                  { value: "attribute_contradiction", label: "Attribute Contradiction" },
                  { value: "missing_attributes", label: "Missing Attributes" },
                  { value: "duplicate_title", label: "Duplicate Title" },
                  { value: "price_anomaly", label: "Price Anomaly" },
                ]}
              />
              <Select
                value={`${issueSortBy}:${issueSortOrder}`}
                onChange={handleIssueSortChange}
                ariaLabel="Sort quality issues"
                options={[
                  { value: "created_at:desc", label: "Newest First" },
                  { value: "created_at:asc", label: "Oldest First" },
                  { value: "severity:desc", label: "Highest Severity" },
                  { value: "severity:asc", label: "Lowest Severity" },
                ]}
              />
            </div>

            <div
              style={{
                flex: 1,
                overflowY: "auto",
                maxHeight: 520,
                paddingRight: 4,
                display: "flex",
                flexDirection: "column",
                gap: 12
              }}
            >
              {issuesLoading ? (
                <div className="loading"><div className="spinner" />Loading issues...</div>
              ) : issues.length > 0 ? (
                issues.map((issue) => (
                  <DataIssueCard
                    key={issue.id}
                    issue={issue}
                    onResolve={handleResolveIssue}
                  />
                ))
              ) : (
                <div className="empty-state" style={{ margin: "auto 0" }}>
                  <CheckCircle2 size={42} style={{ color: "var(--accent-green)" }} />
                  <h3>Clean Catalog!</h3>
                  <p>No active data issues match your filters.</p>
                </div>
              )}
            </div>

            {!issuesLoading && issueTotal > 0 && (
              <PaginationBar
                page={issuePage}
                pageSize={issuePageSize}
                total={issueTotal}
                onPageChange={setIssuePage}
                onPageSizeChange={(size) => {
                  setIssuePageSize(size);
                  setIssuePage(1);
                }}
                itemLabel="issues"
                pageSizeOptions={[5, 10, 15, 25]}
              />
            )}
          </div>
        </div>
      </div>

    </div>
  );
}
