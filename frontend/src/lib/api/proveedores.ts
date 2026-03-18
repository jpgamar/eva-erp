import api from "./client";

export const proveedoresApi = {
  list: (params?: { search?: string }) =>
    api.get("/proveedores", { params }).then(r => r.data),
  get: (id: string) => api.get(`/proveedores/${id}`).then(r => r.data),
  create: (data: any) => api.post("/proveedores", data).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/proveedores/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/proveedores/${id}`).then(r => r.data),
};
