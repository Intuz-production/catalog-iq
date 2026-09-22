/**
 * CatalogIQ — CSV Column Mapper
 *
 * Confirms detected CSV columns against catalog fields before ingest.
 */

import Select from "./Select";

const FIELD_LABELS = {
  sku: "SKU",
  title: "Title",
  description: "Description",
  category: "Category",
  brand: "Brand",
  price: "Price",
  currency: "Currency",
  color: "Color",
  size: "Size",
  material: "Material",
  weight: "Weight",
  upc: "UPC",
  specifications: "Specifications",
};

/**
 * @typedef {Object} CsvColumnMapperProps
 * @property {string} filename
 * @property {string} encoding
 * @property {string} delimiter
 * @property {number} totalRows
 * @property {string[]} columns
 * @property {string[]} standardFields
 * @property {string[]} [warnings]
 * @property {Record<string, string>} mapping
 * @property {(column: string, field: string) => void} onMappingChange
 * @property {boolean} ingesting
 * @property {() => void} onCancel
 * @property {() => void} onConfirm
 */

// This is a component to confirm CSV column mapping before ingestion
export default function CsvColumnMapper({
  filename,
  encoding,
  delimiter,
  totalRows,
  columns,
  standardFields,
  warnings = [],
  mapping,
  onMappingChange,
  ingesting,
  onCancel,
  onConfirm,
}) {
  const hasSku = Boolean(mapping.sku);
  const fieldByColumn = Object.fromEntries(
    Object.entries(mapping)
      .filter(([, column]) => Boolean(column))
      .map(([field, column]) => [column, field])
  );

  const fieldOptions = [
    { value: "", label: "Ignore" },
    ...standardFields.map((field) => ({
      value: field,
      label: field === "sku" ? `${FIELD_LABELS[field] || field} *` : FIELD_LABELS[field] || field,
    })),
  ];

  return (
    <div className="csv-mapper">
      <div className="csv-mapper-header">
        <div>
          <h4>Confirm Column Mapping</h4>
          <p>
            {filename} · {totalRows} rows · {encoding} · delimiter {delimiter}
          </p>
        </div>
      </div>

      {warnings.length > 0 && (
        <ul className="csv-mapper-warnings">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      <p className="csv-mapper-required">
        SKU * · {hasSku ? mapping.sku : "Not mapped"}
      </p>

      <div className="csv-mapper-fields">
        {columns.map((column) => (
          <label key={column} className="csv-mapper-field">
            <span>{column}</span>
            <Select
              size="sm"
              value={fieldByColumn[column] || ""}
              onChange={(field) => onMappingChange(column, field)}
              options={fieldOptions}
              placeholder="Ignore"
              ariaLabel={`Map ${column} to catalog field`}
              disabled={ingesting}
            />
          </label>
        ))}
      </div>

      <div className="csv-mapper-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={ingesting}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onConfirm}
          disabled={ingesting || !hasSku}
        >
          {ingesting ? "Starting ingest..." : "Start Ingest"}
        </button>
      </div>
    </div>
  );
}
