import { useEffect, useRef, useState } from "react";
import { copyText } from "./copyText";
import FieldSelect from "./FieldSelect";
import { ICB_PAGE_SIZE } from "./api/icb";

const COPY_FIELDS = [
  { key: "country", label: "Country" },
  { key: "location", label: "Location" },
  { key: "branch", label: "CW1 Branch" },
  { key: "unloco", label: "UNLOCO" },
  { key: "groupCode", label: "Group code" },
  { key: "groupName", label: "Group name" },
  { key: "agentCode", label: "Agent code" },
  { key: "icbCode", label: "ICB code" },
  { key: "direction", label: "Direction" },
  { key: "notes", label: "Notes" },
];

export default function IcbTable({
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
  const pageSize = pagination.pageSize || rows.length || ICB_PAGE_SIZE;
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  const pages = Array.from({ length: totalPages }, (_, index) => index + 1);

  return (
    <section className="card">
      <div className="summary">
        <span className="summary-count">
          <strong>{total}</strong> {total === 1 ? "station" : "stations"}
        </span>
      </div>
      <div className="table-wrap" ref={wrapRef}>
        <table className={`wide-table${loading && rows.length ? " is-paging" : ""}`}>
          <thead>
            <tr>
              <th>Country</th>
              <th>Location</th>
              <th>CW1 Branch</th>
              <th>UNLOCO</th>
              <th>Group code</th>
              <th>Group name</th>
              <th>Agent</th>
              <th>ICB</th>
              <th>Direction</th>
              <th>Notes</th>
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
                  {meta?.rowCount ? "No stations match this search." : "Import ICB.csv to populate this table."}
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
                        {field.key === "branch" || field.key === "icbCode" || field.key === "agentCode" ? (
                          <strong>{value || "—"}</strong>
                        ) : (
                          value || "—"
                        )}
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
        <span>{total === 0 ? "No stations" : `Showing ${from}–${to} of ${total}`}</span>
        <div className="pagination-nav">
          <button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
            Previous
          </button>
          <label className="pagination-select">
            Page
            <FieldSelect
              compact
              value={String(page)}
              disabled={totalPages <= 1}
              searchable={totalPages > 8}
              options={pages.map((number) => ({ value: String(number), label: String(number) }))}
              onChange={(next) => onPageChange(Number(next))}
              ariaLabel="Select stations page"
            />
            of {totalPages}
          </label>
          <button type="button" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
