const API_ROOT = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/api`;
const BASE = `${API_ROOT}/customer-remarks`;

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(
      text?.trim()
        ? `Import failed (HTTP ${response.status}). ${text.replace(/<[^>]+>/g, " ").trim().slice(0, 180)}`
        : `Invalid response (HTTP ${response.status}).`
    );
  }
  if (!response.ok) {
    const detail = payload.errors
      ?.slice(0, 5)
      .map((error) => `Row ${error.row}: ${error.message}`)
      .join("; ");
    throw new Error(
      detail ? `${payload.message} ${detail}` : payload.message || `HTTP ${response.status}`
    );
  }
  return payload;
}

export const api = {
  list: (q, page = 1, pageSize = 20) =>
    request(`${BASE}?q=${encodeURIComponent(q)}&page=${page}&pageSize=${pageSize}`),
  create: (data) =>
    request(BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  update: (id, data) =>
    request(`${BASE}/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  remove: (id) => request(`${BASE}/${id}`, { method: "DELETE" }),
  importCsv: async (file) => {
    const { csvFileToRecords, readFileText } = await import("./csv");
    const text = await readFileText(file);
    const records = csvFileToRecords(text);
    return request(`${BASE}/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, records }),
    });
  },
  listLogs: (page = 1, pageSize = 80) =>
    request(`${API_ROOT}/activity-logs?page=${page}&pageSize=${pageSize}`),
  recordLog: (action, detail = "") =>
    request(`${API_ROOT}/activity-logs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, detail }),
    }).catch(() => {}),
};
