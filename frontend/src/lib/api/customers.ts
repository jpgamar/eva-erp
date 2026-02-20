import api from "./client";

export const customersApi = {
  list: (params?: { status?: string; plan?: string; search?: string }) =>
    api.get("/customers", { params }).then(r => r.data),
  create: (data: any) => api.post("/customers", data).then(r => r.data),
  get: (id: string) => api.get(`/customers/${id}`).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/customers/${id}`, data).then(r => r.data),
  summary: () => api.get("/customers/summary").then(r => r.data),
  payments: (id: string) => api.get(`/customers/${id}/payments`).then(r => r.data),
};
