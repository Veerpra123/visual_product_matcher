import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const API = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default function App() {
  const [health, setHealth] = useState(null);
  const [checking, setChecking] = useState(true);

  const [file, setFile] = useState(null);
  const [url, setUrl] = useState("");
  const [topK, setTopK] = useState(12);
  const [minSim, setMinSim] = useState(0.75);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState([]);

  const [queryPreview, setQueryPreview] = useState("");
  const [filePreviewURL, setFilePreviewURL] = useState("");
  const fileInputRef = useRef(null);

  const canSearch = useMemo(() => (file && file.name) || url.trim().length > 0, [file, url]);

  useEffect(() => {
    (async () => {
      try {
        setChecking(true);
        const r = await fetch(`${API}/health`);
        setHealth(await r.json());
      } catch {
        setError(`Cannot reach backend at ${API}`);
      } finally {
        setChecking(false);
      }
    })();
  }, []);

  const onFileChange = (e) => {
    const f = e.target.files?.[0] || null;
    setFile(f);
    if (filePreviewURL) URL.revokeObjectURL(filePreviewURL);
    if (f) {
      const u = URL.createObjectURL(f);
      setFilePreviewURL(u);
      setQueryPreview(u);
    } else {
      setQueryPreview(url.trim());
    }
  };

  useEffect(() => {
    if (!file) {
      const val = url.trim();
      setQueryPreview(isLikelyImageURL(val) ? val : "");
    }
  }, [url, file]);

  useEffect(() => () => filePreviewURL && URL.revokeObjectURL(filePreviewURL), [filePreviewURL]);

  const onSearch = async () => {
    if (!canSearch) return;
    setError("");
    setLoading(true);
    setResults([]);
    try {
      const fd = new FormData();
      if (file && file.name) fd.append("file", file);
      if (url.trim()) fd.append("image_url", url.trim());
      fd.append("top_k", String(topK));
      fd.append("min_similarity", String(minSim));
      const res = await fetch(`${API}/search`, { method: "POST", body: fd });
      if (!res.ok) {
        const txt = await res.text().catch(() => "unknown error");
        throw new Error(txt);
      }
      const data = await res.json();
      setResults(data.items || []);
    } catch (e) {
      setError(`Search failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const resetQuery = () => {
    if (filePreviewURL) URL.revokeObjectURL(filePreviewURL);
    setFilePreviewURL("");
    setFile(null);
    setUrl("");
    setQueryPreview("");
    setResults([]);
    setError("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="page">
      <header className="header">
        <div className="brand">Visual Product Matcher</div>
        <div className="pill">
          <span className={`dot ${checking ? "warn" : health ? "ok" : "err"}`} />
          {checking ? "checking…" : health ? (
            <>
              rows: <b>{health.rows}</b> <span className="dot tiny" />
              indexed: <b>{health.indexed}</b> <span className="dot tiny" />
              device: <b>{health.device}</b>
            </>
          ) : "offline"}
        </div>
      </header>

      <div className="container">
        <section className="panel form">
          <div className="controls">
            <div className="filebox">
              <label className="label">Upload image</label>
              <input ref={fileInputRef} type="file" accept="image/*" onChange={onFileChange} />
            </div>
            <div className="or">OR</div>
            <div className="urlbox">
              <label className="label">Image URL</label>
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/image.jpg" />
            </div>
          </div>
          <div className="buttons">
            <button className="btn ghost" onClick={resetQuery}>Reset</button>
            <button className="btn primary" disabled={!canSearch || loading} onClick={onSearch}>
              {loading ? "Searching…" : "Search"}
            </button>
          </div>
          <div className="grid-3">
            <div>
              <label className="label">Min similarity ({minSim.toFixed(2)})</label>
              <input type="range" min="0" max="0.95" step="0.01"
                value={minSim} onChange={(e) => setMinSim(parseFloat(e.target.value))} />
            </div>
            <div>
              <label className="label">Top-K ({topK})</label>
              <input type="range" min="1" max="52" step="1"
                value={topK} onChange={(e) => setTopK(parseInt(e.target.value))} />
            </div>
          </div>
          {error && <div className="error-box">{error}</div>}
        </section>

        <div className="main-grid">
          {/* Query Preview */}
          <section className="panel">
            <div className="label">Query Preview</div>
            <div className="preview">
              {queryPreview ? (
                <>
                  <img
                    src={queryPreview}
                    alt="Query"
                    className="img-fit"
                    onError={(e) => {
                      e.target.onerror = null;
                      e.target.src = "";
                    }}
                  />
                  <div className="meta">
                    {file
                      ? <span>📁 {file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
                      : url ? <span>🔗 {safeHostname(url)}</span>
                      : null}
                  </div>
                </>
              ) : (
                <div className="empty">No query yet</div>
              )}
            </div>
          </section>

          {/* Results */}
          <section className="panel">
            <div className="label">Results</div>
            <div className="results">
              {loading ? <div className="empty">Searching…</div>
                : results.length === 0 ? <div className="empty">No results — upload or paste an image.</div>
                : results.map((p) => {
                  // p.image_url may be absolute or relative; use safe src
                  const src = p.image_url && /^https?:\/\//i.test(p.image_url) ? p.image_url : `${API}${p.image_url}`;
                  return (
                    <article key={`${p.id}-${p.image_url || Math.random()}`} className="card">
                      <img loading="lazy" src={src} alt={p.name || p.title || ''} className="img-fit" />
                      <div className="meta">
                        <div className="name">{p.name || p.title || `#${p.id}`}</div>
                        <div className="cat">{p.category || ""}</div>
                        {p.price != null && !Number.isNaN(Number(p.price)) && <div className="price">💰 ${Number(p.price).toFixed(2)}</div>}
                        {p.brand && <div className="brand">🏷️ {p.brand}</div>}
                        {p.score != null && <div className="score">Score: {(Number(p.score) * 100).toFixed(1)}%</div>}
                      </div>
                    </article>
                  );
                })}
            </div>
          </section>
        </div>

        <footer>API: {API}</footer>
      </div>
    </div>
  );
}

function isLikelyImageURL(s) {
  return /^https?:\/\//i.test(s);
}

function safeHostname(s) {
  try {
    if (!s) return "";
    const u = new URL(s);
    return u.hostname;
  } catch {
    return "";
  }
}
