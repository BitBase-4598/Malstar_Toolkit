import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { api } from "./api";

const emptyFilters = {
  timestamp: "",
  module: "",
  action: "",
  outcome: "",
  detail: "",
  clientIp: "",
};

const MODULES = [
  { value: "", label: "All modules" },
  { value: "records", label: "Records" },
  { value: "files", label: "Files" },
  { value: "sops", label: "SOPs" },
  { value: "dashboard", label: "Dashboard" },
  { value: "leave", label: "Leave" },
  { value: "ask", label: "Ask" },
  { value: "server", label: "Server" },
];

function pad(value) {
  return String(value).padStart(2, "0");
}

function formatLogTime(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "—";
  }
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(raw)) {
    return raw;
  }
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return raw;
  }
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function outcomeLabel(outcome) {
  const value = String(outcome || "").toLowerCase();
  if (value === "exception") {
    return "Exception";
  }
  if (value === "failure") {
    return "Failure";
  }
  if (value === "success") {
    return "Success";
  }
  return outcome || "—";
}

function copyRequestId(requestId) {
  if (!requestId || !navigator.clipboard) {
    return;
  }
  navigator.clipboard.writeText(requestId).catch(() => {});
}

export default function ActivityLog({ entries, loading, filters, onFiltersChange, total }) {
  const [draft, setDraft] = useState(filters || emptyFilters);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      onFiltersChange?.((current) => {
        if (
          current.timestamp === draft.timestamp &&
          current.module === draft.module &&
          current.action === draft.action &&
          current.outcome === draft.outcome &&
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
          <span className="log-summary-note">Key manipulations; failures highlighted</span>
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
        <select value={draft.module} onChange={update("module")} aria-label="Filter module">
          {MODULES.map((item) => (
            <option key={item.value || "all"} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <input
          value={draft.action}
          onChange={update("action")}
          placeholder="Filter action"
          aria-label="Filter action"
        />
        <select value={draft.outcome} onChange={update("outcome")} aria-label="Filter outcome">
          <option value="">All outcomes</option>
          <option value="failure">Failures only</option>
          <option value="success">Success</option>
          <option value="exception">Exception</option>
        </select>
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
        <span>Module</span>
        <span>Action</span>
        <span>Outcome</span>
        <span>Detail</span>
        <span>IP</span>
      </div>
      <div className="log-list">
        {loading && entries.length === 0 ? (
          <p className="log-empty">Loading log...</p>
        ) : entries.length === 0 ? (
          <p className="log-empty">No matching activity.</p>
        ) : (
          entries.map((entry) => {
            const failed = entry.outcome === "failure" || entry.outcome === "exception";
            return (
              <div
                key={entry.id}
                className={`log-row${failed ? " log-row-failure" : ""}`}
              >
                <time dateTime={entry.timestamp}>{formatLogTime(entry.timestamp)}</time>
                <span className="log-module">{entry.module || "—"}</span>
                <span className="log-action">{entry.action}</span>
                <span className={`log-outcome log-outcome-${entry.outcome || "unknown"}`}>
                  {outcomeLabel(entry.outcome)}
                </span>
                <span className="log-detail">
                  {entry.detail || entry.summary || "—"}
                  {entry.requestId ? (
                    <button
                      type="button"
                      className="log-request-id"
                      title="Copy request ID"
                      onClick={() => copyRequestId(entry.requestId)}
                    >
                      {entry.requestId}
                    </button>
                  ) : null}
                </span>
                <span className="log-ip">{entry.clientIp || "—"}</span>
              </div>
            );
          })
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
