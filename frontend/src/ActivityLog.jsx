import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { api } from "./api";

const emptyFilters = {
  timestamp: "",
  action: "",
  detail: "",
  clientIp: "",
};

export default function ActivityLog({ entries, loading, filters, onFiltersChange, total }) {
  const [draft, setDraft] = useState(filters || emptyFilters);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      onFiltersChange?.((current) => {
        if (
          current.timestamp === draft.timestamp &&
          current.action === draft.action &&
          current.detail === draft.detail &&
          current.clientIp === draft.clientIp
        ) {
          return current;
        }
        return { ...draft };
      });
    }, 300);
    return () => clearTimeout(timer);
  }, [draft, onFiltersChange]);

  const update = (field) => (event) => {
    setDraft((current) => ({ ...current, [field]: event.target.value }));
  };

  const exportCsv = async () => {
    setExporting(true);
    try {
      const blob = await api.exportLogs(draft);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `activity-log-${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      window.alert(error.message);
    } finally {
      setExporting(false);
    }
  };

  return (
    <section className="card log-card">
      <div className="summary">
        <span>
          <strong>Activity log</strong>
          <span className="log-summary-note">Create, update, delete, and import only</span>
        </span>
        <button type="button" className="ghost" onClick={exportCsv} disabled={exporting}>
          <Download size={16} />
          {exporting ? "Exporting..." : "Export CSV"}
        </button>
      </div>
      <div className="log-filters">
        <input
          value={draft.timestamp}
          onChange={update("timestamp")}
          placeholder="Filter timestamp"
          aria-label="Filter timestamp"
        />
        <input
          value={draft.action}
          onChange={update("action")}
          placeholder="Filter action"
          aria-label="Filter action"
        />
        <input
          value={draft.detail}
          onChange={update("detail")}
          placeholder="Filter detail"
          aria-label="Filter detail"
        />
        <input
          value={draft.clientIp}
          onChange={update("clientIp")}
          placeholder="Filter IP"
          aria-label="Filter client IP"
        />
      </div>
      <div className="log-row log-head">
        <span>Timestamp</span>
        <span>Action</span>
        <span>Detail</span>
        <span>IP</span>
      </div>
      <div className="log-list">
        {loading && entries.length === 0 ? (
          <p className="log-empty">Loading log...</p>
        ) : entries.length === 0 ? (
          <p className="log-empty">No matching activity.</p>
        ) : (
          entries.map((entry) => (
            <div key={entry.id} className="log-row">
              <time dateTime={entry.timestamp}>{entry.timestamp}</time>
              <span className="log-action">{entry.action}</span>
              <span className="log-detail">{entry.detail || "—"}</span>
              <span className="log-ip">{entry.clientIp || "—"}</span>
            </div>
          ))
        )}
      </div>
      {typeof total === "number" ? (
        <div className="pagination">
          <span>
            Showing {entries.length} of {total} key events
          </span>
        </div>
      ) : null}
    </section>
  );
}
