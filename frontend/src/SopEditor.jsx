import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Plus, Save, Trash2, X } from "lucide-react";
import { api } from "./api";

const emptySop = {
  title: "",
  purpose: "",
  owner: "",
  revision: "",
  status: "draft",
  steps: [""],
  attachmentIds: [],
};

export default function SopEditor({ sop, saving, onCancel, onSubmit, onNotice, onRefreshLogs }) {
  const [form, setForm] = useState(emptySop);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    const next = sop
      ? {
          title: sop.title || "",
          purpose: sop.purpose || "",
          owner: sop.owner || "",
          revision: sop.revision || "",
          status: sop.status || "draft",
          steps: sop.steps?.length ? sop.steps.map((step) => step.instruction) : [""],
          attachmentIds: sop.attachments?.map((item) => item.id) || [],
        }
      : emptySop;
    setForm(next);
  }, [sop]);

  useEffect(() => {
    api.listFiles()
      .then((result) => setFiles(result.data || []))
      .catch((error) => onNotice?.({ type: "error", text: error.message }));
  }, [onNotice]);

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));

  const setStep = (index, value) => {
    setForm((current) => {
      const steps = [...current.steps];
      steps[index] = value;
      return { ...current, steps };
    });
  };

  const addStep = () => setForm((current) => ({ ...current, steps: [...current.steps, ""] }));

  const removeStep = (index) => {
    setForm((current) => {
      const steps = current.steps.filter((_, itemIndex) => itemIndex !== index);
      return { ...current, steps: steps.length ? steps : [""] };
    });
  };

  const moveStep = (index, direction) => {
    setForm((current) => {
      const next = index + direction;
      if (next < 0 || next >= current.steps.length) {
        return current;
      }
      const steps = [...current.steps];
      [steps[index], steps[next]] = [steps[next], steps[index]];
      return { ...current, steps };
    });
  };

  const toggleFile = (id) => {
    setForm((current) => {
      const has = current.attachmentIds.includes(id);
      return {
        ...current,
        attachmentIds: has
          ? current.attachmentIds.filter((item) => item !== id)
          : [...current.attachmentIds, id],
      };
    });
  };

  const uploadAttachment = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    setUploading(true);
    try {
      const result = await api.uploadFile(file);
      const uploaded = result.data;
      setFiles((current) => [uploaded, ...current.filter((item) => item.id !== uploaded.id)]);
      setForm((current) => ({
        ...current,
        attachmentIds: current.attachmentIds.includes(uploaded.id)
          ? current.attachmentIds
          : [...current.attachmentIds, uploaded.id],
      }));
      onNotice?.({ type: "success", text: "File uploaded and attached." });
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setUploading(false);
    }
  };

  const save = (event) => {
    event.preventDefault();
    onSubmit({
      ...form,
      steps: form.steps.map((instruction) => ({ instruction })),
    });
  };

  return (
    <form className="card sop-editor" onSubmit={save}>
      <div className="summary">
        <strong>{sop ? "Edit SOP" : "New SOP"}</strong>
        <button type="button" className="ghost" onClick={onCancel} disabled={saving}>
          <X size={16} />
          Cancel
        </button>
      </div>
      <div className="sop-editor-body">
        <div className="grid">
          <label>
            Title *
            <input required value={form.title} onChange={update("title")} disabled={saving} />
          </label>
          <label>
            Owner
            <input value={form.owner} onChange={update("owner")} disabled={saving} />
          </label>
          <label>
            Revision
            <input value={form.revision} onChange={update("revision")} disabled={saving} />
          </label>
          <label>
            Status
            <select value={form.status} onChange={update("status")} disabled={saving}>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
            </select>
          </label>
          <label className="wide">
            Purpose
            <textarea rows="3" value={form.purpose} onChange={update("purpose")} disabled={saving} />
          </label>
        </div>
        <div className="sop-section">
          <div className="summary">
            <strong>Steps</strong>
            <button type="button" className="ghost" onClick={addStep} disabled={saving}>
              <Plus size={16} />
              Add step
            </button>
          </div>
          {form.steps.map((instruction, index) => (
            <div className="sop-step-edit" key={index}>
              <span>{index + 1}</span>
              <textarea
                rows="2"
                value={instruction}
                onChange={(event) => setStep(index, event.target.value)}
                disabled={saving}
                placeholder="Describe this step"
              />
              <div className="actions">
                <button type="button" onClick={() => moveStep(index, -1)} disabled={saving || index === 0} aria-label="Move up">
                  <ArrowUp size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => moveStep(index, 1)}
                  disabled={saving || index === form.steps.length - 1}
                  aria-label="Move down"
                >
                  <ArrowDown size={16} />
                </button>
                <button type="button" className="danger" onClick={() => removeStep(index)} disabled={saving} aria-label="Remove step">
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
        <div className="sop-section">
          <div className="summary">
            <strong>Attachments</strong>
            <label className="ghost upload-label">
              {uploading ? "Uploading..." : "Upload and attach"}
              <input hidden type="file" accept=".docx,.xlsx" onChange={uploadAttachment} disabled={saving || uploading} />
            </label>
          </div>
          <div className="attach-list">
            {files.length === 0 ? (
              <p className="preview-empty">No files in the library yet.</p>
            ) : (
              files.map((file) => (
                <label key={file.id} className="attach-item">
                  <input
                    type="checkbox"
                    checked={form.attachmentIds.includes(file.id)}
                    onChange={() => toggleFile(file.id)}
                    disabled={saving}
                  />
                  <span>{file.originalName}</span>
                  <em>{file.kind}</em>
                </label>
              ))
            )}
          </div>
        </div>
      </div>
      <div className="modal-actions">
        <button type="button" className="secondary" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
        <button className="primary" disabled={saving}>
          <Save size={16} />
          {saving ? "Saving..." : "Save SOP"}
        </button>
      </div>
    </form>
  );
}
