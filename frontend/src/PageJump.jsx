import { useEffect, useState } from "react";

export default function PageJump({ page, totalPages, onChange, ariaLabel = "Page" }) {
  const safeTotal = Math.max(Number(totalPages) || 1, 1);
  const safePage = Math.min(Math.max(Number(page) || 1, 1), safeTotal);
  const [draft, setDraft] = useState(String(safePage));

  useEffect(() => {
    setDraft(String(safePage));
  }, [safePage]);

  const commit = () => {
    const parsed = Number.parseInt(String(draft).trim(), 10);
    const next = Number.isFinite(parsed) ? Math.min(Math.max(parsed, 1), safeTotal) : safePage;
    setDraft(String(next));
    if (next !== safePage) {
      onChange(next);
    }
  };

  return (
    <label className="pagination-select">
      Page
      <input
        type="number"
        inputMode="numeric"
        min={1}
        max={safeTotal}
        value={draft}
        disabled={safeTotal <= 1}
        aria-label={ariaLabel}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            commit();
          }
        }}
      />
      of {safeTotal}
    </label>
  );
}
