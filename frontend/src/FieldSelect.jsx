import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown } from "lucide-react";

function optionValue(option) {
  return String(option?.value ?? "");
}

function selectedSetFrom(value, multiple) {
  if (multiple) {
    const list = Array.isArray(value) ? value : value ? [value] : [];
    return new Set(list.map(String).filter(Boolean));
  }
  return new Set([String(value ?? "")]);
}

function triggerLabel(options, selected, multiple, placeholder) {
  if (!multiple) {
    const current = [...selected][0] ?? "";
    return options.find((option) => optionValue(option) === current)?.label || placeholder;
  }
  if (selected.size === 0) {
    return placeholder;
  }
  const labels = options
    .filter((option) => {
      const key = optionValue(option);
      return key && selected.has(key);
    })
    .map((option) => option.label);
  if (labels.length === 1) {
    return labels[0];
  }
  const joined = labels.join(", ");
  return joined.length <= 36 ? joined : `${labels.length} selected`;
}

export default function FieldSelect({
  value,
  options = [],
  onChange,
  disabled = false,
  searchable = false,
  compact = false,
  multiple = false,
  required = false,
  placeholder = "Select",
  ariaLabel,
  className = "",
}) {
  const wrapRef = useRef(null);
  const menuRef = useRef(null);
  const searchRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const [menuStyle, setMenuStyle] = useState(null);
  const selected = useMemo(() => selectedSetFrom(value, multiple), [value, multiple]);
  const current = [...selected][0] ?? "";
  const label = triggerLabel(options, selected, multiple, placeholder);
  const matches = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!searchable || !text) {
      return options;
    }
    return options.filter((option) => String(option.label || "").toLowerCase().includes(text));
  }, [options, query, searchable]);
  const visible = matches.length > 80 ? matches.slice(0, 80) : matches;

  useEffect(() => {
    const onDoc = (event) => {
      if (wrapRef.current?.contains(event.target) || menuRef.current?.contains(event.target)) {
        return;
      }
      setOpen(false);
      setQuery("");
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    if (!open) {
      setMenuStyle(null);
      return undefined;
    }
    const place = () => {
      const rect = wrapRef.current?.getBoundingClientRect();
      if (!rect) {
        return;
      }
      const maxHeight = 260;
      const gap = 4;
      const spaceBelow = window.innerHeight - rect.bottom - gap;
      const openUp = spaceBelow < 160 && rect.top > spaceBelow;
      const width = Math.max(rect.width, compact ? 88 : rect.width);
      setMenuStyle({
        position: "fixed",
        left: Math.min(rect.left, window.innerWidth - width - 8),
        width,
        maxHeight,
        ...(openUp
          ? { bottom: window.innerHeight - rect.top + gap, top: "auto" }
          : { top: rect.bottom + gap, bottom: "auto" }),
      });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, compact, matches.length]);

  useEffect(() => {
    if (open && searchable && menuStyle) {
      searchRef.current?.focus();
    }
  }, [open, searchable, menuStyle]);

  useEffect(() => {
    setHighlight(0);
  }, [query, open]);

  const pick = (option) => {
    if (option?.disabled) {
      return;
    }
    const key = optionValue(option);
    if (multiple) {
      if (!key) {
        onChange?.([]);
        return;
      }
      const next = selected.has(key)
        ? [...selected].filter((item) => item !== key)
        : [...selected, key];
      onChange?.(next);
      return;
    }
    onChange?.(key);
    setOpen(false);
    setQuery("");
  };

  const onKeyDown = (event) => {
    if (disabled) {
      return;
    }
    if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp" || event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      setOpen(true);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((index) => Math.min(index + 1, Math.max(visible.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter" && open) {
      event.preventDefault();
      if (visible[highlight]) {
        pick(visible[highlight]);
      }
    } else if (event.key === " " && open && event.target !== searchRef.current) {
      event.preventDefault();
      if (visible[highlight]) {
        pick(visible[highlight]);
      }
    } else if (event.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  };

  return (
    <div
      className={`field-select${compact ? " is-compact" : ""}${className ? ` ${className}` : ""}`}
      ref={wrapRef}
    >
      {required ? (
        <input
          className="field-select-required"
          tabIndex={-1}
          required
          value={current}
          onChange={() => {}}
          aria-hidden="true"
        />
      ) : null}
      <button
        type="button"
        className={`field-select-trigger${open ? " is-open" : ""}`}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        title={label}
        onClick={() => {
          if (!disabled) {
            setOpen((currentOpen) => !currentOpen);
          }
        }}
        onKeyDown={onKeyDown}
      >
        <span>{label}</span>
        <ChevronDown size={compact ? 14 : 16} aria-hidden="true" />
      </button>
      {open && menuStyle
        ? createPortal(
            <div
              ref={menuRef}
              className={`field-select-menu${compact ? " is-compact" : ""}`}
              role="listbox"
              aria-multiselectable={multiple || undefined}
              style={menuStyle}
            >
              {searchable ? (
                <input
                  ref={searchRef}
                  className="field-select-search"
                  value={query}
                  placeholder="Type to filter"
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={onKeyDown}
                />
              ) : null}
              {matches.length === 0 ? (
                <p className="field-select-empty">No matching option</p>
              ) : (
                <>
                  {visible.map((option, index) => {
                  const key = optionValue(option);
                  const isAll = multiple && key === "";
                  const isSelected = isAll ? selected.size === 0 : selected.has(key) || (!multiple && key === current);
                  return (
                    <button
                      key={key || `empty-${index}`}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      className={`${multiple ? "is-multi " : ""}${isSelected ? "is-selected" : ""}${index === highlight ? " is-active" : ""}`}
                      disabled={option.disabled}
                      onMouseEnter={() => setHighlight(index)}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => pick(option)}
                    >
                      {multiple ? (
                        <span className={`field-select-check${isSelected ? " is-on" : ""}`} aria-hidden="true">
                          {isSelected ? <Check size={12} strokeWidth={3} /> : null}
                        </span>
                      ) : null}
                      {option.label}
                    </button>
                  );
                })}
                  {matches.length > visible.length ? (
                    <p className="field-select-empty">Showing {visible.length} of {matches.length}. Type to filter.</p>
                  ) : null}
                </>
              )}
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
