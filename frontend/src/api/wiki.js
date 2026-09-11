import { API_ROOT, IMPORT_TIMEOUT_MS, JSON_UPLOAD_LIMIT, fileToBase64, request } from "./client";

const WIKI = `${API_ROOT}/wiki`;

async function postFile(url, file, extra = {}) {
  const form = new FormData();
  form.append("file", file);
  try {
    return await request(url, { method: "POST", body: form, timeout: IMPORT_TIMEOUT_MS, ...extra });
  } catch (error) {
    if (file.size > JSON_UPLOAD_LIMIT) {
      throw error;
    }
    const content = await fileToBase64(file);
    return request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, content }),
      timeout: IMPORT_TIMEOUT_MS,
      ...extra,
    });
  }
}

export const wikiApi = {
  listWiki: (q = "") => request(`${WIKI}?q=${encodeURIComponent(q)}`),
  getWiki: (id) => request(`${WIKI}/${id}`),
  getWikiByLink: (title) => request(`${WIKI}/by-link?q=${encodeURIComponent(title)}`),
  createWiki: (data) =>
    request(WIKI, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateWiki: (id, data) =>
    request(`${WIKI}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteWiki: (id) => request(`${WIKI}/${id}`, { method: "DELETE" }),
  importWikiVault: (file, replace = false) =>
    postFile(`${WIKI}/import${replace ? "?replace=1" : ""}`, file),
  uploadWikiNote: (file) => postFile(`${WIKI}/upload`, file),
};
