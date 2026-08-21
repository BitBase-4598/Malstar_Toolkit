import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Pencil, Save, Trash2, X } from "lucide-react";
import { api } from "./api";
import { holidayInfo, isOffDay } from "./chinaHolidays";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const LEAVE_TYPES = [
  { value: "annual", label: "Annual" },
  { value: "sick", label: "Sick" },
  { value: "wfh", label: "WFH" },
  { value: "other", label: "Other" },
];
const STATUSES = [
  { value: "planned", label: "Planned" },
  { value: "confirmed", label: "Confirmed" },
];
const emptyForm = {
  person: "",
  leaveType: "annual",
  status: "planned",
};

function pad(value) {
  return String(value).padStart(2, "0");
}

function toIso(year, monthIndex, day) {
  return `${year}-${pad(monthIndex + 1)}-${pad(day)}`;
}

function todayIso() {
  const now = new Date();
  return toIso(now.getFullYear(), now.getMonth(), now.getDate());
}

function formatDayLabel(iso) {
  const date = new Date(`${iso}T00:00:00`);
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function monthTitle(year, monthIndex) {
  return new Date(year, monthIndex, 1).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

function monthCells(year, monthIndex) {
  const weekday = (new Date(year, monthIndex, 1).getDay() + 6) % 7;
  const days = new Date(year, monthIndex + 1, 0).getDate();
  const cells = Array.from({ length: weekday }, () => null);
  for (let day = 1; day <= days; day += 1) {
    cells.push(day);
  }
  while (cells.length % 7 !== 0) {
    cells.push(null);
  }
  return cells;
}

function typeLabel(value) {
  return LEAVE_TYPES.find((item) => item.value === value)?.label || value;
}

export default function LeaveForecast({ onNotice, onRefreshLogs }) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [selected, setSelected] = useState(todayIso());
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const splitRef = useRef(null);
  const calendarWidthRef = useRef(640);
  const draggingRef = useRef(false);
  const [dragging, setDragging] = useState(false);
  const [calendarWidth, setCalendarWidth] = useState(() => {
    const saved = Number(window.localStorage.getItem("malstar-leave-calendar-width"));
    return saved >= 360 ? saved : 640;
  });

  calendarWidthRef.current = calendarWidth;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.listLeavePlans(year, month + 1);
      setPlans(result.data || []);
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }, [year, month, onNotice]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setSelected((current) => {
      const [currentYear, currentMonth] = current.split("-").map(Number);
      if (currentYear === year && currentMonth === month + 1) {
        return current;
      }
      const today = new Date();
      if (today.getFullYear() === year && today.getMonth() === month) {
        return todayIso();
      }
      return toIso(year, month, 1);
    });
    setEditing(null);
    setForm(emptyForm);
  }, [year, month]);

  const counts = useMemo(() => {
    const map = {};
    plans.forEach((plan) => {
      map[plan.leaveDate] = (map[plan.leaveDate] || 0) + 1;
    });
    return map;
  }, [plans]);

  const dayPlans = plans.filter((plan) => plan.leaveDate === selected);
  const cells = monthCells(year, month);
  const today = todayIso();

  const shiftMonth = (delta) => {
    const next = new Date(year, month + delta, 1);
    setYear(next.getFullYear());
    setMonth(next.getMonth());
  };

  const update = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
  };

  const startEdit = (plan) => {
    setEditing(plan);
    setForm({
      person: plan.person,
      leaveType: plan.leaveType,
      status: plan.status,
    });
  };

  const cancelEdit = () => {
    setEditing(null);
    setForm(emptyForm);
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = { ...form, leaveDate: selected };
      const result = editing
        ? await api.updateLeavePlan(editing.id, payload)
        : await api.createLeavePlan(payload);
      onNotice?.({ type: "success", text: result.message });
      cancelEdit();
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    } finally {
      setSaving(false);
    }
  };

  const remove = async (plan) => {
    if (!window.confirm(`Delete ${plan.person}'s leave on ${plan.leaveDate}?`)) {
      return;
    }
    try {
      const result = await api.deleteLeavePlan(plan.id);
      onNotice?.({ type: "success", text: result.message });
      if (editing?.id === plan.id) {
        cancelEdit();
      }
      await load();
      await onRefreshLogs?.();
    } catch (error) {
      onNotice?.({ type: "error", text: error.message });
    }
  };

  const onSplitPointerDown = (event) => {
    event.preventDefault();
    draggingRef.current = true;
    setDragging(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onSplitPointerMove = (event) => {
    if (!draggingRef.current || !splitRef.current) {
      return;
    }
    const rect = splitRef.current.getBoundingClientRect();
    const max = Math.max(rect.width - 300, 360);
    const next = Math.min(Math.max(event.clientX - rect.left, 360), max);
    setCalendarWidth(next);
  };

  const stopSplitDrag = () => {
    if (!draggingRef.current) {
      return;
    }
    draggingRef.current = false;
    setDragging(false);
    window.localStorage.setItem("malstar-leave-calendar-width", String(calendarWidthRef.current));
  };

  return (
    <div
      ref={splitRef}
      className={`tool-split leave-split${dragging ? " is-resizing" : ""}`}
    >
      <section className="card leave-calendar-card" style={{ width: `${calendarWidth}px` }}>
        <div className="summary leave-month-bar">
          <button type="button" className="ghost" onClick={() => shiftMonth(-1)} aria-label="Previous month">
            <ChevronLeft size={18} />
          </button>
          <strong>{monthTitle(year, month)}</strong>
          <button type="button" className="ghost" onClick={() => shiftMonth(1)} aria-label="Next month">
            <ChevronRight size={18} />
          </button>
        </div>
        <div className="leave-calendar">
          {WEEKDAYS.map((day) => (
            <div key={day} className={`leave-weekday${day === "Sat" || day === "Sun" ? " weekend" : ""}`}>
              {day}
            </div>
          ))}
          {cells.map((day, index) => {
            if (!day) {
              return <div key={`empty-${index}`} className="leave-day empty" />;
            }
            const iso = toIso(year, month, day);
            const count = counts[iso] || 0;
            const holiday = holidayInfo(iso);
            const off = isOffDay(iso);
            const classes = [
              "leave-day",
              iso === selected ? "selected" : "",
              iso === today ? "today" : "",
              count ? "has-leave" : "",
              off ? "off" : "",
            ]
              .filter(Boolean)
              .join(" ");
            return (
              <button
                key={iso}
                type="button"
                className={classes}
                title={
                  holiday
                    ? `${holiday.nameZh} ${holiday.nameEn}`
                    : off
                      ? "Weekend"
                      : undefined
                }
                onClick={() => {
                  setSelected(iso);
                  cancelEdit();
                }}
              >
                <span>{day}</span>
                {holiday ? <small className="leave-holiday-name">{holiday.shortLabel}</small> : null}
                {count ? <em>{count}</em> : null}
              </button>
            );
          })}
        </div>
      </section>
      <div
        className="split-handle"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize calendar"
        onPointerDown={onSplitPointerDown}
        onPointerMove={onSplitPointerMove}
        onPointerUp={stopSplitDrag}
        onPointerCancel={stopSplitDrag}
      />
      <section className="card leave-day-card">
        <div className="summary">
          <span>
            <strong>{formatDayLabel(selected)}</strong>
            {holidayInfo(selected) ? (
              <span className="status-pill">{holidayInfo(selected).nameZh} {holidayInfo(selected).nameEn}</span>
            ) : null}
            {loading ? <span className="status-pill">Loading</span> : null}
          </span>
        </div>
        <div className="leave-day-body">
          {dayPlans.length === 0 ? (
            <p className="preview-empty">No leave plans for this day yet.</p>
          ) : (
            <ul className="leave-plan-list">
              {dayPlans.map((plan) => (
                <li key={plan.id} className={editing?.id === plan.id ? "active" : ""}>
                  <div>
                    <strong>{plan.person}</strong>
                    <span className={`status-pill ${plan.leaveType}`}>{typeLabel(plan.leaveType)}</span>
                    <span className={`status-pill ${plan.status}`}>{plan.status}</span>
                  </div>
                  <div className="actions">
                    <button type="button" onClick={() => startEdit(plan)} aria-label={`Edit ${plan.person}`}>
                      <Pencil size={16} />
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => remove(plan)}
                      aria-label={`Delete ${plan.person}`}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <form className="leave-form" onSubmit={save}>
            <h3>{editing ? "Edit leave plan" : "Add leave plan"}</h3>
            <label>
              Person *
              <input
                required
                value={form.person}
                onChange={update("person")}
                disabled={saving}
                placeholder="Name"
              />
            </label>
            <div className="leave-form-row">
              <label>
                Leave type
                <select value={form.leaveType} onChange={update("leaveType")} disabled={saving}>
                  {LEAVE_TYPES.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Status
                <select value={form.status} onChange={update("status")} disabled={saving}>
                  {STATUSES.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="leave-form-actions">
              {editing ? (
                <button type="button" className="ghost" onClick={cancelEdit} disabled={saving}>
                  <X size={16} />
                  Cancel
                </button>
              ) : null}
              <button type="submit" className="primary" disabled={saving}>
                <Save size={16} />
                {saving ? "Saving..." : editing ? "Save plan" : "Add plan"}
              </button>
            </div>
          </form>
        </div>
      </section>
    </div>
  );
}
