import api from "./client";

export const okrsApi = {
  activePeriod: () => api.get("/okrs/active").then(r => r.data),
  listPeriods: () => api.get("/okrs/periods").then(r => r.data),
  getPeriod: (id: string) => api.get(`/okrs/periods/${id}`).then(r => r.data),
  createPeriod: (data: any) => api.post("/okrs/periods", data).then(r => r.data),
  createObjective: (data: any) => api.post("/okrs/objectives", data).then(r => r.data),
  updateObjective: (id: string, data: any) => api.patch(`/okrs/objectives/${id}`, data).then(r => r.data),
  createKeyResult: (data: any) => api.post("/okrs/key-results", data).then(r => r.data),
  updateKeyResult: (id: string, data: any) => api.patch(`/okrs/key-results/${id}`, data).then(r => r.data),
};
