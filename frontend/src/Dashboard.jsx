import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { api } from "./api";
import FieldSelect from "./FieldSelect";

const DONUT_COLORS = ["#42b0d5", "#00243d", "#0077b2", "#4c4c4c", "#77c6e0"];

function shortHandler(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "(blank)";
  }
  return text.split("@")[0];
}

function formatMinutes(value) {
  if (value == null || value === "") {
    return "—";
  }
  return `${value} min`;
}

function statusTone(status) {
  const text = String(status || "").toLowerCase();
  if (text.includes("converted")) {
    return "converted";
  }
  if (text.includes("processing")) {
    return "processing";
  }
  return "";
}

function StatusLabel({ value }) {
  const label = String(value || "—").replace("AI-Booking: ", "");
  const tone = statusTone(value);
  return <span className={`status-pill dash-status${tone ? ` ${tone}` : ""}`}>{label}</span>;
}

function BarList({ items, valueKey = "count", highlightKey }) {
  const max = Math.max(...items.map((item) => Number(item[valueKey]) || 0), 1);
  return (
    <ul className="dash-bars">
      {items.map((item) => {
        const value = Number(item[valueKey]) || 0;
        const width = Math.max((value / max) * 100, value ? 4 : 0);
        const highlighted = highlightKey ? item[highlightKey] : false;
        return (
          <li key={item.label} className={highlighted ? "is-highest" : ""}>
            <span className="dash-bar-label" title={item.label}>
              {shortHandler(item.label)}
            </span>
            <span className="dash-bar-track">
              <span className="dash-bar-fill" style={{ width: `${width}%` }} />
            </span>
            <span className="dash-bar-value">{valueKey === "minutes" ? `${value} min` : value}</span>
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
      <svg viewBox="0 0 140 140" aria-label="Status mix">
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
              {item.label.replace("AI-Booking: ", "")}
            </span>
            <span className="dash-bar-value">{item.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function HourChart({ items }) {
  const max = Math.max(...items.map((item) => item.count || 0), 1);
  return (
    <div className="dash-hours" aria-label="Volume by hour">
      {items.map((item) => {
        const height = Math.max(((item.count || 0) / max) * 100, item.count ? 6 : 0);
        const hour = item.label.slice(0, 2);
        return (
          <div key={item.label} className="dash-hour" title={`${item.label} · ${item.count}`}>
            {item.count ? <span className="dash-hour-count">{item.count}</span> : <span className="dash-hour-count is-empty" />}
            <span className="dash-hour-bar" style={{ height: `${height}%` }} />
            <span className="dash-hour-label">{hour}</span>
          </div>
        );
      })}
    </div>
  );
}

const DASH_TABLE_PAGE_SIZE = 50;

function DataTable({ rows, maxProcessOrder }) {
  const [page, setPage] = useState(1);
  const total = rows.length;
  const totalPages = Math.max(1, Math.ceil(total / DASH_TABLE_PAGE_SIZE) || 1);
  const firstId = rows[0]?.id;

  useEffect(() => {
    setPage(1);
  }, [total, firstId]);

  const safePage = Math.min(page, totalPages);
  const from = total === 0 ? 0 : (safePage - 1) * DASH_TABLE_PAGE_SIZE + 1;
  const to = Math.min(safePage * DASH_TABLE_PAGE_SIZE, total);
  const visible = rows.slice((safePage - 1) * DASH_TABLE_PAGE_SIZE, safePage * DASH_TABLE_PAGE_SIZE);
  const pages = Array.from({ length: totalPages }, (_, index) => index + 1);

  return (
    <section className="card dash-data">
      <div className="summary">
        <div>
          <strong>All bookings</strong>
          <p className="dash-section-note">Complete rows for the selected date range</p>
        </div>
        <span className="dash-count-chip">
          {total} {total === 1 ? "row" : "rows"}
        </span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Order</th>
              <th>Shipment</th>
              <th>Status</th>
              <th>Handler</th>
              <th>Received</th>
              <th>Handling</th>
              <th>Converted</th>
              <th>Process</th>
              <th>Wait</th>
              <th>Message Id</th>
              <th>Date</th>
              <th>Mailbox</th>
              <th>Subject</th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td colSpan="13" className="empty">
                  No bookings in this date range.
                </td>
              </tr>
            ) : (
              visible.map((row) => (
                <tr key={row.id} className={row.orderNumber && row.orderNumber === maxProcessOrder ? "selected" : ""}>
                  <td>
                    <strong>{row.orderNumber || "—"}</strong>
                  </td>
                  <td>{row.shipmentNumber || "—"}</td>
                  <td>
                    <StatusLabel value={row.emailStatus} />
                  </td>
                  <td title={row.handledBy}>{shortHandler(row.handledBy)}</td>
                  <td>{row.emailReceived || "—"}</td>
                  <td>{row.handlingTime || "—"}</td>
                  <td>{row.bookingConvertedTime || "—"}</td>
                  <td>{formatMinutes(row.processMinutes)}</td>
                  <td>{formatMinutes(row.handleWaitMinutes)}</td>
                  <td>{row.messageId || "—"}</td>
                  <td>{row.date || "—"}</td>
                  <td>{row.mailbox || "—"}</td>
                  <td className="dash-subject">{row.subject || "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <span>{total === 0 ? "No bookings" : `Showing ${from}–${to} of ${total}`}</span>
        <div className="pagination-nav">
          <button type="button" disabled={safePage <= 1} onClick={() => setPage((value) => value - 1)}>
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
              onChange={(next) => setPage(Number(next))}
              ariaLabel="Select bookings page"
            />
            of {totalPages}
          </label>
          <button type="button" disabled={safePage >= totalPages} onClick={() => setPage((value) => value + 1)}>
            Next
          </button>
        </div>
      </div>
    </section>
  );
}

const Dashboard = forwardRef(function Dashboard({ onNotice, onRefreshLogs, onImportingChange }, ref) {
  const inputRef = useRef();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const load = useCallback(
    async (from = dateFrom, to = dateTo) => {
      setLoading(true);
      try {
        const result = await api.getDashboard(from, to);
        const payload = result.data || null;
        setData(payload);
        if (!from && payload?.meta?.dateFrom) {
          setDateFrom(payload.meta.dateFrom);
        }
        if (!to && payload?.meta?.dateTo) {
          setDateTo(payload.meta.dateTo);
        }
      } catch (error) {
        onNotice?.({ type: "error", text: error.message });
      } finally {
        setLoading(false);
      }
    },
    [dateFrom, dateTo, onNotice]
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    onImportingChange?.(importing);
  }, [importing, onImportingChange]);

  const openUpload = () => inputRef.current?.click();

  useImperativeHandle(ref, () => ({ openUpload, importing }));

  const upload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    setImporting(true);
    try {
      const result = await api.importDashboard(file);
      setData(result.data || null);
      setDateFrom(result.data?.meta?.dateFrom || "");
      setDateTo(result.data?.meta?.dateTo || "");
      onNotice?.({ type: "success", text: result.message || "Dashboard updated" });
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setImporting(false);
    }
  };

  const applyDates = (from, to) => {
    setDateFrom(from);
    setDateTo(to);
  };

  const kpis = data?.kpis;
  const meta = data?.meta;
  const empty = !meta?.rowCount;
  const rows = data?.rows || [];

  return (
    <div className="dash-layout">
      <input ref={inputRef} hidden type="file" accept=".csv,text/csv" onChange={upload} />
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
                onChange={(event) => applyDates(event.target.value, dateTo)}
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
                onChange={(event) => applyDates(dateFrom, event.target.value)}
              />
            </label>
          </div>
        </div>
        <p className="dash-meta">
          {empty
            ? "Upload the LCL booking daily report CSV."
            : `${meta.filename} · ${meta.filteredCount} of ${meta.rowCount} rows · ${meta.uploadedAt}`}
        </p>
      </div>
      {loading && !data ? <p className="preview-empty">Loading dashboard...</p> : null}
      {empty && !loading ? (
        <section className="card dash-empty">
          <p>No dashboard data yet. Upload a daily report with Order Number, Shipment Number, timestamps, and Handled By.</p>
        </section>
      ) : null}
      {!empty && kpis ? (
        <>
          <div className="dash-section">
            <div className="dash-section-head">
              <h3>Overview</h3>
              <p>Key volumes and process-times for the selected dates</p>
            </div>
            <div className="dash-kpis">
              <article className="dash-kpi">
                <span>Total bookings</span>
                <strong className="dash-kpi-count">{kpis.total}</strong>
              </article>
              <article className="dash-kpi">
                <span>Converted</span>
                <strong className="dash-kpi-count">{kpis.converted}</strong>
                <em>{kpis.conversionRate}% conversion</em>
              </article>
              <article className="dash-kpi">
                <span>Processing</span>
                <strong className="dash-kpi-count">{kpis.processing}</strong>
              </article>
              <article className="dash-kpi">
                <span>Handlers</span>
                <strong className="dash-kpi-count">{kpis.handlers}</strong>
              </article>
              <article className="dash-kpi">
                <span>Missing shipment</span>
                <strong className="dash-kpi-count">{kpis.missingShipment}</strong>
              </article>
              <article className="dash-kpi">
                <span>Average process-time</span>
                <strong className="dash-kpi-count">{kpis.avgProcessLabel}</strong>
              </article>
              <article className="dash-kpi dash-kpi-highest">
                <span>
                  Highest process-time
                  <span className="status-pill danger">highest</span>
                </span>
                <strong className="dash-kpi-count">{kpis.maxProcessLabel}</strong>
                <em>
                  {kpis.maxProcessOrder || "—"}
                  {kpis.maxProcessHandler ? ` · ${shortHandler(kpis.maxProcessHandler)}` : ""}
                </em>
              </article>
            </div>
          </div>
          <div className="dash-section">
            <div className="dash-section-head">
              <h3>Performance</h3>
              <p>Handler volume, status mix, process-time, and inbound hours</p>
            </div>
            <div className="dash-charts">
              <section className="card">
                <div className="summary">
                  <div>
                    <strong>By handler</strong>
                    <p className="dash-section-note">Bookings handled in this period</p>
                  </div>
                </div>
                <div className="dash-chart-body">
                  <BarList items={data.series?.byHandler || []} />
                </div>
              </section>
              <section className="card">
                <div className="summary">
                  <div>
                    <strong>Status</strong>
                    <p className="dash-section-note">Mix of email statuses</p>
                  </div>
                </div>
                <div className="dash-chart-body">
                  <DonutChart items={data.series?.byStatus || []} />
                </div>
              </section>
              <section className="card">
                <div className="summary">
                  <div>
                    <strong>Avg process-time by handler</strong>
                    <p className="dash-section-note">Converted time minus handling time</p>
                  </div>
                </div>
                <div className="dash-chart-body">
                  <BarList items={data.series?.processByHandler || []} valueKey="minutes" highlightKey="isMax" />
                </div>
              </section>
              <section className="card">
                <div className="summary">
                  <div>
                    <strong>Volume by hour received</strong>
                    <p className="dash-section-note">Inbound email hour</p>
                  </div>
                </div>
                <div className="dash-chart-body dash-chart-hours">
                  <HourChart items={data.series?.byHour || []} />
                </div>
              </section>
            </div>
          </div>
          <div className="dash-lower">
            <section className="card">
              <div className="summary">
                <div>
                  <strong>Conclusions</strong>
                  <p className="dash-section-note">Read-outs for this date range</p>
                </div>
              </div>
              <ul className="dash-conclusions">
                {(data.conclusions || []).map((item) => (
                  <li key={item.kind} className={item.kind === "highest-process" ? "is-highest" : ""}>
                    {item.text}
                  </li>
                ))}
              </ul>
            </section>
            <section className="card dash-flagged">
              <div className="summary">
                <div>
                  <strong>Flagged rows</strong>
                  <p className="dash-section-note">Abnormal waits or process-times</p>
                </div>
                <span className="dash-count-chip">{data.flagged?.length || 0}</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Order</th>
                      <th>Shipment</th>
                      <th>Handler</th>
                      <th>Process</th>
                      <th>Wait</th>
                      <th>Reasons</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.flagged || []).length === 0 ? (
                      <tr>
                        <td colSpan="6" className="empty">
                          No abnormal rows in this date range.
                        </td>
                      </tr>
                    ) : (
                      data.flagged.map((row) => (
                        <tr key={row.id} className={row.isHighestProcess ? "selected" : ""}>
                          <td>
                            <strong>{row.orderNumber || "—"}</strong>
                          </td>
                          <td>{row.shipmentNumber || "—"}</td>
                          <td>{shortHandler(row.handledBy)}</td>
                          <td>{formatMinutes(row.processMinutes)}</td>
                          <td>{formatMinutes(row.handleWaitMinutes)}</td>
                          <td>{(row.reasons || []).join(", ")}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
          <DataTable rows={rows} maxProcessOrder={kpis.maxProcessOrder} />
        </>
      ) : null}
    </div>
  );
});

export default Dashboard;
