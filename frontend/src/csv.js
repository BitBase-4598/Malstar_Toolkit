function parseCsvRows(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  const source = String(text || "").replace(/^\uFEFF/, "");

  for (let i = 0; i < source.length; i += 1) {
    const char = source[i];
    const next = source[i + 1];
    if (inQuotes) {
      if (char === '"' && next === '"') {
        field += '"';
        i += 1;
      } else if (char === '"') {
        inQuotes = false;
      } else {
        field += char;
      }
      continue;
    }
    if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }
  if (field.length || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((item) => item.some((value) => String(value || "").trim()));
}

export function csvFileToRecords(text) {
  const rows = parseCsvRows(text);
  if (!rows.length) {
    throw new Error("CSV contains no data rows.");
  }
  const headers = rows[0].map((header) => String(header || "").trim().toLowerCase());
  const orgIndex = headers.indexOf("ctrlorgcode");
  const customerIndex = headers.indexOf("customer");
  if (orgIndex < 0 || customerIndex < 0) {
    throw new Error("CSV must include CTRLOrgcode and Customer columns.");
  }
  const remark1 = headers.indexOf("remark1");
  const remark2 = headers.indexOf("remark2");
  const remark3 = headers.indexOf("remark3");
  const value = (row, index) => (index >= 0 ? row[index] || "" : "");

  return rows.slice(1).map((row) => ({
    ctrlOrgcode: value(row, orgIndex),
    customer: value(row, customerIndex),
    remark1: value(row, remark1),
    remark2: value(row, remark2),
    remark3: value(row, remark3),
  }));
}

export function readFileText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Could not read the CSV file."));
    reader.readAsText(file);
  });
}
