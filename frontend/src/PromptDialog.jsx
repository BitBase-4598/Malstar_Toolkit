import { useState } from "react";
import { X } from "lucide-react";
import ModalShell from "./ModalShell";

export default function PromptDialog({
  title = "Rename",
  message,
  label = "Name",
  defaultValue = "",
  confirmLabel = "Save",
  cancelLabel = "Cancel",
  busy = false,
  onCancel,
  onConfirm,
}) {
  const [value, setValue] = useState(defaultValue);

  const submit = (event) => {
    event.preventDefault();
    const next = value.trim();
    if (!next || busy) {
      return;
    }
    onConfirm(next);
  };

  return (
    <ModalShell
      as="form"
      className="modal-confirm"
      busy={busy}
      onClose={busy ? undefined : onCancel}
      onSubmit={submit}
      labelledBy="prompt-title"
      describedBy={message ? "prompt-message" : undefined}
    >
      <div className="modal-head">
        <div>
          <h2 id="prompt-title">{title}</h2>
        </div>
        <button type="button" onClick={onCancel} disabled={busy} aria-label="Close">
          <X size={18} />
        </button>
      </div>
      <div className="modal-body">
        {message ? <p id="prompt-message">{message}</p> : null}
        <label>
          {label}
          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            disabled={busy}
            required
          />
        </label>
      </div>
      <div className="modal-actions">
        <button type="button" className="secondary" onClick={onCancel} disabled={busy}>
          {cancelLabel}
        </button>
        <button className="primary" disabled={busy || !value.trim()}>
          {busy ? "Working..." : confirmLabel}
        </button>
      </div>
    </ModalShell>
  );
}
