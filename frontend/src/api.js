const BASE = "/api/customer-remarks";

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({ message: "Invalid response" }));
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
  importCsv: (file) => {
    const formData = new FormData();
    formData.append("file", file);
    return request(`${BASE}/import-csv`, { method: "POST", body: formData });
  },
};
