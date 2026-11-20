import { API_ROOT, IMPORT_TIMEOUT_MS, JSON_UPLOAD_LIMIT, fileToBase64, request } from "./client";

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
  importTwPrefill: async (file) => {
    const form = new FormData();
    form.append("file", file);
    try {
      return await request(`${API_ROOT}/tw-prefill/import`, {
        method: "POST",
        body: form,
        timeout: IMPORT_TIMEOUT_MS,
      });
    } catch (error) {
      if (file.size > JSON_UPLOAD_LIMIT) {
        throw error;
      }
      const content = await fileToBase64(file);
      return request(`${API_ROOT}/tw-prefill/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, content }),
        timeout: IMPORT_TIMEOUT_MS,
      });
    }
  },
};
