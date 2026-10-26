import { useEffect, useRef, useState } from "react";
import { Download, Trash2, Upload, X } from "lucide-react";
import { api } from "./api";
import FieldSelect from "./FieldSelect";
import FilePreview from "./FilePreview";
import ModalShell from "./ModalShell";
import {
  DETAIL_FIELDS,
  FILE_ACCEPT,
  STATUSES,
  imagesFromClipboard,
  joinEmails,
  mailboxOptions,
  splitEmails,
} from "./caseConstants";

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

export default function CaseFormModal({
  mode,
  editing,
  form,
  setForm,
  formError,
  saving,
  uploading,
  statusBusy,
  pendingFiles,
  files,
  preview,
  previewLoading,
  onClose,
  onSave,
  onDelete,
  onChangeStatus,
  onAddPendingFiles,
  onAttachExisting,
  onRemoveFile,
  onShowLocalPreview,
  onOpenSavedPreview,
  onClearPreview,
  onPendingFromClipboard,
}) {
  const attachRef = useRef();

  useEffect(() => {
    const onPaste = (event) => {
      if (saving || uploading) {
        return;
      }
      const images = imagesFromClipboard(event);
      if (!images.length) {
        return;
      }
      event.preventDefault();
      onPendingFromClipboard(images);
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [onPendingFromClipboard, saving, uploading]);

  return (
    <ModalShell
      as="form"
      className="case-modal"
      busy={saving || uploading}
      onClose={onClose}
      onSubmit={onSave}
      labelledBy="badcases-modal-title"
      closeOnOverlay={false}
      closeOnEscape={false}
    >
      <div className="modal-head">
        <div>
          <h2 id="badcases-modal-title">
            {mode === "new" ? "New case" : `Edit case #${editing?.id}`}
          </h2>
          <p>A booking order ID or shipment number is required. Paste a screenshot in Files below.</p>
        </div>
        <button type="button" onClick={onClose} disabled={saving || uploading} aria-label="Close">
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
                onChangeStatus(editing, status);
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
      </div>
      <div className="case-files">
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
            onChange={editing ? onAttachExisting : onAddPendingFiles}
            multiple
          />
        </div>
        {pendingFiles.some((file) => String(file.type || "").startsWith("image/")) ||
        files.some((file) => file.kind === "image") ? (
          <div className="case-thumbs">
            {pendingFiles.map((file, index) => (
              <PendingImageThumb
                key={`${file.name}-${index}`}
                file={file}
                onOpen={() => onShowLocalPreview(file)}
              />
            ))}
            {files
              .filter((file) => file.kind === "image")
              .map((file) => (
                <button
                  key={file.id}
                  type="button"
                  className="case-thumb"
                  title={file.originalName}
                  onClick={() => onOpenSavedPreview(editing.id, file)}
                >
                  <img src={api.caseFileContentUrl(editing.id, file.id)} alt={file.originalName} />
                </button>
              ))}
          </div>
        ) : null}
        <div className="attach-list">
          {files.length === 0 && pendingFiles.length === 0 ? (
            <p className="preview-empty">No files yet.</p>
          ) : null}
          {pendingFiles.map((file, index) => (
            <div key={`${file.name}-${index}`} className="attach-item">
              <button type="button" className="attach-name" onClick={() => onShowLocalPreview(file)}>
                {file.name}
              </button>
              <button
                type="button"
                className="danger"
                onClick={() => onRemoveFile(file)}
                aria-label="Remove file"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
          {files.map((file) => (
            <div key={file.id} className="attach-item">
              <button
                type="button"
                className="attach-name"
                onClick={() => onOpenSavedPreview(editing.id, file)}
              >
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
              <button
                type="button"
                className="danger"
                onClick={() => onRemoveFile(file)}
                aria-label="Remove file"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
          {preview || previewLoading ? (
            <div className="case-file-preview">
              <div className="case-preview-head">
                <p className="case-preview-caption">{preview?.file?.originalName || "Preview"}</p>
                <button type="button" className="ghost" onClick={onClearPreview}>
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
        <p className="case-paste-hint">Paste a screenshot here</p>
      </div>
      <div className="modal-actions">
        <button type="button" className="secondary" onClick={onClose} disabled={saving || uploading}>
          Cancel
        </button>
        {editing ? (
          <button type="button" className="danger" onClick={() => onDelete(editing)} disabled={saving}>
            Delete case
          </button>
        ) : null}
        <button className="primary" disabled={saving || uploading}>
          {saving ? "Saving..." : editing ? "Save" : "Submit"}
        </button>
      </div>
    </ModalShell>
  );
}
