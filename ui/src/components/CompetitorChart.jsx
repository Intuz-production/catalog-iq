/**
 * CatalogIQ — Competitor Chart Component
 *
 * Displays competitor price comparison as a bar chart.
 */

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, Legend,
} from "recharts";

const SOURCE_COLORS = {
  amazon: "#ff9900",
  walmart: "#0071ce",
  flipkart: "#2f7ee4",
  ours: "#10b981",
};

export default function CompetitorChart({ product, competitorPrices = [] }) {
  if (!product || competitorPrices.length === 0) {
    return (
      <div className="empty-state" style={{ padding: 32 }}>
        <p>No competitor data available for this product.</p>
      </div>
    );
  }

  const chartData = [
    {
      name: "Your Price",
      price: product.price || 0,
      source: "ours",
    },
    ...competitorPrices
      .filter((cp) => cp.competitor_price)
      .map((cp) => ({
        name: cp.source.charAt(0).toUpperCase() + cp.source.slice(1),
        price: cp.competitor_price,
        source: cp.source,
      })),
  ];

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
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
            ${data.price.toFixed(2)}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
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
            tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            axisLine={{ stroke: "var(--border-color)" }}
            tickFormatter={(v) => `$${v}`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="price" radius={[6, 6, 0, 0]} maxBarSize={60}>
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
  );
}
