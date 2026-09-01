import { useEffect, useRef, useState } from "react";
import { copyText } from "./copyText";
import PageJump from "./PageJump";
import { UNLOCO_PAGE_SIZE } from "./api/unloco";

const COPY_FIELDS = [
  { key: "countryName", label: "Country Name" },
  { key: "countryCode", label: "Country" },
  { key: "unCode", label: "UNLOCODE" },
  { key: "portName", label: "Port" },
  { key: "category", label: "LCL Category" },
];

export default function UnlocoTable({
  rows,
  loading,
  pagination,
  page,
  meta,
  onPageChange,
  onCopied,
  onCopyError,
}) {
  const wrapRef = useRef(null);
  const [copiedKey, setCopiedKey] = useState("");

  useEffect(() => {
    if (wrapRef.current) {
      wrapRef.current.scrollTop = 0;
    }
  }, [page, rows]);

  const copyCell = async (row, field) => {
    const value = String(row[field.key] || "").trim();
    if (!value) {
      return;
    }
    try {
      await copyText(value);
      const key = `${row.id}-${field.key}`;
      setCopiedKey(key);
      window.setTimeout(() => {
        setCopiedKey((current) => (current === key ? "" : current));
      }, 700);
      onCopied?.(value, field.label);
    } catch {
      onCopyError?.("Could not copy to the clipboard.");
    }
  };

  const total = pagination.total || 0;
  const totalPages = pagination.totalPages || 1;
  const pageSize = pagination.pageSize || rows.length || UNLOCO_PAGE_SIZE;
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <section className="card">
      <div className="summary">
        <span className="summary-count">
          <strong>{total}</strong> {total === 1 ? "location" : "locations"}
        </span>
      </div>
      <div className="table-wrap" ref={wrapRef}>
        <table className={`wide-table${loading && rows.length ? " is-paging" : ""}`}>
          <thead>
            <tr>
              {COPY_FIELDS.map((field) => (
                <th key={field.key}>{field.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 ? (
              <tr>
                <td colSpan={COPY_FIELDS.length} className="empty">
                  Loading...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={COPY_FIELDS.length} className="empty">
                  {meta?.rowCount
                    ? "No UNLOCODEs match this search."
                    : "Import UNLOCODE.csv to populate this table."}
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id}>
                  {COPY_FIELDS.map((field) => {
                    const value = String(row[field.key] || "").trim();
                    const copyable = Boolean(value);
                    return (
                      <td
                        key={field.key}
                        className={[copyable ? "copyable" : "", copiedKey === `${row.id}-${field.key}` ? "copied" : ""]
                          .filter(Boolean)
                          .join(" ")}
                        title={copyable ? "Click to copy" : undefined}
                        aria-label={copyable ? `Click to copy ${field.label}` : undefined}
                        onClick={() => copyCell(row, field)}
                      >
                        {field.key === "unCode" ? <strong>{value || "—"}</strong> : value || "—"}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <span>{total === 0 ? "No locations" : `Showing ${from}–${to} of ${total}`}</span>
        <div className="pagination-nav">
          <button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
            Previous
          </button>
          <PageJump
            page={page}
            totalPages={totalPages}
            onChange={(next) => onPageChange(Number(next))}
            ariaLabel="Select UNLOCODE page"
          />
          <button type="button" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
