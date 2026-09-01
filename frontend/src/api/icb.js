import { API_ROOT, IMPORT_TIMEOUT_MS, request } from "./client";

export const ICB_PAGE_SIZE = 100;

export const icbApi = {
  listIcb: (q = "", page = 1, pageSize = ICB_PAGE_SIZE, options) =>
    request(`${API_ROOT}/icb?q=${encodeURIComponent(q)}&page=${page}&pageSize=${pageSize}`, options),
  createIcb: (data) =>
    request(`${API_ROOT}/icb`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateIcb: (id, data) =>
    request(`${API_ROOT}/icb/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  removeIcb: (id) => request(`${API_ROOT}/icb/${id}`, { method: "DELETE" }),
  importIcb: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${API_ROOT}/icb/import`, { method: "POST", body: form, timeout: IMPORT_TIMEOUT_MS });
  },
};
