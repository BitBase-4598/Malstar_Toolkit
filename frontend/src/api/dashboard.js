import { API_ROOT, request } from "./client";

export const dashboardApi = {
  getDashboard: (dateFrom = "", dateTo = "", mailbox = "") => {
    const params = new URLSearchParams();
    if (dateFrom) {
      params.set("dateFrom", dateFrom);
    }
    if (dateTo) {
      params.set("dateTo", dateTo);
    }
    const mailboxes = Array.isArray(mailbox) ? mailbox : mailbox ? [mailbox] : [];
    for (const name of mailboxes) {
      if (name) {
        params.append("mailbox", name);
      }
    }
    const query = params.toString();
    return request(`${API_ROOT}/dashboard${query ? `?${query}` : ""}`);
  },
  importDashboard: async (file) => {
    const { csvFileToDashboardRecords, readFileText } = await import("../csv");
    const text = await readFileText(file);
    const records = csvFileToDashboardRecords(text);
    return request(`${API_ROOT}/dashboard/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, records }),
    });
  },
};
