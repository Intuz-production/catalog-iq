/**
 * CatalogIQ — Pagination Bar Component
 *
 * Reusable footer controls for server-paginated data tables.
 */

import Select from "./Select";

export default function PaginationBar({
  page = 1,
  pageSize = 15,
  total = 0,
  onPageChange,
  onPageSizeChange,
  itemLabel = "items",
  pageSizeOptions = [10, 15, 25, 50],
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);

  return (
    <div className="pagination-bar">
      <div className="pagination-summary">
        Showing {rangeStart}–{rangeEnd} of {total} {itemLabel}
      </div>
      <div className="pagination-controls">
        <div className="pagination-size">
          <span>Rows per page</span>
          <Select
            value={String(pageSize)}
            onChange={(value) => onPageSizeChange?.(Number(value))}
            size="sm"
            ariaLabel="Rows per page"
            options={pageSizeOptions.map((size) => ({
              value: String(size),
              label: String(size),
            }))}
          />
        </div>
        <span className="pagination-page-label">
          Page {page} of {totalPages}
        </span>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => onPageChange?.(page - 1)}
          disabled={page <= 1}
        >
          Previous
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => onPageChange?.(page + 1)}
          disabled={page >= totalPages}
        >
          Next
        </button>
      </div>
    </div>
  );
}
