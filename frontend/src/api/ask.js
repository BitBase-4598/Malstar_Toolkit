import { API_ROOT, request } from "./client";

export const askApi = {
  askStatus: () => request(`${API_ROOT}/ask/status`),
  askReindex: () =>
    request(`${API_ROOT}/ask/reindex`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }),
  ask: (question) =>
    request(`${API_ROOT}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
};
