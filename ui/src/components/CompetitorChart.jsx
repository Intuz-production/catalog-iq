/**
 * CatalogIQ — Competitor Chart Component
 *
 * Displays competitor price comparison as a bar chart.
 */

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import { formatPrice, normalizePrice } from "../lib/currency";

/** Matches marketplace badge accents in index.css */
const SOURCE_COLORS = {
  amazon: "#f59e0b",
  walmart: "#60a5fa",
  ebay: "#8b5cf6",
  target: "#06b6d4",
  flipkart: "#60a5fa",
  ours: "#34d399",
};

function getLatestPricesBySource(competitorPrices) {
  const latestBySource = new Map();

  for (const entry of competitorPrices) {
    if (!entry.competitor_price || entry.is_simulated) {
      continue;
    }

    const existing = latestBySource.get(entry.source);
    if (!existing) {
      latestBySource.set(entry.source, entry);
      continue;
    }

    const existingTime = existing.scraped_at ? new Date(existing.scraped_at).getTime() : 0;
    const entryTime = entry.scraped_at ? new Date(entry.scraped_at).getTime() : 0;
    if (entryTime > existingTime) {
      latestBySource.set(entry.source, entry);
    }
  }

  return Array.from(latestBySource.values());
}

export default function CompetitorChart({
  product,
  competitorPrices = [],
  exchangeRate,
}) {
  const latestPrices = getLatestPricesBySource(competitorPrices);
  const displayCurrency = product?.currency || "USD";

  if (!exchangeRate || exchangeRate <= 0) {
    return (
      <div className="empty-state" style={{ padding: 32 }}>
        <p>Exchange rate not loaded. Refresh the page to compare prices.</p>
      </div>
    );
  }

  if (!product || latestPrices.length === 0) {
    return (
      <div className="empty-state" style={{ padding: 32 }}>
        <p>No competitor data available for this product.</p>
      </div>
    );
  }

  const chartData = [
    {
      name: "Your Price",
      displayPrice: product.price || 0,
      originalPrice: product.price || 0,
      originalCurrency: displayCurrency,
      source: "ours",
      isSimulated: false,
      matchScore: null,
    },
    ...latestPrices.map((cp) => {
      const originalCurrency = cp.competitor_currency || "USD";
      const sourceLabel = cp.source.charAt(0).toUpperCase() + cp.source.slice(1);
      return {
        name: sourceLabel,
        displayPrice: normalizePrice(
          cp.competitor_price,
          originalCurrency,
          displayCurrency,
          exchangeRate,
        ),
        originalPrice: cp.competitor_price,
        originalCurrency,
        source: cp.source,
        matchScore: cp.match_score,
      };
    }),
  ];

  const displayPrices = chartData.map((entry) => entry.displayPrice);
  const minPrice = Math.min(...displayPrices);
  const maxPrice = Math.max(...displayPrices);
  const range = maxPrice - minPrice;
  const padding = range > 0 ? range * 0.12 : maxPrice * 0.08;
  const yDomain = [
    Math.max(0, Math.floor(minPrice - padding)),
    Math.ceil(maxPrice + padding),
  ];

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const showOriginal = data.originalCurrency !== displayCurrency;

      return (
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border-color)",
            borderRadius: "var(--radius-md)",
            padding: "10px 14px",
            fontSize: "0.82rem",
          }}
        >
          <p style={{ fontWeight: 600, marginBottom: 4 }}>{data.name}</p>
          <p style={{ color: SOURCE_COLORS[data.source] || "var(--text-primary)" }}>
            {formatPrice(data.displayPrice, displayCurrency)}
          </p>
          {data.matchScore != null && (
            <p style={{ color: "var(--text-muted)", marginTop: 4 }}>
              Match confidence: {Math.round(data.matchScore * 100)}%
            </p>
          )}
          {showOriginal && (
            <p style={{ color: "var(--text-muted)", marginTop: 4 }}>
              Original: {formatPrice(data.originalPrice, data.originalCurrency)}
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div style={{ width: "100%" }}>
      <div style={{ width: "100%", height: 280 }}>
      <ResponsiveContainer>
        <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--border-color)"
            vertical={false}
          />
          <XAxis
            dataKey="name"
            tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            axisLine={{ stroke: "var(--border-color)" }}
          />
          <YAxis
            domain={yDomain}
            tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            axisLine={{ stroke: "var(--border-color)" }}
            tickFormatter={(value) => formatPrice(value, displayCurrency)}
          />
          <Tooltip content={<CustomTooltip />} cursor={false} />
          <Bar dataKey="displayPrice" radius={[6, 6, 0, 0]} maxBarSize={60}>
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={SOURCE_COLORS[entry.source] || "var(--accent-blue)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}
