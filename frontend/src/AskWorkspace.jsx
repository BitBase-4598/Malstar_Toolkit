import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from "react";
import { ClipboardList, FolderOpen, RefreshCw, Send } from "lucide-react";
import { api } from "./api";

const AskWorkspace = forwardRef(function AskWorkspace({ onNotice, onRefreshLogs, onOpenCitation, onReindexingChange }, ref) {
  const [status, setStatus] = useState(null);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [result, setResult] = useState(null);

  const loadStatus = useCallback(async () => {
    try {
      const payload = await api.askStatus();
      setStatus(payload.data || null);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  }, [onNotice]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const reindex = useCallback(async () => {
    setReindexing(true);
    try {
      const payload = await api.askReindex();
      setStatus(payload.data || null);
      onNotice?.({ type: "success", text: payload.message || "Index rebuilt" });
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setReindexing(false);
    }
  }, [onNotice, onRefreshLogs]);

  useEffect(() => {
    onReindexingChange?.(reindexing);
  }, [reindexing, onReindexingChange]);

  useImperativeHandle(ref, () => ({ reindex, reindexing }));

  const submit = async (event) => {
    event.preventDefault();
    const text = question.trim();
    if (!text || loading) {
      return;
    }
    setLoading(true);
    try {
      const payload = await api.ask(text);
      setResult(payload.data || null);
      await loadStatus();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  };

  const chunkCount = status?.chunkCount || 0;
  const llmEnabled = Boolean(status?.llmEnabled);
  const sopCount = status?.sources?.sops || 0;
  const fileCount = status?.sources?.files || 0;

  return (
    <div className="ask-layout">
      {chunkCount === 0 ? (
        <div className="ask-banner">
          The index is empty. Upload files or save SOPs, then rebuild the index.
        </div>
      ) : null}
      {!llmEnabled ? (
        <div className="ask-banner muted">
          Answers are matching excerpts until Azure OpenAI is configured. Citations still open the source SOP or file.
        </div>
      ) : null}
      <section className="card ask-card">
        <div className="summary">
          <span className="summary-count">
            <strong>{chunkCount}</strong> {chunkCount === 1 ? "chunk" : "chunks"} from {sopCount} SOPs and {fileCount} files
          </span>
          <span>
            {llmEnabled ? "Azure OpenAI on" : "Keyword search"}
            {status?.lastIndexedAt ? ` · indexed ${status.lastIndexedAt}` : ""}
          </span>
        </div>
        <form className="ask-form" onSubmit={submit}>
          <label htmlFor="ask-question">Question</label>
          <textarea
            id="ask-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask about an SOP or uploaded file"
            rows={4}
          />
          <div className="ask-form-actions">
            <button className="ghost" type="button" onClick={reindex} disabled={reindexing}>
              <RefreshCw size={16} />
              {reindexing ? "Rebuilding..." : "Rebuild index"}
            </button>
            <button className="primary" type="submit" disabled={loading || !question.trim()}>
              <Send size={16} />
              {loading ? "Searching..." : "Ask"}
            </button>
          </div>
        </form>
      </section>
      {result ? (
        <section className="card ask-card ask-result">
          <div className="summary">
            <strong>{result.mode === "generate" ? "Answer" : "Matches"}</strong>
            <span className={`status-pill ${result.mode === "generate" ? "active" : "planned"}`}>
              {result.mode === "generate" ? "generated" : "retrieved"}
            </span>
          </div>
          <div className="ask-result-body">
            <div className="ask-answer">{result.answer}</div>
            <h3>Sources</h3>
            {result.citations?.length ? (
              <ul className="ask-citations">
                {result.citations.map((citation, index) => {
                  const isSop = citation.sourceType === "sop";
                  return (
                    <li key={`${citation.sourceType}-${citation.sourceId}-${citation.locator}-${index}`}>
                      <button type="button" onClick={() => onOpenCitation?.(citation)}>
                        <span className="ask-citation-index">[{index + 1}]</span>
                        <span className="ask-citation-icon" aria-hidden="true">
                          {isSop ? <ClipboardList size={16} /> : <FolderOpen size={16} />}
                        </span>
                        <span className="ask-citation-copy">
                          <strong>{citation.title}</strong>
                          <em>
                            {isSop ? "SOP" : "File"} · {citation.locator}
                          </em>
                          <span>{citation.excerpt}</span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="preview-empty">No sources to open.</p>
            )}
          </div>
        </section>
      ) : (
        <p className="ask-hint">Ask a question to search SOP steps and uploaded DOCX or Excel files.</p>
      )}
    </div>
  );
});

export default AskWorkspace;
