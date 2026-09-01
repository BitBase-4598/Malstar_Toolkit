import { API_ROOT, IMPORT_TIMEOUT_MS, request } from "./client";

export const UNLOCO_PAGE_SIZE = 50;

export const unlocoApi = {
  listUnloco: (q = "", page = 1, pageSize = UNLOCO_PAGE_SIZE, options) =>
    request(`${API_ROOT}/unlocode?q=${encodeURIComponent(q)}&page=${page}&pageSize=${pageSize}`, options),
  createUnloco: (data) =>
    request(`${API_ROOT}/unlocode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  importUnloco: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${API_ROOT}/unlocode/import`, { method: "POST", body: form, timeout: IMPORT_TIMEOUT_MS });
  },
};
