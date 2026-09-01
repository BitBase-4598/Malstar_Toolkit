import { useEffect } from "react";
import { Save, X } from "lucide-react";

const ICB_FIELDS = [
  { key: "country", label: "Country", required: true },
  { key: "location", label: "Location" },
  { key: "branch", label: "CW1 Branch" },
  { key: "unloco", label: "UNLOCO" },
  { key: "groupCode", label: "Group code" },
  { key: "groupName", label: "Group name" },
  { key: "agentCode", label: "Agent code" },
  { key: "icbCode", label: "ICB code" },
];

const UNLOCO_FIELDS = [
  { key: "countryName", label: "Country Name" },
  { key: "countryCode", label: "Country", required: true },
  { key: "unCode", label: "UNLOCODE", required: true },
  { key: "portName", label: "Port" },
  { key: "category", label: "LCL Category" },
];

export default function CatalogInsertModal({ kind, form, saving, editing, onChange, onClose, onSubmit }) {
  const isIcb = kind === "icb";
  const fields = isIcb ? ICB_FIELDS : UNLOCO_FIELDS;
  const title = editing
    ? isIcb
      ? "Edit ICB station"
      : "Edit UNLOCODE"
    : isIcb
      ? "Add ICB station"
      : "Add UNLOCODE";
  const hint = isIcb
    ? "Country, CW1 Branch, or ICB code identifies the station."
    : "Country and UNLOCODE identify the location.";

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
            <h2>{title}</h2>
            <p>{hint}</p>
          </div>
          <button type="button" onClick={onClose} disabled={saving} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="grid">
          {fields.map((field) => (
            <label key={field.key} className={field.key === "notes" || field.key === "category" ? "wide" : undefined}>
              {field.label}
              {field.required ? " *" : ""}
              <input
                required={Boolean(field.required)}
                name={field.key}
                value={form[field.key] || ""}
                onChange={update(field.key)}
                disabled={saving}
              />
            </label>
          ))}
          {isIcb ? (
            <label className="wide">
              Notes
              <textarea rows="2" value={form.notes || ""} onChange={update("notes")} disabled={saving} />
            </label>
          ) : null}
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
