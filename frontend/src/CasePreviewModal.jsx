import { Download, Pencil, X } from "lucide-react";
import { api } from "./api";
import FilePreview from "./FilePreview";
import ModalShell from "./ModalShell";
import {
  DETAIL_FIELDS,
  emailLabel,
  joinEmails,
  splitEmails,
  statusLabel,
} from "./caseConstants";

export default function CasePreviewModal({
  editing,
  files,
  preview,
  previewLoading,
  copiedField,
  busy,
  onClose,
  onEdit,
  onCopy,
  onOpenPreview,
  onClearPreview,
}) {
  return (
    <ModalShell
      as="div"
      className="case-modal"
      busy={busy}
      onClose={onClose}
      labelledBy="badcases-modal-title"
    >
      <div className="modal-head">
        <div>
          <h2 id="badcases-modal-title">Case #{editing?.id}</h2>
          <p>Preview only. Download attachments here, or use the pencil to edit.</p>
        </div>
        <button type="button" onClick={onClose} disabled={busy} aria-label="Close">
          <X size={18} />
        </button>
      </div>
      <div className="grid">
        <div className="case-view-field">
          <span>Booking order ID</span>
          <div className="case-copy-line">
            <strong>{editing?.bookingOrderId || "—"}</strong>
            {editing?.bookingOrderId ? (
              <button
                type="button"
                className="ghost case-copy"
                onClick={() => onCopy("booking", editing.bookingOrderId)}
              >
                {copiedField === "booking" ? "Copied" : "Copy"}
              </button>
            ) : null}
          </div>
        </div>
        <div className="case-view-field">
          <span>Shipment number</span>
          <div className="case-copy-line">
            <strong>{editing?.shipmentNumber || "—"}</strong>
            {editing?.shipmentNumber ? (
              <button
                type="button"
                className="ghost case-copy"
                onClick={() => onCopy("shipment", editing.shipmentNumber)}
              >
                {copiedField === "shipment" ? "Copied" : "Copy"}
              </button>
            ) : null}
          </div>
        </div>
        <div className="case-view-field wide">
          <span>Email</span>
          <div className="case-copy-line">
            <strong>{emailLabel(editing?.email)}</strong>
            {splitEmails(editing?.email).length ? (
              <button
                type="button"
                className="ghost case-copy"
                onClick={() => onCopy("email", joinEmails(splitEmails(editing.email)))}
              >
                {copiedField === "email" ? "Copied" : "Copy"}
              </button>
            ) : null}
          </div>
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
      </div>
      <div className="case-files">
        <div className="attach-head">
          <strong>Files</strong>
        </div>
        {files.some((file) => file.kind === "image") ? (
          <div className="case-thumbs">
            {files
              .filter((file) => file.kind === "image")
              .map((file) => (
                <button
                  key={file.id}
                  type="button"
                  className="case-thumb"
                  title={file.originalName}
                  onClick={() => onOpenPreview(editing.id, file)}
                >
                  <img src={api.caseFileContentUrl(editing.id, file.id)} alt={file.originalName} />
                </button>
              ))}
          </div>
        ) : null}
        <div className="attach-list">
          {files.length === 0 ? <p className="preview-empty">No files.</p> : null}
          {files.map((file) => (
            <div key={file.id} className="attach-item">
              <button type="button" className="attach-name" onClick={() => onOpenPreview(editing.id, file)}>
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
      </div>
      <div className="modal-actions">
        <button type="button" className="secondary" onClick={onClose}>
          Close
        </button>
        <button type="button" className="primary" onClick={onEdit}>
          <Pencil size={16} />
          Edit
        </button>
      </div>
    </ModalShell>
  );
}
