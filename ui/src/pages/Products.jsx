/**
 * CatalogIQ — Products Page
 *
 * Product catalog management with server-side search, filtering, sorting, and pagination.
 */

import { useState, useEffect } from "react";
import { Search } from "lucide-react";
import {
  fetchProducts, fetchCategories, deleteProduct,
  generateSingleContent, fetchProductIssues, updateProduct,
} from "../api/client";
import ProductTable from "../components/ProductTable";
import ProductDetailDialog from "../components/ProductDetailDialog";
import Select from "../components/Select";
import { useToast } from "../lib/use-toast";
import { useConfirm } from "../lib/use-confirm";

const DEFAULT_PAGE_SIZE = 15;

export default function Products() {
  const { showToast } = useToast();
  const { confirm } = useConfirm();
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [sortBy, setSortBy] = useState("updated_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [productIssues, setProductIssues] = useState([]);
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadCategories();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery((prev) => {
        const next = searchInput.trim();
        if (prev !== next) {
          setPage(1);
        }
        return next;
      });
    }, 300);

    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    loadProducts();
  }, [page, pageSize, statusFilter, categoryFilter, searchQuery, sortBy, sortOrder]);

  async function loadProducts() {
    try {
      setLoading(true);
      const data = await fetchProducts({
        skip: (page - 1) * pageSize,
        limit: pageSize,
        status: statusFilter || undefined,
        category: categoryFilter || undefined,
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
      showToast(err.message || "Failed to load products", "error");
      setProducts([]);
      setTotal(0);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function loadCategories() {
    try {
      const cats = await fetchCategories();
      setCategories(cats);
    } catch (err) {
      showToast(err.message || "Failed to load categories", "error");
    }
  }

  function handleStatusFilterChange(value) {
    setStatusFilter(value);
    setPage(1);
  }

  function handleCategoryFilterChange(value) {
    setCategoryFilter(value);
    setPage(1);
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

  async function handleDeleteRequest(product) {
    const confirmed = await confirm({
      title: "Delete Product",
      message: `Are you sure you want to delete "${product.title}"? This action cannot be undone.`,
      confirmLabel: "Delete",
      cancelLabel: "Cancel",
      variant: "danger",
    });
    if (!confirmed) return;

    try {
      await deleteProduct(product.id);
      showToast("Product deleted", "success");
      loadProducts();
      if (selectedProduct?.id === product.id) setSelectedProduct(null);
    } catch (err) {
      showToast(err.message || "Failed to delete product", "error");
    }
  }

  async function handleGenerateContent(productId) {
    const product = products.find((item) => item.id === productId) || selectedProduct;
    const productTitle = product?.title || `Product #${productId}`;

    const confirmed = await confirm({
      title: "Generate SEO Content",
      message: `Generate SEO content for "${productTitle}"? This creates a description and SEO metadata from product attributes and may overwrite existing generated content.`,
      confirmLabel: "Generate",
      cancelLabel: "Cancel",
      variant: "primary",
    });
    if (!confirmed) return;

    try {
      setGenerating(true);
      const result = await generateSingleContent(productId);
      if (result.warnings?.length) {
        showToast(`Content generated with ${result.warnings.length} warning${result.warnings.length === 1 ? "" : "s"}`, "warning");
      } else {
        showToast("Content generated successfully", "success");
      }
      await loadProducts();
      if (selectedProduct?.id === productId) {
        const issues = await fetchProductIssues(productId);
        setProductIssues(issues);
        setSelectedProduct({
          ...selectedProduct,
          generated_description: result.generated_description,
          seo_title: result.seo_title,
          seo_keywords: result.seo_keywords,
          issue_count: issues.filter((issue) => !issue.resolved).length,
        });
      }
    } catch (err) {
      showToast(`Content generation failed: ${err.message}`, "error");
    } finally {
      setGenerating(false);
    }
  }

  async function handleViewDetails(product) {
    setSelectedProduct(product);
    setProductIssues([]);
    setIssuesLoading(true);

    try {
      const issues = await fetchProductIssues(product.id);
      setProductIssues(issues);
    } catch (err) {
      setProductIssues([]);
      showToast(err.message || "Failed to load product issues", "error");
    } finally {
      setIssuesLoading(false);
    }
  }

  function handleCloseDetails() {
    if (generating || saving) return;
    setSelectedProduct(null);
    setProductIssues([]);
    setIssuesLoading(false);
  }

  async function handleSaveProduct(productId, payload) {
    try {
      setSaving(true);
      const updated = await updateProduct(productId, payload);
      showToast("Product updated and quality checks re-run", "success");
      await loadProducts();
      setSelectedProduct(updated);
      const issues = await fetchProductIssues(productId);
      setProductIssues(issues);
    } catch (err) {
      showToast(err.message || "Failed to update product", "error");
      throw err;
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="animate-in">
      <div className="page-header">
        <h2>Products</h2>
        <p>Manage your product catalog</p>
      </div>

      {/* Toolbar */}
      <div className="toolbar">
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
        <div className="filters-row">
          <Select
            value={statusFilter}
            onChange={handleStatusFilterChange}
            placeholder="All Statuses"
            ariaLabel="Filter by status"
            options={[
              { value: "", label: "All Statuses" },
              { value: "active", label: "Active" },
              { value: "draft", label: "Draft" },
              { value: "flagged", label: "Flagged" },
              { value: "archived", label: "Archived" },
            ]}
          />
          <Select
            value={categoryFilter}
            onChange={handleCategoryFilterChange}
            placeholder="All Categories"
            ariaLabel="Filter by category"
            options={[
              { value: "", label: "All Categories" },
              ...categories.map((cat) => ({ value: cat, label: cat })),
            ]}
          />
        </div>
      </div>

      {/* Product Table */}
      <ProductTable
        products={products}
        loading={loading}
        onDelete={handleDeleteRequest}
        onGenerateContent={handleGenerateContent}
        onViewDetails={handleViewDetails}
        sortBy={sortBy}
        sortOrder={sortOrder}
        onSort={handleSort}
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
        onPageSizeChange={handlePageSizeChange}
      />
      </div>

      <ProductDetailDialog
        product={selectedProduct}
        issues={productIssues}
        issuesLoading={issuesLoading}
        generating={generating}
        saving={saving}
        onClose={handleCloseDetails}
        onGenerateContent={handleGenerateContent}
        onSave={handleSaveProduct}
      />
    </>
  );
}
