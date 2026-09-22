/**
 * CatalogIQ — Issue Field Helpers
 *
 * Shared naming for the product field a quality issue points at. Issues store
 * field names as product columns ("description"), the attribute bag
 * ("attributes"), prefixed attributes ("attributes.color"), or bare attribute
 * keys ("color"), so both the issue card and the product panes normalize here.
 */

const ATTRIBUTE_PREFIX = "attributes.";
const PRODUCT_FIELDS = new Set(["title", "description", "price", "brand", "category", "sku"]);

function titleCase(value) {
  return value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/**
 * Normalize an issue field name into a key the product panes can match.
 *
 * @param {string|null|undefined} fieldName Raw field name stored on the issue.
 * @returns {string|null} "title", "attributes", "attribute:color", or null.
 */
// This is a utility to normalize an issue field name for matching product fields
export function normalizeFieldKey(fieldName) {
  const name = (fieldName || "").trim().toLowerCase();
  if (!name) return null;
  if (name === "attributes") return "attributes";
  if (name.startsWith(ATTRIBUTE_PREFIX)) {
    const attrKey = name.slice(ATTRIBUTE_PREFIX.length).trim();
    return attrKey ? `attribute:${attrKey}` : "attributes";
  }
  if (PRODUCT_FIELDS.has(name)) return name;
  return `attribute:${name}`;
}

/**
 * Build a readable label for the flagged field.
 *
 * @param {string|null|undefined} fieldName Raw field name stored on the issue.
 * @returns {string} Label such as "Description" or "Attribute: Color".
 */
// This is a utility to turn an issue field name into a readable label
export function formatFieldLabel(fieldName) {
  const key = normalizeFieldKey(fieldName);
  if (!key) return "Whole Product";
  if (key === "attributes") return "All Attributes";
  if (key.startsWith("attribute:")) return `Attribute: ${titleCase(key.slice("attribute:".length))}`;
  return titleCase(key);
}

/**
 * Count how many open issues flag each product field.
 *
 * @param {Array<{field_name?: string|null}>} issues Open issues for one product.
 * @returns {Map<string, number>} Normalized field key to issue count.
 */
// This is a utility to count open issues per product field
export function countIssuesByField(issues) {
  const counts = new Map();
  issues.forEach((issue) => {
    const key = normalizeFieldKey(issue.field_name);
    if (!key) return;
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  return counts;
}

const SEVERITY_RANK = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

/**
 * Prefer a rule-sourced issue over an AI duplicate of the same field.
 *
 * @param {object} left First issue.
 * @param {object} right Second issue.
 * @returns {object} Issue that should remain in the review list.
 */
// This is a utility to pick the stronger issue when two flag the same field
export function preferIssue(left, right) {
  const leftRule = left?.suggestion_source === "ai" ? 0 : 1;
  const rightRule = right?.suggestion_source === "ai" ? 0 : 1;
  if (leftRule !== rightRule) {
    return leftRule > rightRule ? left : right;
  }
  const leftSeverity = SEVERITY_RANK[left?.severity] || 0;
  const rightSeverity = SEVERITY_RANK[right?.severity] || 0;
  return rightSeverity > leftSeverity ? right : left;
}

/**
 * Group open issues by product and keep one card per field.
 *
 * @param {Array<object>} issues Open issues for a file.
 * @param {Array<{id: number, sku?: string, title?: string}>} [products] Products in the same file.
 * @returns {Array<{productId: number, sku: string, title: string, issues: object[]}>}
 */
// This is a utility to group quality issues by product for review
export function groupIssuesByProduct(issues, products = []) {
  const productById = new Map(products.map((product) => [product.id, product]));
  const grouped = new Map();

  issues.forEach((issue) => {
    const productId = issue.product_id;
    if (!grouped.has(productId)) {
      const product = productById.get(productId);
      grouped.set(productId, {
        productId,
        sku: product?.sku || `Product ${productId}`,
        title: product?.title || "",
        issues: [],
      });
    }
    grouped.get(productId).issues.push(issue);
  });

  return Array.from(grouped.values()).map((group) => {
    const byField = new Map();
    group.issues.forEach((issue) => {
      const key = normalizeFieldKey(issue.field_name) || "product";
      const existing = byField.get(key);
      byField.set(key, existing ? preferIssue(existing, issue) : issue);
    });
    return {
      ...group,
      issues: Array.from(byField.values()),
    };
  });
}
