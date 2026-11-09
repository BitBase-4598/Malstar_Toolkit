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
  saveHandlerRoster: (names) => request(`${API_ROOT}/dashboard/handler-roster`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ names }),
  }),
  exportDashboardPdf: async (dateFrom = "", dateTo = "", mailbox = "") => {
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
    const response = await request(`${API_ROOT}/dashboard/export.pdf${query ? `?${query}` : ""}`);
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename=\"?([^\";]+)\"?/);
    const filename = match?.[1] || "malstar-ops.pdf";
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
};
