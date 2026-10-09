/**
 * CatalogIQ — Product update mapping
 *
 * Maps AI "Give a Thought" field names to ProductUpdate payload keys so applied
 * values match what the product detail UI displays.
 */

const WOO_FIELD_KEYS = new Set([
  "title",
  "description",
  "category",
  "brand",
  "price",
  "stock",
  "in_stock",
  "image_url",
]);

/**
 * Product column to update for description copy shown in ContentPreview.
 *
 * @param {{ generated_description?: string|null }} product
 * @returns {"generated_description"|"description"}
 */
export function descriptionStorageKey(product) {
  return product?.generated_description ? "generated_description" : "description";
}

/**
 * Parse WooCommerce in-stock values from AI or form text.
 *
 * @param {unknown} after
 * @returns {boolean}
 */
export function parseInStockValue(after) {
  if (after === true) return true;
  if (after === false) return false;
  const val = String(after ?? "").trim().toLowerCase();
  if (val === "" || val === "true" || val === "1" || val === "yes") return true;
  if (
    val === "false" ||
    val === "0" ||
    val === "no" ||
    val === "outofstock" ||
    val === "out of stock"
  ) {
    return false;
  }
  return Boolean(after);
}

/**
 * Match an attribute key case-insensitively to existing product attributes.
 *
 * @param {Record<string, unknown>|null|undefined} attributes
 * @param {string} rawKey
 * @returns {string}
 */
export function resolveAttributeKey(attributes, rawKey) {
  const target = String(rawKey || "").trim();
  if (!target) return target;
  const keys = Object.keys(attributes || {});
  const match = keys.find((key) => key.toLowerCase() === target.toLowerCase());
  return match ?? target;
}

/**
 * Map one accepted AI change to a ProductUpdate key/value pair.
 *
 * @param {{ field: string, after: string }} change
 * @param {Object} product
 * @returns {{ key: string, value: unknown }|null}
 */
export function mapThoughtChangeToUpdate(change, product) {
  const { field, after } = change;
  if (!WOO_FIELD_KEYS.has(field)) {
    return null;
  }
  if (field === "price") {
    const parsed = Number.parseFloat(after);
    return { key: "price", value: Number.isNaN(parsed) ? null : parsed };
  }
  if (field === "stock") {
    const parsed = Number.parseInt(after, 10);
    return { key: "stock", value: Number.isNaN(parsed) ? null : parsed };
  }
  if (field === "in_stock") {
    return { key: "in_stock", value: parseInStockValue(after) };
  }
  if (field === "description") {
    return { key: descriptionStorageKey(product), value: after };
  }
  return { key: field, value: after };
}

/**
 * Build a ProductUpdate payload from accepted thought changes only.
 *
 * @param {Object} product
 * @param {Array<{ field: string, after: string }>} selectedChanges
 * @returns {{ payload: Record<string, unknown>, unmappedFields: string[] }}
 */
export function buildThoughtApplyPayload(product, selectedChanges) {
  const payload = {};
  const newAttributes = { ...(product.attributes || {}) };
  let attributesChanged = false;
  const unmappedFields = [];

  for (const change of selectedChanges) {
    const mapped = mapThoughtChangeToUpdate(change, product);
    if (mapped) {
      payload[mapped.key] = mapped.value;
      continue;
    }
    if (change.field.startsWith("attribute:")) {
      const rawKey = change.field.replace("attribute:", "");
      const attrKey = resolveAttributeKey(newAttributes, rawKey);
      newAttributes[attrKey] = change.after;
      attributesChanged = true;
      continue;
    }
    unmappedFields.push(change.field);
  }

  if (attributesChanged) {
    payload.attributes = newAttributes;
  }

  return { payload, unmappedFields };
}

/**
 * Normalize any product save payload before PATCH (edit form, Give a Thought, etc.).
 *
 * @param {Object} product
 * @param {Record<string, unknown>} payload
 * @returns {Record<string, unknown>}
 */
export function normalizeProductUpdatePayload(product, payload) {
  const next = { ...payload };
  if (
    Object.prototype.hasOwnProperty.call(next, "description") &&
    !Object.prototype.hasOwnProperty.call(next, "generated_description") &&
    product?.generated_description
  ) {
    next.generated_description = next.description;
    delete next.description;
  }
  if (typeof next.in_stock === "string") {
    next.in_stock = parseInStockValue(next.in_stock);
  }
  return next;
}
