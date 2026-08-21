import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { Download, Pencil, Trash2 } from "lucide-react";
import { api } from "./api";
import FilePreview from "./FilePreview";

function formatSize(bytes) {
  const size = Number(bytes) || 0;
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

const FileManager = forwardRef(function FileManager({ onNotice, onRefreshLogs }, ref) {
  const inputRef = useRef();
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const splitRef = useRef(null);
  const listWidthRef = useRef(420);
  const [listWidth, setListWidth] = useState(() => {
    const saved = Number(window.localStorage.getItem("malstar-files-list-width"));
    return saved >= 240 ? saved : 420;
  });
  const [dragging, setDragging] = useState(false);
  const draggingRef = useRef(false);

  listWidthRef.current = listWidth;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.listFiles(query);
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

  const showPreview = async (id) => {
    setSelectedId(id);
    setPreviewLoading(true);
    try {
      const result = await api.previewFile(id);
      setPreview(result.data);
    } catch (error) {
      setPreview(null);
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setPreviewLoading(false);
    }
  };

  const upload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    setUploading(true);
    try {
      const result = await api.uploadFile(file);
      onNotice?.({ type: "success", text: result.message });
      await load();
      await onRefreshLogs?.();
      if (result.data?.id) {
        await showPreview(result.data.id);
      }
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setUploading(false);
    }
  };

  useImperativeHandle(ref, () => ({
    openUpload: () => inputRef.current?.click(),
    openPreview: (id) => {
      if (id) {
        showPreview(id);
      }
    },
    uploading,
  }));

  const rename = async (row) => {
    const next = window.prompt("Rename file", row.originalName);
    if (!next || next.trim() === row.originalName) {
      return;
    }
    try {
      const result = await api.renameFile(row.id, next.trim());
      onNotice?.({ type: "success", text: result.message });
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const remove = async (row) => {
    if (!window.confirm(`Delete ${row.originalName}?`)) {
      return;
    }
    try {
      const result = await api.deleteFile(row.id);
      onNotice?.({ type: "success", text: result.message });
      if (selectedId === row.id) {
        setSelectedId(null);
        setPreview(null);
      }
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const onSplitPointerDown = (event) => {
    event.preventDefault();
    draggingRef.current = true;
    setDragging(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onSplitPointerMove = (event) => {
    if (!draggingRef.current || !splitRef.current) {
      return;
    }
    const rect = splitRef.current.getBoundingClientRect();
    const max = Math.max(rect.width - 280, 240);
    const next = Math.min(Math.max(event.clientX - rect.left, 240), max);
    setListWidth(next);
  };

  const stopSplitDrag = () => {
    if (!draggingRef.current) {
      return;
    }
    draggingRef.current = false;
    setDragging(false);
    window.localStorage.setItem("malstar-files-list-width", String(listWidthRef.current));
  };

  return (
    <div
      ref={splitRef}
      className={`tool-split files-split${dragging ? " is-resizing" : ""}`}
    >
      <input
        ref={inputRef}
        hidden
        type="file"
        accept=".docx,.xlsx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        onChange={upload}
      />
      <section className="card file-list-card" style={{ width: `${listWidth}px` }}>
        <div className="summary">
          <span className="summary-count">
            <strong>{rows.length}</strong> {rows.length === 1 ? "file" : "files"}
          </span>
          {uploading ? <span>Uploading...</span> : null}
        </div>
        <div className="search file-search">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search files"
          />
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Size</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="5" className="empty">
                    Loading...
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan="5" className="empty">
                    No files yet. Upload a .docx or .xlsx file.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr
                    key={row.id}
                    className={selectedId === row.id ? "selected" : ""}
                    onClick={() => showPreview(row.id)}
                  >
                    <td>
                      <strong>{row.originalName}</strong>
                    </td>
                    <td>{row.kind.toUpperCase()}</td>
                    <td>{formatSize(row.size)}</td>
                    <td>{row.uploadedAt}</td>
                    <td>
                      <div className="actions">
                        <a
                          href={api.downloadUrl(row.id)}
                          onClick={(event) => event.stopPropagation()}
                          aria-label="Download file"
                        >
                          <Download size={16} />
                        </a>
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            rename(row);
                          }}
                          aria-label="Rename file"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          type="button"
                          className="danger"
                          onClick={(event) => {
                            event.stopPropagation();
                            remove(row);
                          }}
                          aria-label="Delete file"
                        >
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
      <div
        className="split-handle"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize file list"
        onPointerDown={onSplitPointerDown}
        onPointerMove={onSplitPointerMove}
        onPointerUp={stopSplitDrag}
        onPointerCancel={stopSplitDrag}
      />
      <section className="card preview-card">
        <div className="summary">
          <strong>{preview?.file?.originalName || "Preview"}</strong>
        </div>
        <div className="preview-body">
          <FilePreview key={preview?.file?.id || "empty"} preview={preview} loading={previewLoading} />
        </div>
      </section>
    </div>
  );
});

export default FileManager;
