import { TOOLS } from "./tools";

const FAVICON_SRC = `${(import.meta.env.BASE_URL || "/").replace(/\/$/, "")}/favicon.png`;

function MaerskStar() {
  return <img className="star" src={FAVICON_SRC} alt="" width={32} height={32} />;
}

export default function Sidebar({ section, onSectionChange }) {
  return (
    <aside className="sidebar">
      <button
        type="button"
        className="sidebar-brand"
        onClick={() => onSectionChange("leave")}
        aria-label="Back to Leave Forecast"
      >
        <div className="brand">
          <MaerskStar />
          <p className="brand-kicker">MALSTAR</p>
        </div>
        <h1>MALSTAR_Toolkit</h1>
      </button>
      <nav className="sidebar-nav" aria-label="Main">
        <p className="sidebar-nav-label">Tools</p>
        {TOOLS.map((item) => {
          const Icon = item.icon;
          const active = section === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className={active ? "nav-item active" : "nav-item"}
              onClick={() => onSectionChange(item.id)}
              aria-current={active ? "page" : undefined}
            >
              <Icon size={18} />
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
