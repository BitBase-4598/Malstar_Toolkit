import { API_ROOT, request } from "./client";

export const UNLOCO_PAGE_SIZE = 50;

export const unlocoApi = {
  listUnloco: (q = "", page = 1, pageSize = UNLOCO_PAGE_SIZE) =>
    request(`${API_ROOT}/unlocode?q=${encodeURIComponent(q)}&page=${page}&pageSize=${pageSize}`),
  importUnloco: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${API_ROOT}/unlocode/import`, { method: "POST", body: form });
  },
};
