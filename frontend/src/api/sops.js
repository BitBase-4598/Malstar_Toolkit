import { API_ROOT, request } from "./client";

const SOPS = `${API_ROOT}/sops`;

export const sopsApi = {
  listSops: (q = "") => request(`${SOPS}?q=${encodeURIComponent(q)}`),
  getSop: (id) => request(`${SOPS}/${id}`),
  createSop: (data) =>
    request(SOPS, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateSop: (id, data) =>
    request(`${SOPS}/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteSop: (id) => request(`${SOPS}/${id}`, { method: "DELETE" }),
};
