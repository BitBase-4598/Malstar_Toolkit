import { API_ROOT, IMPORT_TIMEOUT_MS, request } from "./client";

function queryString(filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    const text = String(value || "").trim();
    if (text) {
      params.set(key, text);
    }
  });
  return params.toString();
}

const CHUNK_CHARS = 900_000;

function splitCsv(text, limit) {
  const rows = [];
  let row = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    row += char;
    if (char === "\"") {
      if (quoted && text[index + 1] === "\"") {
        row += text[index + 1];
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (!quoted && (char === "\n" || char === "\r")) {
      if (char === "\r" && text[index + 1] === "\n") {
        row += text[index + 1];
        index += 1;
      }
      rows.push(row);
      row = "";
    }
  }
  if (row.trim()) {
    rows.push(row.endsWith("\n") ? row : `${row}\n`);
  }
  if (!rows.length) {
    return [];
  }
  const header = rows[0].endsWith("\n") ? rows[0] : `${rows[0]}\n`;
  const chunks = [];
  let body = "";
  rows.slice(1).forEach((line) => {
    const record = line.endsWith("\n") ? line : `${line}\n`;
    if (body && header.length + body.length + record.length > limit) {
      chunks.push(header + body);
      body = "";
    }
    body += record;
  });
  if (body) {
    chunks.push(header + body);
  }
  return chunks.length ? chunks : [header];
}

export const twPrefillApi = {
  suggestTwPrefill: (filters, options) =>
    request(`${API_ROOT}/tw-prefill/suggest?${queryString(filters)}`, options),
  importTwPrefill: async (file) => {
    const text = await file.text();
    const chunks = splitCsv(text, CHUNK_CHARS);
    if (!chunks.length) {
      throw new Error("CSV is empty.");
    }
    let added = 0;
    let skipped = 0;
    let rowCount = 0;
    for (let index = 0; index < chunks.length; index += 1) {
      let result;
      try {
        result = await request(`${API_ROOT}/tw-prefill/import`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename: file.name, csv: chunks[index] }),
          timeout: IMPORT_TIMEOUT_MS,
        });
      } catch (error) {
        const placed = added ? ` Added ${added.toLocaleString()} before this part failed.` : "";
        throw new Error(`${error.message}${placed}`);
      }
      added += result.data?.added || 0;
      skipped += result.data?.skipped || 0;
      rowCount = result.data?.rowCount || rowCount;
    }
    const noun = added === 1 ? "shipment" : "shipments";
    return {
      success: true,
      message: `Added ${added.toLocaleString()} ${noun}, skipped ${skipped.toLocaleString()} duplicates`,
      data: { filename: file.name, added, skipped, rowCount },
    };
  },
};
