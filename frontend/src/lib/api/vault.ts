import api from "./client";

export const vaultApi = {
  status: () => api.get("/vault/status").then(r => r.data),
  setup: (master_password: string) => api.post("/vault/setup", { master_password }).then(r => r.data),
  unlock: (master_password: string) => api.post("/vault/unlock", { master_password }).then(r => r.data),
  lock: () => api.post("/vault/lock").then(r => r.data),
  list: (params?: { category?: string; search?: string }) => api.get("/vault/credentials", { params }).then(r => r.data),
  get: (id: string) => api.get(`/vault/credentials/${id}`).then(r => r.data),
  create: (data: any) => api.post("/vault/credentials", data).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/vault/credentials/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/vault/credentials/${id}`).then(r => r.data),
  costSummary: () => api.get("/vault/cost-summary").then(r => r.data),
  auditLog: (params?: { credential_id?: string }) => api.get("/vault/audit-log", { params }).then(r => r.data),
};
