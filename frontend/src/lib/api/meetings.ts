import api from "./client";

export const meetingsApi = {
  list: (params?: { type?: string; search?: string }) => api.get("/meetings", { params }).then(r => r.data),
  create: (data: any) => api.post("/meetings", data).then(r => r.data),
  get: (id: string) => api.get(`/meetings/${id}`).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/meetings/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/meetings/${id}`).then(r => r.data),
  upcoming: () => api.get("/meetings/upcoming").then(r => r.data),
  recent: () => api.get("/meetings/recent").then(r => r.data),
};
