/**
 * CatalogIQ — Currency helpers for cross-currency price display.
 * Exchange rates must be supplied by the backend config API.
 */

/**
 * Convert a price between USD and INR using the configured exchange rate.
 */
export function normalizePrice(price, fromCurrency, toCurrency, exchangeRate) {
  if (!exchangeRate || exchangeRate <= 0) {
    throw new Error("A valid exchange rate is required for currency conversion.");
  }

  if (fromCurrency === toCurrency) {
    return price;
  }
  if (fromCurrency === "INR" && toCurrency === "USD") {
    return price / exchangeRate;
  }
  if (fromCurrency === "USD" && toCurrency === "INR") {
    return price * exchangeRate;
  }
  return price;
}

/**
 * Format a price with the appropriate currency symbol.
 */
export function formatPrice(price, currency) {
  const symbol = currency === "INR" ? "₹" : "$";
  return `${symbol}${price.toFixed(2)}`;
}
