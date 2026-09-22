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
 * @typedef {Object} ColumnMappingConfig
 * @property {"standard" | "custom" | "ignore"} type
 * @property {string} value
 */

/**
 * @typedef {Object} CsvColumnMapperProps
 * @property {string} filename
 * @property {string} encoding
 * @property {string} delimiter
 * @property {number} totalRows
 * @property {string[]} columns
 * @property {string[]} standardFields
 * @property {string[]} [warnings]
 * @property {Record<string, ColumnMappingConfig>} mapping
 * @property {(column: string, config: ColumnMappingConfig) => void} onMappingChange
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
  const hasSku = Object.values(mapping).some((m) => m.type === "standard" && m.value === "sku");
  const skuColumn = Object.entries(mapping).find(
    ([, m]) => m.type === "standard" && m.value === "sku"
  )?.[0];

  const fieldOptions = [
    { value: "__custom__", label: "Custom Attribute..." },
    { value: "__ignore__", label: "Ignore Column" },
    ...standardFields.map((field) => ({
      value: `__standard__${field}`,
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
        SKU * · {hasSku ? skuColumn : "Not mapped"}
      </p>

      <div className="csv-mapper-fields">
        {columns.map((column) => {
          const config = mapping[column] || { type: "ignore", value: "" };
          let selectValue = "__ignore__";
          if (config.type === "standard") selectValue = `__standard__${config.value}`;
          if (config.type === "custom") selectValue = "__custom__";

          return (
            <div key={column} className="csv-mapper-field">
              <label>
                <span>{column}</span>
                <Select
                  size="sm"
                  value={selectValue}
                  onChange={(val) => {
                    if (val === "__ignore__") {
                      onMappingChange(column, { type: "ignore", value: "" });
                    } else if (val === "__custom__") {
                      onMappingChange(column, { type: "custom", value: column });
                    } else if (val.startsWith("__standard__")) {
                      onMappingChange(column, { type: "standard", value: val.replace("__standard__", "") });
                    }
                  }}
                  options={fieldOptions}
                  placeholder="Select mapping"
                  ariaLabel={`Map ${column} to catalog field`}
                  disabled={ingesting}
                />
              </label>
              {config.type === "custom" && (
                <input
                  type="text"
                  className="csv-mapper-custom-input"
                  value={config.value}
                  onChange={(e) => onMappingChange(column, { type: "custom", value: e.target.value })}
                  placeholder="Attribute name"
                  disabled={ingesting}
                  aria-label={`Custom attribute name for ${column}`}
                />
              )}
            </div>
          );
        })}
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
