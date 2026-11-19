import { useEffect, useState } from "react";
import { ChevronDown, X } from "lucide-react";
import { api } from "./api";
import { copyText } from "./copyText";

const KEYS = [
  { id: "shipper", placeholder: "Shipper", label: "Shipper" },
  { id: "consignee", placeholder: "Consignee", label: "Consignee" },
  { id: "shipperName", placeholder: "Full name", label: "Shipper full name" },
  { id: "consigneeName", placeholder: "Full name", label: "Consignee full name" },
  { id: "origin", placeholder: "Origin", label: "Origin" },
  { id: "dest", placeholder: "Dest", label: "Dest" },
];

const SECTIONS = [
  {
    id: "shipper",
    title: "Shipper",
    cells: [
      { key: "shipperName", label: "Full name", typed: "shipperName", wide: true },
      { key: "shipper", label: "Code", typed: "shipper" },
      { key: "shipperAddress", label: "Address", wide: true },
    ],
  },
  {
    id: "consignee",
    title: "Consignee",
    cells: [
      { key: "consigneeName", label: "Full name", typed: "consigneeName", wide: true },
      { key: "consignee", label: "Code", typed: "consignee" },
      { key: "consigneeAddress", label: "Address", wide: true },
    ],
  },
  {
    id: "location",
    title: "Location",
    cells: [
      { key: "origin", label: "Place of Receipt", typed: "origin" },
      { key: "plannedDischarge", label: "Port of Discharge" },
      { key: "dest", label: "Place of Delivery", typed: "dest" },
    ],
  },
  {
    id: "partners",
    title: "Partners",
    cells: [
      { key: "controllingCustomer", label: "Controlling Customer" },
      { key: "controllingAgent", label: "Controlling Agent" },
      { key: "pickupAgent", label: "Pickup Agent" },
      { key: "deliveryAgent", label: "Delivery Agent" },
    ],
  },
  {
    id: "details",
    title: "Details",
    cells: [
      { key: "pickupCfs", label: "Pickup CFS" },
      { key: "incoterm", label: "Incoterm" },
      { key: "svcLevel", label: "Svc. lvl." },
      { key: "hblMode", label: "HBL Dlv. Mode" },
      { key: "stackability", label: "Stackability" },
      { key: "businessUnit", label: "Business Unit" },
    ],
  },
];

const emptyFilters = {
  shipper: "",
  consignee: "",
  shipperName: "",
  consigneeName: "",
  origin: "",
  dest: "",
};

function badgeClass(label) {
  if (label === "高") {
    return "is-high";
  }
  if (label === "中高") {
    return "is-mid";
  }
  return "is-low";
}

function statFor(fields, key, value) {
  if (!value) {
    return null;
  }
  return (fields?.[key] || []).find((item) => item.value === value) || null;
}

export default function TwPrefillPanel({ onNotice, onCopyError, reloadToken = 0 }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [filters, setFilters] = useState(emptyFilters);
  const [debounced, setDebounced] = useState(emptyFilters);
  const [result, setResult] = useState(null);
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(filters), 120);
    return () => clearTimeout(timer);
  }, [filters]);

  useEffect(() => {
    const active = Object.values(debounced).some((value) => String(value || "").trim());
    if (!active) {
      setResult(null);
      setSelected(0);
      return undefined;
    }
    const controller = new AbortController();
    api
      .suggestTwPrefill(debounced, { signal: controller.signal })
      .then((payload) => {
        setResult(payload);
        setSelected(0);
      })
      .catch((error) => {
        if (error.name === "AbortError") {
          return;
        }
        onNotice?.({ type: "error", text: error.message });
      });
    return () => controller.abort();
  }, [debounced, reloadToken, onNotice]);

  const combos = result?.combos || [];
  const combo = combos[selected] || null;

  const copyValue = async (value) => {
    if (!value) {
      return;
    }
    try {
      await copyText(value);
      onNotice?.({ type: "success", text: `Copied: ${value}`, placement: "top" });
    } catch (error) {
      onCopyError?.(error.message);
    }
  };

  const shown = (key) => combo?.[key] ?? "";
  const filled = Object.values(filters).some((value) => String(value || "").trim());
  const reset = () => {
    setFilters(emptyFilters);
    setDebounced(emptyFilters);
    setResult(null);
    setSelected(0);
  };

  return (
    <div className="prefill">
      <section className="prefill-section prefill-query">
        <div className="prefill-keys">
          {KEYS.map((field) => (
            <div className="prefill-key" key={field.id}>
              <input
                aria-label={field.label}
                placeholder={field.placeholder}
                value={filters[field.id]}
                onChange={(event) => setFilters((current) => ({ ...current, [field.id]: event.target.value }))}
              />
              {filters[field.id] ? (
                <button
                  type="button"
                  aria-label={`Clear ${field.label}`}
                  onClick={() => setFilters((current) => ({ ...current, [field.id]: "" }))}
                >
                  <X size={14} />
                </button>
              ) : null}
            </div>
          ))}
        </div>
        <button type="button" className={filled ? "primary prefill-reset" : "ghost prefill-reset"} onClick={reset} disabled={!filled}>
          Reset
        </button>
        {combos.length ? (
          <div className="filter-chips prefill-combos" role="listbox" aria-label="Combinations">
            {combos.map((item, index) => (
              <button
                key={`${item.shipper}|${item.consignee}|${item.origin}|${item.dest}|${item.pickupCfs}|${index}`}
                type="button"
                role="option"
                aria-selected={index === selected}
                className={index === selected ? "active" : ""}
                onClick={() => {
                setSelected(index);
                }}
              >
                <span>{item.shipper || item.origin}</span>
                <span>{item.consignee || item.dest}</span>
                <span>{item.count}</span>
                {item.confidence ? (
                  <span className={`status-pill prefill-badge ${badgeClass(item.confidence)}`}>{item.confidence}</span>
                ) : null}
              </button>
            ))}
          </div>
        ) : null}
      </section>
      <div className="prefill-board">
      {SECTIONS.map((section) => {
        const collapsed = section.id === "details" && !detailsOpen;
        return (
        <section className={`prefill-section is-${section.id}${collapsed ? " is-collapsed" : ""}`} key={section.id}>
          {section.id === "details" ? (
            <button
              type="button"
              className="prefill-disclosure"
              aria-expanded={detailsOpen}
              onClick={() => setDetailsOpen((open) => !open)}
            >
              <span>{section.title}</span>
              <ChevronDown size={16} className={detailsOpen ? "is-open" : ""} />
            </button>
          ) : (
            <h2>{section.title}</h2>
          )}
          {collapsed ? null : (
          <div className="prefill-grid">
            {section.cells.map((cell) => {
              const value = shown(cell.key);
              const suggested = Boolean(value) && !(cell.typed && String(filters[cell.typed] || "").trim());
              const stat = suggested ? statFor(result?.fields, cell.key, value) : null;
              return (
                <div
                  key={cell.key}
                  className={`prefill-cell${cell.wide ? " is-wide" : ""}${suggested ? " is-suggested" : ""}`}
                >
                  <span className="prefill-label">{cell.label}</span>
                  {value ? (
                    <button type="button" className="prefill-value" onClick={() => copyValue(value)}>
                      {value}
                    </button>
                  ) : (
                    <span className="prefill-value" />
                  )}
                  {stat?.confidence ? (
                    <span className="prefill-meta">
                      <span className={`status-pill prefill-badge ${badgeClass(stat.confidence)}`}>{stat.confidence}</span>
                      <span>{stat.count}</span>
                    </span>
                  ) : null}
                </div>
              );
            })}
          </div>
          )}
        </section>
        );
      })}
      </div>
    </div>
  );
}
