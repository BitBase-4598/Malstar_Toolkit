import { useEffect, useMemo, useRef, useState } from "react";
import { WORLD_COUNTRIES, WORLD_HEIGHT, WORLD_WIDTH } from "./worldCountries";

const LAND = "#1b455c";
const BORDER = "#00243d";
const HEAT_STOPS = ["#1b455c", "#245870", "#2f7a9a", "#42b0d5", "#8ad4ea", "#e8f6fb"];

const ARROW_COLOR = {
  export: "#42b0d5",
  import: "#e8f6fb",
  cross: "#77c6e0",
};

function project(lat, lng) {
  return {
    x: ((lng + 180) / 360) * WORLD_WIDTH,
    y: ((90 - lat) / 150) * WORLD_HEIGHT,
  };
}

function parseHex(hex) {
  const n = hex.replace("#", "");
  return [parseInt(n.slice(0, 2), 16), parseInt(n.slice(2, 4), 16), parseInt(n.slice(4, 6), 16)];
}

function mixHex(from, to, t) {
  const a = parseHex(from);
  const b = parseHex(to);
  const mix = a.map((channel, i) => Math.round(channel + (b[i] - channel) * t));
  return `#${mix.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

function heatT(count, max) {
  if (!count || max <= 0) {
    return 0;
  }
  return Math.sqrt(count / max);
}

function heatFill(count, max) {
  const t = heatT(count, max);
  if (t <= 0) {
    return LAND;
  }
  const scaled = t * (HEAT_STOPS.length - 1);
  const index = Math.min(Math.floor(scaled), HEAT_STOPS.length - 2);
  return mixHex(HEAT_STOPS[index], HEAT_STOPS[index + 1], scaled - index);
}

function curveControl(from, to) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.hypot(dx, dy) || 1;
  const bulge = Math.min(48, len * 0.18);
  return {
    x: (from.x + to.x) / 2 - (dy / len) * bulge,
    y: (from.y + to.y) / 2 + (dx / len) * bulge,
  };
}

function curvePath(from, to) {
  const mid = curveControl(from, to);
  return `M ${from.x} ${from.y} Q ${mid.x} ${mid.y} ${to.x} ${to.y}`;
}

const ASPECT = WORLD_WIDTH / WORLD_HEIGHT;
const WORLD_VIEW = { x: 0, y: 0, w: WORLD_WIDTH, h: WORLD_HEIGHT };

function expand(box, x, y) {
  box.minX = Math.min(box.minX, x);
  box.minY = Math.min(box.minY, y);
  box.maxX = Math.max(box.maxX, x);
  box.maxY = Math.max(box.maxY, y);
}

function fitDataView(points, arrows, zoomToData) {
  if (!zoomToData) {
    return WORLD_VIEW;
  }
  const box = { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity };
  const padPt = 22;
  for (const item of points || []) {
    const { x, y } = project(item.lat, item.lng);
    expand(box, x - padPt, y - padPt);
    expand(box, x + padPt, y + padPt);
  }
  for (const arrow of arrows || []) {
    const from = project(arrow.fromLat, arrow.fromLng);
    const to = project(arrow.toLat, arrow.toLng);
    const mid = curveControl(from, to);
    expand(box, from.x, from.y);
    expand(box, to.x, to.y);
    expand(box, mid.x, mid.y);
  }
  if (!Number.isFinite(box.minX)) {
    return WORLD_VIEW;
  }
  const pad = 40;
  const minX = box.minX - pad;
  const minY = box.minY - pad;
  const maxX = box.maxX + pad;
  const maxY = box.maxY + pad;
  let w = Math.max(maxX - minX, 220);
  let h = Math.max(maxY - minY, 220 / ASPECT);
  if (w / h > ASPECT) {
    h = w / ASPECT;
  } else {
    w = h * ASPECT;
  }
  w = Math.min(w, WORLD_WIDTH);
  h = Math.min(h, WORLD_HEIGHT);
  if (w > WORLD_WIDTH * 0.92) {
    return WORLD_VIEW;
  }
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  let x = cx - w / 2;
  let y = cy - h / 2;
  x = Math.min(Math.max(x, 0), WORLD_WIDTH - w);
  y = Math.min(Math.max(y, 0), WORLD_HEIGHT - h);
  return { x, y, w, h };
}

function viewsClose(a, b) {
  return (
    Math.abs(a.x - b.x) < 0.3 &&
    Math.abs(a.y - b.y) < 0.3 &&
    Math.abs(a.w - b.w) < 0.3 &&
    Math.abs(a.h - b.h) < 0.3
  );
}

function useAnimatedViewBox(target, duration = 620) {
  const [view, setView] = useState(WORLD_VIEW);
  const currentRef = useRef(WORLD_VIEW);
  const frameRef = useRef(0);

  useEffect(() => {
    const from = currentRef.current;
    if (viewsClose(from, target)) {
      currentRef.current = target;
      setView(target);
      return undefined;
    }
    cancelAnimationFrame(frameRef.current);
    const started = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - started) / duration);
      const ease = 1 - (1 - t) ** 3;
      const next = {
        x: from.x + (target.x - from.x) * ease,
        y: from.y + (target.y - from.y) * ease,
        w: from.w + (target.w - from.w) * ease,
        h: from.h + (target.h - from.h) * ease,
      };
      currentRef.current = next;
      setView(next);
      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        currentRef.current = target;
        setView(target);
      }
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, duration]);

  return view;
}

function selectedSet(selected) {
  if (Array.isArray(selected)) {
    return new Set(selected);
  }
  return new Set(selected ? [selected] : []);
}

export default function LclMap({ points, arrows, selected, onSelect, showArrows, zoomToData }) {
  const [tooltip, setTooltip] = useState(null);
  const [hoverIso, setHoverIso] = useState("");
  const active = selectedSet(selected);
  const byIso = useMemo(
    () => Object.fromEntries((points || []).map((item) => [item.iso2, item])),
    [points]
  );
  const max = Math.max(...(points || []).map((item) => item.count), 1);
  const arrowMax = Math.max(...(arrows || []).map((item) => item.count), 1);
  const visibleArrows = useMemo(
    () => (showArrows ? arrows || [] : []),
    [showArrows, arrows]
  );
  const targetView = useMemo(
    () => fitDataView(points, visibleArrows, zoomToData),
    [points, visibleArrows, zoomToData]
  );
  const view = useAnimatedViewBox(targetView);

  const showTip = (event, item, iso2, extra) => {
    if (!item && !iso2) {
      setHoverIso("");
      setTooltip(null);
      return;
    }
    const pad = 16;
    const tipWidth = 240;
    const tipHeight = 72;
    setHoverIso(iso2 || item.iso2);
    setTooltip({
      country: item?.country || extra?.country || iso2,
      iso2: iso2 || item.iso2,
      count: extra?.count || item?.count || 0,
      direction: extra?.direction || "",
      x: Math.min(Math.max(event.clientX + 12, pad), window.innerWidth - tipWidth - pad),
      y: Math.min(Math.max(event.clientY + 12, pad), window.innerHeight - tipHeight - pad),
    });
  };

  const activate = (iso2) => {
    onSelect?.(iso2);
  };

  return (
    <div className="lcl-map">
      <svg
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Destination world heatmap of shipment volume by country"
        onMouseLeave={() => {
          setHoverIso("");
          setTooltip(null);
        }}
      >
        <defs>
          {Object.entries(ARROW_COLOR).map(([kind, color]) => (
            <marker
              key={kind}
              id={`lcl-arrow-${kind}`}
              markerWidth="8"
              markerHeight="8"
              refX="6"
              refY="4"
              orient="auto"
              markerUnits="strokeWidth"
            >
              <path d="M0 0 L8 4 L0 8 Z" fill={color} />
            </marker>
          ))}
        </defs>
        <rect width={WORLD_WIDTH} height={WORLD_HEIGHT} fill="#00243d" />
        {WORLD_COUNTRIES.map((country) => {
          const item = byIso[country.iso2];
          const isActive = active.has(country.iso2) || country.iso2 === hoverIso;
          const fill = heatFill(item?.count || 0, max);
          return (
            <path
              key={country.iso2}
              d={country.d}
              fill={isActive ? mixHex(fill, "#ffffff", item?.count ? 0.18 : 0.12) : fill}
              stroke={isActive ? "#e8f6fb" : BORDER}
              strokeWidth={isActive ? 1.4 : 0.55}
              vectorEffect="non-scaling-stroke"
              style={{ cursor: "pointer" }}
              onMouseMove={(event) => showTip(event, item, country.iso2)}
              onClick={() => activate(country.iso2)}
            />
          );
        })}
        {visibleArrows.map((arrow, index) => {
          const from = project(arrow.fromLat, arrow.fromLng);
          const to = project(arrow.toLat, arrow.toLng);
          const kind = arrow.kind || "export";
          const width = 1 + Math.sqrt(arrow.count / arrowMax) * 3.2;
          return (
            <path
              key={`${arrow.kind}-${arrow.iso2}-${index}`}
              d={curvePath(from, to)}
              fill="none"
              stroke={ARROW_COLOR[kind] || ARROW_COLOR.export}
              strokeWidth={width}
              strokeLinecap="round"
              strokeDasharray={kind === "cross" ? "6 4" : undefined}
              markerEnd={`url(#lcl-arrow-${kind})`}
              opacity="0.9"
              style={{ pointerEvents: "stroke", cursor: "pointer" }}
              onMouseMove={(event) => showTip(event, byIso[arrow.iso2], arrow.iso2, arrow)}
              onClick={() => activate(arrow.iso2)}
            />
          );
        })}
      </svg>
      <div className="lcl-map-legend">
        <span className="lcl-map-heat-key">
          Low
          <i className="lcl-map-heat-bar" aria-hidden="true" />
          High
        </span>
        {showArrows ? (
          <>
            <span className="lcl-map-arrow export">Export</span>
            <span className="lcl-map-arrow import">Import</span>
            <span className="lcl-map-arrow cross">Cross trade</span>
          </>
        ) : null}
      </div>
      {tooltip ? (
        <div className="lcl-globe-tip" style={{ left: tooltip.x, top: tooltip.y }}>
          <strong>
            {tooltip.country} · {tooltip.iso2}
          </strong>
          <span>
            {tooltip.count.toLocaleString()} shipments
            {tooltip.direction ? ` · ${tooltip.direction}` : ""}
          </span>
        </div>
      ) : null}
    </div>
  );
}
