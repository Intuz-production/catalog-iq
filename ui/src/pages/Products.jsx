/**
 * CatalogIQ — Products Page
 *
 * Product catalog management with search, filtering, and detail views.
 */

import { useState, useEffect } from "react";
import { Search, Filter, X } from "lucide-react";
import {
  fetchProducts, fetchCategories, deleteProduct,
  generateSingleContent, fetchProductIssues,
} from "../api/client";
import ProductTable from "../components/ProductTable";
import ContentPreview from "../components/ContentPreview";
import DataIssueCard from "../components/DataIssueCard";

export default function Products() {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [productIssues, setProductIssues] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    loadProducts();
    loadCategories();
  }, [statusFilter, categoryFilter]);

  async function loadProducts() {
    try {
      setLoading(true);
      const data = await fetchProducts({
        status: statusFilter || undefined,
        category: categoryFilter || undefined,
        search: search || undefined,
        limit: 100,
      });
      setProducts(data);
    } catch (err) {
      showToast("Failed to load products", "error");
    } finally {
      setLoading(false);
    }
  }

  async function loadCategories() {
    try {
      const cats = await fetchCategories();
      setCategories(cats);
    } catch (err) {
      console.error("Failed to load categories:", err);
    }
  }

  async function handleSearch(e) {
    e.preventDefault();
    loadProducts();
  }

  async function handleDelete(productId) {
    if (!confirm("Are you sure you want to delete this product?")) return;
    try {
      await deleteProduct(productId);
      showToast("Product deleted", "success");
      loadProducts();
      if (selectedProduct?.id === productId) setSelectedProduct(null);
    } catch (err) {
      showToast("Failed to delete product", "error");
    }
  }

  async function handleGenerateContent(productId) {
    try {
      setGenerating(true);
      const result = await generateSingleContent(productId);
      showToast("Content generated successfully", "success");
      loadProducts();
      if (selectedProduct?.id === productId) {
        setSelectedProduct({
          ...selectedProduct,
          generated_description: result.generated_description,
          seo_title: result.seo_title,
          seo_keywords: result.seo_keywords,
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
    try {
      const issues = await fetchProductIssues(product.id);
      setProductIssues(issues);
    } catch (err) {
      setProductIssues([]);
    }
  }

  function showToast(message, type = "info") {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }

  return (
    <div className="animate-in">
      <div className="page-header">
        <h2>Products</h2>
        <p>Manage your product catalog</p>
      </div>

      {/* Toolbar */}
      <div className="toolbar">
        <form onSubmit={handleSearch} className="search-input">
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
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ paddingLeft: 36 }}
            />
          </div>
        </form>
        <div className="filters-row">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="draft">Draft</option>
            <option value="flagged">Flagged</option>
            <option value="archived">Archived</option>
          </select>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Product Table */}
      <ProductTable
        products={products}
        loading={loading}
        onDelete={handleDelete}
        onGenerateContent={handleGenerateContent}
        onViewDetails={handleViewDetails}
      />

      {/* Product Detail Panel */}
      {selectedProduct && (
        <div
          style={{
            position: "fixed",
            top: 0,
            right: 0,
            bottom: 0,
            width: 520,
            background: "var(--bg-secondary)",
            borderLeft: "1px solid var(--border-color)",
            zIndex: 200,
            overflow: "auto",
            padding: 24,
            boxShadow: "-8px 0 30px rgba(0,0,0,0.5)",
            animation: "slideIn 0.3s ease",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <h3>{selectedProduct.title}</h3>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setSelectedProduct(null)}
            >
              <X size={16} />
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
            <div>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>SKU</span>
              <p style={{ fontFamily: "monospace" }}>{selectedProduct.sku}</p>
            </div>
            <div>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Price</span>
              <p>{selectedProduct.price ? `${selectedProduct.currency} ${selectedProduct.price.toFixed(2)}` : "N/A"}</p>
            </div>
            <div>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Category</span>
              <p>{selectedProduct.category || "N/A"}</p>
            </div>
            <div>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Brand</span>
              <p>{selectedProduct.brand || "N/A"}</p>
            </div>
          </div>

          {/* Attributes */}
          {selectedProduct.attributes && Object.keys(selectedProduct.attributes).length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <h4 style={{ fontSize: "0.85rem", marginBottom: 8 }}>Attributes</h4>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {Object.entries(selectedProduct.attributes).map(([key, val]) => (
                  <span
                    key={key}
                    style={{
                      padding: "4px 10px",
                      background: "var(--bg-input)",
                      borderRadius: 50,
                      fontSize: "0.78rem",
                      border: "1px solid var(--border-color)",
                    }}
                  >
                    <strong style={{ color: "var(--text-secondary)" }}>{key}:</strong>{" "}
                    {String(val)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Content */}
          <div style={{ marginBottom: 20 }}>
            <ContentPreview product={selectedProduct} />
          </div>

          {!selectedProduct.generated_description && (
            <button
              className="btn btn-primary"
              onClick={() => handleGenerateContent(selectedProduct.id)}
              disabled={generating}
              style={{ width: "100%", justifyContent: "center", marginBottom: 20 }}
            >
              {generating ? (
                <>
                  <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2, margin: 0 }} />
                  Generating...
                </>
              ) : (
                "Generate SEO Description"
              )}
            </button>
          )}

          {/* Issues */}
          {productIssues.length > 0 && (
            <div>
              <h4 style={{ fontSize: "0.85rem", marginBottom: 10 }}>
                Data Issues ({productIssues.length})
              </h4>
              {productIssues.map((issue) => (
                <DataIssueCard key={issue.id} issue={issue} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="toast-container">
          <div className={`toast ${toast.type}`}>{toast.message}</div>
        </div>
      )}
    </div>
  );
}
