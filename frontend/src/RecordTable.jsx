import { useEffect, useRef, useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { copyText } from "./copyText";
import PageJump from "./PageJump";

const COPY_FIELDS = [
  { key: "ctrlOrgcode", label: "CTRLOrgcode" },
  { key: "customer", label: "Customer" },
  { key: "remark1", label: "Remark1" },
  { key: "remark2", label: "Remark2" },
  { key: "remark3", label: "Remark3" },
];

export default function RecordTable({
  rows,
  loading,
  pagination,
  page,
  onPageChange,
  onEdit,
  onDelete,
  onCopied,
  onCopyError,
}) {
  const [copiedKey, setCopiedKey] = useState("");
  const wrapRef = useRef(null);

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
  const pageSize = pagination.pageSize || rows.length || 12;
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <section className="card">
      <div className="summary">
        <span className="summary-count">
          <strong>{pagination.total}</strong> {pagination.total === 1 ? "record" : "records"}
        </span>
      </div>
      <div className="table-wrap" ref={wrapRef}>
        <table className={`wide-table${loading && rows.length ? " is-paging" : ""}`}>
          <colgroup>
            <col className="col-code" />
            <col className="col-customer" />
            <col className="col-remark" />
            <col className="col-remark" />
            <col className="col-remark" />
            <col className="col-actions" />
          </colgroup>
          <thead>
            <tr>
              <th>CTRLOrgcode</th>
              <th>Customer</th>
              <th>Remark1</th>
              <th>Remark2</th>
              <th>Remark3</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 ? (
              <tr>
                <td colSpan="6" className="empty">
                  Loading...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan="6" className="empty">
                  No records found.
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
                        className={[
                          copyable ? "copyable" : "",
                          copiedKey === `${row.id}-${field.key}` ? "copied" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        title={copyable ? "Click to copy" : undefined}
                        aria-label={copyable ? `Click to copy ${field.label}` : undefined}
                        onClick={() => copyCell(row, field)}
                      >
                        {field.key === "ctrlOrgcode" ? <strong>{value}</strong> : value || "-"}
                      </td>
                    );
                  })}
                  <td>
                    <div className="actions">
                      <button type="button" onClick={() => onEdit(row)} aria-label="Edit record">
                        <Pencil size={16} />
                      </button>
                      <button
                        type="button"
                        className="danger"
                        onClick={() => onDelete(row)}
                        aria-label="Delete record"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <span>{total === 0 ? "No records" : `Showing ${from}–${to} of ${total}`}</span>
        <div className="pagination-nav">
          <button type="button" disabled={page <= 1} onClick={() => onPageChange((value) => value - 1)}>
            Previous
          </button>
          <PageJump
            page={Math.min(page, totalPages)}
            totalPages={totalPages}
            onChange={(next) => onPageChange(Number(next))}
            ariaLabel="Select page"
          />
          <button type="button" disabled={page >= totalPages} onClick={() => onPageChange((value) => value + 1)}>
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
