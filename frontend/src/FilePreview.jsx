import { useEffect, useState } from "react";

function previewSrc(url) {
  if (!url) {
    return "";
  }
  if (/^https?:\/\//i.test(url)) {
    return url;
  }
  const base = (import.meta.env.BASE_URL || "/").replace(/\/$/, "");
  return `${base}${url.startsWith("/") ? url : `/${url}`}`;
}

export default function FilePreview({ preview, loading }) {
  const [sheet, setSheet] = useState(0);
  const [imageOpen, setImageOpen] = useState(false);

  useEffect(() => {
    setImageOpen(false);
  }, [preview?.url, preview?.file?.id]);

  useEffect(() => {
    if (!imageOpen) {
      return undefined;
    }
    const onKey = (event) => {
      if (event.key === "Escape") {
        setImageOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [imageOpen]);

  if (loading) {
    return <p className="preview-empty">Loading preview...</p>;
  }
  if (!preview) {
    return <p className="preview-empty">Select a file to preview.</p>;
  }
  if (preview.kind === "image") {
    const name = preview.file?.originalName || "Picture";
    const src = previewSrc(preview.url);
    return (
      <>
        <button
          type="button"
          className="preview-image-wrap"
          onClick={() => setImageOpen(true)}
          title="Click to enlarge"
        >
          <img className="preview-image" src={src} alt={name} />
        </button>
        {imageOpen ? (
          <div
            className="overlay preview-image-overlay"
            role="presentation"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                setImageOpen(false);
              }
            }}
          >
            <img
              className="preview-image-large"
              src={src}
              alt={name}
              onClick={() => setImageOpen(false)}
            />
          </div>
        ) : null}
      </>
    );
  }
  if (preview.kind === "docx") {
    return (
      <div className="preview-html" dangerouslySetInnerHTML={{ __html: preview.html || "<p>No preview text.</p>" }} />
    );
  }
  if (preview.kind === "xlsx") {
    const sheets = preview.sheets || [];
    const current = sheets[sheet] || sheets[0];
    if (!current) {
      return <p className="preview-empty">This workbook has no sheets.</p>;
    }
    return (
      <div className="excel-preview">
        <div className="sheet-tabs">
          {sheets.map((item, index) => (
            <button
              key={item.name}
              type="button"
              className={index === sheet ? "active" : ""}
              onClick={() => setSheet(index)}
            >
              {item.name}
            </button>
          ))}
        </div>
        <div className="table-wrap preview-sheet">
          <table>
            <tbody>
              {(current.rows || []).length === 0 ? (
                <tr>
                  <td className="empty">This sheet is empty.</td>
                </tr>
              ) : (
                current.rows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex}>{cell || ""}</td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {current.truncated ? <p className="search-hint">Preview shows the first 200 rows.</p> : null}
      </div>
    );
  }
  return <p className="preview-empty">Preview is not available for this file type.</p>;
}
