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

export function csvFileToDashboardRecords(text) {
  const rows = parseCsvRows(text);
  if (!rows.length) {
    throw new Error("CSV contains no data rows.");
  }
  const headers = rows[0].map((header) => String(header || "").replace(/\s+/g, " ").trim().toLowerCase());
  const required = [
    ["order number", "orderNumber"],
    ["shipment number", "shipmentNumber"],
    ["message id", "messageId"],
    ["date", "date"],
    ["email received", "emailReceived"],
    ["email status", "emailStatus"],
    ["handled by", "handledBy"],
    ["handling time", "handlingTime"],
    ["booking converted time", "bookingConvertedTime"],
    ["subject", "subject"],
    ["mailbox", "mailbox"],
  ];
  const indexes = {};
  const missing = [];
  required.forEach(([header, key]) => {
    const index = headers.indexOf(header);
    indexes[key] = index;
    if (index < 0) {
      missing.push(header);
    }
  });
  if (missing.length) {
    throw new Error("CSV must include: " + missing.join(", ") + ".");
  }
  const value = (row, key) => (indexes[key] >= 0 ? String(row[indexes[key]] ?? "").trim() : "");
  return rows.slice(1).map((row) => ({
    orderNumber: value(row, "orderNumber"),
    shipmentNumber: value(row, "shipmentNumber"),
    messageId: value(row, "messageId"),
    date: value(row, "date"),
    emailReceived: value(row, "emailReceived"),
    emailStatus: value(row, "emailStatus"),
    handledBy: value(row, "handledBy"),
    handlingTime: value(row, "handlingTime"),
    bookingConvertedTime: value(row, "bookingConvertedTime"),
    subject: value(row, "subject"),
    mailbox: value(row, "mailbox"),
  }));
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
