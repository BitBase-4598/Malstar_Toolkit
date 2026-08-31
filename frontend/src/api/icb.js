import { API_ROOT, request } from "./client";

export const ICB_PAGE_SIZE = 100;

export const icbApi = {
  listIcb: (q = "", page = 1, pageSize = ICB_PAGE_SIZE) =>
    request(`${API_ROOT}/icb?q=${encodeURIComponent(q)}&page=${page}&pageSize=${pageSize}`),
  importIcb: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${API_ROOT}/icb/import`, { method: "POST", body: form });
  },
};
