import { API_ROOT, request } from "./client";

const LEAVE = `${API_ROOT}/leave-plans`;

export const leaveApi = {
  listLeavePeople: (options) => request(`${API_ROOT}/leave-people`, options),
  listLeavePlans: (year, month, options) =>
    request(`${LEAVE}?year=${encodeURIComponent(year)}&month=${encodeURIComponent(month)}`, options),
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
