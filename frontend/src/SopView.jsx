import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { api } from "./api";
import FilePreview from "./FilePreview";

export default function SopView({ sop, onEdit, onDelete, onNotice }) {
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [selectedId, setSelectedId] = useState(null);

  const openPreview = async (file) => {
    setSelectedId(file.id);
    setPreviewLoading(true);
    try {
      const result = await api.previewFile(file.id);
      setPreview(result.data);
    } catch (error) {
      setPreview(null);
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <div className="tool-split">
      <section className="card sop-view">
        <div className="summary">
          <span>
            <strong>{sop.title}</strong>
            <span className={`status-pill ${sop.status}`}>{sop.status}</span>
          </span>
          <div className="actions">
            <button type="button" onClick={onEdit} aria-label="Edit SOP">
              <Pencil size={16} />
            </button>
            <button type="button" className="danger" onClick={onDelete} aria-label="Delete SOP">
              <Trash2 size={16} />
            </button>
          </div>
        </div>
        <div className="sop-view-body">
          <dl className="sop-meta">
            <div>
              <dt>Owner</dt>
              <dd>{sop.owner || "-"}</dd>
            </div>
            <div>
              <dt>Revision</dt>
              <dd>{sop.revision || "-"}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{sop.updatedAt}</dd>
            </div>
          </dl>
          <h3>Purpose</h3>
          <p className="sop-purpose">{sop.purpose || "No purpose recorded."}</p>
          <h3>Steps</h3>
          {sop.steps?.length ? (
            <ol className="sop-steps">
              {sop.steps.map((step) => (
                <li key={step.id || step.stepNumber}>{step.instruction}</li>
              ))}
            </ol>
          ) : (
            <p className="preview-empty">No steps yet.</p>
          )}
          <h3>Attachments</h3>
          {sop.attachments?.length ? (
            <ul className="attach-links">
              {sop.attachments.map((file) => (
                <li key={file.id}>
                  <button
                    type="button"
                    className={selectedId === file.id ? "active" : ""}
                    onClick={() => openPreview(file)}
                  >
                    {file.originalName}
                  </button>
                  <a href={api.downloadUrl(file.id)}>Download</a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="preview-empty">No attachments.</p>
          )}
        </div>
      </section>
      <section className="card preview-card">
        <div className="summary">
          <strong>{preview?.file?.originalName || "Attachment preview"}</strong>
        </div>
        <div className="preview-body">
          <FilePreview key={preview?.file?.id || "empty"} preview={preview} loading={previewLoading} />
        </div>
      </section>
    </div>
  );
}
