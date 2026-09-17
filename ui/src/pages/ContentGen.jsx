/**
 * CatalogIQ — Content Generator Page
 *
 * Batch SEO content generation with tone control and result previews.
 */

import { useState, useEffect } from "react";
import { Sparkles, RefreshCw, Search } from "lucide-react";
import { generateContent, fetchProductsNeedingContent } from "../api/client";
import ContentPreview from "../components/ContentPreview";
import PaginationBar from "../components/PaginationBar";
import Select from "../components/Select";
import SortableColumnHeader from "../components/SortableColumnHeader";
import { useDebouncedValue } from "../lib/use-debounced-value";
import { useToast } from "../lib/use-toast";
import { useConfirm } from "../lib/use-confirm";

const DEFAULT_PAGE_SIZE = 15;

const SORTABLE_COLUMNS = [
  { key: "sku", label: "SKU" },
  { key: "title", label: "Title" },
  { key: "category", label: "Category" },
];

const TONE_OPTIONS = [
  { value: "professional", label: "Professional" },
  { value: "casual", label: "Casual" },
  { value: "luxury", label: "Luxury" },
  { value: "technical", label: "Technical" },
];

export default function ContentGen() {
  const { showToast } = useToast();
  const { confirm } = useConfirm();
  const [products, setProducts] = useState([]);
  const [selected, setSelected] = useState([]);
  const [tone, setTone] = useState("professional");
  const [includeSeo, setIncludeSeo] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState("");
  const searchQuery = useDebouncedValue(searchInput.trim(), 300);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [sortBy, setSortBy] = useState("updated_at");
  const [sortOrder, setSortOrder] = useState("desc");

  useEffect(() => {
    setPage(1);
  }, [searchQuery, pageSize, sortBy, sortOrder]);

  useEffect(() => {
    loadProducts();
  }, [page, pageSize, searchQuery, sortBy, sortOrder]);

  async function loadProducts() {
    try {
      setLoading(true);
      const data = await fetchProductsNeedingContent({
        skip: (page - 1) * pageSize,
        limit: pageSize,
        search: searchQuery || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      setProducts(data.items);
      setTotal(data.total);

      const maxPage = Math.max(1, Math.ceil(data.total / pageSize));
      if (page > maxPage) {
        setPage(maxPage);
      }

      return data;
    } catch (err) {
      setProducts([]);
      setTotal(0);
      showToast(err.message || "Failed to load products", "error");
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    const data = await loadProducts();
    if (data) {
      showToast(`Loaded ${data.total} product${data.total === 1 ? "" : "s"} needing content`, "info");
    }
  }

  async function handleGenerate() {
    if (selected.length === 0) {
      showToast("Select at least one product", "error");
      return;
    }

    const confirmed = await confirm({
      title: "Generate SEO Content",
      message: `Generate content for ${selected.length} product${selected.length === 1 ? "" : "s"} using the "${tone}" tone${includeSeo ? " with SEO metadata" : ""}? Existing generated content will be replaced.`,
      confirmLabel: "Generate",
      cancelLabel: "Cancel",
      variant: "primary",
    });
    if (!confirmed) return;

    try {
      setGenerating(true);
      const res = await generateContent(selected, tone, includeSeo);
      setResults(res);
      const ok = res.filter((item) => item.success).length;
      const failed = selected.length - ok;
      const warningCount = res.reduce((count, item) => count + (item.warnings?.length || 0), 0);

      if (failed > 0) {
        showToast(`Generated content for ${ok}/${selected.length} products (${failed} failed)`, "warning");
      } else if (warningCount > 0) {
        showToast(`Generated content for ${ok}/${selected.length} products with ${warningCount} warning${warningCount === 1 ? "" : "s"}`, "warning");
      } else {
        showToast(`Generated content for ${ok}/${selected.length} products`, "success");
      }

      setSelected([]);
      loadProducts();
    } catch (err) {
      showToast(err.message || "Content generation failed", "error");
    } finally {
      setGenerating(false);
    }
  }

  function toggleSelect(id) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }

  function selectAllOnPage() {
    const pageIds = products.map((product) => product.id);
    const allSelected = pageIds.every((id) => selected.includes(id));
    if (allSelected) {
      setSelected((prev) => prev.filter((id) => !pageIds.includes(id)));
      return;
    }
    setSelected((prev) => [...new Set([...prev, ...pageIds])]);
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

  const pageIds = products.map((product) => product.id);
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selected.includes(id));

  return (
    <div className="animate-in">
      <div className="page-header">
        <h2>Content Generator</h2>
        <p>Generate SEO descriptions and metadata from structured product attributes</p>
      </div>

      <div className="toolbar content-gen-toolbar">
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
        <Select
          value={tone}
          onChange={setTone}
          ariaLabel="Content generation tone"
          options={TONE_OPTIONS}
        />
        <label className="content-gen-option">
          <input
            type="checkbox"
            checked={includeSeo}
            onChange={(event) => setIncludeSeo(event.target.checked)}
            disabled={generating}
          />
          <span>Include SEO metadata</span>
        </label>
        <button type="button" className="btn btn-ghost btn-sm" onClick={selectAllOnPage}>
          {allPageSelected ? "Deselect Page" : "Select Page"}
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleGenerate}
          disabled={generating || selected.length === 0}
        >
          {generating ? (
            <>
              <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2, margin: 0 }} />
              Generating...
            </>
          ) : (
            <>
              <Sparkles size={16} />
              Generate ({selected.length})
            </>
          )}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={handleRefresh}>
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="loading">
          <div className="spinner" />
          Loading...
        </div>
      ) : products.length > 0 ? (
        <>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th style={{ width: 40 }}></th>
                  {SORTABLE_COLUMNS.map((column) => (
                    <SortableColumnHeader
                      key={column.key}
                      columnKey={column.key}
                      label={column.label}
                      sortBy={sortBy}
                      sortOrder={sortOrder}
                      onSort={handleSort}
                    />
                  ))}
                  <th>Brand</th>
                </tr>
              </thead>
              <tbody>
                {products.map((product) => (
                  <tr key={product.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.includes(product.id)}
                        onChange={() => toggleSelect(product.id)}
                      />
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: "0.82rem" }}>{product.sku}</td>
                    <td style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {product.title}
                    </td>
                    <td>{product.category || "—"}</td>
                    <td>{product.brand || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <PaginationBar
            page={page}
            pageSize={pageSize}
            total={total}
            onPageChange={setPage}
            onPageSizeChange={handlePageSizeChange}
            itemLabel="products"
          />
        </>
      ) : (
        <div className="empty-state">
          <h3>All products have generated content</h3>
          <p>No products match your search or still need SEO content.</p>
        </div>
      )}

      {results.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-header">
            <h3>Generation Results</h3>
          </div>
          {results.map((result) => (
            <div key={result.product_id} className="content-gen-result">
              <div className="content-gen-result-header">
                <div>
                  <div className="content-gen-result-title">
                    {result.title || `Product #${result.product_id}`}
                  </div>
                  {result.sku && <div className="content-gen-result-sku">SKU: {result.sku}</div>}
                </div>
                <span className={`badge ${result.success ? "badge-active" : "badge-high"}`}>
                  {result.success ? "Success" : "Failed"}
                </span>
              </div>
              {result.success ? (
                <ContentPreview
                  product={{
                    generated_description: result.generated_description,
                    seo_title: result.seo_title,
                    seo_keywords: result.seo_keywords,
                  }}
                  warnings={result.warnings || []}
                  wordCount={result.word_count}
                />
              ) : (
                <p className="content-gen-result-error">{result.error}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
