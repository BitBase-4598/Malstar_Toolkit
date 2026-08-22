import { API_ROOT, request } from "./client";

const FILTER_KEYS = ["timestamp", "action", "detail", "clientIp", "module", "outcome", "requestId"];

function queryFromFilters(filters = {}) {
  const params = new URLSearchParams();
  FILTER_KEYS.forEach((key) => {
    const value = String(filters[key] || "").trim();
    if (value) {
      params.set(key, value);
    }
  });
  return params;
}

export const logsApi = {
  listLogs: (page = 1, pageSize = 200, filters = {}) => {
    const params = queryFromFilters(filters);
    params.set("page", String(page));
    params.set("pageSize", String(pageSize));
    return request(`${API_ROOT}/activity-logs?${params.toString()}`);
  },
  exportLogs: async (filters = {}) => {
    const query = queryFromFilters(filters).toString();
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
