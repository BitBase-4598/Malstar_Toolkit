import { API_ROOT, IMPORT_TIMEOUT_MS, request } from "./client";

function queryString(filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    const text = String(value || "").trim();
    if (text) {
      params.set(key, text);
    }
  });
  return params.toString();
}

export const twPrefillApi = {
  suggestTwPrefill: (filters, options) =>
    request(`${API_ROOT}/tw-prefill/suggest?${queryString(filters)}`, options),
  importTwPrefill: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${API_ROOT}/tw-prefill/import`, { method: "POST", body: form, timeout: IMPORT_TIMEOUT_MS });
  },
};
