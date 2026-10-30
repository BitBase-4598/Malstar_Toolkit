import { useState } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { TOOLS } from "./tools";

const FAVICON_SRC = `${(import.meta.env.BASE_URL || "/").replace(/\/$/, "")}/favicon.png`;
const STORAGE_KEY = "malstar-sidebar-collapsed";

function readCollapsed() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function MaerskStar() {
  return <img className="star" src={FAVICON_SRC} alt="" width={32} height={32} />;
}

export default function Sidebar({ section, onSectionChange }) {
  const [collapsed, setCollapsed] = useState(readCollapsed);

  const toggle = () => {
    setCollapsed((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* keep the in-memory choice when storage is blocked */
      }
      return next;
    });
  };

  return (
    <aside className={collapsed ? "sidebar is-collapsed" : "sidebar"}>
      <button
        type="button"
        className="sidebar-brand"
        onClick={() => onSectionChange("leave")}
        aria-label="Back to Leave Forecast"
        title={collapsed ? "Leave Forecast" : undefined}
      >
        <div className="brand">
          <MaerskStar />
          <p className="brand-kicker">MALSTAR</p>
        </div>
        <h1>MALSTAR_Toolkit</h1>
      </button>
      <nav className="sidebar-nav" aria-label="Main">
        <p className="sidebar-nav-label">Tools</p>
        {TOOLS.filter((item) => !item.hidden).map((item) => {
          const Icon = item.icon;
          const active = section === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className={active ? "nav-item active" : "nav-item"}
              onMouseEnter={() => item.Workspace?.preload?.()}
              onClick={() => onSectionChange(item.id)}
              aria-label={item.label}
              aria-current={active ? "page" : undefined}
              title={collapsed ? item.label : undefined}
            >
              <Icon size={18} />
              <span className="nav-item-label">{item.label}</span>
            </button>
          );
        })}
      </nav>
      <button
        type="button"
        className="sidebar-toggle"
        onClick={toggle}
        aria-expanded={!collapsed}
        aria-label={collapsed ? "Show sidebar" : "Hide sidebar"}
        title={collapsed ? "Show sidebar" : "Hide sidebar"}
      >
        {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        <span className="nav-item-label">{collapsed ? "Show" : "Hide"}</span>
      </button>
    </aside>
  );
}
