import { useState, useEffect } from "react";
import { Sparkles, RefreshCw } from "lucide-react";
import { fetchProducts, generateContent, fetchProductsNeedingContent } from "../api/client";
import ContentPreview from "../components/ContentPreview";

export default function ContentGen() {
  const [products, setProducts] = useState([]);
  const [selected, setSelected] = useState([]);
  const [tone, setTone] = useState("professional");
  const [generating, setGenerating] = useState(false);
  const [results, setResults] = useState([]);
  const [toast, setToast] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadProducts(); }, []);

  async function loadProducts() {
    try {
      setLoading(true);
      const data = await fetchProductsNeedingContent(50);
      setProducts(data);
    } catch { setProducts([]); }
    finally { setLoading(false); }
  }

  async function handleGenerate() {
    if (selected.length === 0) { showToast("Select at least one product", "error"); return; }
    try {
      setGenerating(true);
      const res = await generateContent(selected, tone, true);
      setResults(res);
      const ok = res.filter(r => r.success).length;
      showToast(`Generated content for ${ok}/${selected.length} products`, "success");
      loadProducts();
    } catch (err) { showToast(`Generation failed: ${err.message}`, "error"); }
    finally { setGenerating(false); }
  }

  function toggleSelect(id) {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }

  function selectAll() {
    setSelected(selected.length === products.length ? [] : products.map(p => p.id));
  }

  function showToast(msg, type) { setToast({message: msg, type}); setTimeout(() => setToast(null), 3000); }

  if (loading) return <div className="loading"><div className="spinner"/>Loading...</div>;

  return (
    <div className="animate-in">
      <div className="page-header">
        <h2>Content Generator</h2>
        <p>Generate SEO product descriptions using AI</p>
      </div>
      <div className="toolbar">
        <select value={tone} onChange={e => setTone(e.target.value)} style={{width: "auto", minWidth: 160}}>
          <option value="professional">Professional</option>
          <option value="casual">Casual</option>
          <option value="luxury">Luxury</option>
          <option value="technical">Technical</option>
        </select>
        <button className="btn btn-ghost btn-sm" onClick={selectAll}>
          {selected.length === products.length ? "Deselect All" : "Select All"}
        </button>
        <button className="btn btn-primary" onClick={handleGenerate} disabled={generating || selected.length === 0}>
          {generating ? <><div className="spinner" style={{width:16,height:16,borderWidth:2,margin:0}}/>Generating...</> : <><Sparkles size={16}/>Generate ({selected.length})</>}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={loadProducts}><RefreshCw size={14}/>Refresh</button>
      </div>

      {products.length > 0 ? (
        <div className="table-container">
          <table>
            <thead><tr><th style={{width:40}}></th><th>SKU</th><th>Title</th><th>Category</th><th>Has Content</th></tr></thead>
            <tbody>
              {products.map(p => (
                <tr key={p.id}>
                  <td><input type="checkbox" checked={selected.includes(p.id)} onChange={() => toggleSelect(p.id)}/></td>
                  <td style={{fontFamily:"monospace",fontSize:"0.82rem"}}>{p.sku}</td>
                  <td style={{maxWidth:300,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{p.title}</td>
                  <td>{p.category||"--"}</td>
                  <td>{p.generated_description ? <span className="badge badge-active">Yes</span> : <span className="badge badge-draft">No</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state"><h3>All products have content</h3><p>No products need content generation.</p></div>
      )}

      {results.length > 0 && (
        <div className="card" style={{marginTop: 20}}>
          <div className="card-header"><h3>Generation Results</h3></div>
          {results.map(r => (
            <div key={r.product_id} style={{marginBottom:16, padding:14, border:"1px solid var(--border-color)", borderRadius:"var(--radius-md)"}}>
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:8}}>
                <span style={{fontWeight:600}}>Product #{r.product_id}</span>
                <span className={`badge ${r.success?"badge-active":"badge-high"}`}>{r.success?"Success":"Failed"}</span>
              </div>
              {r.success ? <ContentPreview product={{generated_description:r.generated_description,seo_title:r.seo_title,seo_keywords:r.seo_keywords}}/> : <p style={{color:"var(--accent-red-light)",fontSize:"0.85rem"}}>{r.error}</p>}
            </div>
          ))}
        </div>
      )}

      {toast && <div className="toast-container"><div className={`toast ${toast.type}`}>{toast.message}</div></div>}
    </div>
  );
}
