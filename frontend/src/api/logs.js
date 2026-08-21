import { API_ROOT, request } from "./client";

export const logsApi = {
  listLogs: (page = 1, pageSize = 200, filters = {}) => {
    const params = new URLSearchParams({
      page: String(page),
      pageSize: String(pageSize),
    });
    ["timestamp", "action", "detail", "clientIp"].forEach((key) => {
      const value = String(filters[key] || "").trim();
      if (value) {
        params.set(key, value);
      }
    });
    return request(`${API_ROOT}/activity-logs?${params.toString()}`);
  },
  exportLogs: async (filters = {}) => {
    const params = new URLSearchParams();
    ["timestamp", "action", "detail", "clientIp"].forEach((key) => {
      const value = String(filters[key] || "").trim();
      if (value) {
        params.set(key, value);
      }
    });
    const query = params.toString();
    const response = await fetch(`${API_ROOT}/activity-logs/export${query ? `?${query}` : ""}`);
    if (!response.ok) {
      throw new Error(`Export failed (HTTP ${response.status}).`);
    }
    return response.blob();
  },
  recordLog: (action, detail = "") =>
    request(`${API_ROOT}/activity-logs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, detail }),
    }).catch(() => {}),
};
