const API_ROOT = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/api`;
const BASE = `${API_ROOT}/customer-remarks`;
const FILES = `${API_ROOT}/files`;
const SOPS = `${API_ROOT}/sops`;
const JSON_UPLOAD_LIMIT = 4 * 1024 * 1024;

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/octet-stream") || contentType.includes("officedocument")) {
    if (!response.ok) {
      throw new Error(`Download failed (HTTP ${response.status}).`);
    }
    return response;
  }
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(
      text?.trim()
        ? `Request failed (HTTP ${response.status}). ${text.replace(/<[^>]+>/g, " ").trim().slice(0, 180)}`
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

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(new Error("Could not read the file."));
    reader.readAsDataURL(file);
  });
}

export const RECORDS_PAGE_SIZE = 12;

export const api = {
  list: (q, page = 1, pageSize = RECORDS_PAGE_SIZE) =>
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
  listFiles: (q = "") => request(`${FILES}?q=${encodeURIComponent(q)}`),
  uploadFile: async (file) => {
    const form = new FormData();
    form.append("file", file);
    try {
      return await request(FILES, { method: "POST", body: form });
    } catch (error) {
      if (file.size > JSON_UPLOAD_LIMIT) {
        throw error;
      }
      const content = await fileToBase64(file);
      return request(FILES, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, content }),
      });
    }
  },
  previewFile: (id) => request(`${FILES}/${id}/preview`),
  renameFile: (id, originalName) =>
    request(`${FILES}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ originalName }),
    }),
  deleteFile: (id) => request(`${FILES}/${id}`, { method: "DELETE" }),
  downloadUrl: (id) => `${FILES}/${id}`,
  listSops: (q = "") => request(`${SOPS}?q=${encodeURIComponent(q)}`),
  getSop: (id) => request(`${SOPS}/${id}`),
  createSop: (data) =>
    request(SOPS, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateSop: (id, data) =>
    request(`${SOPS}/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteSop: (id) => request(`${SOPS}/${id}`, { method: "DELETE" }),
  listLogs: (page = 1, pageSize = 80) =>
    request(`${API_ROOT}/activity-logs?page=${page}&pageSize=${pageSize}`),
  recordLog: (action, detail = "") =>
    request(`${API_ROOT}/activity-logs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, detail }),
    }).catch(() => {}),
};
