import api from "./client";

export const prospectsApi = {
  list: (params?: { status?: string; search?: string }) => api.get("/prospects", { params }).then(r => r.data),
  create: (data: any) => api.post("/prospects", data).then(r => r.data),
  get: (id: string) => api.get(`/prospects/${id}`).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/prospects/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/prospects/${id}`).then(r => r.data),
  summary: () => api.get("/prospects/summary").then(r => r.data),
  dueFollowups: () => api.get("/prospects/due-followups").then(r => r.data),
  addInteraction: (id: string, data: any) => api.post(`/prospects/${id}/interactions`, data).then(r => r.data),
  listInteractions: (id: string) => api.get(`/prospects/${id}/interactions`).then(r => r.data),
  convert: (id: string) => api.post(`/prospects/${id}/convert`).then(r => r.data),
};
