import { Pencil, Search, X } from "lucide-react";
import FieldSelect from "./FieldSelect";
import { CASE_PAGE_SIZE } from "./api/cases";
import PageJump from "./PageJump";
import { STATUSES, displayDate, emailLabel } from "./caseConstants";

export default function CaseList({
  query,
  onQueryChange,
  total,
  loading,
  rows,
  page,
  totalPages,
  statusBusy,
  saving,
  onOpenCase,
  onChangeStatus,
  onLoadPage,
}) {
  return (
    <>
      <div className="page-intro">
        <p>
          Collect a bad case with a booking order ID or a shipment number. Paste a screenshot or
          attach a file, then preview it in the case.
        </p>
      </div>
      <div className="search">
        <Search size={19} />
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search booking order ID, shipment number, email, or description"
          aria-describedby="badcases-search-hint"
        />
        {query ? (
          <button type="button" onClick={() => onQueryChange("")} aria-label="Clear search">
            <X size={17} />
          </button>
        ) : null}
      </div>
      <p id="badcases-search-hint" className="search-hint">
        {total} {total === 1 ? "case" : "cases"}
      </p>
      <section className="card">
        <div className="table-wrap">
          <table className="wide-table badcases-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Booking order ID</th>
                <th>Shipment number</th>
                <th>Email</th>
                <th>Description</th>
                <th>Files</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading && rows.length === 0 ? (
                <tr>
                  <td colSpan="8" className="empty">
                    Loading…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan="8" className="empty">
                    No cases yet. Create one with New case.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id} className="clickable" onClick={() => onOpenCase(row, "view")}>
                    <td>{displayDate(row)}</td>
                    <td title={row.bookingOrderId || undefined}>{row.bookingOrderId || "—"}</td>
                    <td title={row.shipmentNumber || undefined}>{row.shipmentNumber || "—"}</td>
                    <td className="case-email" title={emailLabel(row.email)}>
                      {emailLabel(row.email)}
                    </td>
                    <td className="case-note" title={row.description || undefined}>
                      {row.description || "—"}
                    </td>
                    <td>{row.fileCount || "—"}</td>
                    <td className="case-status" onClick={(event) => event.stopPropagation()}>
                      <FieldSelect
                        compact
                        ariaLabel={`Status for case ${row.id}`}
                        value={row.status}
                        options={STATUSES.map((item) => ({ value: item.id, label: item.label }))}
                        onChange={(status) => onChangeStatus(row, status)}
                        disabled={statusBusy === row.id || saving}
                      />
                    </td>
                    <td className="actions" onClick={(event) => event.stopPropagation()}>
                      <button
                        type="button"
                        className="case-edit"
                        onClick={() => onOpenCase(row, "edit")}
                        aria-label={`Edit case ${row.id}`}
                      >
                        <Pencil size={16} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="pagination">
          <span>
            {total === 0
              ? "No cases"
              : `Showing ${(page - 1) * CASE_PAGE_SIZE + 1}–${Math.min(page * CASE_PAGE_SIZE, total)} of ${total}`}
          </span>
          <div className="pagination-nav">
            <button type="button" disabled={page <= 1 || loading} onClick={() => onLoadPage(page - 1)}>
              Previous
            </button>
            <PageJump
              page={page}
              totalPages={totalPages}
              onChange={(next) => onLoadPage(Number(next))}
              ariaLabel="Select BadCases page"
            />
            <button
              type="button"
              disabled={page >= totalPages || loading}
              onClick={() => onLoadPage(page + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </>
  );
}
