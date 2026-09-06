import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from "react";
import { BookOpen, RefreshCw, Search } from "lucide-react";
import { api } from "./api";

const WikiWorkspace = forwardRef(function WikiWorkspace({ onNotice, onRefreshLogs, onReindexingChange }, ref) {
  const [query, setQuery] = useState("");
  const [pages, setPages] = useState([]);
  const [hits, setHits] = useState([]);
  const [meta, setMeta] = useState(null);
  const [current, setCurrent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reindexing, setReindexing] = useState(false);

  const loadPages = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.listWiki();
      setPages(result.data || []);
      setMeta(result.meta || null);
      return result.data || [];
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
      return [];
    } finally {
      setLoading(false);
    }
  }, [onNotice]);

  const openPage = useCallback(async (slug) => {
    if (!slug) {
      return;
    }
    try {
      const result = await api.getWiki(slug);
      setCurrent(result.data || null);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  }, [onNotice]);

  useEffect(() => {
    let cancelled = false;
    loadPages().then((rows) => {
      if (!cancelled && rows[0]?.slug) {
        openPage(rows[0].slug);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [loadPages, openPage]);

  useEffect(() => {
    const text = query.trim();
    if (!text) {
      setHits([]);
      return undefined;
    }
    const timer = setTimeout(async () => {
      try {
        const result = await api.searchWiki(text);
        setHits(result.data || []);
      } catch (error) {
        onNotice?.({ type: "error", text: error.message });
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [query, onNotice]);

  const reindex = useCallback(async () => {
    setReindexing(true);
    try {
      const payload = await api.wikiReindex();
      setMeta(payload.data || null);
      onNotice?.({ type: "success", text: payload.message || "Wiki rebuilt" });
      const rows = await loadPages();
      if (rows[0]?.slug) {
        await openPage(rows[0].slug);
      }
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setReindexing(false);
    }
  }, [loadPages, openPage, onNotice, onRefreshLogs]);

  useEffect(() => {
    onReindexingChange?.(reindexing);
  }, [reindexing, onReindexingChange]);

  useImperativeHandle(ref, () => ({ reindex, openPage }));

  const pageCount = meta?.pageCount || pages.length;
  const embedded = meta?.embeddedCount || 0;

  return (
    <div className="wiki-layout">
      <div className="ask-banner muted">
        Wiki indexes remarks, SOPs, files, cases, and GCA feedback. LCL shipments and UNLOCODE
        rows stay in SearchBar. {meta?.embeddingEnabled ? "Azure embeddings are on." : "Keyword search is on until an embedding deployment is set."}
      </div>
      <div className="tool-split wiki-split">
        <section className="card">
          <div className="summary">
            <span className="summary-count">
              <strong>{pageCount}</strong> {pageCount === 1 ? "page" : "pages"}
              {embedded ? ` · ${embedded} embeddings` : ""}
            </span>
            <button className="ghost" type="button" onClick={reindex} disabled={reindexing}>
              <RefreshCw size={16} />
              {reindexing ? "Rebuilding..." : "Rebuild"}
            </button>
          </div>
          <label className="wiki-search">
            <Search size={16} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search wiki pages"
            />
          </label>
          {query.trim() && hits.length ? (
            <ul className="wiki-list">
              {hits.map((hit, index) => (
                <li key={`${hit.slug}-${hit.locator}-${index}`}>
                  <button
                    type="button"
                    className={current?.slug === hit.slug ? "active" : ""}
                    onClick={() => openPage(hit.slug)}
                  >
                    <strong>{hit.title}</strong>
                    <em>{hit.sourceLabel} · {hit.locator}</em>
                    <span>{hit.excerpt}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <ul className="wiki-list">
              {loading ? <li className="preview-empty">Loading wiki…</li> : null}
              {!loading && !pages.length ? <li className="preview-empty">No wiki pages yet.</li> : null}
              {pages.map((page) => (
                <li key={page.slug}>
                  <button
                    type="button"
                    className={current?.slug === page.slug ? "active" : ""}
                    onClick={() => openPage(page.slug)}
                  >
                    <strong>{page.title}</strong>
                    <em>{page.sourceLabel}</em>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card wiki-article">
          {current ? (
            <>
              <div className="summary">
                <span>
                  <BookOpen size={18} />
                  <strong>{current.title}</strong>
                  <span className="status-pill planned">{current.sourceLabel}</span>
                </span>
              </div>
              <div className="wiki-article-body">{current.body}</div>
            </>
          ) : (
            <p className="preview-empty">Select a wiki page.</p>
          )}
        </section>
      </div>
    </div>
  );
});

export default WikiWorkspace;
