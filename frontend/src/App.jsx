import { useCallback, useEffect, useRef, useState } from "react";
import { Search, X, Plus, Upload } from "lucide-react";
import { api, RECORDS_PAGE_SIZE } from "./api";
import Sidebar from "./Sidebar";
import RecordTable from "./RecordTable";
import RecordModal from "./RecordModal";
import ActivityLog from "./ActivityLog";
import FileManager from "./FileManager";
import SopWorkspace from "./SopWorkspace";
import { lettersOnly } from "./letters";

const emptyForm = {
  ctrlOrgcode: "",
  customer: "",
  remark1: "",
  remark2: "",
  remark3: "",
};

const TITLES = {
  records: "AutoRatingSearchBar",
  files: "Files",
  sops: "SOPs",
  logs: "Activity log",
};

const LAYERS = {
  records: "Search tool",
  files: "Library tool",
  sops: "Process tool",
  logs: "Audit tool",
};

export default function App() {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({ page: 1, total: 0, totalPages: 1 });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [notice, setNotice] = useState({ type: "", text: "" });
  const [toastLeaving, setToastLeaving] = useState(false);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [section, setSection] = useState("records");
  const [visited, setVisited] = useState({ records: true });
  const fileRef = useRef();
  const filesRef = useRef();
  const sopsRef = useRef();
  const pageCache = useRef(new Map());
  const pageInflight = useRef(new Map());
  const loadSeq = useRef(0);

  const cacheKey = (q, targetPage) => `${q}|${targetPage}`;

  const invalidateRecordPages = () => {
    pageCache.current.clear();
    pageInflight.current.clear();
  };

  const fetchRecords = useCallback(async (q, targetPage) => {
    const key = cacheKey(q, targetPage);
    if (pageCache.current.has(key)) {
      return pageCache.current.get(key);
    }
    if (pageInflight.current.has(key)) {
      return pageInflight.current.get(key);
    }
    const request = api
      .list(q, targetPage, RECORDS_PAGE_SIZE)
      .then((result) => {
        pageCache.current.set(key, result);
        pageInflight.current.delete(key);
        return result;
      })
      .catch((error) => {
        pageInflight.current.delete(key);
        throw error;
      });
    pageInflight.current.set(key, request);
    return request;
  }, []);

  const prefetchNeighbors = useCallback(
    (q, currentPage, totalPages) => {
      if (currentPage + 1 <= totalPages) {
        fetchRecords(q, currentPage + 1);
      }
      if (currentPage - 1 >= 1) {
        fetchRecords(q, currentPage - 1);
      }
    },
    [fetchRecords]
  );

  const refreshLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      const result = await api.listLogs();
      setLogs(result.data || []);
    } catch {
      /* keep previous log rows */
    } finally {
      setLogsLoading(false);
    }
  }, []);

  useEffect(() => {
    api.recordLog("Opened MALSTAR_Toolkit", "page loaded");
    refreshLogs();
    const timer = setInterval(refreshLogs, 4000);
    return () => clearInterval(timer);
  }, [refreshLogs]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced((current) => {
        if (current !== query) {
          invalidateRecordPages();
        }
        return query;
      });
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

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

  const load = useCallback(async () => {
    const seq = ++loadSeq.current;
    const key = cacheKey(debounced, page);
    const cached = pageCache.current.get(key);
    if (cached) {
      if (seq !== loadSeq.current) {
        return;
      }
      setRows(cached.data || []);
      setPagination(cached.pagination);
      setLoading(false);
      prefetchNeighbors(debounced, page, cached.pagination?.totalPages || 1);
      return;
    }
    setLoading(true);
    try {
      const result = await fetchRecords(debounced, page);
      if (seq !== loadSeq.current) {
        return;
      }
      setRows(result.data || []);
      setPagination(result.pagination);
      prefetchNeighbors(debounced, page, result.pagination?.totalPages || 1);
    } catch (error) {
      if (seq !== loadSeq.current) {
        return;
      }
      setNotice({ type: "error", text: error.message });
    } finally {
      if (seq === loadSeq.current) {
        setLoading(false);
      }
    }
  }, [debounced, page, fetchRecords, prefetchNeighbors]);

  useEffect(() => {
    load();
  }, [load]);

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setModal(true);
    api.recordLog("Opened add form");
  };

  const openEdit = (row) => {
    setEditing(row);
    setForm({
      ctrlOrgcode: row.ctrlOrgcode,
      customer: row.customer,
      remark1: row.remark1,
      remark2: row.remark2,
      remark3: row.remark3,
    });
    setModal(true);
    api.recordLog("Opened edit form", `${row.ctrlOrgcode} / ${row.customer}`);
  };

  const closeModal = useCallback(() => {
    if (!saving) {
      setModal(false);
    }
  }, [saving]);

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const result = editing ? await api.update(editing.id, form) : await api.create(form);
      setNotice({ type: "success", text: result.message });
      setModal(false);
      invalidateRecordPages();
      await load();
      await refreshLogs();
    } catch (error) {
      api.recordLog("Save failed", error.message);
      setNotice({ type: "error", text: error.message });
    } finally {
      setSaving(false);
    }
  };

  const remove = async (row) => {
    if (!window.confirm(`Delete ${row.ctrlOrgcode} / ${row.customer}?`)) {
      api.recordLog("Delete cancelled", `${row.ctrlOrgcode} / ${row.customer}`);
      return;
    }
    try {
      const result = await api.remove(row.id);
      setNotice({ type: "success", text: result.message });
      invalidateRecordPages();
      if (rows.length === 1 && page > 1) {
        setPage((current) => current - 1);
      } else {
        await load();
      }
      await refreshLogs();
    } catch (error) {
      api.recordLog("Delete failed", error.message);
      setNotice({ type: "error", text: error.message });
    }
  };

  const upload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setImporting(true);
    api.recordLog("CSV import started", file.name);
    try {
      const result = await api.importCsv(file);
      const extra = result.duplicates
        ? ` Duplicate rows in CSV used last value (${result.duplicates}).`
        : "";
      setNotice({
        type: "success",
        text: `${result.message}. Created ${result.created}, updated ${result.updated}.${extra}`,
      });
      setPage(1);
      invalidateRecordPages();
      await load();
      await refreshLogs();
    } catch (error) {
      api.recordLog("CSV import failed", error.message);
      setNotice({ type: "error", text: error.message });
    } finally {
      setImporting(false);
      event.target.value = "";
    }
  };

  const changeSection = (next) => {
    setSection(next);
    setVisited((current) => (current[next] ? current : { ...current, [next]: true }));
    api.recordLog("Opened section", next);
  };

  const updateQuery = (value) => setQuery(lettersOnly(value));

  const changePage = (next) => {
    const target = typeof next === "function" ? next(page) : Number(next);
    if (!Number.isFinite(target) || target < 1 || target === page) {
      return;
    }
    const cached = pageCache.current.get(cacheKey(debounced, target));
    if (cached) {
      setRows(cached.data || []);
      setPagination(cached.pagination);
      setLoading(false);
    }
    setPage(target);
  };

  return (
    <div className="app-shell">
      <Sidebar
        section={section}
        onSectionChange={changeSection}
      />
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-copy">
            <p className="topbar-kicker">{LAYERS[section] || "MALSTAR_Toolkit"}</p>
            <h2>{TITLES[section] || "MALSTAR_Toolkit"}</h2>
          </div>
          <div className="topbar-actions">
            {section === "records" ? (
              <>
                <input
                  ref={fileRef}
                  hidden
                  type="file"
                  accept=".csv,text/csv"
                  onChange={upload}
                />
                <button className="ghost" type="button" onClick={() => fileRef.current.click()} disabled={importing}>
                  <Upload size={16} />
                  {importing ? "Importing..." : "Import CSV"}
                </button>
                <button className="primary" type="button" onClick={openNew}>
                  <Plus size={16} />
                  Add record
                </button>
              </>
            ) : null}
            {section === "files" ? (
              <button className="primary" type="button" onClick={() => filesRef.current?.openUpload()}>
                <Upload size={16} />
                Upload file
              </button>
            ) : null}
            {section === "sops" ? (
              <button className="primary" type="button" onClick={() => sopsRef.current?.openNew()}>
                <Plus size={16} />
                New SOP
              </button>
            ) : null}
          </div>
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
            {visited.records ? (
              <div className={`page-panel${section === "records" ? " active" : ""}`} aria-hidden={section !== "records"}>
                <div className="page-intro">
                  <p>Search and maintain organization-level customer remarks.</p>
                </div>
                <div className="search">
                  <Search size={19} />
                  <input
                    value={query}
                    onChange={(event) => updateQuery(event.target.value)}
                    onPaste={(event) => {
                      event.preventDefault();
                      updateQuery(event.clipboardData.getData("text"));
                    }}
                    placeholder="Paste or type a company name"
                    aria-describedby="search-hint"
                  />
                  {query && (
                    <button type="button" onClick={() => setQuery("")} aria-label="Clear search">
                      <X size={17} />
                    </button>
                  )}
                </div>
                <p id="search-hint" className="search-hint">
                  Matching uses letters in the company name only. Punctuation, numbers, and extra text are cleared automatically.
                </p>
                <RecordTable
                  rows={rows}
                  loading={loading}
                  pagination={pagination}
                  page={page}
                  onPageChange={changePage}
                  onEdit={openEdit}
                  onDelete={remove}
                  onCopied={(value, label) => {
                    setNotice({ type: "success", text: `Copied: ${value}`, placement: "top" });
                    api.recordLog("Copied cell", `${label}: ${value}`);
                  }}
                  onCopyError={(message) => {
                    setNotice({ type: "error", text: message });
                    api.recordLog("Copy failed", message);
                  }}
                />
              </div>
            ) : null}
            {visited.files ? (
              <div className={`page-panel${section === "files" ? " active" : ""}`} aria-hidden={section !== "files"}>
                <FileManager ref={filesRef} onNotice={setNotice} onRefreshLogs={refreshLogs} />
              </div>
            ) : null}
            {visited.sops ? (
              <div className={`page-panel${section === "sops" ? " active" : ""}`} aria-hidden={section !== "sops"}>
                <SopWorkspace ref={sopsRef} onNotice={setNotice} onRefreshLogs={refreshLogs} />
              </div>
            ) : null}
            {visited.logs ? (
              <div className={`page-panel${section === "logs" ? " active" : ""}`} aria-hidden={section !== "logs"}>
                <ActivityLog entries={logs} loading={logsLoading} />
              </div>
            ) : null}
          </div>
        </main>
      </div>
      {modal && (
        <RecordModal
          editing={editing}
          form={form}
          saving={saving}
          onChange={setForm}
          onClose={closeModal}
          onSubmit={save}
        />
      )}
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
