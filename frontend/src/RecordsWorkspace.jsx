import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { api, RECORDS_PAGE_SIZE } from "./api";
import { ICB_PAGE_SIZE } from "./api/icb";
import { UNLOCO_PAGE_SIZE } from "./api/unloco";
import RecordTable from "./RecordTable";
import RecordModal from "./RecordModal";
import IcbTable from "./IcbTable";
import UnlocoTable from "./UnlocoTable";
import { lettersOnly } from "./letters";

const emptyForm = {
  ctrlOrgcode: "",
  customer: "",
  remark1: "",
  remark2: "",
  remark3: "",
};

const SEARCH_TABS = [
  { id: "remarks", label: "Controlling Customer" },
  { id: "icb", label: "Controlling Agent" },
  { id: "unlocode", label: "UNLOCODE" },
];

const RecordsWorkspace = forwardRef(function RecordsWorkspace(
  { onNotice, onRefreshLogs, onImportingChange, searchTab = "remarks", onSearchTabChange },
  ref
) {
  const remarksFileRef = useRef();
  const icbFileRef = useRef();
  const unlocoFileRef = useRef();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({ page: 1, total: 0, totalPages: 1 });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [icbImporting, setIcbImporting] = useState(false);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const pageCache = useRef(new Map());
  const pageInflight = useRef(new Map());
  const loadSeq = useRef(0);
  const [icbRows, setIcbRows] = useState([]);
  const [icbPage, setIcbPage] = useState(1);
  const [icbPagination, setIcbPagination] = useState({
    page: 1,
    total: 0,
    totalPages: 1,
    pageSize: ICB_PAGE_SIZE,
  });
  const [icbMeta, setIcbMeta] = useState({ filename: "", importedAt: "", rowCount: 0 });
  const [icbLoading, setIcbLoading] = useState(false);
  const icbLoadSeq = useRef(0);
  const [unlocoImporting, setUnlocoImporting] = useState(false);
  const [unlocoRows, setUnlocoRows] = useState([]);
  const [unlocoPage, setUnlocoPage] = useState(1);
  const [unlocoPagination, setUnlocoPagination] = useState({
    page: 1,
    total: 0,
    totalPages: 1,
    pageSize: UNLOCO_PAGE_SIZE,
  });
  const [unlocoMeta, setUnlocoMeta] = useState({ filename: "", importedAt: "", rowCount: 0 });
  const [unlocoLoading, setUnlocoLoading] = useState(false);
  const unlocoLoadSeq = useRef(0);

  const remarksQuery = lettersOnly(debounced);
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
      setIcbPage(1);
      setUnlocoPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    onImportingChange?.(importing || icbImporting || unlocoImporting);
  }, [importing, icbImporting, unlocoImporting, onImportingChange]);

  const load = useCallback(async () => {
    const seq = ++loadSeq.current;
    const key = cacheKey(remarksQuery, page);
    const cached = pageCache.current.get(key);
    if (cached) {
      if (seq !== loadSeq.current) {
        return;
      }
      setRows(cached.data || []);
      setPagination(cached.pagination);
      setLoading(false);
      prefetchNeighbors(remarksQuery, page, cached.pagination?.totalPages || 1);
      return;
    }
    setLoading(true);
    try {
      const result = await fetchRecords(remarksQuery, page);
      if (seq !== loadSeq.current) {
        return;
      }
      setRows(result.data || []);
      setPagination(result.pagination);
      prefetchNeighbors(remarksQuery, page, result.pagination?.totalPages || 1);
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
  }, [remarksQuery, page, fetchRecords, prefetchNeighbors, onNotice]);

  const loadIcb = useCallback(async () => {
    const seq = ++icbLoadSeq.current;
    setIcbLoading(true);
    try {
      const result = await api.listIcb(debounced, icbPage, ICB_PAGE_SIZE);
      if (seq !== icbLoadSeq.current) {
        return;
      }
      setIcbRows(result.data || []);
      setIcbPagination(result.pagination || { page: 1, total: 0, totalPages: 1, pageSize: ICB_PAGE_SIZE });
      setIcbMeta(result.meta || { filename: "", importedAt: "", rowCount: 0 });
    } catch (error) {
      if (seq !== icbLoadSeq.current) {
        return;
      }
      onNotice?.({ type: "error", text: error.message });
    } finally {
      if (seq === icbLoadSeq.current) {
        setIcbLoading(false);
      }
    }
  }, [debounced, icbPage, onNotice]);

  const loadUnloco = useCallback(async () => {
    const seq = ++unlocoLoadSeq.current;
    setUnlocoLoading(true);
    try {
      const result = await api.listUnloco(debounced, unlocoPage, UNLOCO_PAGE_SIZE);
      if (seq !== unlocoLoadSeq.current) {
        return;
      }
      setUnlocoRows(result.data || []);
      setUnlocoPagination(result.pagination || { page: 1, total: 0, totalPages: 1, pageSize: UNLOCO_PAGE_SIZE });
      setUnlocoMeta(result.meta || { filename: "", importedAt: "", rowCount: 0 });
    } catch (error) {
      if (seq !== unlocoLoadSeq.current) {
        return;
      }
      onNotice?.({ type: "error", text: error.message });
    } finally {
      if (seq === unlocoLoadSeq.current) {
        setUnlocoLoading(false);
      }
    }
  }, [debounced, unlocoPage, onNotice]);

  useEffect(() => {
    if (searchTab === "remarks") {
      load();
    }
  }, [load, searchTab]);

  useEffect(() => {
    if (searchTab === "icb") {
      loadIcb();
    }
  }, [loadIcb, searchTab]);

  useEffect(() => {
    if (searchTab === "unlocode") {
      loadUnloco();
    }
  }, [loadUnloco, searchTab]);

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setModal(true);
  };

  const openUpload = () => {
    if (searchTab === "icb") {
      icbFileRef.current?.click();
      return;
    }
    if (searchTab === "unlocode") {
      unlocoFileRef.current?.click();
      return;
    }
    remarksFileRef.current?.click();
  };

  useImperativeHandle(ref, () => ({
    openNew,
    openUpload,
    importing: importing || icbImporting || unlocoImporting,
  }));

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

  const uploadRemarks = async (event) => {
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

  const uploadIcb = async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setIcbImporting(true);
    try {
      const result = await api.importIcb(file);
      onNotice?.({ type: "success", text: result.message });
      setIcbPage(1);
      const listed = await api.listIcb(debounced, 1, ICB_PAGE_SIZE);
      setIcbRows(listed.data || []);
      setIcbPagination(listed.pagination || { page: 1, total: 0, totalPages: 1, pageSize: ICB_PAGE_SIZE });
      setIcbMeta(listed.meta || { filename: "", importedAt: "", rowCount: 0 });
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setIcbImporting(false);
      event.target.value = "";
    }
  };

  const uploadUnloco = async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setUnlocoImporting(true);
    try {
      const result = await api.importUnloco(file);
      onNotice?.({ type: "success", text: result.message });
      setUnlocoPage(1);
      const listed = await api.listUnloco(debounced, 1, UNLOCO_PAGE_SIZE);
      setUnlocoRows(listed.data || []);
      setUnlocoPagination(listed.pagination || { page: 1, total: 0, totalPages: 1, pageSize: UNLOCO_PAGE_SIZE });
      setUnlocoMeta(listed.meta || { filename: "", importedAt: "", rowCount: 0 });
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setUnlocoImporting(false);
      event.target.value = "";
    }
  };

  const changePage = (next) => {
    const target = typeof next === "function" ? next(page) : Number(next);
    if (!Number.isFinite(target) || target < 1 || target === page) {
      return;
    }
    const cached = pageCache.current.get(cacheKey(remarksQuery, target));
    if (cached) {
      setRows(cached.data || []);
      setPagination(cached.pagination);
      setLoading(false);
    }
    setPage(target);
  };

  const copied = (value) => {
    onNotice?.({ type: "success", text: `Copied: ${value}`, placement: "top" });
  };

  return (
    <>
      <input ref={remarksFileRef} hidden type="file" accept=".csv,text/csv" onChange={uploadRemarks} />
      <input ref={icbFileRef} hidden type="file" accept=".csv,text/csv" onChange={uploadIcb} />
      <input ref={unlocoFileRef} hidden type="file" accept=".csv,text/csv" onChange={uploadUnloco} />
      <div className="page-intro">
        <p>Search controlling customer, controlling agent, or UNLOCODE.</p>
      </div>
      <div className="search">
        <Search size={19} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={
            searchTab === "unlocode"
              ? "Country name, country, UNLOCODE, or port"
              : "Company, port, UNLOCODE, or ICB code"
          }
          aria-describedby="search-hint"
        />
        {query ? (
          <button type="button" onClick={() => setQuery("")} aria-label="Clear search">
            <X size={17} />
          </button>
        ) : null}
      </div>
      <div className="filter-chips search-chips" role="tablist" aria-label="Search results">
        {SEARCH_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={searchTab === tab.id}
            className={searchTab === tab.id ? "active" : ""}
            onClick={() => onSearchTabChange?.(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <p id="search-hint" className="search-hint">
        {searchTab === "unlocode"
          ? unlocoMeta.rowCount
            ? `${unlocoMeta.filename || "UNLOCODE.csv"} · ${unlocoMeta.rowCount.toLocaleString()} locations${unlocoMeta.importedAt ? ` · ${unlocoMeta.importedAt}` : ""}. Search country name, country, UNLOCODE, or port.`
            : "Import UNLOCODE.csv to load locations. Search country name, country, UNLOCODE, or port."
          : searchTab === "icb"
            ? icbMeta.rowCount
              ? `${icbMeta.filename || "ICB.csv"} · ${icbMeta.rowCount} stations${icbMeta.importedAt ? ` · ${icbMeta.importedAt}` : ""}. Search country, branch, UNLOCO, agent, or ICB.`
              : "Import ICB.csv to load stations. Search country, branch, UNLOCO, agent, or ICB."
            : "Remarks match letters in the company name. Punctuation and numbers are ignored."}
      </p>
      {searchTab === "unlocode" ? (
        <UnlocoTable
          rows={unlocoRows}
          loading={unlocoLoading}
          pagination={unlocoPagination}
          page={unlocoPage}
          meta={unlocoMeta}
          onPageChange={setUnlocoPage}
          onCopied={copied}
          onCopyError={(message) => onNotice?.({ type: "error", text: message })}
        />
      ) : searchTab === "icb" ? (
        <IcbTable
          rows={icbRows}
          loading={icbLoading}
          pagination={icbPagination}
          page={icbPage}
          meta={icbMeta}
          onPageChange={setIcbPage}
          onCopied={copied}
          onCopyError={(message) => onNotice?.({ type: "error", text: message })}
        />
      ) : (
        <RecordTable
          rows={rows}
          loading={loading}
          pagination={pagination}
          page={page}
          onPageChange={changePage}
          onEdit={openEdit}
          onDelete={remove}
          onCopied={copied}
          onCopyError={(message) => onNotice?.({ type: "error", text: message })}
        />
      )}
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
