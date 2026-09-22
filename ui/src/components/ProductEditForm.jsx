/**
 * CatalogIQ — Product Edit Form
 *
 * Editable fields for correcting catalog data and resolving quality issues.
 */

import { useState } from "react";
import Select from "./Select";

const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "flagged", label: "Flagged" },
];

const IN_STOCK_OPTIONS = [
  { value: "true", label: "Yes — In Stock" },
  { value: "false", label: "No — Out of Stock" },
];

/**
 * @typedef {Object} ProductEditFormProps
 * @property {Object} product
 * @property {boolean} [saving]
 * @property {(payload: Object) => void} onSubmit
 * @property {() => void} onCancel
 */

// This is a component to edit core product catalog fields
export default function ProductEditForm({ product, saving = false, onSubmit, onCancel }) {
  const attrs = product.attributes || {};
  const [status, setStatus] = useState(product.status || "active");
  const [inStock, setInStock] = useState(
    product.in_stock === false ? "false" : "true"
  );

  const statusOptions = STATUS_OPTIONS.some((opt) => opt.value === product.status)
    ? STATUS_OPTIONS
    : (product.status ? [...STATUS_OPTIONS, { value: product.status, label: product.status.charAt(0).toUpperCase() + product.status.slice(1) }] : STATUS_OPTIONS);

  function handleSubmit(event) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);

    const color = String(formData.get("color") || "").trim();
    const size = String(formData.get("size") || "").trim();
    const material = String(formData.get("material") || "").trim();
    const nextAttributes = { ...attrs };

    if (color) nextAttributes.color = color;
    else delete nextAttributes.color;

    if (size) nextAttributes.size = size;
    else delete nextAttributes.size;

    if (material) nextAttributes.material = material;
    else delete nextAttributes.material;

    const priceRaw = String(formData.get("price") || "").trim();
    let price = null;
    if (priceRaw) {
      const parsed = Number.parseFloat(priceRaw);
      if (Number.isNaN(parsed)) {
        return;
      }
      price = parsed;
    }

    const title = String(formData.get("title") || "").trim();
    if (!title) {
      return;
    }

    const stockRaw = String(formData.get("stock") || "").trim();
    const stock = stockRaw !== "" ? Math.max(0, Math.round(Number(stockRaw))) : null;

    onSubmit({
      title,
      description: String(formData.get("description") || "").trim() || null,
      category: String(formData.get("category") || "").trim() || null,
      brand: String(formData.get("brand") || "").trim() || null,
      price,
      status,
      attributes: nextAttributes,
      seo_title: String(formData.get("seo_title") || "").trim() || null,
      seo_keywords: String(formData.get("seo_keywords") || "").trim() || null,
      stock: Number.isNaN(stock) ? null : stock,
      in_stock: inStock !== "false",
      image_url: String(formData.get("image_url") || "").trim() || null,
    });
  }

  return (
    <form className="product-edit-form" onSubmit={handleSubmit}>
      <div className="form-group">
        <label htmlFor="product-edit-title">Title</label>
        <input
          id="product-edit-title"
          name="title"
          type="text"
          defaultValue={product.title || ""}
          required
          disabled={saving}
        />
      </div>

      <div className="form-group">
        <label htmlFor="product-edit-description">
          Description
          {product.generated_description ? (
            <span style={{ fontWeight: 400, color: "var(--text-muted)", fontSize: "0.8rem", marginLeft: 6 }}>
              (AI-generated)
            </span>
          ) : null}
        </label>
        <textarea
          id="product-edit-description"
          name="description"
          rows={4}
          defaultValue={product.generated_description || product.description || ""}
          placeholder="Enter a product description"
          disabled={saving}
        />
      </div>

      <div className="product-edit-grid">
        <div className="form-group">
          <label htmlFor="product-edit-category">Category</label>
          <input
            id="product-edit-category"
            name="category"
            type="text"
            defaultValue={product.category || ""}
            disabled={saving}
          />
        </div>
        <div className="form-group">
          <label htmlFor="product-edit-brand">Brand</label>
          <input
            id="product-edit-brand"
            name="brand"
            type="text"
            defaultValue={product.brand || ""}
            disabled={saving}
          />
        </div>
        <div className="form-group">
          <label htmlFor="product-edit-price">Price ({product.currency || "USD"})</label>
          <input
            id="product-edit-price"
            name="price"
            type="number"
            min="0"
            step="0.01"
            defaultValue={product.price ?? ""}
            disabled={saving}
          />
        </div>
        <div className="form-group">
          <span className="product-edit-field-label">Status</span>
          <Select
            value={status}
            onChange={setStatus}
            ariaLabel="Product status"
            options={statusOptions}
            disabled={saving}
          />
        </div>
      </div>

      <div className="product-edit-grid">
        <div className="form-group">
          <label htmlFor="product-edit-color">Color</label>
          <input
            id="product-edit-color"
            name="color"
            type="text"
            defaultValue={attrs.color || ""}
            disabled={saving}
          />
        </div>
        <div className="form-group">
          <label htmlFor="product-edit-size">Size</label>
          <input
            id="product-edit-size"
            name="size"
            type="text"
            defaultValue={attrs.size || ""}
            disabled={saving}
          />
        </div>
        <div className="form-group">
          <label htmlFor="product-edit-material">Material</label>
          <input
            id="product-edit-material"
            name="material"
            type="text"
            defaultValue={attrs.material || ""}
            disabled={saving}
          />
        </div>
      </div>

      <div className="product-edit-divider" />
      <h4 className="product-edit-section-title">SEO &amp; Content</h4>

      <div className="form-group">
        <label htmlFor="product-edit-seo-title">SEO Title</label>
        <input
          id="product-edit-seo-title"
          name="seo_title"
          type="text"
          maxLength={200}
          defaultValue={product.seo_title || ""}
          placeholder="e.g. Best Running Shoes — Brand Name"
          disabled={saving}
        />
      </div>

      <div className="form-group">
        <label htmlFor="product-edit-seo-keywords">SEO Keywords</label>
        <input
          id="product-edit-seo-keywords"
          name="seo_keywords"
          type="text"
          defaultValue={product.seo_keywords || ""}
          placeholder="comma-separated, e.g. running shoes, eco footwear"
          disabled={saving}
        />
      </div>

      <div className="product-edit-divider" />
      <h4 className="product-edit-section-title">Inventory &amp; Media</h4>

      <div className="product-edit-grid">
        <div className="form-group">
          <label htmlFor="product-edit-stock">Stock Quantity</label>
          <input
            id="product-edit-stock"
            name="stock"
            type="number"
            min="0"
            step="1"
            defaultValue={product.stock ?? ""}
            placeholder="e.g. 100"
            disabled={saving}
          />
        </div>
        <div className="form-group">
          <span className="product-edit-field-label">In Stock?</span>
          <Select
            value={inStock}
            onChange={setInStock}
            ariaLabel="In stock status"
            options={IN_STOCK_OPTIONS}
            disabled={saving}
          />
        </div>
      </div>

      <div className="form-group">
        <label htmlFor="product-edit-image-url">Image URL</label>
        <input
          id="product-edit-image-url"
          name="image_url"
          type="url"
          defaultValue={product.image_url || ""}
          placeholder="https://example.com/product-image.jpg"
          disabled={saving}
        />
      </div>

      <p className="product-edit-hint">
        Saving will re-run data quality checks and update flagged issues automatically.
      </p>

      <div className="product-edit-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </div>
    </form>
  );
}
