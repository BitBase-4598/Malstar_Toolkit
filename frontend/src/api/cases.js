import { API_ROOT, JSON_UPLOAD_LIMIT, fileToBase64, request } from "./client";

export const FEEDBACK_CATEGORIES = [
  "Human Error",
  "Commercial knowledge & Operation Process Rules Updates",
  "System Enhancements",
  "Defects",
  "Invalid Feedback",
  "Process ambiguity reclarification",
];

const BASE = `${API_ROOT}/cases`;

export const CASE_PAGE_SIZE = 10;

export const casesApi = {
  listCases: (q = "", page = 1, pageSize = CASE_PAGE_SIZE) =>
    request(`${BASE}?q=${encodeURIComponent(q)}&page=${page}&pageSize=${pageSize}`),
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
  uploadCaseFile: async (id, file) => {
    const form = new FormData();
    form.append("file", file);
    try {
      return await request(`${BASE}/${id}/files`, { method: "POST", body: form });
    } catch (error) {
      if (file.size > JSON_UPLOAD_LIMIT) {
        throw error;
      }
      const content = await fileToBase64(file);
      return request(`${BASE}/${id}/files`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, content }),
      });
    }
  },
  deleteCaseFile: (caseId, fileId) => request(`${BASE}/${caseId}/files/${fileId}`, { method: "DELETE" }),
  previewCaseFile: (caseId, fileId) => request(`${BASE}/${caseId}/files/${fileId}/preview`),
  caseFileContentUrl: (caseId, fileId) => `${BASE}/${caseId}/files/${fileId}/content`,
  caseFileDownloadUrl: (caseId, fileId) => `${BASE}/${caseId}/files/${fileId}`,
};
