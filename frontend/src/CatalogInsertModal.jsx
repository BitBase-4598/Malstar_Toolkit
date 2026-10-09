import { Save, X } from "lucide-react";
import ModalShell from "./ModalShell";

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

const DELCL_FIELDS = [
  { key: "consigneeName", label: "Consignee Name" },
  { key: "orgaCode", label: "Orga code" },
  { key: "remark", label: "Remark" },
  { key: "senator", label: "Senator" },
  { key: "deliveryAgent", label: "Delivery Agent" },
];

const KIND = {
  icb: {
    fields: ICB_FIELDS,
    addTitle: "Add ICB station",
    editTitle: "Edit ICB station",
    hint: "Country, CW1 Branch, or ICB code identifies the station.",
  },
  unlocode: {
    fields: UNLOCO_FIELDS,
    addTitle: "Add UNLOCODE",
    editTitle: "Edit UNLOCODE",
    hint: "Country and UNLOCODE identify the location.",
  },
  delcl: {
    fields: DELCL_FIELDS,
    addTitle: "Add DE-LCL",
    editTitle: "Edit DE-LCL",
    hint: "Consignee name or orga code identifies the row.",
  },
};

export default function CatalogInsertModal({ kind, form, saving, editing, onChange, onClose, onSubmit }) {
  const isIcb = kind === "icb";
  const spec = KIND[kind] || KIND.unlocode;
  const fields = spec.fields;
  const title = editing ? spec.editTitle : spec.addTitle;
  const hint = spec.hint;

  const update = (field) => (event) => onChange({ ...form, [field]: event.target.value });

  return (
    <ModalShell as="form" busy={saving} onClose={onClose} onSubmit={onSubmit} labelledBy="catalog-modal-title">
      <div className="modal-head">
        <div>
          <h2 id="catalog-modal-title">{title}</h2>
          <p>{hint}</p>
        </div>
        <button type="button" onClick={onClose} disabled={saving} aria-label="Close">
          <X size={18} />
        </button>
      </div>
      <div className="grid">
        {fields.map((field) => (
          <label key={field.key} className={field.key === "notes" || field.key === "category" || field.key === "remark" || field.key === "deliveryAgent" ? "wide" : undefined}>
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
    </ModalShell>
  );
}
