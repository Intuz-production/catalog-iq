import { useState, useEffect } from "react";
import { BarChart3, RefreshCw, TrendingDown, Package, Bell, Check } from "lucide-react";
import { fetchProducts, fetchAlerts, fetchCompetitorPrices, triggerCompetitorScrape, acknowledgeAlert } from "../api/client";
import CompetitorChart from "../components/CompetitorChart";

export default function Competitors() {
  const [alerts, setAlerts] = useState([]);
  const [prices, setPrices] = useState([]);
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [productPrices, setProductPrices] = useState([]);
  const [scraping, setScraping] = useState(false);
  const [scrapeResult, setScrapeResult] = useState(null);
  const [toast, setToast] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadData(); }, []);

  async function loadData() {
    try {
      setLoading(true);
      const [a, pr, p] = await Promise.all([
        fetchAlerts({ acknowledged: false, limit: 50 }),
        fetchCompetitorPrices({ limit: 50 }),
        fetchProducts({ limit: 100 }),
      ]);
      setAlerts(a); setPrices(pr); setProducts(p);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }

  async function handleScrape() {
    try {
      setScraping(true); setScrapeResult(null);
      const res = await triggerCompetitorScrape();
      setScrapeResult(res.summary);
      showToast(`Scraped ${res.summary.products_scraped} products, found ${res.summary.results_found} results`, "success");
      loadData();
    } catch (err) { showToast(`Scrape failed: ${err.message}`, "error"); }
    finally { setScraping(false); }
  }

  async function handleAcknowledge(alertId) {
    try {
      await acknowledgeAlert(alertId);
      setAlerts(prev => prev.filter(a => a.id !== alertId));
      showToast("Alert acknowledged", "success");
    } catch { showToast("Failed to acknowledge", "error"); }
  }

  async function handleSelectProduct(product) {
    setSelectedProduct(product);
    try {
      const pp = await fetchCompetitorPrices({ product_id: product.id, limit: 10 });
      setProductPrices(pp);
    } catch { setProductPrices([]); }
  }

  function showToast(msg, type) { setToast({message:msg,type}); setTimeout(()=>setToast(null),3000); }

  if (loading) return <div className="loading"><div className="spinner"/>Loading...</div>;

  const ALERT_ICONS = {
    undercut: TrendingDown, out_of_stock: Package, price_drop: TrendingDown, price_increase: BarChart3, back_in_stock: Package,
  };

  return (
    <div className="animate-in">
      <div className="page-header"><h2>Competitor Monitoring</h2><p>Track competitor prices across Amazon, Walmart, and Flipkart</p></div>

      <div className="toolbar">
        <button className="btn btn-primary" onClick={handleScrape} disabled={scraping}>
          {scraping ? <><div className="spinner" style={{width:16,height:16,borderWidth:2,margin:0}}/>Scraping...</> : <><BarChart3 size={16}/>Run Competitor Scrape</>}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={loadData}><RefreshCw size={14}/>Refresh</button>
      </div>

      {scrapeResult && (
        <div className="stats-grid" style={{marginBottom:20}}>
          <div className="stat-card blue" style={{padding:14}}><div className="stat-label">Products Scraped</div><div className="stat-value" style={{fontSize:"1.5rem"}}>{scrapeResult.products_scraped}</div></div>
          <div className="stat-card green" style={{padding:14}}><div className="stat-label">Results Found</div><div className="stat-value" style={{fontSize:"1.5rem"}}>{scrapeResult.results_found}</div></div>
          <div className="stat-card orange" style={{padding:14}}><div className="stat-label">Alerts Generated</div><div className="stat-value" style={{fontSize:"1.5rem"}}>{scrapeResult.alerts_generated}</div></div>
        </div>
      )}

      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:20}}>
        {/* Alerts */}
        <div className="card">
          <div className="card-header"><h3>Active Alerts</h3><span className="badge badge-high"><Bell size={10}/>{alerts.length}</span></div>
          <div style={{maxHeight:500,overflow:"auto"}}>
            {alerts.length > 0 ? alerts.map(alert => {
              const Icon = ALERT_ICONS[alert.alert_type] || BarChart3;
              return (
                <div key={alert.id} className="alert-item">
                  <div className={`alert-icon ${alert.alert_type}`}><Icon size={18}/></div>
                  <div className="alert-content" style={{flex:1}}>
                    <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:4}}>
                      <span className={`badge badge-${alert.source}`}>{alert.source}</span>
                      <span style={{fontSize:"0.72rem",color:"var(--text-muted)"}}>{alert.alert_type.replace(/_/g," ")}</span>
                    </div>
                    <p style={{fontSize:"0.85rem"}}>{alert.message}</p>
                    {alert.our_price && alert.competitor_price && (
                      <div style={{display:"flex",gap:16,marginTop:6,fontSize:"0.78rem"}}>
                        <span>Your price: <strong style={{color:"var(--accent-green-light)"}}>${alert.our_price.toFixed(2)}</strong></span>
                        <span>Competitor: <strong style={{color:"var(--accent-red-light)"}}>${alert.competitor_price.toFixed(2)}</strong></span>
                      </div>
                    )}
                    <div className="alert-meta">{new Date(alert.created_at).toLocaleDateString()}</div>
                  </div>
                  <button className="btn btn-ghost btn-sm" onClick={() => handleAcknowledge(alert.id)}><Check size={14}/></button>
                </div>
              );
            }) : <div className="empty-state" style={{padding:32}}><p>No active alerts.</p></div>}
          </div>
        </div>

        {/* Price Comparison */}
        <div className="card">
          <div className="card-header"><h3>Price Comparison</h3></div>
          <div style={{marginBottom:14}}>
            <select onChange={e => { const p = products.find(x => x.id === parseInt(e.target.value)); if(p) handleSelectProduct(p); }} defaultValue="">
              <option value="" disabled>Select a product...</option>
              {products.map(p => <option key={p.id} value={p.id}>{p.sku} - {p.title.slice(0,50)}</option>)}
            </select>
          </div>
          {selectedProduct ? (
            <CompetitorChart product={selectedProduct} competitorPrices={productPrices}/>
          ) : (
            <div className="empty-state" style={{padding:32}}><p>Select a product to view price comparison.</p></div>
          )}
        </div>
      </div>

      {toast && <div className="toast-container"><div className={`toast ${toast.type}`}>{toast.message}</div></div>}
    </div>
  );
}
