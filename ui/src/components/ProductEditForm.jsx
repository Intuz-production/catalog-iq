/**
 * CatalogIQ — Product Edit Form
 *
 * Editable fields for correcting catalog data and resolving quality issues.
 */

import { useState } from "react";
import Select from "./Select";

const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "draft", label: "Draft" },
  { value: "flagged", label: "Flagged" },
  { value: "archived", label: "Archived" },
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

    onSubmit({
      title,
      description: String(formData.get("description") || "").trim() || null,
      category: String(formData.get("category") || "").trim() || null,
      brand: String(formData.get("brand") || "").trim() || null,
      price,
      status,
      attributes: nextAttributes,
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
        <label htmlFor="product-edit-description">Description</label>
        <textarea
          id="product-edit-description"
          name="description"
          rows={4}
          defaultValue={product.description || ""}
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
            options={STATUS_OPTIONS}
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
