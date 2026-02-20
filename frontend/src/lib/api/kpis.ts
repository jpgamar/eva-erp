import api from "./client";

export const kpisApi = {
  current: () => api.get("/kpis/current").then(r => r.data),
  history: (months = 12) => api.get("/kpis/history", { params: { months } }).then(r => r.data),
  snapshot: () => api.post("/kpis/snapshot").then(r => r.data),
};
