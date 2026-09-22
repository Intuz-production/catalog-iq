/**
 * CatalogIQ — Upload Product Feed Dialog
 *
 * Modal for selecting a supplier CSV, confirming column mapping, and starting ingest.
 * Supports creating a new group or appending into an existing group.
 */

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Download, FileSpreadsheet, Info, Upload, X } from "lucide-react";
import CsvColumnMapper from "./CsvColumnMapper";
import Select from "./Select";
import {
  downloadSampleCsv,
  fetchIngestionJobs,
  previewCSV,
  uploadCSV,
} from "../api/client";
import { useConfirm } from "../lib/use-confirm";
import { useToast } from "../lib/use-toast";

const EXPECTED_FIELDS = [
  "sku *",
  "title",
  "description",
  "price",
  "category",
  "brand",
  "specifications",
];

const APPENDABLE_STATUSES = new Set([
  "completed",
  "completed_with_ai_errors",
  "analyzing",
]);

const NEW_GROUP_VALUE = "__new__";

/**
 * @typedef {Object} UploadProductFeedDialogProps
 * @property {boolean} open
 * @property {() => void} onClose
 * @property {(job: Object) => void} [onUploaded]
 */

function jobGroupLabel(job) {
  return job.group_name || job.filename || `Group #${job.id}`;
}

// This is a component to upload and map a supplier CSV in a dialog
export default function UploadProductFeedDialog({ open, onClose, onUploaded }) {
  const { showToast } = useToast();
  const { confirm } = useConfirm();
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [pendingFile, setPendingFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [columnMapping, setColumnMapping] = useState({});
  const [sampleDownloading, setSampleDownloading] = useState(false);
  const [destinationValue, setDestinationValue] = useState(NEW_GROUP_VALUE);
  const [groupName, setGroupName] = useState("");
  const [groupNameTouched, setGroupNameTouched] = useState(false);
  const [existingJobs, setExistingJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  const isBusy = uploading || previewLoading;
  const isNewGroup = destinationValue === NEW_GROUP_VALUE;
  const existingJobId = isNewGroup ? "" : destinationValue;

  useEffect(() => {
    if (!open) {
      resetPreview();
      setDragActive(false);
      setUploading(false);
      setPreviewLoading(false);
      setDestinationValue(NEW_GROUP_VALUE);
      setGroupName("");
      setGroupNameTouched(false);
      setExistingJobs([]);
      return;
    }

    let cancelled = false;
    async function loadJobs() {
      try {
        setJobsLoading(true);
        const data = await fetchIngestionJobs({
          skip: 0,
          limit: 100,
          sort_by: "started_at",
          sort_order: "desc",
        });
        if (cancelled) return;
        const appendable = (data.items || []).filter((job) =>
          APPENDABLE_STATUSES.has(job.status)
        );
        setExistingJobs(appendable);
      } catch (err) {
        if (!cancelled) {
          setExistingJobs([]);
          showToast(err.message || "Could not load existing groups", "error");
        }
      } finally {
        if (!cancelled) setJobsLoading(false);
      }
    }

    loadJobs();
    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;

    function handleKeyDown(event) {
      if (event.key === "Escape" && !isBusy) {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, isBusy, onClose]);

  function resetPreview() {
    setPendingFile(null);
    setPreview(null);
    setColumnMapping({});
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleDrag(event) {
    event.preventDefault();
    event.stopPropagation();
    if (event.type === "dragenter" || event.type === "dragover") {
      setDragActive(true);
    } else if (event.type === "dragleave") {
      setDragActive(false);
    }
  }

  async function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);

    if (event.dataTransfer.files?.[0]) {
      await loadCsvPreview(event.dataTransfer.files[0]);
    }
  }

  async function handleFileSelect(event) {
    if (event.target.files?.[0]) {
      await loadCsvPreview(event.target.files[0]);
    }
  }

  async function loadCsvPreview(file) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      showToast("Unsupported file type. Please upload a CSV file.", "error");
      return;
    }

    try {
      setPreviewLoading(true);
      const data = await previewCSV(file);
      const nextMapping = {};
      data.standard_fields.forEach((field) => {
        nextMapping[field] = data.suggested_mapping[field] || "";
      });
      setPendingFile(file);
      setPreview(data);
      setColumnMapping(nextMapping);
      if (isNewGroup && !groupNameTouched) {
        setGroupName(file.name);
      }
      if (data.warnings?.length) {
        showToast(data.warnings[0], "info");
      }
    } catch (err) {
      resetPreview();
      showToast(err.message || "Could not preview CSV file.", "error");
    } finally {
      setPreviewLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function handleMappingChange(column, field) {
    setColumnMapping((current) => {
      const next = { ...current };
      for (const [mappedField, mappedColumn] of Object.entries(next)) {
        if (mappedColumn === column) {
          next[mappedField] = "";
        }
      }
      if (field) {
        next[field] = column;
      }
      return next;
    });
  }

  function handleDestinationChange(value, context = {}) {
    setDestinationValue(value);
    if (value === NEW_GROUP_VALUE) {
      const fromSearch = String(context.searchQuery || "").trim();
      if (fromSearch) {
        setGroupName(fromSearch.slice(0, 255));
        setGroupNameTouched(true);
        return;
      }
      setGroupNameTouched(false);
      if (pendingFile) {
        setGroupName(pendingFile.name);
      } else {
        setGroupName("");
      }
      return;
    }

    const selected = existingJobs.find((job) => String(job.id) === String(value));
    if (selected) {
      // Prefill once on selection; leave Group Name editable afterward.
      setGroupName(jobGroupLabel(selected));
      setGroupNameTouched(false);
    }
  }

  async function handleConfirmIngest() {
    if (!pendingFile) return;

    if (!isNewGroup && !existingJobId) {
      showToast("Select an existing group to add products into.", "error");
      return;
    }

    const trimmedName = groupName.trim();
    const targetLabel = !isNewGroup
      ? jobGroupLabel(
          existingJobs.find((job) => String(job.id) === String(existingJobId)) || {
            id: existingJobId,
            group_name: trimmedName,
          }
        )
      : trimmedName || pendingFile.name;

    const confirmed = await confirm({
      title: isNewGroup ? "Upload Product Feed" : "Add to Group",
      message: isNewGroup
        ? `Ingest "${pendingFile.name}" as group "${targetLabel}"? This will create or update products in your catalog.`
        : `Add rows from "${pendingFile.name}" into group "${targetLabel}"?`,
      confirmLabel: isNewGroup ? "Start Ingest" : "Add to Group",
      cancelLabel: "Cancel",
      variant: "primary",
    });
    if (!confirmed) return;

    const mappingPayload = Object.fromEntries(
      Object.entries(columnMapping).filter(([, column]) => Boolean(column))
    );

    try {
      setUploading(true);
      showToast(`Uploading ${pendingFile.name}...`, "info");
      const result = await uploadCSV(pendingFile, mappingPayload, {
        ingestionJobId: isNewGroup ? undefined : Number(existingJobId),
        // Always send group name so append can rename an existing group.
        groupName: trimmedName || pendingFile.name,
      });

      if (result.status === "completed") {
        const skipNote =
          result.skipped_rows > 0 ? ` (${result.skipped_rows} skipped)` : "";
        showToast(
          `Successfully processed: ${result.processed_rows} rows${skipNote}`,
          "success"
        );
      } else if (result.status === "analyzing") {
        const skipNote =
          result.skipped_rows > 0 ? ` ${result.skipped_rows} rows skipped.` : "";
        showToast(
          `Processed ${result.processed_rows} rows. AI analysis is running in the background.${skipNote}`,
          "info"
        );
      } else if (result.status === "failed") {
        showToast(`Ingestion failed: ${result.error_message || "Unknown error"}`, "error");
      } else {
        showToast("CSV file uploaded for processing", "info");
      }

      resetPreview();
      onClose();
      if (onUploaded) {
        await onUploaded(result);
      }
    } catch (err) {
      showToast(err.message || "Failed to upload CSV file", "error");
    } finally {
      setUploading(false);
    }
  }

  function handleClose() {
    if (isBusy) return;
    resetPreview();
    onClose();
  }

  async function handleDownloadSample(event) {
    event.preventDefault();
    event.stopPropagation();
    if (sampleDownloading || isBusy) return;

    try {
      setSampleDownloading(true);
      await downloadSampleCsv();
      showToast("Sample CSV downloaded", "success");
    } catch (err) {
      showToast(err.message || "Failed to download sample CSV", "error");
    } finally {
      setSampleDownloading(false);
    }
  }

  if (!open) return null;

  const destinationOptions = [
    { value: NEW_GROUP_VALUE, label: "New group", pinned: true },
    ...existingJobs.map((job) => ({
      value: String(job.id),
      label: `${jobGroupLabel(job)} (#${job.id})`,
    })),
  ];

  return createPortal(
    <div
      className="product-detail-overlay"
      role="presentation"
      onClick={isBusy ? undefined : handleClose}
    >
      <div
        className="product-detail-dialog upload-feed-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-feed-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="product-detail-header">
          <div className="product-detail-header-main">
            <div className="product-detail-title-row">
              <h2 id="upload-feed-title">Upload Product Feed</h2>
            </div>
            <p className="product-detail-subtitle">
              Import a supplier CSV into a new or existing group
            </p>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm product-detail-close"
            aria-label="Close upload dialog"
            onClick={handleClose}
            disabled={isBusy}
          >
            <X size={16} />
          </button>
        </div>

        <div className="product-detail-body product-detail-body-single">
          <div className="upload-feed-group-fields">
            <div className="upload-feed-field">
              <Select
                label="Destination"
                className="select-full-width"
                value={destinationValue}
                onChange={handleDestinationChange}
                options={destinationOptions}
                placeholder={jobsLoading ? "Loading groups..." : "Select destination"}
                disabled={isBusy || jobsLoading}
                ariaLabel="Select upload destination"
                searchable
                searchPlaceholder="Search groups..."
              />
            </div>

            <div className="upload-feed-field">
              <label className="upload-feed-field-label" htmlFor="upload-group-name">
                Group Name
              </label>
              <input
                id="upload-group-name"
                type="text"
                value={groupName}
                maxLength={255}
                placeholder="e.g. Spring Catalog"
                disabled={isBusy}
                onChange={(event) => {
                  setGroupName(event.target.value);
                  setGroupNameTouched(true);
                }}
              />
            </div>
          </div>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".csv"
            style={{ display: "none" }}
            disabled={isBusy}
          />

          {preview ? (
            <div className="upload-feed-selected">
              <span className="upload-feed-selected-icon" aria-hidden="true">
                <FileSpreadsheet size={18} />
              </span>
              <div className="upload-feed-selected-main">
                <strong>{preview.filename}</strong>
                <small>
                  {uploading
                    ? "Running product data normalization & cleaning..."
                    : `${preview.total_rows} rows · ${preview.encoding} · delimiter ${preview.delimiter}`}
                </small>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={isBusy}
              >
                Change File
              </button>
            </div>
          ) : (
            <div
              className={`upload-zone ${dragActive ? "dragover" : ""}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              {previewLoading ? (
                <div className="upload-feed-status">
                  <div className="spinner" style={{ width: 42, height: 42 }} />
                  <p style={{ fontWeight: 600 }}>Reading CSV File...</p>
                  <p className="upload-hint">Detecting encoding, delimiter, and columns</p>
                </div>
              ) : (
                <>
                  <Upload size={48} style={{ color: "var(--accent-blue-light)" }} />
                  <p style={{ fontWeight: 500, fontSize: "1.05rem", marginTop: 8 }}>
                    Drag & drop your supplier CSV here, or{" "}
                    <span style={{ color: "var(--accent-blue-light)" }}>browse</span>
                  </p>
                  <p className="upload-hint">
                    Supported file format: CSV (.csv) up to 10MB. Mapping is confirmed before ingest.
                  </p>
                </>
              )}
            </div>
          )}

          {preview || previewLoading ? null : (
            <div className="upload-feed-sample">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={handleDownloadSample}
                disabled={sampleDownloading || isBusy}
              >
                <Download size={14} />
                {sampleDownloading ? "Downloading..." : "Download Sample CSV"}
              </button>
              <span>Try AI ingest analysis with the bundled demo catalog.</span>
            </div>
          )}

          {preview && (
            <CsvColumnMapper
              filename={preview.filename}
              encoding={preview.encoding}
              delimiter={preview.delimiter}
              totalRows={preview.total_rows}
              columns={preview.columns}
              standardFields={preview.standard_fields}
              warnings={preview.warnings}
              mapping={columnMapping}
              onMappingChange={handleMappingChange}
              ingesting={uploading}
              onCancel={resetPreview}
              onConfirm={handleConfirmIngest}
            />
          )}

          {preview ? null : (
            <div className="upload-feed-structure">
              <h4>
                <Info size={14} /> Expected CSV Structure
              </h4>
              <p>
                The CSV parser maps supplier headers to catalog fields. After upload you can confirm
                or change that mapping.
              </p>
              <div className="upload-feed-field-tags">
                {EXPECTED_FIELDS.map((field) => (
                  <span
                    key={field}
                    className={field.includes("*") ? "upload-feed-field-required" : undefined}
                  >
                    {field}
                  </span>
                ))}
              </div>
              <p className="upload-feed-structure-note">
                SKU is required. Title is recommended; if it is missing, the SKU is used. Other mapped
                fields are cleaned and stored on the product, including specifications.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
