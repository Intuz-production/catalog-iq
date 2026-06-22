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
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Info,
  Clock,
  Plus,
  Edit2
} from "lucide-react";
import {
  uploadCSV,
  fetchIngestionJobs,
  fetchAllIssues,
  resolveIssue
} from "../api/client";
import DataIssueCard from "../components/DataIssueCard";

export default function Ingestion() {
  const [jobs, setJobs] = useState([]);
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [toast, setToast] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      setLoading(true);
      const [jobsData, issuesData] = await Promise.all([
        fetchIngestionJobs(15),
        fetchAllIssues(false, 50)
      ]);
      setJobs(jobsData);
      setIssues(issuesData);
    } catch (err) {
      showToast("Failed to load ingestion data", "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    try {
      const [jobsData, issuesData] = await Promise.all([
        fetchIngestionJobs(15),
        fetchAllIssues(false, 50)
      ]);
      setJobs(jobsData);
      setIssues(issuesData);
      showToast("Data refreshed", "info");
    } catch (err) {
      showToast("Failed to refresh data", "error");
    }
  }

  function showToast(message, type = "info") {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }

  // Handle drag events
  function handleDrag(e) {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }

  // Handle drop event
  async function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await processUploadedFile(e.dataTransfer.files[0]);
    }
  }

  // Handle manual file selection
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

      // Refresh data
      const [jobsData, issuesData] = await Promise.all([
        fetchIngestionJobs(15),
        fetchAllIssues(false, 50)
      ]);
      setJobs(jobsData);
      setIssues(issuesData);
    } catch (err) {
      showToast(err.message || "Failed to upload CSV file", "error");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleResolveIssue(issueId) {
    try {
      await resolveIssue(issueId);
      showToast("Issue marked as resolved", "success");
      
      // Update local issue state
      setIssues(prev => prev.filter(i => i.id !== issueId));
    } catch (err) {
      showToast("Failed to resolve issue", "error");
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

  if (loading && jobs.length === 0 && issues.length === 0) {
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
        {/* Left Column: Upload & History */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {/* CSV File Drag & Drop Zone */}
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

            {/* CSV Format Guidance */}
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

          {/* Recent Ingestion Jobs */}
          <div className="card">
            <div className="card-header">
              <h3>Ingestion History</h3>
            </div>
            
            {jobs.length > 0 ? (
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Job ID</th>
                      <th>File Name</th>
                      <th>Status</th>
                      <th>Processed</th>
                      <th>Created</th>
                      <th>Updated</th>
                      <th>Issues</th>
                      <th>Date</th>
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
            ) : (
              <div className="empty-state">
                <FileSpreadsheet size={40} />
                <h3>No Ingestion Jobs Yet</h3>
                <p>Upload a product catalog CSV to start the ingestion pipeline.</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Flags & Contradictions */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div className="card" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
            <div className="card-header" style={{ marginBottom: 12 }}>
              <h3>Open Quality Issues</h3>
              <span className={`badge ${issues.length > 0 ? "badge-high" : "badge-active"}`}>
                {issues.length} Flagged
              </span>
            </div>
            
            <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: 16 }}>
              Review contradiction flags and missing catalog details flagged during CSV normalization.
            </p>

            <div
              style={{
                flex: 1,
                overflowY: "auto",
                maxHeight: 700,
                paddingRight: 4,
                display: "flex",
                flexDirection: "column",
                gap: 12
              }}
            >
              {issues.length > 0 ? (
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
                  <p>No active data issues or attribute contradictions found.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Toast Feedback */}
      {toast && (
        <div className="toast-container">
          <div className={`toast ${toast.type}`}>
            {toast.message}
          </div>
        </div>
      )}
    </div>
  );
}
