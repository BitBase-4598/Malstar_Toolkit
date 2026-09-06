import { X } from "lucide-react";
import ModalShell from "./ModalShell";

export default function ConfirmDialog({
  title = "Please confirm",
  message,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  danger = true,
  busy = false,
  onCancel,
  onConfirm,
}) {
  return (
    <ModalShell
      className="modal-confirm"
      busy={busy}
      onClose={busy ? undefined : onCancel}
      labelledBy="confirm-title"
      describedBy="confirm-message"
    >
      <div className="modal-head">
        <div>
          <h2 id="confirm-title">{title}</h2>
        </div>
        <button type="button" onClick={onCancel} disabled={busy} aria-label="Close">
          <X size={18} />
        </button>
      </div>
      <div className="modal-body">
        <p id="confirm-message">{message}</p>
      </div>
      <div className="modal-actions">
        <button type="button" className="secondary" onClick={onCancel} disabled={busy}>
          {cancelLabel}
        </button>
        <button
          type="button"
          className={danger ? "danger" : "primary"}
          onClick={onConfirm}
          disabled={busy}
        >
          {busy ? "Working..." : confirmLabel}
        </button>
      </div>
    </ModalShell>
  );
}
