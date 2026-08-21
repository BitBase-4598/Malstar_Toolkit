import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { api, RECORDS_PAGE_SIZE } from "./api";
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

const RecordsWorkspace = forwardRef(function RecordsWorkspace({ onNotice, onRefreshLogs, onImportingChange }, ref) {
  const fileRef = useRef();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({ page: 1, total: 0, totalPages: 1 });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
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
    const pending = api
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
    pageInflight.current.set(key, pending);
    return pending;
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
    onImportingChange?.(importing);
  }, [importing, onImportingChange]);

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
      onNotice?.({ type: "error", text: error.message });
    } finally {
      if (seq === loadSeq.current) {
        setLoading(false);
      }
    }
  }, [debounced, page, fetchRecords, prefetchNeighbors, onNotice]);

  useEffect(() => {
    load();
  }, [load]);

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setModal(true);
  };

  const openUpload = () => fileRef.current?.click();

  useImperativeHandle(ref, () => ({ openNew, openUpload, importing }));

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
      onNotice?.({ type: "success", text: result.message });
      setModal(false);
      invalidateRecordPages();
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
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
      onNotice?.({ type: "success", text: result.message });
      invalidateRecordPages();
      if (rows.length === 1 && page > 1) {
        setPage((current) => current - 1);
      } else {
        await load();
      }
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
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
      const extra = result.duplicates
        ? ` Duplicate rows in CSV used last value (${result.duplicates}).`
        : "";
      onNotice?.({
        type: "success",
        text: `${result.message}. Created ${result.created}, updated ${result.updated}.${extra}`,
      });
      setPage(1);
      invalidateRecordPages();
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setImporting(false);
      event.target.value = "";
    }
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
    <>
      <input ref={fileRef} hidden type="file" accept=".csv,text/csv" onChange={upload} />
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
        onCopied={(value) => {
          onNotice?.({ type: "success", text: `Copied: ${value}`, placement: "top" });
        }}
        onCopyError={(message) => {
          onNotice?.({ type: "error", text: message });
        }}
      />
      {modal ? (
        <RecordModal
          editing={editing}
          form={form}
          saving={saving}
          onChange={setForm}
          onClose={closeModal}
          onSubmit={save}
        />
      ) : null}
    </>
  );
});

export default RecordsWorkspace;
