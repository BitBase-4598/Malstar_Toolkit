import { useCallback, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { api } from "./api";
import Sidebar from "./Sidebar";
import { TOOLS, TOOL_BY_ID } from "./tools";

export default function App() {
  const [notice, setNotice] = useState({ type: "", text: "" });
  const [toastLeaving, setToastLeaving] = useState(false);
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logFilters, setLogFilters] = useState({
    timestamp: "",
    action: "",
    detail: "",
    clientIp: "",
  });
  const [logTotal, setLogTotal] = useState(0);
  const [section, setSection] = useState("leave");
  const [visited, setVisited] = useState({ leave: true });
  const filesRef = useRef();
  const sopsRef = useRef();
  const askRef = useRef();
  const dashRef = useRef();
  const recordsRef = useRef();
  const pendingCitation = useRef(null);
  const [askReindexing, setAskReindexing] = useState(false);
  const [dashImporting, setDashImporting] = useState(false);
  const [recordsImporting, setRecordsImporting] = useState(false);

  const refreshLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      const result = await api.listLogs(1, 200, logFilters);
      setLogs(result.data || []);
      setLogTotal(result.pagination?.total || 0);
    } catch {
      /* keep previous log rows */
    } finally {
      setLogsLoading(false);
    }
  }, [logFilters]);

  useEffect(() => {
    if (section !== "logs") {
      return undefined;
    }
    refreshLogs();
    const timer = setInterval(refreshLogs, 4000);
    return () => clearInterval(timer);
  }, [section, refreshLogs]);

  useEffect(() => {
    if (!notice.text) {
      setToastLeaving(false);
      return undefined;
    }
    if (notice.type === "success") {
      setToastLeaving(false);
      const fadeTimer = setTimeout(() => setToastLeaving(true), 1000);
      const clearTimer = setTimeout(() => setNotice({ type: "", text: "" }), 1300);
      return () => {
        clearTimeout(fadeTimer);
        clearTimeout(clearTimer);
      };
    }
    const timer = setTimeout(() => setNotice({ type: "", text: "" }), 5000);
    return () => clearTimeout(timer);
  }, [notice]);

  const changeSection = (next) => {
    setSection(next);
    setVisited((current) => (current[next] ? current : { ...current, [next]: true }));
  };

  const openCitation = (citation) => {
    if (!citation?.sourceId) {
      return;
    }
    pendingCitation.current = citation;
    changeSection(citation.sourceType === "sop" ? "sops" : "files");
  };

  useEffect(() => {
    const citation = pendingCitation.current;
    if (!citation) {
      return;
    }
    if (citation.sourceType === "sop" && visited.sops && section === "sops") {
      pendingCitation.current = null;
      sopsRef.current?.openView(citation.sourceId);
    }
    if (citation.sourceType === "file" && visited.files && section === "files") {
      pendingCitation.current = null;
      filesRef.current?.openPreview(citation.sourceId);
    }
  }, [section, visited]);

  const current = TOOL_BY_ID[section];
  const Actions = current?.Actions;
  const actionProps = {
    recordsRef,
    recordsImporting,
    dashRef,
    dashImporting,
    filesRef,
    sopsRef,
    askRef,
    askReindexing,
  };

  const workspaceProps = (tool) => {
    if (tool.id === "logs") {
      return {
        entries: logs,
        loading: logsLoading,
        filters: logFilters,
        onFiltersChange: setLogFilters,
        total: logTotal,
      };
    }
    const props = {
      onNotice: setNotice,
      onRefreshLogs: refreshLogs,
    };
    if (tool.id === "dashboard") {
      props.onImportingChange = setDashImporting;
    }
    if (tool.id === "records") {
      props.onImportingChange = setRecordsImporting;
    }
    if (tool.id === "ask") {
      props.onOpenCitation = openCitation;
      props.onReindexingChange = setAskReindexing;
    }
    return props;
  };

  const workspaceRef = {
    dashboard: dashRef,
    records: recordsRef,
    files: filesRef,
    sops: sopsRef,
    ask: askRef,
  };

  return (
    <div className="app-shell">
      <Sidebar section={section} onSectionChange={changeSection} />
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-copy">
            <p className="topbar-kicker">{current?.layer || "MALSTAR_Toolkit"}</p>
            <h2>{current?.title || "MALSTAR_Toolkit"}</h2>
          </div>
          <div className="topbar-actions">{Actions ? <Actions {...actionProps} /> : null}</div>
        </header>
        <main className="page">
          {notice.text && notice.type === "error" && (
            <div className="alert error">
              {notice.text}
              <button type="button" onClick={() => setNotice({ type: "", text: "" })} aria-label="Dismiss">
                <X size={16} />
              </button>
            </div>
          )}
          <div className="page-stack">
            {TOOLS.map((tool) => {
              if (!visited[tool.id]) {
                return null;
              }
              const Workspace = tool.Workspace;
              return (
                <div
                  key={tool.id}
                  className={`page-panel${section === tool.id ? " active" : ""}`}
                  aria-hidden={section !== tool.id}
                >
                  {workspaceRef[tool.id] ? (
                    <Workspace ref={workspaceRef[tool.id]} {...workspaceProps(tool)} />
                  ) : (
                    <Workspace {...workspaceProps(tool)} />
                  )}
                </div>
              );
            })}
          </div>
        </main>
      </div>
      {notice.text && notice.type === "success" && (
        <div
          className={`toast success${notice.placement === "top" ? " toast-top" : ""}${toastLeaving ? " leaving" : ""}`}
          role="status"
        >
          {notice.text}
        </div>
      )}
    </div>
  );
}
