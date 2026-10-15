import { API_ROOT, IMPORT_TIMEOUT_MS, request } from "./client";

export const DEBOSCH_PAGE_SIZE = 50;

export const deboschApi = {
  listDebosch: (q = "", page = 1, pageSize = DEBOSCH_PAGE_SIZE, options) =>
    request(`${API_ROOT}/de-bosch?q=${encodeURIComponent(q)}&page=${page}&pageSize=${pageSize}`, options),
  createDebosch: (data) =>
    request(`${API_ROOT}/de-bosch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateDebosch: (id, data) =>
    request(`${API_ROOT}/de-bosch/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  removeDebosch: (id) => request(`${API_ROOT}/de-bosch/${id}`, { method: "DELETE" }),
  importDebosch: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${API_ROOT}/de-bosch/import`, { method: "POST", body: form, timeout: IMPORT_TIMEOUT_MS });
  },
};
