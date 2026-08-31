import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { api } from "./api";
import Sidebar from "./Sidebar";
import { TOOLS, TOOL_BY_ID } from "./tools";
import Dashboard from "./Dashboard";

const LclDashboard = lazy(() => import("./LclDashboard"));
const GcaDashboard = lazy(() => import("./GcaDashboard"));

const DASH_PAGES = [
  { id: "ops", label: "MALSTAR_Ops" },
  { id: "lcl", label: "LCL Volume" },
  { id: "gca", label: "GCA Hypercare" },
];

export default function App() {
  const [notice, setNotice] = useState({ type: "", text: "" });
  const [toastLeaving, setToastLeaving] = useState(false);
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logFilters, setLogFilters] = useState({
    timestamp: "",
    module: "",
    action: "",
    outcome: "",
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
  const lclRef = useRef();
  const gcaRef = useRef();
  const recordsRef = useRef();
  const feedbackRef = useRef();
  const pendingCitation = useRef(null);
  const [askReindexing, setAskReindexing] = useState(false);
  const [dashImporting, setDashImporting] = useState(false);
  const [lclImporting, setLclImporting] = useState(false);
  const [gcaImporting, setGcaImporting] = useState(false);
  const [dashPage, setDashPage] = useState("ops");
  const [dashPagesVisited, setDashPagesVisited] = useState({ ops: true });
  const [recordsImporting, setRecordsImporting] = useState(false);
  const [feedbackImporting, setFeedbackImporting] = useState(false);
  const [searchTab, setSearchTab] = useState("remarks");

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

  const changeDashPage = (next) => {
    setDashPage(next);
    setDashPagesVisited((current) => (current[next] ? current : { ...current, [next]: true }));
  };

  useEffect(() => {
    if (section === "dashboard") {
      import("./LclDashboard");
    }
  }, [section]);

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
    searchTab,
    feedbackRef,
    feedbackImporting,
    dashRef,
    dashImporting,
    dashPage,
    lclRef,
    lclImporting,
    gcaRef,
    gcaImporting,
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
      props.searchTab = searchTab;
      props.onSearchTabChange = setSearchTab;
    }
    if (tool.id === "feedback") {
      props.onImportingChange = setFeedbackImporting;
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
    feedback: feedbackRef,
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
            {section === "dashboard" ? (
              <div className="topbar-page-switch" role="tablist" aria-label="Dashboard page">
                {DASH_PAGES.map((page) => (
                  <button
                    key={page.id}
                    type="button"
                    role="tab"
                    aria-selected={dashPage === page.id}
                    className={dashPage === page.id ? "primary" : "ghost"}
                    onMouseEnter={() => {
                      if (page.id === "lcl") {
                        import("./LclDashboard");
                      }
                    }}
                    onClick={() => changeDashPage(page.id)}
                  >
                    {page.label}
                  </button>
                ))}
              </div>
            ) : (
              <h2>{current?.title || "MALSTAR_Toolkit"}</h2>
            )}
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
              if (tool.id === "dashboard") {
                return (
                  <div
                    key={tool.id}
                    className={`page-panel${section === tool.id ? " active" : ""}`}
                    aria-hidden={section !== tool.id}
                  >
                    {dashPagesVisited.ops ? (
                      <div className={`dash-sub${dashPage === "ops" ? " active" : ""}`} hidden={dashPage !== "ops"}>
                        <Dashboard
                          ref={dashRef}
                          onNotice={setNotice}
                          onRefreshLogs={refreshLogs}
                          onImportingChange={setDashImporting}
                        />
                      </div>
                    ) : null}
                    {dashPagesVisited.lcl ? (
                      <div className={`dash-sub${dashPage === "lcl" ? " active" : ""}`} hidden={dashPage !== "lcl"}>
                        <Suspense fallback={<p className="lcl-empty">Loading LCL Volume…</p>}>
                          <LclDashboard
                            ref={lclRef}
                            embedded
                            onNotice={setNotice}
                            onRefreshLogs={refreshLogs}
                            onImportingChange={setLclImporting}
                          />
                        </Suspense>
                      </div>
                    ) : null}
                    {dashPagesVisited.gca ? (
                      <div className={`dash-sub${dashPage === "gca" ? " active" : ""}`} hidden={dashPage !== "gca"}>
                        <Suspense fallback={<p className="preview-empty">Loading GCA Hypercare…</p>}>
                          <GcaDashboard
                            ref={gcaRef}
                            embedded
                            onNotice={setNotice}
                            onRefreshLogs={refreshLogs}
                            onImportingChange={setGcaImporting}
                          />
                        </Suspense>
                      </div>
                    ) : null}
                  </div>
                );
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
