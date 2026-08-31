import { API_ROOT, request } from "./client";

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
  lclFilters: () => request(`${API_ROOT}/lcl/filters`),
  lclDashboard: (params) => request(`${API_ROOT}/lcl/dashboard${query(params)}`),
  lclSummary: (params) => request(`${API_ROOT}/lcl/summary${query(params)}`),
  lclMap: (params) => request(`${API_ROOT}/lcl/map${query(params)}`),
  importLcl: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${API_ROOT}/lcl/import`, { method: "POST", body: form });
  },
};
