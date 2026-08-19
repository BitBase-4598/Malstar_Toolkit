import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { copyText } from "./copyText";

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
      onCopied?.(field.label);
    } catch {
      onCopyError?.("Could not copy to the clipboard.");
    }
  };

  return (
    <section className="card">
      <div className="summary">
        <strong>{pagination.total}</strong> record(s)
      </div>
      <div className="table-wrap">
        <table>
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
            {loading ? (
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
        <button type="button" disabled={page <= 1} onClick={() => onPageChange((value) => value - 1)}>
          Previous
        </button>
        <span>
          Page {pagination.page} / {pagination.totalPages}
        </span>
        <button
          type="button"
          disabled={page >= pagination.totalPages}
          onClick={() => onPageChange((value) => value + 1)}
        >
          Next
        </button>
      </div>
    </section>
  );
}
