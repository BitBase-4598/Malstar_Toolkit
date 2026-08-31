import { API_ROOT, request } from "./client";

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
  getGcaSummary: (params) => request(`${API_ROOT}/gca/summary${query(params)}`),
  listGcaBookings: (params) => request(`${API_ROOT}/gca/bookings${query(params)}`),
  listGcaFeedback: (params) => request(`${API_ROOT}/gca/feedback${query(params)}`),
  importGca: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${API_ROOT}/gca/import`, { method: "POST", body: form });
  },
};
