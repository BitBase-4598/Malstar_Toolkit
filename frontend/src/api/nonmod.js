import { API_ROOT, IMPORT_TIMEOUT_MS, request } from "./client";

export const NONMOD_PAGE_SIZE = 50;

function query(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const nonmodApi = {
  uploadNonMod: (file, reportDate) => {
    const form = new FormData();
    form.append("file", file);
    if (reportDate) {
      form.append("reportDate", reportDate);
    }
    return request(`${API_ROOT}/non-mod/upload`, {
      method: "POST",
      body: form,
      timeout: IMPORT_TIMEOUT_MS,
    });
  },
  getNonModLatest: (options) => request(`${API_ROOT}/non-mod/latest`, options),
  listNonModRows: (reportDate = "", page = 1, pageSize = NONMOD_PAGE_SIZE, options) =>
    request(
      `${API_ROOT}/non-mod/rows${query({ reportDate, page, pageSize })}`,
      options,
    ),
  getNonModFieldRanking: (reportDate = "", options) =>
    request(`${API_ROOT}/non-mod/field-ranking${query({ reportDate })}`, options),
};
