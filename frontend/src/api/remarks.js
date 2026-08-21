import { API_ROOT, request } from "./client";

export const RECORDS_PAGE_SIZE = 12;
const BASE = `${API_ROOT}/customer-remarks`;

export const remarksApi = {
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
    const { csvFileToRecords, readFileText } = await import("../csv");
    const text = await readFileText(file);
    const records = csvFileToRecords(text);
    return request(`${BASE}/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, records }),
    });
  },
};
