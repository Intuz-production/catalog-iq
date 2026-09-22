import { useState, useEffect } from "react";
import { BarChart3, RefreshCw, TrendingDown, Package, Bell, Check } from "lucide-react";
import {
  fetchProducts, fetchAlerts, fetchCompetitorPrices,
  triggerCompetitorScrape, acknowledgeAlert,
} from "../api/client";
import CompetitorChart from "../components/CompetitorChart";
import Select from "../components/Select";
import { useToast } from "../lib/use-toast";
import { useConfirm } from "../lib/use-confirm";
import { useCompetitorConfig } from "../lib/use-competitor-config";
import { formatPrice } from "../lib/currency";

export default function Competitors() {
  const { showToast } = useToast();
  const { confirm } = useConfirm();
  const [alerts, setAlerts] = useState([]);
  const [prices, setPrices] = useState([]);
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [productPrices, setProductPrices] = useState([]);
  const [scraping, setScraping] = useState(false);
  const [scrapeResult, setScrapeResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const { config: monitoringConfig, reload: reloadMonitoringConfig } = useCompetitorConfig();

  useEffect(() => { loadData(); }, []);

  const marketplaceLabels = monitoringConfig?.sources?.map((source) => source.label).join(", ") || "configured marketplaces";
  const enabledSourceIds = monitoringConfig?.sources?.map((source) => source.id) || null;

  async function loadData() {
    try {
      setLoading(true);
      const [a, pr, p, config] = await Promise.all([
        fetchAlerts({ acknowledged: false, limit: 50 }),
        fetchCompetitorPrices({ limit: 50 }),
        fetchProducts({ limit: 100 }),
        reloadMonitoringConfig(),
      ]);
      setAlerts(a); setPrices(pr); setProducts(p.items);
      return { alerts: a, prices: pr, products: p, config };
    } catch (err) {
      showToast(err.message || "Failed to load competitor data", "error");
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    const data = await loadData();
    if (data) {
      showToast("Competitor data refreshed", "info");
    }
  }

  async function handleScrape() {
    const confirmed = await confirm({
      title: "Run Competitor Scrape",
      message: `Start a competitor price scrape across ${marketplaceLabels}? This may take a few minutes.`,
      confirmLabel: "Run Scrape",
      cancelLabel: "Cancel",
      variant: "primary",
    });
    if (!confirmed) return;

    try {
      setScraping(true); setScrapeResult(null);
      const res = await triggerCompetitorScrape(null, enabledSourceIds);
      setScrapeResult(res.summary);
      const live = res.summary.live_results ?? 0;
      const skipped = res.summary.skipped_results ?? 0;
      showToast(
        `Scraped ${res.summary.products_scraped} products — ${live} live, ${skipped} skipped`,
        live > 0 ? "success" : "warning",
      );
      loadData();
    } catch (err) {
      showToast(err.message || "Competitor scrape failed", "error");
    }
    finally { setScraping(false); }
  }

  async function handleAcknowledge(alert) {
    const confirmed = await confirm({
      title: "Acknowledge Alert",
      message: `Mark this alert as acknowledged?\n\n${alert.message}`,
      confirmLabel: "Acknowledge",
      cancelLabel: "Cancel",
      variant: "primary",
    });
    if (!confirmed) return;

    try {
      await acknowledgeAlert(alert.id);
      setAlerts(prev => prev.filter(a => a.id !== alert.id));
      showToast("Alert acknowledged", "success");
    } catch (err) {
      showToast(err.message || "Failed to acknowledge alert", "error");
    }
  }

  async function handleSelectProduct(product) {
    setSelectedProduct(product);
    try {
      const pp = await fetchCompetitorPrices({ product_id: product.id, limit: 10 });
      setProductPrices(pp);
      if (pp.length === 0) {
        showToast("No competitor prices found for this product", "info");
      }
    } catch (err) {
      setProductPrices([]);
      showToast(err.message || "Failed to load competitor prices", "error");
    }
  }

  if (loading) return <div className="loading"><div className="spinner"/>Loading...</div>;

  const ALERT_ICONS = {
    undercut: TrendingDown, out_of_stock: Package, price_drop: TrendingDown, price_increase: BarChart3, back_in_stock: Package,
  };

  const configuredSources = monitoringConfig?.sources ?? [];
  const currencyBySource = Object.fromEntries(
    configuredSources.map((source) => [source.id, source.currency || "USD"]),
  );

  function formatAlertPrice(price, source) {
    if (price == null) return "—";
    const currency = currencyBySource[source] || "USD";
    return formatPrice(price, currency);
  }

  const alertGroups = configuredSources.map((source) => ({
    id: source.id,
    platform: source.platform || source.label,
    region: source.region || monitoringConfig?.region?.toUpperCase() || "",
    label: source.label,
    alerts: alerts.filter((alert) => alert.source === source.id),
  }));

  return (
    <div className="animate-in">
      <div className="page-header">
        <h2>Competitor Monitoring</h2>
        <p>
          Track competitor prices across {marketplaceLabels}
          {monitoringConfig?.region ? ` (${monitoringConfig.region.toUpperCase()} region)` : ""}
        </p>
      </div>

      <div className="toolbar">
        <button className="btn btn-primary" onClick={handleScrape} disabled={scraping}>
          {scraping ? <><div className="spinner" style={{width:16,height:16,borderWidth:2,margin:0}}/>Scraping...</> : <><BarChart3 size={16}/>Run Competitor Scrape</>}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={handleRefresh}><RefreshCw size={14}/>Refresh</button>
      </div>

      {scrapeResult && (
        <div className="stats-grid" style={{marginBottom:20}}>
          <div className="stat-card blue" style={{padding:14}}><div className="stat-label">Products Scraped</div><div className="stat-value" style={{fontSize:"1.5rem"}}>{scrapeResult.products_scraped}</div></div>
          <div className="stat-card green" style={{padding:14}}><div className="stat-label">Live Results</div><div className="stat-value" style={{fontSize:"1.5rem"}}>{scrapeResult.live_results ?? 0}</div></div>
          <div className="stat-card orange" style={{padding:14}}><div className="stat-label">Skipped</div><div className="stat-value" style={{fontSize:"1.5rem"}}>{scrapeResult.skipped_results ?? 0}</div></div>
          <div className="stat-card red" style={{padding:14}}><div className="stat-label">Alerts Generated</div><div className="stat-value" style={{fontSize:"1.5rem"}}>{scrapeResult.alerts_generated}</div></div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header"><h3>Price Comparison</h3></div>
        <div style={{ marginBottom: 14, maxWidth: 480 }}>
          <Select
            value={selectedProduct ? String(selectedProduct.id) : ""}
            onChange={(value) => {
              const product = products.find((item) => item.id === parseInt(value, 10));
              if (product) handleSelectProduct(product);
            }}
            placeholder="Select a product..."
            ariaLabel="Select product for price comparison"
            className="select-full-width"
            options={products.map((product) => ({
              value: String(product.id),
              label: `${product.sku} - ${product.title.slice(0, 50)}`,
            }))}
          />
        </div>
        {selectedProduct ? (
          <CompetitorChart
            product={selectedProduct}
            competitorPrices={productPrices}
            exchangeRate={monitoringConfig?.usd_inr_exchange_rate}
          />
        ) : (
          <div className="empty-state" style={{ padding: 32 }}><p>Select a product to view price comparison.</p></div>
        )}
      </div>

      <section className="card competitor-alerts-section">
        <div className="card-header">
          <h3>Active Alerts</h3>
          <span className="badge badge-high"><Bell size={10} />{alerts.length}</span>
        </div>

        {alertGroups.length > 0 ? (
        <div className="competitor-alerts-groups">
          {alertGroups.map((group) => (
            <div key={group.id} className="competitor-alerts-group">
              <div className="competitor-alerts-group-header">
                <div className="marketplace-badges">
                  <span className={`badge badge-${group.id}`}>{group.platform}</span>
                  {group.region ? <span className="badge badge-region">{group.region}</span> : null}
                </div>
                <span className="competitor-alerts-group-count">{group.alerts.length} alert{group.alerts.length === 1 ? "" : "s"}</span>
              </div>
              <div className="competitor-alerts-group-list">
                {group.alerts.length > 0 ? group.alerts.map((alert) => {
                    const Icon = ALERT_ICONS[alert.alert_type] || BarChart3;
                    return (
                      <div key={alert.id} className="alert-item">
                        <div className={`alert-icon ${alert.alert_type}`}><Icon size={18} /></div>
                        <div className="alert-content" style={{ flex: 1 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                            <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                              {alert.alert_type.replace(/_/g, " ")}
                            </span>
                          </div>
                          <p style={{ fontSize: "0.85rem" }}>{alert.message}</p>
                          {alert.our_price != null && alert.competitor_price != null && (
                            <div style={{ display: "flex", gap: 16, marginTop: 6, fontSize: "0.78rem", flexWrap: "wrap" }}>
                              <span>
                                Your price:{" "}
                                <strong style={{ color: "var(--accent-green-light)" }}>
                                  ${alert.our_price.toFixed(2)}
                                </strong>
                              </span>
                              <span>
                                Competitor:{" "}
                                <strong style={{ color: "var(--accent-red-light)" }}>
                                  {formatAlertPrice(alert.competitor_price, alert.source)}
                                </strong>
                              </span>
                            </div>
                          )}
                          <div className="alert-meta">
                            {new Date(alert.created_at).toLocaleString(undefined, {
                              dateStyle: "medium",
                              timeStyle: "short",
                            })}
                          </div>
                        </div>
                        <button className="btn btn-ghost btn-sm" onClick={() => handleAcknowledge(alert)} aria-label="Acknowledge alert">
                          <Check size={14} />
                        </button>
                      </div>
                    );
                  }) : (
                    <div className="competitor-alerts-empty">
                      <p>No active alerts for {group.label}.</p>
                    </div>
                  )}
              </div>
            </div>
          ))}
        </div>
        ) : (
          <div className="empty-state" style={{ padding: 32 }}>
            <p>Set SCRAPE_REGION in .env to us or in to enable competitor alerts.</p>
          </div>
        )}
      </section>

    </div>
  );
}
