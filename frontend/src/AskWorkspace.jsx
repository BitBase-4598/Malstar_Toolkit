import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import {
  BookOpen,
  ClipboardList,
  FileText,
  FolderOpen,
  Inbox,
  MapPin,
  MessageSquare,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Trash2,
  Upload,
} from "lucide-react";
import { api } from "./api";
import FilePreview from "./FilePreview";
import useConfirm from "./useConfirm";
import usePrompt from "./usePrompt";
import { renderWikiMarkdown } from "./wikiMarkdown";

function sourceMeta(type) {
  switch (type) {
    case "wiki":
      return { label: "Wiki", Icon: BookOpen };
    case "sop":
      return { label: "SOP", Icon: ClipboardList };
    case "file":
      return { label: "File", Icon: FolderOpen };
    case "remark":
      return { label: "Remark", Icon: FileText };
    case "case":
      return { label: "Case", Icon: Inbox };
    case "gca":
      return { label: "GCA", Icon: MessageSquare };
    case "icb":
      return { label: "ICB", Icon: MapPin };
    case "unloco":
      return { label: "UNLOCODE", Icon: MapPin };
    default:
      return { label: type || "Source", Icon: BookOpen };
  }
}

function RecordFields({ record }) {
  if (!record || typeof record !== "object") {
    return <p className="preview-empty">No details.</p>;
  }
  const entries = Object.entries(record).filter(([, value]) => {
    if (value == null || value === "") {
      return false;
    }
    if (typeof value === "object") {
      return false;
    }
    return true;
  });
  if (!entries.length) {
    return <p className="preview-empty">No details.</p>;
  }
  return (
    <dl className="ask-record">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

const AskWorkspace = forwardRef(function AskWorkspace({ onNotice, onRefreshLogs, onReindexingChange }, ref) {
  const [status, setStatus] = useState(null);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [result, setResult] = useState(null);
  const [notes, setNotes] = useState([]);
  const [noteQuery, setNoteQuery] = useState("");
  const [notesLoading, setNotesLoading] = useState(false);
  const [selectedNote, setSelectedNote] = useState(null);
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftBody, setDraftBody] = useState("");
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(null);
  const vaultInputRef = useRef();
  const fileInputRef = useRef();
  const [confirm, confirmDialog] = useConfirm();
  const [promptName, promptDialog] = usePrompt();

  const loadStatus = useCallback(async () => {
    try {
      const payload = await api.askStatus();
      setStatus(payload.data || null);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  }, [onNotice]);

  const loadNotes = useCallback(async () => {
    setNotesLoading(true);
    try {
      const payload = await api.listWiki(noteQuery);
      setNotes(payload.data || []);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setNotesLoading(false);
    }
  }, [noteQuery, onNotice]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    const timer = setTimeout(loadNotes, noteQuery ? 250 : 0);
    return () => clearTimeout(timer);
  }, [loadNotes, noteQuery]);

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

  const openNote = useCallback(async (id) => {
    if (!id) {
      return;
    }
    try {
      const payload = await api.getWiki(id);
      setSelectedNote(payload.data || null);
      setEditing(false);
      setPreview({ kind: "wiki", note: payload.data });
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  }, [onNotice]);

  const openNewNote = useCallback(async () => {
    const title = await promptName({
      title: "New wiki note",
      message: "This note is stored in Ask and indexed for search. It does not change your local Obsidian vault until you copy it back.",
      label: "Title",
      defaultValue: "Untitled",
      confirmLabel: "Create",
    });
    if (!title) {
      return;
    }
    try {
      const payload = await api.createWiki({ title: title.trim() });
      setSelectedNote(payload.data);
      setDraftTitle(payload.data.title);
      setDraftBody(payload.data.body || "");
      setEditing(true);
      setPreview({ kind: "wiki", note: payload.data });
      await loadNotes();
      await loadStatus();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  }, [loadNotes, loadStatus, onNotice, onRefreshLogs, promptName]);

  const saveNote = async () => {
    if (!selectedNote || saving) {
      return;
    }
    setSaving(true);
    try {
      const payload = await api.updateWiki(selectedNote.id, {
        title: draftTitle.trim() || selectedNote.title,
        body: draftBody,
      });
      setSelectedNote(payload.data);
      setEditing(false);
      setPreview({ kind: "wiki", note: payload.data });
      onNotice?.({ type: "success", text: payload.message || "Note saved" });
      await loadNotes();
      await loadStatus();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setSaving(false);
    }
  };

  const removeNote = async () => {
    if (!selectedNote) {
      return;
    }
    const ok = await confirm({
      title: "Delete note",
      message: `Delete “${selectedNote.title}”? This removes it from Ask search, not from your local Obsidian vault.`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) {
      return;
    }
    try {
      await api.deleteWiki(selectedNote.id);
      setSelectedNote(null);
      setEditing(false);
      setPreview(null);
      onNotice?.({ type: "success", text: "Note deleted" });
      await loadNotes();
      await loadStatus();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const handleKnowledgeFile = async (file) => {
    const name = (file.name || "").toLowerCase();
    try {
      let payload;
      if (name.endsWith(".zip")) {
        payload = await api.importWikiVault(file);
        onNotice?.({ type: "success", text: payload.message || "Vault imported" });
      } else if (name.endsWith(".md")) {
        payload = await api.uploadWikiNote(file);
        setSelectedNote(payload.data);
        setPreview({ kind: "wiki", note: payload.data });
        setEditing(false);
        onNotice?.({ type: "success", text: payload.message || "Note uploaded" });
      } else {
        payload = await api.uploadFile(file);
        onNotice?.({ type: "success", text: payload.message || "File uploaded" });
      }
      await loadNotes();
      await loadStatus();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  useImperativeHandle(ref, () => ({
    reindex,
    reindexing,
    openNewNote,
    openUpload: () => fileInputRef.current?.click(),
    openVault: () => vaultInputRef.current?.click(),
  }));

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

  const openCitation = async (citation) => {
    const type = citation?.sourceType;
    if (type === "wiki" && citation.sourceId) {
      await openNote(citation.sourceId);
      return;
    }
    if (type === "file" && citation.sourceId) {
      setEditing(false);
      setPreview({ kind: "file", loading: true, citation });
      try {
        const payload = await api.previewFile(citation.sourceId);
        setPreview({ kind: "file", filePreview: payload.data, citation });
      } catch (error) {
        setPreview({ kind: "file", citation });
        onNotice?.({ type: "error", text: error.message });
      }
      return;
    }
    if (type === "sop" && citation.sourceId) {
      setEditing(false);
      setPreview({ kind: "sop", loading: true, citation });
      try {
        const payload = await api.getSop(citation.sourceId);
        setPreview({ kind: "sop", sop: payload.data, citation });
      } catch (error) {
        setPreview({ kind: "record", citation });
        onNotice?.({ type: "error", text: error.message });
      }
      return;
    }
    setEditing(false);
    setPreview({ kind: "record", citation });
  };

  const onWikiClick = async (event) => {
    const button = event.target.closest("[data-wiki-title]");
    if (!button) {
      return;
    }
    const title = button.getAttribute("data-wiki-title");
    if (!title) {
      return;
    }
    try {
      const payload = await api.getWikiByLink(title);
      setSelectedNote(payload.data);
      setEditing(false);
      setPreview({ kind: "wiki", note: payload.data });
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const chunkCount = status?.chunkCount || 0;
  const llmEnabled = Boolean(status?.llmEnabled);
  const sources = status?.sources || {};
  const wikiCount = sources.wiki || notes.length || 0;

  return (
    <div className="ask-layout">
      <input
        ref={vaultInputRef}
        hidden
        type="file"
        accept=".zip,application/zip"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) {
            handleKnowledgeFile(file);
          }
        }}
      />
      <input
        ref={fileInputRef}
        hidden
        type="file"
        accept=".md,.zip,.docx,.xlsx,.png,.jpg,.jpeg,.webp,.gif,text/markdown,application/zip"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) {
            handleKnowledgeFile(file);
          }
        }}
      />
      {chunkCount === 0 ? (
        <div className="ask-banner">
          {status?.indexing
            ? "Indexing wiki notes, files, and SOPs. You can ask again in a moment."
            : "The index is empty. Import an Obsidian vault zip, add a note, or upload a file, then rebuild the index."}
        </div>
      ) : null}
      {!llmEnabled ? (
        <div className="ask-banner muted">
          Answers are matching excerpts until Azure OpenAI is configured. Open a source here to read or edit wiki notes.
        </div>
      ) : null}
      <div className="ask-columns">
        <div className="ask-primary">
          <section className="card ask-card">
            <div className="summary">
              <span className="summary-count">
                <strong>{chunkCount}</strong> {chunkCount === 1 ? "chunk" : "chunks"}
                {` · ${wikiCount} notes`}
                {sources.sops ? ` · ${sources.sops} SOPs` : ""}
                {sources.files ? ` · ${sources.files} files` : ""}
                {sources.remarks ? ` · ${sources.remarks} remarks` : ""}
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
                placeholder="Ask about a wiki note, SOP, uploaded file, remark, ICB, or UNLOCODE"
                rows={4}
              />
              <div className="ask-form-actions">
                <button className="ghost" type="button" onClick={() => fileInputRef.current?.click()}>
                  <Upload size={16} />
                  Upload
                </button>
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
                <strong>
                  {result.mode === "generate" ? "Answer" : result.mode === "indexing" ? "Indexing" : "Matches"}
                </strong>
                <span className={`status-pill ${result.mode === "generate" ? "active" : "planned"}`}>
                  {result.mode === "generate" ? "generated" : result.mode === "indexing" ? "indexing" : "retrieved"}
                </span>
              </div>
              <div className="ask-result-body">
                <div className="ask-answer">{result.answer}</div>
                <h3>Sources</h3>
                {result.citations?.length ? (
                  <ul className="ask-citations">
                    {result.citations.map((citation, index) => {
                      const meta = sourceMeta(citation.sourceType);
                      const Icon = meta.Icon;
                      return (
                        <li key={`${citation.sourceType}-${citation.sourceId}-${citation.locator}-${index}`}>
                          <button type="button" onClick={() => openCitation(citation)}>
                            <span className="ask-citation-index">[{index + 1}]</span>
                            <span className="ask-citation-icon" aria-hidden="true">
                              <Icon size={16} />
                            </span>
                            <span className="ask-citation-copy">
                              <strong>{citation.title}</strong>
                              <em>
                                {citation.label || meta.label} · {citation.locator}
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
            <p className="ask-hint">
              Ask a question to search wiki notes, SOP steps, uploaded files, customer remarks, cases, GCA feedback, ICB, and UNLOCODE.
            </p>
          )}
        </div>
        <aside className="card ask-knowledge">
          <div className="summary">
            <strong>Knowledge</strong>
            <div className="actions">
              <button type="button" onClick={openNewNote} aria-label="New note">
                <Plus size={16} />
              </button>
              <button type="button" onClick={() => vaultInputRef.current?.click()} aria-label="Import vault zip">
                <Upload size={16} />
              </button>
            </div>
          </div>
          <label htmlFor="ask-notes-q">Notes</label>
          <input
            id="ask-notes-q"
            className="ask-notes-search"
            value={noteQuery}
            onChange={(event) => setNoteQuery(event.target.value)}
            placeholder="Search notes"
          />
          <div className="ask-notes-list">
            {notesLoading ? (
              <p className="preview-empty">Loading notes…</p>
            ) : notes.length ? (
              <ul>
                {notes.map((note) => (
                  <li key={note.id}>
                    <button
                      type="button"
                      className={selectedNote?.id === note.id ? "active" : ""}
                      onClick={() => openNote(note.id)}
                    >
                      <strong>{note.title}</strong>
                      <em>{note.path}</em>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="preview-empty">No wiki notes yet. Import a vault zip or create a note.</p>
            )}
          </div>
          <div className="ask-knowledge-preview">
            {editing && selectedNote ? (
              <div className="ask-note-editor">
                <label htmlFor="ask-note-title">Title</label>
                <input
                  id="ask-note-title"
                  value={draftTitle}
                  onChange={(event) => setDraftTitle(event.target.value)}
                />
                <label htmlFor="ask-note-body">Markdown</label>
                <textarea
                  id="ask-note-body"
                  value={draftBody}
                  onChange={(event) => setDraftBody(event.target.value)}
                  rows={12}
                />
                <div className="ask-form-actions">
                  <button className="ghost" type="button" onClick={() => setEditing(false)}>
                    Cancel
                  </button>
                  <button className="primary" type="button" onClick={saveNote} disabled={saving}>
                    {saving ? "Saving..." : "Save note"}
                  </button>
                </div>
              </div>
            ) : preview?.kind === "wiki" && preview.note ? (
              <div className="ask-note-view">
                <div className="summary">
                  <span>
                    <strong>{preview.note.title}</strong>
                    <em>{preview.note.path}</em>
                  </span>
                  <div className="actions">
                    <button
                      type="button"
                      aria-label="Edit note"
                      onClick={() => {
                        setDraftTitle(preview.note.title);
                        setDraftBody(preview.note.body || "");
                        setSelectedNote(preview.note);
                        setEditing(true);
                      }}
                    >
                      <Pencil size={16} />
                    </button>
                    <button type="button" className="danger" aria-label="Delete note" onClick={removeNote}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
                <div
                  className="ask-markdown"
                  onClick={onWikiClick}
                  dangerouslySetInnerHTML={{
                    __html: renderWikiMarkdown(preview.note.body, preview.note.attachments),
                  }}
                />
              </div>
            ) : preview?.kind === "file" ? (
              <FilePreview preview={preview.filePreview} loading={preview.loading} />
            ) : preview?.kind === "sop" && preview.sop ? (
              <div className="ask-note-view">
                <strong>{preview.sop.title}</strong>
                <p className="sop-purpose">{preview.sop.purpose || "No purpose recorded."}</p>
                {preview.sop.steps?.length ? (
                  <ol className="sop-steps">
                    {preview.sop.steps.map((step) => (
                      <li key={step.id || step.stepNumber}>{step.instruction}</li>
                    ))}
                  </ol>
                ) : (
                  <p className="preview-empty">No steps.</p>
                )}
              </div>
            ) : preview?.kind === "record" && preview.citation ? (
              <div className="ask-note-view">
                <strong>{preview.citation.title}</strong>
                <p>{preview.citation.excerpt}</p>
                <RecordFields record={preview.citation.record} />
              </div>
            ) : (
              <p className="preview-empty">Open a note or an Ask source to read it here.</p>
            )}
          </div>
        </aside>
      </div>
      {confirmDialog}
      {promptDialog}
    </div>
  );
});

export default AskWorkspace;
