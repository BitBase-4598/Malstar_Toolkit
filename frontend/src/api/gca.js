import { API_ROOT, IMPORT_TIMEOUT_MS, request } from "./client";

export const GCA_PAGE_SIZE = 50;

function query(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value) {
      search.set(key, value);
    }
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const gcaApi = {
  getGcaSummary: (params, options) => request(`${API_ROOT}/gca/summary${query(params)}`, options),
  listGcaBookings: (params, options) => request(`${API_ROOT}/gca/bookings${query(params)}`, options),
  listGcaFeedback: (params, options) => request(`${API_ROOT}/gca/feedback${query(params)}`, options),
  importGca: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${API_ROOT}/gca/import`, { method: "POST", body: form, timeout: IMPORT_TIMEOUT_MS });
  },
};
