import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { api } from "./api";
import FieldSelect from "./FieldSelect";
import { GCA_PAGE_SIZE } from "./api/gca";

const DONUT_COLORS = ["#42b0d5", "#00243d", "#0077b2", "#4c4c4c", "#77c6e0"];
const LANES = [
  { id: "", label: "All" },
  { id: "non-europe", label: "Non-Europe" },
  { id: "europe", label: "Europe" },
];

function formatNumber(value, digits = 0) {
  if (value == null || value === "") {
    return "—";
  }
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function statusTone(status) {
  const text = String(status || "").toLowerCase();
  if (text.includes("converted")) {
    return "converted";
  }
  if (text.includes("cancel")) {
    return "danger";
  }
  if (text.includes("pending") || text.includes("processing")) {
    return "processing";
  }
  return "";
}

function StatusLabel({ value }) {
  const label = String(value || "—");
  const tone = statusTone(value);
  return <span className={`status-pill dash-status${tone ? ` ${tone}` : ""}`}>{label}</span>;
}

function BarList({ items }) {
  const max = Math.max(...items.map((item) => Number(item.count) || 0), 1);
  return (
    <ul className="dash-bars">
      {items.map((item) => {
        const value = Number(item.count) || 0;
        const width = Math.max((value / max) * 100, value ? 4 : 0);
        return (
          <li key={item.label}>
            <span className="dash-bar-label" title={item.label}>
              {item.label}
            </span>
            <span className="dash-bar-track">
              <span className="dash-bar-fill" style={{ width: `${width}%` }} />
            </span>
            <span className="dash-bar-value">{value.toLocaleString()}</span>
          </li>
        );
      })}
    </ul>
  );
}

function DonutChart({ items }) {
  const total = items.reduce((sum, item) => sum + (Number(item.count) || 0), 0);
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <div className="dash-donut">
      <svg viewBox="0 0 140 140" aria-label="Conversion mix">
        <g transform="rotate(-90 70 70)">
          {items.map((item, index) => {
            const value = Number(item.count) || 0;
            const dash = total ? (value / total) * circumference : 0;
            const circle = (
              <circle
                key={item.label}
                cx="70"
                cy="70"
                r={radius}
                fill="none"
                stroke={DONUT_COLORS[index % DONUT_COLORS.length]}
                strokeWidth="22"
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offset}
              />
            );
            offset += dash;
            return circle;
          })}
        </g>
        <circle cx="70" cy="70" r="36" fill="#ffffff" />
        <text x="70" y="66" textAnchor="middle" className="dash-donut-total">
          {total}
        </text>
        <text x="70" y="84" textAnchor="middle" className="dash-donut-caption">
          bookings
        </text>
      </svg>
      <ul className="dash-donut-legend">
        {items.map((item, index) => (
          <li key={item.label}>
            <span className="dash-swatch" style={{ background: DONUT_COLORS[index % DONUT_COLORS.length] }} />
            <span className="dash-legend-label" title={item.label}>
              {item.label}
            </span>
            <span className="dash-bar-value">{item.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DayChart({ items }) {
  const max = Math.max(...items.map((item) => item.count || 0), 1);
  return (
    <div className="dash-hours gca-days" aria-label="Daily booking volume">
      {items.map((item) => {
        const height = Math.max(((item.count || 0) / max) * 100, item.count ? 6 : 0);
        const label = String(item.label || "").slice(5);
        return (
          <div key={item.label} className="dash-hour" title={`${item.label} · ${item.count} received`}>
            {item.count ? <span className="dash-hour-count">{item.count}</span> : <span className="dash-hour-count is-empty" />}
            <span className="dash-hour-bar" style={{ height: `${height}%` }} />
            <span className="dash-hour-label">{label}</span>
          </div>
        );
      })}
    </div>
  );
}

function pageWindow(totalPages, current, radius = 20) {
  const last = Math.max(1, totalPages || 1);
  const safe = Math.min(Math.max(current || 1, 1), last);
  if (last <= 40) {
    return Array.from({ length: last }, (_, index) => index + 1);
  }
  const start = Math.max(1, safe - radius);
  const end = Math.min(last, safe + radius);
  return Array.from({ length: end - start + 1 }, (_, index) => start + index);
}

function TablePager({ total, page, pageSize, onPageChange, emptyLabel }) {
  const totalPages = Math.max(1, Math.ceil((total || 0) / (pageSize || 50)) || 1);
  const safePage = Math.min(page, totalPages);
  const from = total === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const to = Math.min(safePage * pageSize, total);
  const pages = pageWindow(totalPages, safePage);
  return (
    <div className="pagination">
      <span>{total === 0 ? emptyLabel : `Showing ${from}–${to} of ${total}`}</span>
      <div className="pagination-nav">
        <button type="button" disabled={safePage <= 1} onClick={() => onPageChange(safePage - 1)}>
          Previous
        </button>
        <label className="pagination-select">
          Page
          <FieldSelect
            compact
            value={String(safePage)}
            disabled={totalPages <= 1}
            searchable={totalPages > 8}
            options={pages.map((number) => ({ value: String(number), label: String(number) }))}
            onChange={(next) => onPageChange(Number(next))}
            ariaLabel="Select page"
          />
          of {totalPages}
        </label>
        <button type="button" disabled={safePage >= totalPages} onClick={() => onPageChange(safePage + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}

const GcaDashboard = forwardRef(function GcaDashboard(
  { embedded = false, onNotice, onRefreshLogs, onImportingChange },
  ref
) {
  const inputRef = useRef();
  const [data, setData] = useState(null);
  const [bookings, setBookings] = useState([]);
  const [feedback, setFeedback] = useState([]);
  const [bookingPage, setBookingPage] = useState(1);
  const [feedbackPage, setFeedbackPage] = useState(1);
  const [bookingMeta, setBookingMeta] = useState({ page: 1, total: 0, totalPages: 1, pageSize: GCA_PAGE_SIZE });
  const [feedbackMeta, setFeedbackMeta] = useState({ page: 1, total: 0, totalPages: 1, pageSize: GCA_PAGE_SIZE });
  const [loading, setLoading] = useState(true);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [lane, setLane] = useState("");
  const [reloadSeq, setReloadSeq] = useState(0);

  const openImport = () => inputRef.current?.click();

  useImperativeHandle(ref, () => ({ openImport, importing }));

  useEffect(() => {
    onImportingChange?.(importing);
  }, [importing, onImportingChange]);

  const loadSummary = useCallback(async (signal) => {
    setLoading(true);
    try {
      const summaryResult = await api.getGcaSummary({ dateFrom, dateTo, lane }, { signal });
      const payload = summaryResult.data || null;
      setData(payload);
      if (!dateFrom && payload?.meta?.dateFrom) {
        setDateFrom(payload.meta.dateFrom);
      }
      if (!dateTo && payload?.meta?.dateTo) {
        setDateTo(payload.meta.dateTo);
      }
    } catch (error) {
      if (error.name === "AbortError") {
        return;
      }
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, lane, reloadSeq, onNotice]);

  const loadBookings = useCallback(async (signal) => {
    setTablesLoading(true);
    try {
      const bookingResult = await api.listGcaBookings(
        { dateFrom, dateTo, lane, pageSize: GCA_PAGE_SIZE, page: bookingPage },
        { signal }
      );
      setBookings(bookingResult.data || []);
      setBookingMeta(bookingResult.pagination || { page: 1, total: 0, totalPages: 1, pageSize: GCA_PAGE_SIZE });
    } catch (error) {
      if (error.name === "AbortError") {
        return;
      }
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setTablesLoading(false);
    }
  }, [dateFrom, dateTo, lane, bookingPage, reloadSeq, onNotice]);

  const loadFeedback = useCallback(async (signal) => {
    setTablesLoading(true);
    try {
      const feedbackResult = await api.listGcaFeedback(
        { dateFrom, dateTo, lane, pageSize: GCA_PAGE_SIZE, page: feedbackPage },
        { signal }
      );
      setFeedback(feedbackResult.data || []);
      setFeedbackMeta(feedbackResult.pagination || { page: 1, total: 0, totalPages: 1, pageSize: GCA_PAGE_SIZE });
    } catch (error) {
      if (error.name === "AbortError") {
        return;
      }
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setTablesLoading(false);
    }
  }, [dateFrom, dateTo, lane, feedbackPage, reloadSeq, onNotice]);

  useEffect(() => {
    const controller = new AbortController();
    loadSummary(controller.signal);
    return () => controller.abort();
  }, [loadSummary]);

  useEffect(() => {
    const controller = new AbortController();
    loadBookings(controller.signal);
    return () => controller.abort();
  }, [loadBookings]);

  useEffect(() => {
    const controller = new AbortController();
    loadFeedback(controller.signal);
    return () => controller.abort();
  }, [loadFeedback]);

  const upload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setImporting(true);
    try {
      const result = await api.importGca(file);
      onNotice?.({ type: "success", text: result.message });
      setBookingPage(1);
      setFeedbackPage(1);
      setDateFrom("");
      setDateTo("");
      setReloadSeq((value) => value + 1);
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setImporting(false);
      event.target.value = "";
    }
  };

  const kpis = data?.kpis;
  const meta = data?.meta;
  const empty = !meta?.rowCount;

  return (
    <div className={`dash-layout${embedded ? " gca-embedded" : ""}${loading || tablesLoading ? " is-loading" : ""}`}>
      <input ref={inputRef} hidden type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={upload} />
      <div className="dash-toolbar">
        <div>
          <p className="dash-toolbar-kicker">Reporting period</p>
          <div className="dash-dates">
            <label>
              From
              <input
                type="date"
                value={dateFrom}
                min={meta?.dateMin || undefined}
                max={meta?.dateMax || undefined}
                disabled={empty}
                onChange={(event) => {
                  setDateFrom(event.target.value);
                  setBookingPage(1);
                  setFeedbackPage(1);
                }}
              />
            </label>
            <label>
              To
              <input
                type="date"
                value={dateTo}
                min={meta?.dateMin || undefined}
                max={meta?.dateMax || undefined}
                disabled={empty}
                onChange={(event) => {
                  setDateTo(event.target.value);
                  setBookingPage(1);
                  setFeedbackPage(1);
                }}
              />
            </label>
          </div>
        </div>
        <p className="dash-meta">
          {empty
            ? "Re-import the GCA LCL Project Analysis workbook."
            : `${meta.filename} · ${meta.filteredCount} of ${meta.bookingCount} bookings · ${meta.importedAt}`}
        </p>
      </div>
      <div className="filter-chips">
        {LANES.map((item) => (
          <button
            key={item.id || "all"}
            type="button"
            className={lane === item.id ? "active" : ""}
            onClick={() => {
              setLane(item.id);
              setBookingPage(1);
              setFeedbackPage(1);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
      {loading && !data ? <p className="preview-empty">Loading GCA Hypercare…</p> : null}
      {empty && !loading ? (
        <section className="card dash-empty">
          <p>No GCA data yet. Re-import the hypercare workbook to load SZ1 / SZ EUR bookings and Area feedback.</p>
        </section>
      ) : null}
      {!empty && kpis ? (
        <>
          <div className="dash-section">
            <div className="dash-section-head">
              <h3>Overview</h3>
              <p>SZ1 booking conversion and Area feedback for the selected dates</p>
            </div>
            <div className="dash-kpis">
              <article className="dash-kpi">
                <span>Received</span>
                <strong className="dash-kpi-count">{formatNumber(kpis.received)}</strong>
              </article>
              <article className="dash-kpi">
                <span>GSC converted</span>
                <strong className="dash-kpi-count">{formatNumber(kpis.gscConverted)}</strong>
                <em>{kpis.gscConversionRate}% of received</em>
              </article>
              <article className="dash-kpi">
                <span>AI converted</span>
                <strong className="dash-kpi-count">{formatNumber(kpis.aiConverted)}</strong>
                <em>{kpis.aiConversionRate}% of received</em>
              </article>
              <article className="dash-kpi">
                <span>Cancelled</span>
                <strong className="dash-kpi-count">{formatNumber(kpis.cancelled)}</strong>
                <em>{kpis.cancelledRate}% cancelled</em>
              </article>
              <article className="dash-kpi">
                <span>Feedback</span>
                <strong className="dash-kpi-count">{formatNumber(kpis.feedbackCount)}</strong>
                <em>{kpis.errorsPerBooking} errors per booking</em>
              </article>
              <article className="dash-kpi">
                <span>Pending</span>
                <strong className="dash-kpi-count">{formatNumber(kpis.pending)}</strong>
                <em>{kpis.conversionRate}% converted</em>
              </article>
            </div>
          </div>
          <div className="dash-section">
            <div className="dash-section-head">
              <h3>Performance</h3>
              <p>Daily volume, conversion mix, and feedback categories</p>
            </div>
            <div className="dash-charts">
              <section className="card">
                <div className="summary">
                  <div>
                    <strong>Daily volume</strong>
                    <p className="dash-section-note">Bookings received by date</p>
                  </div>
                </div>
                <div className="dash-chart-body dash-chart-hours">
                  {(data.series?.byDay || []).length ? (
                    <DayChart items={data.series.byDay} />
                  ) : (
                    <p className="dash-section-note">No daily volume in this range.</p>
                  )}
                </div>
              </section>
              <section className="card">
                <div className="summary">
                  <div>
                    <strong>Conversion mix</strong>
                    <p className="dash-section-note">Status of bookings in this period</p>
                  </div>
                </div>
                <div className="dash-chart-body">
                  <DonutChart items={data.series?.byStatus || []} />
                </div>
              </section>
              <section className="card">
                <div className="summary">
                  <div>
                    <strong>Feedback by category</strong>
                    <p className="dash-section-note">Area quality comments, excluding Test</p>
                  </div>
                  <span className="dash-count-chip">{data.series?.byCategory?.length || 0}</span>
                </div>
                <div className="dash-chart-body">
                  <BarList items={data.series?.byCategory || []} />
                </div>
              </section>
            </div>
          </div>
          <section className="card dash-data">
            <div className="summary">
              <div>
                <strong>Bookings</strong>
                <p className="dash-section-note">SZ1 and SZ EUR conversion log</p>
              </div>
              <span className="dash-count-chip">
                {bookingMeta.total} {bookingMeta.total === 1 ? "row" : "rows"}
              </span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Order ID</th>
                    <th>Booking ID</th>
                    <th>Name</th>
                    <th>Status</th>
                    <th>HBL#</th>
                    <th>SCM</th>
                    <th>Lane</th>
                    <th>Feedback</th>
                  </tr>
                </thead>
                <tbody>
                  {bookings.length === 0 ? (
                    <tr>
                      <td colSpan="9" className="empty">
                        No bookings in this filter.
                      </td>
                    </tr>
                  ) : (
                    bookings.map((row) => (
                      <tr key={row.id}>
                        <td>{row.date || "—"}</td>
                        <td>
                          <strong>{row.orderId || "—"}</strong>
                        </td>
                        <td>{row.bookingId || "—"}</td>
                        <td>{row.name || "—"}</td>
                        <td>
                          <StatusLabel value={row.status} />
                        </td>
                        <td>{row.hbl || "—"}</td>
                        <td>{row.scm || "—"}</td>
                        <td>{row.lane === "europe" ? "Europe" : "Non-Europe"}</td>
                        <td>{row.feedbackCount || "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <TablePager
              total={bookingMeta.total || 0}
              page={bookingPage}
              pageSize={bookingMeta.pageSize || GCA_PAGE_SIZE}
              onPageChange={setBookingPage}
              emptyLabel="No bookings"
            />
          </section>
          <section className="card dash-data">
            <div className="summary">
              <div>
                <strong>Area feedback</strong>
                <p className="dash-section-note">Joined to bookings on the last 10 characters of HBL</p>
              </div>
              <span className="dash-count-chip">
                {feedbackMeta.total} {feedbackMeta.total === 1 ? "row" : "rows"}
              </span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>HBL#</th>
                    <th>Field</th>
                    <th>Incorrect</th>
                    <th>Corrected</th>
                    <th>Cause</th>
                    <th>Category</th>
                    <th>GSC PIC</th>
                    <th>Lane</th>
                  </tr>
                </thead>
                <tbody>
                  {feedback.length === 0 ? (
                    <tr>
                      <td colSpan="9" className="empty">
                        No feedback in this filter.
                      </td>
                    </tr>
                  ) : (
                    feedback.map((row) => (
                      <tr key={row.id}>
                        <td>{row.date || "—"}</td>
                        <td>
                          <strong>{row.hbl || "—"}</strong>
                        </td>
                        <td>{row.wronglyIdentified || "—"}</td>
                        <td>{row.incorrect || "—"}</td>
                        <td>{row.corrected || "—"}</td>
                        <td>{row.cause || "—"}</td>
                        <td>{row.category || "—"}</td>
                        <td>{row.gscPic || "—"}</td>
                        <td>{row.lane === "europe" ? "Europe" : row.lane === "non-europe" ? "Non-Europe" : "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <TablePager
              total={feedbackMeta.total || 0}
              page={feedbackPage}
              pageSize={feedbackMeta.pageSize || GCA_PAGE_SIZE}
              onPageChange={setFeedbackPage}
              emptyLabel="No feedback"
            />
          </section>
        </>
      ) : null}
    </div>
  );
});

export default GcaDashboard;
