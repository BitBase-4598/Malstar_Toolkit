import { FileText, FolderOpen, ClipboardList, ScrollText } from "lucide-react";

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

function MaerskStar() {
  return (
    <svg className="star" viewBox="0 0 32 32" aria-hidden="true">
      <polygon fill="currentColor" points={starPoints(16, 16, 7, 14, 6)} />
    </svg>
  );
}

const NAV_ITEMS = [
  { id: "records", label: "Auto Rating Search", icon: FileText },
  { id: "files", label: "Files", icon: FolderOpen },
  { id: "sops", label: "SOPs", icon: ClipboardList },
  { id: "logs", label: "Activity log", icon: ScrollText },
];

export default function Sidebar({ section, onSectionChange }) {
  return (
    <aside className="sidebar">
      <button
        type="button"
        className="sidebar-brand"
        onClick={() => onSectionChange("records")}
        aria-label="Back to Auto Rating Search"
      >
        <div className="brand">
          <MaerskStar />
          <p className="brand-kicker">MALSTAR</p>
        </div>
        <h1>MALSTAR_Toolkit</h1>
      </button>
      <nav className="sidebar-nav" aria-label="Main">
        <p className="sidebar-nav-label">Tools</p>
        {NAV_ITEMS.map((item) => {
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
