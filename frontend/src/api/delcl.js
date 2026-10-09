import { API_ROOT, IMPORT_TIMEOUT_MS, request } from "./client";

export const DELCL_PAGE_SIZE = 50;

export const delclApi = {
  listDelcl: (q = "", page = 1, pageSize = DELCL_PAGE_SIZE, options) =>
    request(`${API_ROOT}/de-lcl?q=${encodeURIComponent(q)}&page=${page}&pageSize=${pageSize}`, options),
  createDelcl: (data) =>
    request(`${API_ROOT}/de-lcl`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateDelcl: (id, data) =>
    request(`${API_ROOT}/de-lcl/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  removeDelcl: (id) => request(`${API_ROOT}/de-lcl/${id}`, { method: "DELETE" }),
  importDelcl: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${API_ROOT}/de-lcl/import`, { method: "POST", body: form, timeout: IMPORT_TIMEOUT_MS });
  },
};
