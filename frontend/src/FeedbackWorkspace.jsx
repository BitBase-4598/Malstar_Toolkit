import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { Download, Pencil, Search, Trash2, Upload, X } from "lucide-react";
import { api } from "./api";
import FieldSelect from "./FieldSelect";
import { CASE_PAGE_SIZE } from "./api/cases";
import FilePreview from "./FilePreview";
import ModalShell from "./ModalShell";
import PageJump from "./PageJump";
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

const CASE_MAILBOXES = [
  "CUSLCL.SZH@LnS.maersk.com",
  "CUSLCLLEUR.SZH@LnS.maersk.com",
  "HKGLCL@LnS.maersk.com",
  "TWNLCL-CUS@LnS.maersk.com",
];

const emptyForm = {
  bookingOrderId: "",
  shipmentNumber: "",
  email: "",
  description: "",
  status: "pending_review",
};

const IDENTIFIER_REQUIRED = "Booking order ID or shipment number is required.";

function statusLabel(value) {
  return STATUSES.find((item) => item.id === value)?.label || value || "—";
}

function splitEmails(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinEmails(values) {
  return (values || []).map((item) => String(item || "").trim()).filter(Boolean).join(", ");
}

function emailLabel(value) {
  const items = splitEmails(value);
  return items.length ? items.join(", ") : "All";
}

function mailboxOptions(value) {
  const extras = splitEmails(value).filter((item) => !CASE_MAILBOXES.includes(item));
  return [...CASE_MAILBOXES, ...extras].map((item) => ({ value: item, label: item }));
}

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

const FeedbackWorkspace = forwardRef(function FeedbackWorkspace(
  { onNotice, onRefreshLogs },
  ref
) {
  const attachRef = useRef();
  const previewUrlRef = useRef("");
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const pageRef = useRef(1);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [modal, setModal] = useState(false);
  const [mode, setMode] = useState("view");
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

  const load = useCallback(async (pageToLoad) => {
    const target = pageToLoad ?? pageRef.current;
    setLoading(true);
    try {
      const result = await api.listCases(debounced, target, CASE_PAGE_SIZE);
      const meta = result.pagination || { page: target, total: 0, totalPages: 1, pageSize: CASE_PAGE_SIZE };
      setRows(result.data || []);
      pageRef.current = meta.page || target;
      setPage(meta.page || target);
      setTotal(meta.total || 0);
      setTotalPages(meta.totalPages || 1);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }, [debounced, onNotice]);

  useEffect(() => {
    load(1);
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
    if (!modal || mode === "view") {
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
  }, [editing, modal, mode, saving, showLocalPreview, uploadFiles, uploading]);

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
    setMode("new");
    setModal(true);
  };

  useImperativeHandle(ref, () => ({ openNew }));

  const applyCase = (data) => {
    setEditing(data);
    setForm({
      bookingOrderId: data.bookingOrderId || "",
      shipmentNumber: data.shipmentNumber || "",
      email: data.email || "",
      description: data.description || "",
      status: data.status || "pending_review",
    });
    setPendingFiles([]);
    setFiles(data.files || []);
    setFormError("");
    clearPreview();
  };

  const openCase = async (row, nextMode) => {
    try {
      const result = await api.getCase(row.id);
      applyCase(result.data);
      setMode(nextMode);
      setModal(true);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const closeModal = () => {
    if (!saving && !uploading) {
      clearPreview();
      setMode("view");
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
      email: joinEmails(splitEmails(form.email)),
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
      await load(editing ? pageRef.current : 1);
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
      const nextPage = rows.length === 1 && page > 1 ? page - 1 : page;
      await load(nextPage);
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
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
      <div className="page-intro">
        <p>Collect a bad case with a booking order ID or a shipment number. Paste a screenshot or attach a file, then preview it in the case.</p>
      </div>
      <div className="search">
        <Search size={19} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search booking order ID, shipment number, email, or description"
          aria-describedby="badcases-search-hint"
        />
        {query ? (
          <button type="button" onClick={() => setQuery("")} aria-label="Clear search">
            <X size={17} />
          </button>
        ) : null}
      </div>
      <p id="badcases-search-hint" className="search-hint">
        {total} {total === 1 ? "case" : "cases"}
      </p>
      <section className="card">
        <div className="table-wrap">
          <table className="wide-table badcases-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Booking order ID</th>
                <th>Shipment number</th>
                <th>Email</th>
                <th>Description</th>
                <th>Files</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading && rows.length === 0 ? (
                <tr>
                  <td colSpan="8" className="empty">
                    Loading…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan="8" className="empty">
                    No cases yet. Create one with New case.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id} className="clickable" onClick={() => openCase(row, "view")}>
                    <td>{displayDate(row)}</td>
                    <td title={row.bookingOrderId || undefined}>{row.bookingOrderId || "—"}</td>
                    <td title={row.shipmentNumber || undefined}>{row.shipmentNumber || "—"}</td>
                    <td className="case-email" title={emailLabel(row.email)}>{emailLabel(row.email)}</td>
                    <td className="case-note" title={row.description || undefined}>{row.description || "—"}</td>
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
                      <button type="button" className="case-edit" onClick={() => openCase(row, "edit")} aria-label={`Edit case ${row.id}`}>
                        <Pencil size={16} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="pagination">
          <span>
            {total === 0 ? "No cases" : `Showing ${(page - 1) * CASE_PAGE_SIZE + 1}–${Math.min(page * CASE_PAGE_SIZE, total)} of ${total}`}
          </span>
          <div className="pagination-nav">
            <button type="button" disabled={page <= 1 || loading} onClick={() => load(page - 1)}>
              Previous
            </button>
            <PageJump
              page={page}
              totalPages={totalPages}
              onChange={(next) => load(Number(next))}
              ariaLabel="Select BadCases page"
            />
            <button type="button" disabled={page >= totalPages || loading} onClick={() => load(page + 1)}>
              Next
            </button>
          </div>
        </div>
      </section>
      {modal ? (
        <ModalShell
          as={mode === "view" ? "div" : "form"}
          className="case-modal"
          busy={saving || uploading}
          onClose={closeModal}
          onSubmit={mode === "view" ? undefined : save}
          labelledBy="badcases-modal-title"
        >
            <div className="modal-head">
              <div>
                <h2 id="badcases-modal-title">
                  {mode === "new" ? "New case" : mode === "edit" ? `Edit case #${editing?.id}` : `Case #${editing?.id}`}
                </h2>
                <p>
                  {mode === "view"
                    ? "Preview only. Download attachments here, or use the pencil to edit."
                    : "A booking order ID or shipment number is required. Paste a screenshot in Files below."}
                </p>
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
              {mode === "view" ? (
                <>
                  <div className="case-view-field">
                    <span>Booking order ID</span>
                    <strong>{editing?.bookingOrderId || "—"}</strong>
                  </div>
                  <div className="case-view-field">
                    <span>Shipment number</span>
                    <strong>{editing?.shipmentNumber || "—"}</strong>
                  </div>
                  <div className="case-view-field wide">
                    <span>Email</span>
                    <strong>{emailLabel(editing?.email)}</strong>
                  </div>
                  <div className="case-view-field">
                    <span>Status</span>
                    <strong>{statusLabel(editing?.status)}</strong>
                  </div>
                  <div className="case-view-field wide">
                    <span>Description</span>
                    <p>{editing?.description || "—"}</p>
                  </div>
                  {DETAIL_FIELDS.filter(([key]) => editing?.[key]).map(([key, label]) => (
                    <div className="case-view-field" key={key}>
                      <span>{label}</span>
                      <strong>{editing[key]}</strong>
                    </div>
                  ))}
                </>
              ) : (
                <>
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
                Email
                <FieldSelect
                  multiple
                  fitMenu
                  value={splitEmails(form.email)}
                  options={[{ value: "", label: "All" }, ...mailboxOptions(form.email)]}
                  onChange={(selected) => setForm((current) => ({ ...current, email: joinEmails(selected) }))}
                  disabled={saving}
                  placeholder="All"
                  ariaLabel="Email"
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
                </>
              )}
            </div>
            <div className="case-files">
              <div className="attach-head">
                <strong>Files</strong>
                {mode !== "view" ? (
                  <button
                    type="button"
                    className="ghost"
                    disabled={saving || uploading}
                    onClick={() => attachRef.current?.click()}
                  >
                    <Upload size={16} />
                    {uploading ? "Uploading..." : "Upload"}
                  </button>
                ) : null}
                <input
                  ref={attachRef}
                  hidden
                  type="file"
                  accept={FILE_ACCEPT}
                  disabled={saving || uploading || mode === "view"}
                  onChange={editing ? attachExisting : addPendingFiles}
                  multiple
                />
              </div>
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
              <div className="attach-list">
                {files.length === 0 && pendingFiles.length === 0 ? (
                  <p className="preview-empty">{mode === "view" ? "No files." : "No files yet."}</p>
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
                    {mode !== "view" ? (
                      <button type="button" className="danger" onClick={() => removeFile(file)} aria-label="Remove file">
                        <Trash2 size={16} />
                      </button>
                    ) : null}
                  </div>
                ))}
                {preview || previewLoading ? (
                  <div className="case-file-preview">
                    <div className="case-preview-head">
                      <p className="case-preview-caption">{preview?.file?.originalName || "Preview"}</p>
                      <button type="button" className="ghost" onClick={clearPreview}>
                        缩小
                      </button>
                    </div>
                    <FilePreview
                      key={preview?.file?.id || preview?.url || "case-preview"}
                      preview={preview}
                      loading={previewLoading}
                    />
                  </div>
                ) : null}
              </div>
              {mode !== "view" ? (
                <p className="case-paste-hint">Paste a screenshot here</p>
              ) : null}
            </div>
            <div className="modal-actions">
              {mode === "view" ? (
                <>
                  <button type="button" className="secondary" onClick={closeModal}>
                    Close
                  </button>
                  <button type="button" className="primary" onClick={() => setMode("edit")}>
                    <Pencil size={16} />
                    Edit
                  </button>
                </>
              ) : (
                <>
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
                </>
              )}
            </div>
        </ModalShell>
      ) : null}
      {confirmDialog}
    </>
  );
});

export default FeedbackWorkspace;
