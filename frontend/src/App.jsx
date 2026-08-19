import { useCallback, useEffect, useRef, useState } from "react";
import { Search, X, Plus, Upload } from "lucide-react";
import { api } from "./api";
import Sidebar from "./Sidebar";
import RecordTable from "./RecordTable";
import RecordModal from "./RecordModal";
import ActivityLog from "./ActivityLog";
import { lettersOnly } from "./letters";

const emptyForm = {
  ctrlOrgcode: "",
  customer: "",
  remark1: "",
  remark2: "",
  remark3: "",
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
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [section, setSection] = useState("records");
  const fileRef = useRef();

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
      setDebounced(query);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!notice.text) {
      return undefined;
    }
    const timer = setTimeout(() => setNotice({ type: "", text: "" }), 5000);
    return () => clearTimeout(timer);
  }, [notice]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.list(debounced, page);
      setRows(result.data);
      setPagination(result.pagination);
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }, [debounced, page]);

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
      await load();
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
    api.recordLog("Opened section", next);
  };

  const updateQuery = (value) => setQuery(lettersOnly(value));

  return (
    <div className="app-shell">
      <Sidebar
        section={section}
        onSectionChange={changeSection}
      />
      <div className="workspace">
        <header className="topbar">
          <h2>{section === "logs" ? "Activity log" : "Records"}</h2>
          <div className="topbar-actions">
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
          </div>
        </header>
        <main className="page">
          {notice.text && (
            <div className={`alert ${notice.type}`}>
              {notice.text}
              <button type="button" onClick={() => setNotice({ type: "", text: "" })} aria-label="Dismiss">
                <X size={16} />
              </button>
            </div>
          )}
          {section === "records" ? (
            <>
              <div className="page-intro">
                <p>Search and maintain organization-level customer remarks.</p>
              </div>
              <div className="search">
                <Search size={19} />
                <input
                  autoFocus
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
                onPageChange={setPage}
                onEdit={openEdit}
                onDelete={remove}
                onCopied={(label) => {
                  setNotice({ type: "success", text: `Copied ${label}` });
                  api.recordLog("Copied cell", label);
                }}
                onCopyError={(message) => {
                  setNotice({ type: "error", text: message });
                  api.recordLog("Copy failed", message);
                }}
              />
            </>
          ) : (
            <ActivityLog entries={logs} loading={logsLoading} />
          )}
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
    </div>
  );
}
