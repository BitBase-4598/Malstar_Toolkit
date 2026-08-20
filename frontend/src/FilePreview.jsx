import { useState } from "react";

export default function FilePreview({ preview, loading }) {
  const [sheet, setSheet] = useState(0);

  if (loading) {
    return <p className="preview-empty">Loading preview...</p>;
  }
  if (!preview) {
    return <p className="preview-empty">Select a file to preview.</p>;
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
