import { useEffect } from "react";
import { Save, X } from "lucide-react";

export default function RecordModal({ editing, form, saving, onChange, onClose, onSubmit }) {
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "Escape" && !saving) {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, saving]);

  const update = (field) => (event) => onChange({ ...form, [field]: event.target.value });

  return (
    <div className="overlay" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && !saving && onClose()}>
      <form className="modal" onSubmit={onSubmit}>
        <div className="modal-head">
          <div>
            <h2>{editing ? "Edit record" : "Add record"}</h2>
            <p>CTRLOrgcode and Customer identify the record.</p>
          </div>
          <button type="button" onClick={onClose} disabled={saving} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="grid">
          <label>
            CTRLOrgcode *
            <input
              required
              name="ctrlOrgcode"
              value={form.ctrlOrgcode}
              onChange={update("ctrlOrgcode")}
              disabled={saving}
            />
          </label>
          <label>
            Customer *
            <input
              required
              name="customer"
              value={form.customer}
              onChange={update("customer")}
              disabled={saving}
            />
          </label>
          <label className="wide">
            Remark1
            <textarea rows="2" value={form.remark1} onChange={update("remark1")} disabled={saving} />
          </label>
          <label className="wide">
            Remark2
            <textarea rows="2" value={form.remark2} onChange={update("remark2")} disabled={saving} />
          </label>
          <label className="wide">
            Remark3
            <textarea rows="2" value={form.remark3} onChange={update("remark3")} disabled={saving} />
          </label>
        </div>
        <div className="modal-actions">
          <button type="button" className="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button className="primary" disabled={saving}>
            <Save size={16} />
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}
