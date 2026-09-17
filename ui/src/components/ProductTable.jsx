/**
 * CatalogIQ — Product Table Component
 *
 * Displays products in a server-driven sortable table with pagination.
 */

import { Eye, Sparkles, Trash2, AlertTriangle } from "lucide-react";
import PaginationBar from "./PaginationBar";
import SortableColumnHeader from "./SortableColumnHeader";

const STATUS_CLASSES = {
  active: "badge-active",
  draft: "badge-draft",
  flagged: "badge-flagged",
  archived: "badge-archived",
};

const SORTABLE_COLUMNS = [
  { key: "sku", label: "SKU" },
  { key: "title", label: "Title" },
  { key: "category", label: "Category" },
  { key: "brand", label: "Brand" },
  { key: "price", label: "Price" },
  { key: "status", label: "Status" },
];

export default function ProductTable({
  products = [],
  onGenerateContent,
  onDelete,
  onViewDetails,
  loading = false,
  sortBy = "updated_at",
  sortOrder = "desc",
  onSort,
  page = 1,
  pageSize = 15,
  total = 0,
  onPageChange,
  onPageSizeChange,
}) {
  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading products...
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="empty-state">
        <Package size={48} />
        <h3>No products found</h3>
        <p>Try adjusting your search or filters, or upload a CSV to get started.</p>
      </div>
    );
  }

  return (
    <>
      <div className="table-container">
        <table>
          <thead>
            <tr>
              {SORTABLE_COLUMNS.map((column) => (
                <SortableColumnHeader
                  key={column.key}
                  columnKey={column.key}
                  label={column.label}
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onSort={onSort}
                />
              ))}
              <th>Issues</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {products.map((product) => (
              <tr key={product.id} className="animate-in">
                <td style={{ fontFamily: "monospace", fontSize: "0.82rem" }}>
                  {product.sku}
                </td>
                <td style={{ maxWidth: 280 }}>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {product.title}
                  </div>
                </td>
                <td>{product.category || "—"}</td>
                <td>{product.brand || "—"}</td>
                <td>
                  {product.price
                    ? `${product.currency} ${product.price.toFixed(2)}`
                    : "—"}
                </td>
                <td>
                  <span className={`badge ${STATUS_CLASSES[product.status] || "badge-draft"}`}>
                    {product.status}
                  </span>
                </td>
                <td>
                  {product.issue_count > 0 ? (
                    <span className="badge badge-high">
                      <AlertTriangle size={12} />
                      {product.issue_count}
                    </span>
                  ) : (
                    <span style={{ color: "var(--text-muted)" }}>0</span>
                  )}
                </td>
                <td>
                  <div style={{ display: "flex", gap: 6 }}>
                    {onViewDetails && (
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => onViewDetails(product)}
                        title="View details"
                      >
                        <Eye size={14} />
                      </button>
                    )}
                    {onGenerateContent && (
                      <button
                        className={`btn btn-sm ${product.generated_description ? "btn-ghost" : "btn-primary"}`}
                        onClick={() => onGenerateContent(product.id)}
                        title={product.generated_description ? "Regenerate SEO content" : "Generate SEO content"}
                      >
                        <Sparkles size={14} />
                      </button>
                    )}
                    {onDelete && (
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => onDelete(product)}
                        title="Delete product"
                        style={{ color: "var(--accent-red)" }}
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <PaginationBar
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
        itemLabel="products"
      />
    </>
  );
}

function Package({ size }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m7.5 4.27 9 5.15" />
      <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
      <path d="m3.3 7 8.7 5 8.7-5" />
      <path d="M12 22V12" />
    </svg>
  );
}
