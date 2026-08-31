import { API_ROOT, request } from "./client";

export const FEEDBACK_CATEGORIES = [
  "Human Error",
  "Commercial knowledge & Operation Process Rules Updates",
  "System Enhancements",
  "Defects",
  "Invalid Feedback",
  "Process ambiguity reclarification",
];

const BASE = `${API_ROOT}/cases`;

export const casesApi = {
  listCases: (q = "") => request(`${BASE}?q=${encodeURIComponent(q)}`),
  getCase: (id) => request(`${BASE}/${id}`),
  createCase: (data) =>
    request(BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateCase: (id, data) =>
    request(`${BASE}/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  setCaseStatus: (id, status) =>
    request(`${BASE}/${id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }),
  deleteCase: (id) => request(`${BASE}/${id}`, { method: "DELETE" }),
  importCases: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${BASE}/import`, { method: "POST", body: form });
  },
  downloadCaseTemplate: async () => {
    const response = await fetch(`${BASE}/template`);
    if (!response.ok) {
      throw new Error("Could not download the template.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "feedback-template.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
  uploadCaseFile: (id, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${BASE}/${id}/files`, { method: "POST", body: form });
  },
  deleteCaseFile: (caseId, fileId) => request(`${BASE}/${caseId}/files/${fileId}`, { method: "DELETE" }),
  caseFileDownloadUrl: (caseId, fileId) => `${BASE}/${caseId}/files/${fileId}`,
};
