import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useState } from "react";
import { api } from "./api";
import LclMap from "./LclMap";

function starPoints(cx, cy, spikes, outerRadius, innerRadius) {
  const points = [];
  const step = Math.PI / spikes;
  let rotation = -Math.PI / 2;
  for (let i = 0; i < spikes * 2; i += 1) {
    const radius = i % 2 === 0 ? outerRadius : innerRadius;
    points.push(`${cx + Math.cos(rotation) * radius},${cy + Math.sin(rotation) * radius}`);
    rotation += step;
  }
  return points.join(" ");
}

function formatNumber(value, digits = 0) {
  if (value == null || value === "") {
    return "—";
  }
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function ChipRow({ label, options, value, onChange, getKey, getText }) {
  const selected = Array.isArray(value) ? value : value ? [value] : [];
  const toggle = (key) => {
    if (selected.includes(key)) {
      onChange(selected.filter((item) => item !== key));
      return;
    }
    onChange([...selected, key]);
  };
  return (
    <div className="lcl-filter-row">
      <span>{label}</span>
      <div className="filter-chips lcl-chips">
        <button type="button" className={selected.length === 0 ? "active" : ""} onClick={() => onChange([])}>
          All
        </button>
        {options.map((option) => {
          const key = getKey(option);
          return (
            <button
              key={key}
              type="button"
              className={selected.includes(key) ? "active" : ""}
              onClick={() => toggle(key)}
            >
              {getText(option)}
            </button>
          );
        })}
      </div>
    </div>
  );
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

function MonthChart({ items }) {
  const max = Math.max(...items.map((item) => item.count || 0), 1);
  const average = items.length
    ? items.reduce((sum, item) => sum + (Number(item.count) || 0), 0) / items.length
    : 0;
  const avgPercent = max ? (average / max) * 100 : 0;
  return (
    <div className="lcl-month-chart" aria-label="Shipments by month">
      <div className="lcl-month-row lcl-month-counts">
        {items.map((item) => (
          <span key={item.label} className={`dash-hour-count${item.count ? "" : " is-empty"}`}>
            {item.count ? item.count.toLocaleString() : ""}
          </span>
        ))}
      </div>
      <div className="lcl-month-plot">
        {items.map((item) => {
          const height = Math.max(((item.count || 0) / max) * 100, item.count ? 4 : 0);
          return (
            <div key={item.label} className="lcl-month-bar" title={`${item.label}: ${item.count}`}>
              <span className="dash-hour-bar" style={{ height: `${height}%` }} />
            </div>
          );
        })}
        {average > 0 ? (
          <div className="lcl-avg-line" style={{ bottom: `${avgPercent}%` }}>
            <em>Yearly avg {formatNumber(average, 0)}</em>
          </div>
        ) : null}
      </div>
      <div className="lcl-month-row">
        {items.map((item) => (
          <span key={item.label} className="dash-hour-label">
            {item.label.slice(0, 3)}
          </span>
        ))}
      </div>
    </div>
  );
}

const YEAR_TREND_COLORS = ["#00243d", "#0077b2", "#42b0d5", "#4c4c4c"];
const MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function seriesPath(values, max, width, height, pad) {
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const step = values.length > 1 ? innerW / (values.length - 1) : innerW;
  let d = "";
  let drawing = false;
  values.forEach((value, index) => {
    if (value == null) {
      drawing = false;
      return;
    }
    const x = pad.left + index * step;
    const y = pad.top + innerH - (value / max) * innerH;
    d += `${drawing ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)} `;
    drawing = true;
  });
  return d.trim();
}

function monthAverages(years) {
  if (!years.length) {
    return [];
  }
  const length = years[0].values.length;
  return Array.from({ length }, (_, index) => {
    const nums = years.map((item) => item.values[index]).filter((value) => value != null);
    if (!nums.length) {
      return null;
    }
    return nums.reduce((sum, value) => sum + value, 0) / nums.length;
  });
}

function YearMonthTrend({ data }) {
  const years = data?.years || [];
  const width = 360;
  const height = 168;
  const pad = { top: 12, right: 8, bottom: 22, left: 36 };
  const averages = monthAverages(years);
  if (!years.length) {
    return <p className="dash-section-note">No year-month trend for the current filters.</p>;
  }
  const max = Math.max(
    ...years.flatMap((item) => item.values.filter((value) => value != null)),
    ...averages.filter((value) => value != null),
    1
  );
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const step = innerW / 11;
  return (
    <div className="lcl-trend">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Average trend by year and month">
        {[0.25, 0.5, 0.75, 1].map((frac) => {
          const y = pad.top + innerH * (1 - frac);
          return (
            <line
              key={frac}
              x1={pad.left}
              x2={width - pad.right}
              y1={y}
              y2={y}
              stroke="#e6eef2"
              strokeWidth="1"
            />
          );
        })}
        {years.map((item, index) => (
          <path
            key={item.year}
            d={seriesPath(item.values, max, width, height, pad)}
            fill="none"
            stroke={YEAR_TREND_COLORS[index % YEAR_TREND_COLORS.length]}
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}
        <path
          d={seriesPath(averages, max, width, height, pad)}
          fill="none"
          stroke="#f5b27a"
          strokeWidth="2pt"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {MONTH_SHORT.map((label, index) => (
          <text
            key={label}
            x={pad.left + index * step}
            y={height - 6}
            textAnchor="middle"
            className="lcl-trend-axis"
          >
            {label}
          </text>
        ))}
        <text x={pad.left - 6} y={pad.top + 4} textAnchor="end" className="lcl-trend-axis">
          {Math.round(max).toLocaleString()}
        </text>
        <text x={pad.left - 6} y={pad.top + innerH} textAnchor="end" className="lcl-trend-axis">
          0
        </text>
      </svg>
      <ul className="lcl-trend-legend">
        {years.map((item, index) => (
          <li key={item.year}>
            <span className="dash-swatch" style={{ background: YEAR_TREND_COLORS[index % YEAR_TREND_COLORS.length] }} />
            {item.year}
          </li>
        ))}
        <li>
          <span className="dash-swatch" style={{ background: "#f5b27a" }} />
          Avg
        </li>
      </ul>
    </div>
  );
}

const LclDashboard = forwardRef(function LclDashboard({ embedded = false, onNotice, onRefreshLogs, onImportingChange }, ref) {
  const [filters, setFilters] = useState({
    direction: [],
    year: [],
    month: [],
    branch: [],
    country: [],
    bosch: [],
  });
  const [options, setOptions] = useState({
    years: [],
    months: [],
    branches: [],
    directions: [],
    countries: [],
    meta: {},
  });
  const [summary, setSummary] = useState(null);
  const [mapPoints, setMapPoints] = useState([]);
  const [mapArrows, setMapArrows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [notice, setNotice] = useState("");

  const query = useMemo(() => {
    const bosch = filters.bosch.length === 1 ? filters.bosch[0] : "";
    return {
      direction: filters.direction,
      year: filters.year,
      month: filters.month,
      branch: filters.branch,
      country: filters.country,
      bosch,
    };
  }, [filters]);

  const loadFilters = useCallback(async () => {
    try {
      const filterResult = await api.lclFilters();
      setOptions(filterResult.data || {
        years: [],
        months: [],
        branches: [],
        directions: [],
        countries: [],
        meta: {},
      });
    } catch (error) {
      if (embedded) {
        onNotice?.({ type: "error", text: error.message });
      } else {
        setNotice(error.message);
      }
    }
  }, [embedded, onNotice]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [summaryResult, mapResult] = await Promise.all([
        api.lclSummary(query),
        api.lclMap(query),
      ]);
      setSummary(summaryResult.data || null);
      const mapData = mapResult.data;
      setMapPoints(Array.isArray(mapData) ? mapData : mapData?.points || []);
      setMapArrows(Array.isArray(mapData) ? [] : mapData?.arrows || []);
      if (!embedded) {
        setNotice("");
      }
    } catch (error) {
      if (embedded) {
        onNotice?.({ type: "error", text: error.message });
      } else {
        setNotice(error.message);
      }
    } finally {
      setLoading(false);
    }
  }, [query, embedded, onNotice]);

  useEffect(() => {
    loadFilters();
  }, [loadFilters]);

  useEffect(() => {
    const timer = setTimeout(() => {
      load();
    }, 200);
    return () => clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    onImportingChange?.(importing);
  }, [importing, onImportingChange]);

  const runImport = useCallback(async () => {
    setImporting(true);
    if (!embedded) {
      setNotice("Importing LCL workbook. This can take a few minutes…");
    }
    try {
      const result = await api.importLcl();
      const text = result.message || "Import complete";
      if (embedded) {
        onNotice?.({ type: "success", text });
      } else {
        setNotice(text);
      }
      await loadFilters();
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      if (embedded) {
        onNotice?.({ type: "error", text: error.message });
      } else {
        setNotice(error.message);
      }
    } finally {
      setImporting(false);
    }
  }, [embedded, load, loadFilters, onNotice, onRefreshLogs]);

  useImperativeHandle(ref, () => ({ openImport: runImport, importing }));

  const kpis = summary?.kpis;
  const meta = options.meta || {};
  const empty = !meta.total;
  const filtersActive = Boolean(
    filters.direction.length ||
      filters.year.length ||
      filters.month.length ||
      filters.branch.length ||
      filters.country.length ||
      filters.bosch.length
  );

  return (
    <div className={`lcl-page${embedded ? " is-embedded" : ""}`}>
      {embedded ? null : (
      <header className="lcl-topbar">
        <div className="lcl-brand">
          <svg className="star" viewBox="0 0 32 32" aria-hidden="true">
            <polygon fill="currentColor" points={starPoints(16, 16, 7, 14, 6)} />
          </svg>
          <div>
            <p className="brand-kicker">MALSTAR</p>
            <h1>LCL Volume Analysis</h1>
          </div>
        </div>
        <div className="lcl-topbar-meta">
          <span>
            {meta.total
              ? `${meta.total.toLocaleString()} shipments · ${meta.filename || "workbook"}`
              : "No LCL data loaded yet"}
          </span>
          <button type="button" className="primary" onClick={runImport} disabled={importing}>
            {importing ? "Importing…" : empty ? "Import workbook" : "Re-import"}
          </button>
        </div>
      </header>
      )}

      {!embedded && notice ? <p className={`lcl-notice${notice.toLowerCase().includes("fail") || notice.toLowerCase().includes("not found") ? " is-error" : ""}`}>{notice}</p> : null}

      <div className="lcl-filters">
        <ChipRow
          label="Direction"
          options={options.directions || []}
          value={filters.direction}
          onChange={(direction) => setFilters((current) => ({ ...current, direction }))}
          getKey={(item) => item}
          getText={(item) => item}
        />
        <ChipRow
          label="Year"
          options={options.years || []}
          value={filters.year}
          onChange={(year) => setFilters((current) => ({ ...current, year }))}
          getKey={(item) => item}
          getText={(item) => item}
        />
        <ChipRow
          label="Month"
          options={options.months || []}
          value={filters.month}
          onChange={(month) => setFilters((current) => ({ ...current, month }))}
          getKey={(item) => item}
          getText={(item) => item}
        />
        <ChipRow
          label="Job branch"
          options={options.branches || []}
          value={filters.branch}
          onChange={(branch) => setFilters((current) => ({ ...current, branch }))}
          getKey={(item) => item}
          getText={(item) => item}
        />
        <ChipRow
          label="Country"
          options={options.countries || []}
          value={filters.country}
          onChange={(country) => setFilters((current) => ({ ...current, country }))}
          getKey={(item) => item.code}
          getText={(item) => item.name ? `${item.name} (${item.code})` : item.code}
        />
        <ChipRow
          label="Bosch"
          options={[
            { code: "yes", name: "Yes" },
            { code: "no", name: "No" },
          ]}
          value={filters.bosch}
          onChange={(bosch) => setFilters((current) => ({ ...current, bosch }))}
          getKey={(item) => item.code}
          getText={(item) => item.name}
        />
      </div>

      {loading && !summary ? (
        <p className="lcl-empty">Loading LCL summary…</p>
      ) : empty ? (
        <p className="lcl-empty">Import the Desktop LCL workbook to populate this dashboard.</p>
      ) : (
        <div className="dash-layout lcl-body">
          <div className="lcl-overview">
            <div className="dash-kpis lcl-kpis">
              <article className="dash-kpi">
                <span>Shipments</span>
                <strong className="dash-kpi-count">{formatNumber(kpis?.shipments)}</strong>
                <em>{formatNumber(kpis?.shipmentIds)} distinct IDs</em>
              </article>
            </div>
            <section className="card">
              <div className="summary">
                <div>
                  <strong>By month</strong>
                  <p className="dash-section-note">Shipment counts with yearly average</p>
                </div>
              </div>
              <div className="dash-chart-body dash-chart-hours">
                <MonthChart items={summary?.byMonth || []} />
              </div>
            </section>
            <section className="card">
              <div className="summary">
                <div>
                  <strong>Average trend</strong>
                  <p className="dash-section-note">By year by month</p>
                </div>
              </div>
              <div className="dash-chart-body">
                <YearMonthTrend data={summary?.byYearMonth} />
              </div>
            </section>
          </div>

          <section className="card lcl-customers">
            <div className="summary">
              <div>
                <strong>Top customers</strong>
                <p className="dash-section-note">Shipment Controlling Party</p>
              </div>
              <span className="dash-count-chip">{summary?.byCustomer?.length || 0}</span>
            </div>
            <div className="dash-chart-body">
              <BarList items={summary?.byCustomer || []} />
            </div>
          </section>

          <section className="card lcl-globe-card">
            <div className="summary">
              <div>
                <strong>Destination map</strong>
                <p className="dash-section-note">
                  Bubble size is shipment volume by dest country.
                  {filtersActive ? " Arrows show export out and import in for the current filters." : " Apply a filter to show direction arrows."}
                  {filters.country.length ? ` Filtered to ${filters.country.join(", ")}.` : ""}
                </p>
              </div>
              <span className="dash-count-chip">{mapPoints.length} countries</span>
            </div>
            <LclMap
              points={mapPoints}
              arrows={mapArrows}
              selected={filters.country}
              showArrows={filtersActive}
              onSelect={(country) =>
                setFilters((current) => {
                  const selected = current.country.includes(country)
                    ? current.country.filter((item) => item !== country)
                    : [...current.country, country];
                  return { ...current, country: selected };
                })
              }
            />
          </section>
        </div>
      )}
    </div>
  );
});

export default LclDashboard;
