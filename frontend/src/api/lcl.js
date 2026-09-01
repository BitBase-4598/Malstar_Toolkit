import { API_ROOT, IMPORT_TIMEOUT_MS, request } from "./client";

function query(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      if (value.length) {
        search.set(key, value.join(","));
      }
      return;
    }
    if (value) {
      search.set(key, value);
    }
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const lclApi = {
  lclFilters: (options) => request(`${API_ROOT}/lcl/filters`, options),
  lclDashboard: (params, options) => request(`${API_ROOT}/lcl/dashboard${query(params)}`, options),
  lclSummary: (params, options) => request(`${API_ROOT}/lcl/summary${query(params)}`, options),
  lclMap: (params, options) => request(`${API_ROOT}/lcl/map${query(params)}`, options),
  importLcl: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${API_ROOT}/lcl/import`, { method: "POST", body: form, timeout: IMPORT_TIMEOUT_MS });
  },
};
