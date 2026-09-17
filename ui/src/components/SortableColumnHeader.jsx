/**
 * CatalogIQ — Sortable Column Header Component
 *
 * Clickable table header that toggles server-side sort direction.
 */

import { ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react";

export default function SortableColumnHeader({
  columnKey,
  label,
  sortBy,
  sortOrder,
  onSort,
  style,
}) {
  function handleClick() {
    if (!onSort) return;
    if (sortBy === columnKey) {
      onSort(columnKey, sortOrder === "asc" ? "desc" : "asc");
      return;
    }
    onSort(columnKey, "asc");
  }

  function renderSortIcon() {
    if (sortBy !== columnKey) {
      return <ArrowUpDown size={12} className="sort-icon sort-icon-muted" />;
    }
    return sortOrder === "asc"
      ? <ArrowUp size={12} className="sort-icon sort-icon-active" />
      : <ArrowDown size={12} className="sort-icon sort-icon-active" />;
  }

  return (
    <th style={style}>
      <button type="button" className="table-sort-button" onClick={handleClick}>
        {label}
        {renderSortIcon()}
      </button>
    </th>
  );
}
