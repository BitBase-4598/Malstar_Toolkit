import { forwardRef, useCallback, useEffect, useImperativeHandle, useState } from "react";
import { Eye, Pencil, Trash2 } from "lucide-react";
import { api } from "./api";
import SopEditor from "./SopEditor";
import SopView from "./SopView";

const SopWorkspace = forwardRef(function SopWorkspace({ onNotice, onRefreshLogs }, ref) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("list");
  const [current, setCurrent] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.listSops(query);
      setRows(result.data || []);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }, [query, onNotice]);

  useEffect(() => {
    const timer = setTimeout(load, query ? 250 : 0);
    return () => clearTimeout(timer);
  }, [load, query]);

  const openNew = () => {
    setCurrent(null);
    setMode("edit");
  };

  useImperativeHandle(ref, () => ({ openNew }));

  const openView = async (id) => {
    try {
      const result = await api.getSop(id);
      setCurrent(result.data);
      setMode("view");
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const openEdit = async (id) => {
    try {
      const result = await api.getSop(id);
      setCurrent(result.data);
      setMode("edit");
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const remove = async (row) => {
    if (!window.confirm(`Delete SOP "${row.title}"?`)) {
      return;
    }
    try {
      const result = await api.deleteSop(row.id);
      onNotice?.({ type: "success", text: result.message });
      setMode("list");
      setCurrent(null);
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const save = async (payload) => {
    setSaving(true);
    try {
      const result = current?.id
        ? await api.updateSop(current.id, payload)
        : await api.createSop(payload);
      onNotice?.({ type: "success", text: result.message });
      setCurrent(result.data);
      setMode("view");
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setSaving(false);
    }
  };

  if (mode === "edit") {
    return (
      <SopEditor
        sop={current}
        saving={saving}
        onCancel={() => setMode(current ? "view" : "list")}
        onSubmit={save}
        onNotice={onNotice}
        onRefreshLogs={onRefreshLogs}
      />
    );
  }

  if (mode === "view" && current) {
    return (
      <SopView
        sop={current}
        onEdit={() => setMode("edit")}
        onDelete={() => remove(current)}
        onNotice={onNotice}
      />
    );
  }

  return (
    <section className="card">
      <div className="summary">
        <span className="summary-count">
          <strong>{rows.length}</strong> {rows.length === 1 ? "SOP" : "SOPs"}
        </span>
      </div>
      <div className="search file-search">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search SOPs by title, owner, or revision"
        />
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Owner</th>
              <th>Revision</th>
              <th>Status</th>
              <th>Steps</th>
              <th>Files</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="7" className="empty">
                  Loading...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan="7" className="empty">
                  No SOPs yet. Create one to document a process.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <strong>{row.title}</strong>
                  </td>
                  <td>{row.owner || "-"}</td>
                  <td>{row.revision || "-"}</td>
                  <td>
                    <span className={`status-pill ${row.status}`}>{row.status}</span>
                  </td>
                  <td>{row.stepCount}</td>
                  <td>{row.attachmentCount}</td>
                  <td>
                    <div className="actions">
                      <button type="button" onClick={() => openView(row.id)} aria-label="View SOP">
                        <Eye size={16} />
                      </button>
                      <button type="button" onClick={() => openEdit(row.id)} aria-label="Edit SOP">
                        <Pencil size={16} />
                      </button>
                      <button type="button" className="danger" onClick={() => remove(row)} aria-label="Delete SOP">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
});

export default SopWorkspace;
