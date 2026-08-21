import { API_ROOT, JSON_UPLOAD_LIMIT, fileToBase64, request } from "./client";

const FILES = `${API_ROOT}/files`;

export const filesApi = {
  listFiles: (q = "") => request(`${FILES}?q=${encodeURIComponent(q)}`),
  uploadFile: async (file) => {
    const form = new FormData();
    form.append("file", file);
    try {
      return await request(FILES, { method: "POST", body: form });
    } catch (error) {
      if (file.size > JSON_UPLOAD_LIMIT) {
        throw error;
      }
      const content = await fileToBase64(file);
      return request(FILES, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, content }),
      });
    }
  },
  previewFile: (id) => request(`${FILES}/${id}/preview`),
  renameFile: (id, originalName) =>
    request(`${FILES}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ originalName }),
    }),
  deleteFile: (id) => request(`${FILES}/${id}`, { method: "DELETE" }),
  downloadUrl: (id) => `${FILES}/${id}`,
};
