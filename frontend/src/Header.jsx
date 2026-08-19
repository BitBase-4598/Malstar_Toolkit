import { Plus, Upload } from "lucide-react";

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

export default function Header({ fileRef, importing, onImportClick, onImportChange, onAdd }) {
  return (
    <header className="topbar">
      <div className="brand">
        <MaerskStar />
        <div className="brand-copy">
          <p className="brand-kicker">MALSTAR</p>
          <h1>MALSTAR_Toolkit</h1>
        </div>
      </div>
      <div className="topbar-actions">
        <input
          ref={fileRef}
          hidden
          type="file"
          accept=".csv,text/csv"
          onChange={onImportChange}
        />
        <button className="secondary" type="button" onClick={onImportClick} disabled={importing}>
          <Upload size={16} />
          {importing ? "Importing..." : "Import CSV"}
        </button>
        <button className="primary" type="button" onClick={onAdd}>
          <Plus size={16} />
          Add record
        </button>
      </div>
    </header>
  );
}
