import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { Search, Trash2, Upload, X } from "lucide-react";
import { api } from "./api";
import FieldSelect from "./FieldSelect";
import { FEEDBACK_CATEGORIES } from "./api/cases";

const STATUSES = [
  { id: "pending_review", label: "Pending review" },
  { id: "reviewed", label: "Reviewed" },
  { id: "closed", label: "Closed" },
];

const FILE_ACCEPT = ".docx,.xlsx,.png,.jpg,.jpeg,.webp,.gif,image/png,image/jpeg,image/webp,image/gif";

const DETAIL_FIELDS = [
  ["hbl", "HBL"],
  ["name", "Name"],
  ["email", "Email"],
  ["wronglyIdentified", "Wrongly identified"],
  ["incorrect", "Incorrect"],
  ["corrected", "Corrected"],
  ["causeOfError", "Cause of error"],
  ["adjustedHbl", "Adjusted HBL"],
  ["gscPic", "GSC PIC"],
  ["week", "Week"],
  ["date", "Date"],
  ["action", "Action"],
];

function statusLabel(value) {
  return STATUSES.find((item) => item.id === value)?.label || value || "—";
}

function statusTone(value) {
  if (value === "closed") {
    return "converted";
  }
  if (value === "reviewed") {
    return "processing";
  }
  return "";
}

function displayDate(row) {
  const raw = row.date || row.startTime || row.createdAt || "";
  return raw.slice(0, 10) || "—";
}

const emptyForm = {
  category: FEEDBACK_CATEGORIES[0],
  description: "",
  status: "pending_review",
};

const FeedbackWorkspace = forwardRef(function FeedbackWorkspace(
  { onNotice, onRefreshLogs, onImportingChange },
  ref
) {
  const importRef = useRef();
  const attachRef = useRef();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [pendingFiles, setPendingFiles] = useState([]);
  const [files, setFiles] = useState([]);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 250);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    onImportingChange?.(importing);
  }, [importing, onImportingChange]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.listCases(debounced);
      setRows(result.data || []);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }, [debounced, onNotice]);

  useEffect(() => {
    load();
  }, [load]);

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setPendingFiles([]);
    setFiles([]);
    setModal(true);
  };

  const openUpload = () => importRef.current?.click();

  const downloadTemplate = async () => {
    try {
      await api.downloadCaseTemplate();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  useImperativeHandle(ref, () => ({ openNew, openUpload, downloadTemplate, importing }));

  const openEdit = async (row) => {
    try {
      const result = await api.getCase(row.id);
      const data = result.data;
      setEditing(data);
      setForm({
        category: data.category || FEEDBACK_CATEGORIES[0],
        description: data.description || "",
        status: data.status || "pending_review",
      });
      setPendingFiles([]);
      setFiles(data.files || []);
      setModal(true);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const closeModal = () => {
    if (!saving && !uploading) {
      setModal(false);
    }
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      let caseId = editing?.id;
      if (editing) {
        const result = await api.updateCase(editing.id, form);
        onNotice?.({ type: "success", text: result.message });
        setEditing(result.data);
        setFiles(result.data.files || []);
      } else {
        const result = await api.createCase({
          category: form.category,
          description: form.description,
        });
        caseId = result.data.id;
        for (const file of pendingFiles) {
          await api.uploadCaseFile(caseId, file);
        }
        onNotice?.({ type: "success", text: result.message });
        setModal(false);
      }
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setSaving(false);
      setPendingFiles([]);
    }
  };

  const remove = async (row) => {
    if (!window.confirm("Delete this feedback?")) {
      return;
    }
    try {
      const result = await api.deleteCase(row.id);
      onNotice?.({ type: "success", text: result.message });
      if (editing?.id === row.id) {
        setModal(false);
      }
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const importCsv = async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setImporting(true);
    try {
      const result = await api.importCases(file);
      const extra = result.skipped ? ` Skipped ${result.skipped}.` : "";
      onNotice?.({ type: "success", text: `${result.message}.${extra}` });
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setImporting(false);
      event.target.value = "";
    }
  };

  const addPendingFiles = (event) => {
    const chosen = Array.from(event.target.files || []);
    if (chosen.length) {
      setPendingFiles((current) => [...current, ...chosen]);
    }
    event.target.value = "";
  };

  const attachExisting = async (event) => {
    const file = event.target.files?.[0];
    if (!file || !editing?.id) {
      return;
    }
    setUploading(true);
    try {
      await api.uploadCaseFile(editing.id, file);
      const result = await api.getCase(editing.id);
      setEditing(result.data);
      setFiles(result.data.files || []);
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const removeFile = async (file) => {
    if (!editing?.id) {
      setPendingFiles((current) => current.filter((item) => item !== file));
      return;
    }
    try {
      await api.deleteCaseFile(editing.id, file.id);
      setFiles((current) => current.filter((item) => item.id !== file.id));
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  return (
    <>
      <input ref={importRef} hidden type="file" accept=".csv,.xlsx,text/csv" onChange={importCsv} />
      <div className="page-intro">
        <p>File Area feedback: pick a category, write what happened, and attach supporting files.</p>
      </div>
      <div className="search">
        <Search size={19} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search category, description, or HBL"
          aria-describedby="feedback-search-hint"
        />
        {query ? (
          <button type="button" onClick={() => setQuery("")} aria-label="Clear search">
            <X size={17} />
          </button>
        ) : null}
      </div>
      <p id="feedback-search-hint" className="search-hint">
        {rows.length} {rows.length === 1 ? "item" : "items"}
      </p>
      <section className="card">
        <div className="table-wrap">
          <table className="wide-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>HBL</th>
                <th>Category</th>
                <th>Description</th>
                <th>Files</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading && rows.length === 0 ? (
                <tr>
                  <td colSpan="7" className="empty">
                    Loading...
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan="7" className="empty">
                    No feedback yet. Create one or import the CSV template.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id} className="clickable" onClick={() => openEdit(row)}>
                    <td>{displayDate(row)}</td>
                    <td>{row.hbl || "—"}</td>
                    <td>
                      <strong>{row.category || "—"}</strong>
                    </td>
                    <td>{row.description || "—"}</td>
                    <td>{row.fileCount || "—"}</td>
                    <td>
                      <span className={`status-pill dash-status${statusTone(row.status) ? ` ${statusTone(row.status)}` : ""}`}>
                        {statusLabel(row.status)}
                      </span>
                    </td>
                    <td className="actions" onClick={(event) => event.stopPropagation()}>
                      <button type="button" className="danger" onClick={() => remove(row)} aria-label="Delete feedback">
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
      {modal ? (
        <div
          className="overlay"
          role="presentation"
          onMouseDown={(event) => event.target === event.currentTarget && closeModal()}
        >
          <form className="modal" onSubmit={save}>
            <div className="modal-head">
              <div>
                <h2>{editing ? `Feedback #${editing.id}` : "New feedback"}</h2>
                <p>Select a category, describe the issue, and attach supporting files.</p>
              </div>
              <button type="button" onClick={closeModal} disabled={saving || uploading} aria-label="Close">
                <X size={18} />
              </button>
            </div>
            <div className="grid">
              <label className="wide">
                Category *
                <FieldSelect
                  required
                  value={form.category}
                  options={(FEEDBACK_CATEGORIES.includes(form.category)
                    ? FEEDBACK_CATEGORIES
                    : [form.category, ...FEEDBACK_CATEGORIES]
                  ).map((item) => ({ value: item, label: item }))}
                  onChange={(category) => setForm({ ...form, category })}
                  disabled={saving}
                />
              </label>
              {editing ? (
                <label>
                  Status
                  <FieldSelect
                    value={form.status}
                    options={STATUSES.map((item) => ({ value: item.id, label: item.label }))}
                    onChange={(status) => setForm({ ...form, status })}
                    disabled={saving}
                  />
                </label>
              ) : null}
              <label className="wide">
                Description *
                <textarea
                  required
                  rows="4"
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                  disabled={saving}
                  placeholder="What was wrong, and what should it have been?"
                />
              </label>
              {editing
                ? DETAIL_FIELDS.filter(([key]) => editing[key]).map(([key, label]) => (
                    <label key={key}>
                      {label}
                      <input readOnly value={editing[key]} />
                    </label>
                  ))
                : null}
              <div className="wide">
                <div className="attach-head">
                  <strong>Supporting files</strong>
                  <button
                    type="button"
                    className="ghost"
                    disabled={saving || uploading}
                    onClick={() => attachRef.current?.click()}
                  >
                    <Upload size={16} />
                    {uploading ? "Uploading..." : "Upload"}
                  </button>
                  <input
                    ref={attachRef}
                    hidden
                    type="file"
                    accept={FILE_ACCEPT}
                    disabled={saving || uploading}
                    onChange={editing ? attachExisting : addPendingFiles}
                    multiple={!editing}
                  />
                </div>
                <div className="attach-list">
                  {!editing && pendingFiles.length === 0 && files.length === 0 ? (
                    <p className="preview-empty">Optional. docx, xlsx, or pictures.</p>
                  ) : null}
                  {pendingFiles.map((file, index) => (
                    <div key={`${file.name}-${index}`} className="attach-item">
                      <span>{file.name}</span>
                      <button type="button" className="danger" onClick={() => removeFile(file)} aria-label="Remove file">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                  {files.map((file) => (
                    <div key={file.id} className="attach-item">
                      <a href={api.caseFileDownloadUrl(editing.id, file.id)} target="_blank" rel="noreferrer">
                        {file.originalName}
                      </a>
                      <em>{file.kind}</em>
                      <button type="button" className="danger" onClick={() => removeFile(file)} aria-label="Remove file">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={closeModal} disabled={saving || uploading}>
                Cancel
              </button>
              {editing ? (
                <button type="button" className="danger" onClick={() => remove(editing)} disabled={saving}>
                  Delete
                </button>
              ) : null}
              <button className="primary" disabled={saving || uploading}>
                {saving ? "Saving..." : editing ? "Save" : "Submit"}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </>
  );
});

export default FeedbackWorkspace;
