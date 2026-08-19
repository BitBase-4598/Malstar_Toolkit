import { useCallback, useEffect, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { api } from "./api";
import Header from "./Header";
import RecordTable from "./RecordTable";
import RecordModal from "./RecordModal";
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
  const fileRef = useRef();

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
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setSaving(false);
    }
  };

  const remove = async (row) => {
    if (!window.confirm(`Delete ${row.ctrlOrgcode} / ${row.customer}?`)) {
      return;
    }
    try {
      const result = await api.remove(row.id);
      setNotice({ type: "success", text: result.message });
      await load();
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    }
  };

  const upload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setImporting(true);
    try {
      const result = await api.importCsv(file);
      setNotice({
        type: "success",
        text: `${result.message}. Created ${result.created}, updated ${result.updated}.`,
      });
      setPage(1);
      await load();
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setImporting(false);
      event.target.value = "";
    }
  };

  const updateQuery = (value) => setQuery(lettersOnly(value));

  return (
    <div className="app-shell">
      <Header
        fileRef={fileRef}
        importing={importing}
        onImportClick={() => fileRef.current.click()}
        onImportChange={upload}
        onAdd={openNew}
      />
      <main className="page">
        <div className="page-intro">
          <h2>Customer remarks</h2>
          <p>Search and maintain organization-level customer remarks.</p>
        </div>
        {notice.text && (
          <div className={`alert ${notice.type}`}>
            {notice.text}
            <button type="button" onClick={() => setNotice({ type: "", text: "" })} aria-label="Dismiss">
              <X size={16} />
            </button>
          </div>
        )}
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
          onCopied={(label) => setNotice({ type: "success", text: `Copied ${label}` })}
          onCopyError={(message) => setNotice({ type: "error", text: message })}
        />
      </main>
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
