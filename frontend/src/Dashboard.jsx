import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import { api } from "./api";
import FieldSelect from "./FieldSelect";

const WEEKDAY_FILTERS = [
  { id: "all", label: "All" },
  { id: "0", label: "Sun" },
  { id: "1", label: "Mon" },
  { id: "2", label: "Tue" },
  { id: "3", label: "Wed" },
  { id: "4", label: "Thu" },
  { id: "5", label: "Fri" },
  { id: "6", label: "Sat" },
];

function parseReceivedStamp(value) {
  const match = String(value || "").trim().match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}))?/);
  if (!match) {
    return null;
  }
  return {
    weekday: new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])).getDay(),
    hour: match[4] != null ? Number(match[4]) : 0,
  };
}

function volumeByHour(rows, weekdayId) {
  const counts = Array(24).fill(0);
  const wanted = weekdayId === "all" ? null : Number(weekdayId);
  for (const row of rows) {
    const stamp = parseReceivedStamp(row.emailReceived);
    if (!stamp) {
      continue;
    }
    if (wanted != null && stamp.weekday !== wanted) {
      continue;
    }
    if (stamp.hour >= 0 && stamp.hour <= 23) {
      counts[stamp.hour] += 1;
    }
  }
  return counts.map((count, hour) => ({
    label: `${String(hour).padStart(2, "0")}:00`,
    count,
  }));
}

const OVER_8H_MINUTES = 8 * 60;

function roundOne(value) {
  return Math.round(value * 10) / 10;
}

function processAverages(rows, includeOver8h) {
  const all = [];
  const byHandler = new Map();
  for (const row of rows) {
    if (row.processMinutes == null || row.processMinutes === "") {
      continue;
    }
    const value = Number(row.processMinutes);
    if (!Number.isFinite(value)) {
      continue;
    }
    if (!includeOver8h && Math.abs(value) > OVER_8H_MINUTES) {
      continue;
    }
    all.push(value);
    const handler = row.handledBy || "(blank)";
    const list = byHandler.get(handler);
    if (list) {
      list.push(value);
    } else {
      byHandler.set(handler, [value]);
    }
  }
  const avg = all.length ? roundOne(all.reduce((sum, value) => sum + value, 0) / all.length) : null;
  const processByHandler = [...byHandler.entries()]
    .map(([label, values]) => ({
      label,
      minutes: roundOne(values.reduce((sum, value) => sum + value, 0) / values.length),
      count: values.length,
    }))
    .sort((left, right) => right.minutes - left.minutes || left.label.localeCompare(right.label));
  const peak = processByHandler[0]?.minutes;
  for (const item of processByHandler) {
    item.isMax = item.minutes === peak;
  }
  return { avg, count: all.length, processByHandler };
}

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

function spreadCoordinates(values, size, minGap) {
  const count = values.length;
  const pos = new Array(count).fill(size / 2);
  if (count <= 1) {
    return pos;
  }
  const order = values
    .map((value, index) => ({ value, index }))
    .sort((left, right) => left.value - right.value || left.index - right.index);
  const gaps = [];
  for (let index = 1; index < count; index += 1) {
    gaps.push(Math.max(0, order[index].value - order[index - 1].value));
  }
  const nonzero = gaps.filter((gap) => gap > 0).sort((left, right) => left - right);
  const median = nonzero[Math.floor((nonzero.length - 1) / 2)] || 1;
  let lengths = gaps.map((gap) => Math.min(Math.max(gap, median * 0.2), median * 3));
  const total = lengths.reduce((sum, gap) => sum + gap, 0) || 1;
  lengths = lengths.map((gap) => (gap / total) * size);
  for (let pass = 0; pass < 8; pass += 1) {
    let need = 0;
    const short = [];
    lengths.forEach((length, index) => {
      if (length + 0.1 < minGap) {
        short.push(index);
        need += minGap - length;
      }
    });
    if (need <= 0.5) {
      break;
    }
    let pool = 0;
    const donors = [];
    lengths.forEach((length, index) => {
      const extra = length - minGap;
      if (extra > 0.5) {
        donors.push({ index, extra });
        pool += extra;
      }
    });
    if (pool <= 0.5) {
      break;
    }
    const take = Math.min(pool, need);
    donors.forEach((donor) => {
      lengths[donor.index] -= (donor.extra / pool) * take;
    });
    short.forEach((index) => {
      const missing = minGap - lengths[index];
      lengths[index] += (missing / need) * take;
    });
  }
  let cursor = 0;
  order.forEach((item, index) => {
    pos[item.index] = cursor;
    if (index < lengths.length) {
      cursor += lengths[index];
    }
  });
  return pos;
}

function coordinateFor(sortedValues, positions, value) {
  if (value <= sortedValues[0]) {
    return positions[0];
  }
  const last = sortedValues.length - 1;
  if (value >= sortedValues[last]) {
    return positions[last];
  }
  for (let index = 1; index < sortedValues.length; index += 1) {
    if (value <= sortedValues[index]) {
      const span = sortedValues[index] - sortedValues[index - 1] || 1;
      const t = (value - sortedValues[index - 1]) / span;
      return positions[index - 1] + t * (positions[index] - positions[index - 1]);
    }
  }
  return positions[last];
}

function HandlerQuadrant({ points }) {
  const width = 360;
  const height = 280;
  const pad = { l: 48, r: 28, t: 22, b: 42 };
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  if (!points.length) {
    return <p className="preview-empty">No handler averages in this range.</p>;
  }
  const minutes = points.map((point) => point.minutes);
  const counts = points.map((point) => point.count);
  const minX = Math.min(...minutes);
  const maxX = Math.max(...minutes);
  const minY = Math.min(...counts);
  const maxY = Math.max(...counts);
  const meanX = minutes.reduce((sum, value) => sum + value, 0) / minutes.length;
  const meanY = counts.reduce((sum, value) => sum + value, 0) / counts.length;
  const xGap = Math.min(26, plotW / Math.max(points.length - 1, 1));
  const yGap = Math.min(22, plotH / Math.max(points.length - 1, 1));
  const xSpread = spreadCoordinates(minutes, plotW, xGap);
  const ySpread = spreadCoordinates(counts, plotH, yGap);
  const xOrder = minutes
    .map((value, index) => ({ value, pos: xSpread[index] }))
    .sort((left, right) => left.value - right.value);
  const yOrder = counts
    .map((value, index) => ({ value, pos: ySpread[index] }))
    .sort((left, right) => left.value - right.value);
  const sx = (value) => pad.l + (plotW - coordinateFor(xOrder.map((item) => item.value), xOrder.map((item) => item.pos), value));
  const sy = (value) => pad.t + (plotH - coordinateFor(yOrder.map((item) => item.value), yOrder.map((item) => item.pos), value));
  const crossX = sx(meanX);
  const crossY = sy(meanY);
  const plotRight = pad.l + plotW;
  const plotBottom = pad.t + plotH;
  const placedLabels = [];
  const bubbles = points
    .map((point, index) => ({
      ...point,
      x: pad.l + (plotW - xSpread[index]),
      y: pad.t + (plotH - ySpread[index]),
      name: shortHandler(point.label),
    }))
    .sort((left, right) => left.y - right.y || left.x - right.x);
  const bubbleBoxes = bubbles.map((point) => ({
    left: point.x - 11,
    right: point.x + 11,
    top: point.y - 11,
    bottom: point.y + 11,
    owner: point.label,
  }));
  const overlaps = (box, extra = []) =>
    [...placedLabels, ...extra].some(
      (item) => !(box.right < item.left || box.left > item.right || box.bottom < item.top || box.top > item.bottom)
    );
  for (const point of bubbles) {
    const textW = Math.max(36, point.name.length * 7.2);
    const attempts = [];
    const towardRight = { x: point.x + 14, anchor: "start" };
    const towardLeft = { x: point.x - 14, anchor: "end" };
    const first = point.x > width * 0.62 ? towardLeft : towardRight;
    const second = first === towardLeft ? towardRight : towardLeft;
    for (const step of [0, 18, -18, 36, -36]) {
      attempts.push({ ...first, dy: 4 + step });
      attempts.push({ ...second, dy: 4 + step });
    }
    const others = bubbleBoxes.filter((item) => item.owner !== point.label);
    let chosen = null;
    let chosenBox = null;
    for (const attempt of attempts) {
      const left = attempt.anchor === "end" ? attempt.x - textW : attempt.x;
      const box = {
        left,
        right: left + textW,
        top: point.y + attempt.dy - 11,
        bottom: point.y + attempt.dy + 3,
      };
      if (box.left < 4 || box.right > width - 4 || box.top < 4 || box.bottom > height - 28) {
        continue;
      }
      if (!overlaps(box, others)) {
        chosen = attempt;
        chosenBox = box;
        break;
      }
    }
    if (!chosen) {
      chosen = attempts[0];
      const left = chosen.anchor === "end" ? chosen.x - textW : chosen.x;
      chosenBox = {
        left,
        right: left + textW,
        top: point.y + chosen.dy - 11,
        bottom: point.y + chosen.dy + 3,
      };
    }
    placedLabels.push(chosenBox);
    point.lx = chosen.x;
    point.ly = point.y + chosen.dy;
    point.anchor = chosen.anchor;
    point.leader = Math.abs(point.ly - point.y) > 12;
  }
  return (
    <div className="dash-quadrant">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Handler quadrant of bookings and average process time">
        <rect x={pad.l} y={pad.t} width={crossX - pad.l} height={crossY - pad.t} className="dash-quadrant-zone" />
        <rect x={crossX} y={pad.t} width={plotRight - crossX} height={crossY - pad.t} className="dash-quadrant-best" />
        <rect x={pad.l} y={crossY} width={crossX - pad.l} height={plotBottom - crossY} className="dash-quadrant-zone" />
        <rect x={crossX} y={crossY} width={plotRight - crossX} height={plotBottom - crossY} className="dash-quadrant-zone" />
        <line x1={crossX} y1={pad.t} x2={crossX} y2={plotBottom} className="dash-quadrant-cross" />
        <line x1={pad.l} y1={crossY} x2={plotRight} y2={crossY} className="dash-quadrant-cross" />
        <text x={sx(minX)} y={height - 22} textAnchor="middle" className="dash-quadrant-axis">
          {roundOne(minX)}
        </text>
        <text x={sx(maxX)} y={height - 22} textAnchor="middle" className="dash-quadrant-axis">
          {roundOne(maxX)}
        </text>
        <text x={pad.l} y={height - 6} className="dash-quadrant-axis">
          higher
        </text>
        <text x={plotRight} y={height - 6} textAnchor="end" className="dash-quadrant-axis">
          lower process time
        </text>
        <text x={pad.l - 8} y={sy(maxY) + 4} textAnchor="end" className="dash-quadrant-axis">
          {maxY}
        </text>
        <text x={pad.l - 8} y={sy(minY) + 4} textAnchor="end" className="dash-quadrant-axis">
          {minY}
        </text>
        <text x={pad.l} y={12} className="dash-quadrant-axis">
          more bookings
        </text>
        {bubbles.map((point) => (
          <g key={point.label}>
            {point.leader ? (
              <line
                x1={point.x}
                y1={point.y}
                x2={point.anchor === "end" ? point.lx + 2 : point.lx - 2}
                y2={point.ly - 3}
                className="dash-quadrant-leader"
              />
            ) : null}
            <circle cx={point.x} cy={point.y} r="8" className="dash-quadrant-ball">
              <title>{`${point.label} · ${point.count} bookings · ${point.minutes} min`}</title>
            </circle>
            <text x={point.lx} y={point.ly} textAnchor={point.anchor} className="dash-quadrant-name">
              {point.name}
            </text>
          </g>
        ))}
      </svg>
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

function DataTable({
  rows,
  maxProcessOrder,
  emptyMessage = "No bookings in this date range.",
  note = "Complete rows for the selected date range",
}) {
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
          <p className="dash-section-note">{note}</p>
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
                  {emptyMessage}
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
  const [hourWeekday, setHourWeekday] = useState("all");
  const [includeOver8h, setIncludeOver8h] = useState(false);
  const [mailboxes, setMailboxes] = useState([]);
  const loadSeq = useRef(0);

  const load = useCallback(
    async (from = dateFrom, to = dateTo, box = mailboxes) => {
      const seq = ++loadSeq.current;
      setLoading(true);
      try {
        const selected = (Array.isArray(box) ? box : box ? [box] : []).map(String).filter(Boolean);
        const result = await api.getDashboard(from, to, selected);
        if (seq !== loadSeq.current) {
          return;
        }
        let payload = result.data || null;
        const allowed = new Set(payload?.meta?.mailboxes || []);
        if (payload?.meta?.hasBlankMailbox) {
          allowed.add("(blank)");
        }
        const valid = selected.filter((name) => allowed.has(name));
        if (valid.length !== selected.length) {
          setMailboxes(valid);
          const cleared = await api.getDashboard(from, to, valid);
          if (seq !== loadSeq.current) {
            return;
          }
          payload = cleared.data || null;
        }
        setData(payload);
        if (!from && payload?.meta?.dateFrom) {
          setDateFrom(payload.meta.dateFrom);
        }
        if (!to && payload?.meta?.dateTo) {
          setDateTo(payload.meta.dateTo);
        }
      } catch (error) {
        if (seq === loadSeq.current) {
          onNotice?.({ type: "error", text: error.message });
        }
      } finally {
        if (seq === loadSeq.current) {
          setLoading(false);
        }
      }
    },
    [dateFrom, dateTo, mailboxes, onNotice]
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
      setMailboxes([]);
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
  const mailboxOptions = useMemo(() => {
    const items = [{ value: "", label: "All mailboxes" }];
    if (meta?.hasBlankMailbox) {
      items.push({ value: "(blank)", label: "(blank)" });
    }
    for (const name of meta?.mailboxes || []) {
      items.push({ value: name, label: name });
    }
    return items;
  }, [meta?.hasBlankMailbox, meta?.mailboxes]);
  const tableEmptyMessage = mailboxes.length
    ? "No bookings for the selected mailboxes in these dates."
    : "No bookings in this date range.";
  const tableNote = mailboxes.length
    ? "Complete rows for the selected dates and mailboxes"
    : "Complete rows for the selected date range";
  const rows = data?.rows || [];
  const hourItems = useMemo(() => volumeByHour(rows, hourWeekday), [rows, hourWeekday]);
  const hourWeekdayLabel = WEEKDAY_FILTERS.find((item) => item.id === hourWeekday)?.label || "All";
  const processStats = useMemo(() => processAverages(rows, includeOver8h), [rows, includeOver8h]);
  const quadrantPoints = useMemo(() => {
    const minutes = new Map(processStats.processByHandler.map((item) => [item.label, item.minutes]));
    return (data?.series?.byHandler || [])
      .map((item) => ({
        label: item.label,
        minutes: minutes.get(item.label),
        count: Number(item.count) || 0,
      }))
      .filter((item) => item.count > 0 && Number.isFinite(item.minutes));
  }, [data?.series?.byHandler, processStats.processByHandler]);
  const avgProcessLabel = processStats.avg == null ? "—" : `${processStats.avg} min`;
  const avgProcessNote = includeOver8h ? "including over 8 hours" : "excluding over 8 hours";
  const conclusions = useMemo(() => {
    const items = data?.conclusions || [];
    if (processStats.avg == null) {
      return items;
    }
    return items.map((item) => {
      if (item.kind !== "average-process") {
        return item;
      }
      return {
        ...item,
        text: includeOver8h
          ? `Average process-time is ${processStats.avg} min across ${processStats.count} bookings including process times over 8 hours.`
          : `Average process-time is ${processStats.avg} min across ${processStats.count} bookings after removing process times over 8 hours.`,
      };
    });
  }, [data?.conclusions, includeOver8h, processStats]);

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
            <label className="dash-mailbox">
              Mailbox
              <FieldSelect
                multiple
                fitMenu
                value={mailboxes}
                disabled={empty || mailboxOptions.length <= 1}
                searchable={(meta?.mailboxes || []).length > 8}
                placeholder="All mailboxes"
                ariaLabel="Filter by mailbox"
                options={mailboxOptions}
                onChange={setMailboxes}
              />
            </label>
          </div>
          <label className="dash-switch">
            <input
              type="checkbox"
              role="switch"
              checked={includeOver8h}
              disabled={empty}
              onChange={(event) => setIncludeOver8h(event.target.checked)}
            />
            <span className="dash-switch-ui" aria-hidden="true" />
            Include over 8 hours in averages
          </label>
        </div>
        <p className="dash-meta">
          {empty
            ? "Upload the LCL booking daily report CSV."
            : `${meta.filename} · ${meta.filteredCount} of ${meta.rowCount} rows · ${meta.uploadedAt}`}
        </p>
      </div>
      {loading && !data ? <p className="preview-empty">Loading dashboard…</p> : null}
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
                <strong className="dash-kpi-count">{avgProcessLabel}</strong>
                <em>{avgProcessNote}</em>
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
              <p>Handler volume, workload quadrants, process-time, and inbound hours</p>
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
                    <strong>Handler quadrants</strong>
                    <p className="dash-section-note">
                      More bookings toward the top. Lower average process time toward the right. Cross is the group average.
                    </p>
                  </div>
                </div>
                <div className="dash-chart-body">
                  <HandlerQuadrant points={quadrantPoints} />
                </div>
              </section>
              <section className="card">
                <div className="summary">
                  <div>
                    <strong>Avg process-time by handler</strong>
                    <p className="dash-section-note">
                      Converted time minus handling time, {avgProcessNote}
                    </p>
                  </div>
                </div>
                <div className="dash-chart-body">
                  <BarList items={processStats.processByHandler} valueKey="minutes" highlightKey="isMax" />
                </div>
              </section>
              <section className="card">
                <div className="summary dash-hour-summary">
                  <div>
                    <strong>Volume by hour received</strong>
                    <p className="dash-section-note">
                      {hourWeekday === "all"
                        ? "Inbound email hour"
                        : `Inbound email hour · ${hourWeekdayLabel}`}
                    </p>
                  </div>
                  <div className="filter-chips dash-weekday-chips" role="tablist" aria-label="Filter by weekday">
                    {WEEKDAY_FILTERS.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        role="tab"
                        aria-selected={hourWeekday === item.id}
                        className={hourWeekday === item.id ? "active" : ""}
                        onClick={() => setHourWeekday(item.id)}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="dash-chart-body dash-chart-hours">
                  <HourChart items={hourItems} />
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
                {(conclusions || []).map((item) => (
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
          <DataTable
            rows={rows}
            maxProcessOrder={kpis.maxProcessOrder}
            emptyMessage={tableEmptyMessage}
            note={tableNote}
          />
        </>
      ) : null}
    </div>
  );
});

export default Dashboard;
