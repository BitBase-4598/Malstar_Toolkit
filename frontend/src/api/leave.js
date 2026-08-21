import { API_ROOT, request } from "./client";

const LEAVE = `${API_ROOT}/leave-plans`;

export const leaveApi = {
  listLeavePlans: (year, month) =>
    request(`${LEAVE}?year=${encodeURIComponent(year)}&month=${encodeURIComponent(month)}`),
  createLeavePlan: (data) =>
    request(LEAVE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  updateLeavePlan: (id, data) =>
    request(`${LEAVE}/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteLeavePlan: (id) => request(`${LEAVE}/${id}`, { method: "DELETE" }),
};
