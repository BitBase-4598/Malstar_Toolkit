import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { Download, Search, Trash2, Upload, X } from "lucide-react";
import { api } from "./api";
import FieldSelect from "./FieldSelect";
import { FEEDBACK_CATEGORIES } from "./api/cases";
import FilePreview from "./FilePreview";
import ModalShell from "./ModalShell";
import useConfirm from "./useConfirm";

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

const emptyForm = {
  bookingOrderId: "",
  shipmentNumber: "",
  category: "",
  description: "",
  status: "pending_review",
};

const IDENTIFIER_REQUIRED = "Booking order ID or shipment number is required.";

function displayDate(row) {
  const raw = row.date || row.startTime || row.createdAt || "";
  return raw.slice(0, 10) || "—";
}

function screenshotFile(blob) {
  const type = blob.type || "image/png";
  const subtype = (type.split("/")[1] || "png").split("+")[0];
  const ext = subtype === "jpeg" ? "jpg" : subtype;
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const given = blob.name && !/^image\./i.test(blob.name) ? blob.name : "";
  return new File([blob], given || `screenshot-${stamp}.${ext}`, { type });
}

function imagesFromClipboard(event) {
  const items = Array.from(event.clipboardData?.items || []);
  const files = [];
  for (const item of items) {
    if (item.kind === "file" && String(item.type || "").startsWith("image/")) {
      const blob = item.getAsFile();
      if (blob) {
        files.push(screenshotFile(blob));
      }
    }
  }
  return files;
}

function PendingImageThumb({ file, onOpen }) {
  const [src, setSrc] = useState("");

  useEffect(() => {
    if (!String(file.type || "").startsWith("image/")) {
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  if (!src) {
    return null;
  }
  return (
    <button type="button" className="case-thumb" onClick={onOpen} title={file.name}>
      <img src={src} alt={file.name} />
    </button>
  );
}

function categoryOptions(current) {
  const values = FEEDBACK_CATEGORIES.includes(current) || !current
    ? FEEDBACK_CATEGORIES
    : [current, ...FEEDBACK_CATEGORIES];
  return [{ value: "", label: "None" }, ...values.map((item) => ({ value: item, label: item }))];
}

const FeedbackWorkspace = forwardRef(function FeedbackWorkspace(
  { onNotice, onRefreshLogs, onImportingChange },
  ref
) {
  const importRef = useRef();
  const attachRef = useRef();
  const previewUrlRef = useRef("");
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
  const [confirm, confirmDialog] = useConfirm();
  const [pendingFiles, setPendingFiles] = useState([]);
  const [files, setFiles] = useState([]);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [formError, setFormError] = useState("");
  const [statusBusy, setStatusBusy] = useState(null);

  const releasePreviewUrl = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = "";
    }
  }, []);

  const clearPreview = useCallback(() => {
    releasePreviewUrl();
    setPreview(null);
    setPreviewLoading(false);
  }, [releasePreviewUrl]);

  useEffect(() => () => releasePreviewUrl(), [releasePreviewUrl]);

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

  const showLocalPreview = useCallback((file) => {
    releasePreviewUrl();
    if (!String(file.type || "").startsWith("image/")) {
      setPreview(null);
      onNotice?.({ type: "error", text: "This file can be previewed after the case is saved." });
      return;
    }
    const url = URL.createObjectURL(file);
    previewUrlRef.current = url;
    setPreview({
      kind: "image",
      url,
      file: { id: file.name, originalName: file.name },
    });
  }, [onNotice, releasePreviewUrl]);

  const openSavedPreview = useCallback(async (caseId, file) => {
    setPreviewLoading(true);
    try {
      const result = await api.previewCaseFile(caseId, file.id);
      releasePreviewUrl();
      setPreview(result.data);
    } catch (error) {
      setPreview(null);
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setPreviewLoading(false);
    }
  }, [onNotice, releasePreviewUrl]);

  const uploadFiles = useCallback(async (caseId, chosen) => {
    if (!chosen.length) {
      return;
    }
    setUploading(true);
    try {
      for (const file of chosen) {
        await api.uploadCaseFile(caseId, file);
      }
      const result = await api.getCase(caseId);
      setEditing(result.data);
      setFiles(result.data.files || []);
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setUploading(false);
    }
  }, [load, onNotice, onRefreshLogs]);

  useEffect(() => {
    if (!modal) {
      return undefined;
    }
    const onPaste = (event) => {
      if (saving || uploading) {
        return;
      }
      const images = imagesFromClipboard(event);
      if (!images.length) {
        return;
      }
      event.preventDefault();
      if (editing?.id) {
        uploadFiles(editing.id, images);
        return;
      }
      setPendingFiles((current) => [...current, ...images]);
      showLocalPreview(images[images.length - 1]);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [editing, modal, saving, showLocalPreview, uploadFiles, uploading]);

  const changeStatus = async (row, status) => {
    if (!row?.id || !status || status === row.status) {
      return;
    }
    setStatusBusy(row.id);
    try {
      const result = await api.setCaseStatus(row.id, status);
      const next = result.data?.status || status;
      setRows((current) => current.map((item) => (item.id === row.id ? { ...item, status: next } : item)));
      if (editing?.id === row.id) {
        setEditing((current) => (current ? { ...current, status: next } : current));
        setForm((current) => ({ ...current, status: next }));
      }
      onNotice?.({ type: "success", text: result.message || "Status updated" });
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setStatusBusy(null);
    }
  };

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setPendingFiles([]);
    setFiles([]);
    setFormError("");
    clearPreview();
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
        bookingOrderId: data.bookingOrderId || "",
        shipmentNumber: data.shipmentNumber || "",
        category: data.category || "",
        description: data.description || "",
        status: data.status || "pending_review",
      });
      setPendingFiles([]);
      setFiles(data.files || []);
      setFormError("");
      clearPreview();
      setModal(true);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const closeModal = () => {
    if (!saving && !uploading) {
      clearPreview();
      setModal(false);
    }
  };

  const save = async (event) => {
    event.preventDefault();
    const bookingOrderId = form.bookingOrderId.trim();
    const shipmentNumber = form.shipmentNumber.trim();
    if (!bookingOrderId && !shipmentNumber) {
      setFormError(IDENTIFIER_REQUIRED);
      return;
    }
    setFormError("");
    const payload = {
      bookingOrderId,
      shipmentNumber,
      category: form.category,
      description: form.description.trim(),
      status: form.status,
    };
    setSaving(true);
    try {
      let caseId = editing?.id;
      if (editing) {
        const result = await api.updateCase(editing.id, payload);
        onNotice?.({ type: "success", text: result.message });
        setEditing(result.data);
        setFiles(result.data.files || []);
      } else {
        const result = await api.createCase(payload);
        caseId = result.data.id;
        for (const file of pendingFiles) {
          await api.uploadCaseFile(caseId, file);
        }
        onNotice?.({ type: "success", text: result.message });
        clearPreview();
        setModal(false);
      }
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      setFormError(error.message);
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setSaving(false);
      setPendingFiles([]);
    }
  };

  const remove = async (row) => {
    const ok = await confirm({
      title: "Delete case",
      message: "Delete this case?",
    });
    if (!ok) {
      return;
    }
    try {
      const result = await api.deleteCase(row.id);
      onNotice?.({ type: "success", text: result.message });
      if (editing?.id === row.id) {
        clearPreview();
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
    const chosen = Array.from(event.target.files || []);
    event.target.value = "";
    if (!chosen.length || !editing?.id) {
      return;
    }
    await uploadFiles(editing.id, chosen);
  };

  const removeFile = async (file) => {
    if (!editing?.id) {
      setPendingFiles((current) => current.filter((item) => item !== file));
      if (preview?.file?.originalName === file.name && preview?.url?.startsWith("blob:")) {
        clearPreview();
      }
      return;
    }
    try {
      await api.deleteCaseFile(editing.id, file.id);
      setFiles((current) => current.filter((item) => item.id !== file.id));
      if (preview?.file?.id === file.id) {
        clearPreview();
      }
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
        <p>Collect a bad case with a booking order ID or a shipment number. Paste a screenshot or attach a file, then preview it in the case.</p>
      </div>
      <div className="search">
        <Search size={19} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search booking order ID, shipment number, or description"
          aria-describedby="badcases-search-hint"
        />
        {query ? (
          <button type="button" onClick={() => setQuery("")} aria-label="Clear search">
            <X size={17} />
          </button>
        ) : null}
      </div>
      <p id="badcases-search-hint" className="search-hint">
        {rows.length} {rows.length === 1 ? "case" : "cases"}
      </p>
      <section className="card">
        <div className="table-wrap">
          <table className="wide-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Booking order ID</th>
                <th>Shipment number</th>
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
                    Loading…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan="7" className="empty">
                    No cases yet. Create one or import the CSV template.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id} className="clickable" onClick={() => openEdit(row)}>
                    <td>{displayDate(row)}</td>
                    <td>{row.bookingOrderId || "—"}</td>
                    <td>{row.shipmentNumber || "—"}</td>
                    <td>{row.description || "—"}</td>
                    <td>{row.fileCount || "—"}</td>
                    <td className="case-status" onClick={(event) => event.stopPropagation()}>
                      <FieldSelect
                        compact
                        ariaLabel={`Status for case ${row.id}`}
                        value={row.status}
                        options={STATUSES.map((item) => ({ value: item.id, label: item.label }))}
                        onChange={(status) => changeStatus(row, status)}
                        disabled={statusBusy === row.id || saving}
                      />
                    </td>
                    <td className="actions" onClick={(event) => event.stopPropagation()}>
                      <button type="button" className="danger" onClick={() => remove(row)} aria-label="Delete case">
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
        <ModalShell
          as="form"
          busy={saving || uploading}
          onClose={closeModal}
          onSubmit={save}
          labelledBy="badcases-modal-title"
        >
            <div className="modal-head">
              <div>
                <h2 id="badcases-modal-title">{editing ? `Case #${editing.id}` : "New case"}</h2>
                <p>A booking order ID or shipment number is required. Paste a screenshot to attach it.</p>
              </div>
              <button type="button" onClick={closeModal} disabled={saving || uploading} aria-label="Close">
                <X size={18} />
              </button>
            </div>
            {formError ? (
              <div className="alert error case-form-error" role="alert">
                {formError}
              </div>
            ) : null}
            <div className="grid">
              <label>
                Booking order ID
                <input
                  value={form.bookingOrderId}
                  onChange={(event) => {
                    const value = event.target.value;
                    setForm((current) => ({ ...current, bookingOrderId: value }));
                  }}
                  disabled={saving}
                  autoComplete="off"
                  placeholder="One of the two is required"
                />
              </label>
              <label>
                Shipment number
                <input
                  value={form.shipmentNumber}
                  onChange={(event) => {
                    const value = event.target.value;
                    setForm((current) => ({ ...current, shipmentNumber: value }));
                  }}
                  disabled={saving}
                  autoComplete="off"
                  placeholder="One of the two is required"
                />
              </label>
              <label className="wide">
                Category
                <FieldSelect
                  value={form.category}
                  options={categoryOptions(form.category)}
                  onChange={(category) => setForm((current) => ({ ...current, category }))}
                  disabled={saving}
                  placeholder="None"
                />
              </label>
              <label>
                Status
                <FieldSelect
                  value={form.status}
                  options={STATUSES.map((item) => ({ value: item.id, label: item.label }))}
                  onChange={(status) => {
                    if (editing?.id) {
                      changeStatus(editing, status);
                      return;
                    }
                    setForm((current) => ({ ...current, status }));
                  }}
                  disabled={saving || statusBusy === editing?.id}
                />
              </label>
              <label className="wide">
                Description
                <textarea
                  rows="4"
                  value={form.description}
                  onChange={(event) => {
                    const value = event.target.value;
                    setForm((current) => ({ ...current, description: value }));
                  }}
                  disabled={saving}
                  placeholder="Case note"
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
                  <strong>Files</strong>
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
                    multiple
                  />
                </div>
                <div className="attach-list">
                  {pendingFiles.some((file) => String(file.type || "").startsWith("image/")) || files.some((file) => file.kind === "image") ? (
                    <div className="case-thumbs">
                      {pendingFiles.map((file, index) => (
                        <PendingImageThumb key={`${file.name}-${index}`} file={file} onOpen={() => showLocalPreview(file)} />
                      ))}
                      {files.filter((file) => file.kind === "image").map((file) => (
                        <button
                          key={file.id}
                          type="button"
                          className="case-thumb"
                          title={file.originalName}
                          onClick={() => openSavedPreview(editing.id, file)}
                        >
                          <img src={api.caseFileContentUrl(editing.id, file.id)} alt={file.originalName} />
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {!editing && pendingFiles.length === 0 && files.length === 0 ? (
                    <p className="preview-empty">Paste a screenshot, or attach docx, xlsx, or pictures.</p>
                  ) : null}
                  {pendingFiles.map((file, index) => (
                    <div key={`${file.name}-${index}`} className="attach-item">
                      <button type="button" className="attach-name" onClick={() => showLocalPreview(file)}>
                        {file.name}
                      </button>
                      <button type="button" className="danger" onClick={() => removeFile(file)} aria-label="Remove file">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                  {files.map((file) => (
                    <div key={file.id} className="attach-item">
                      <button type="button" className="attach-name" onClick={() => openSavedPreview(editing.id, file)}>
                        {file.originalName}
                      </button>
                      <em>{file.kind}</em>
                      <a
                        className="attach-download"
                        href={api.caseFileDownloadUrl(editing.id, file.id)}
                        target="_blank"
                        rel="noreferrer"
                        aria-label={`Download ${file.originalName}`}
                      >
                        <Download size={14} />
                      </a>
                      <button type="button" className="danger" onClick={() => removeFile(file)} aria-label="Remove file">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                  {preview || previewLoading ? (
                    <div className="case-file-preview">
                      <p className="case-preview-caption">{preview?.file?.originalName || "Preview"}</p>
                      <FilePreview
                        key={preview?.file?.id || preview?.url || "case-preview"}
                        preview={preview}
                        loading={previewLoading}
                      />
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={closeModal} disabled={saving || uploading}>
                Cancel
              </button>
              {editing ? (
                <button type="button" className="danger" onClick={() => remove(editing)} disabled={saving}>
                  Delete case
                </button>
              ) : null}
              <button className="primary" disabled={saving || uploading}>
                {saving ? "Saving..." : editing ? "Save" : "Submit"}
              </button>
            </div>
        </ModalShell>
      ) : null}
      {confirmDialog}
    </>
  );
});

export default FeedbackWorkspace;
