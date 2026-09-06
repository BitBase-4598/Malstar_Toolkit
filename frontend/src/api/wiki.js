import { API_ROOT, IMPORT_TIMEOUT_MS, request } from "./client";

export const wikiApi = {
  wikiStatus: () => request(`${API_ROOT}/wiki/status`),
  listWiki: (q = "", sourceType = "") => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (sourceType) params.set("sourceType", sourceType);
    const query = params.toString();
    return request(`${API_ROOT}/wiki${query ? `?${query}` : ""}`);
  },
  searchWiki: (q) => request(`${API_ROOT}/wiki/search?q=${encodeURIComponent(q)}`),
  getWiki: (slug) => request(`${API_ROOT}/wiki/${encodeURIComponent(slug)}`),
  wikiReindex: () =>
    request(`${API_ROOT}/wiki/reindex`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
      timeout: IMPORT_TIMEOUT_MS,
    }),
};
