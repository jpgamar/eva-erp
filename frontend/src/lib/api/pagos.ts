import api from "./client";

export const pagosApi = {
  list: (params?: { proveedor_id?: string; tipo?: string; status?: string; start_date?: string; end_date?: string }) =>
    api.get("/pagos", { params }).then(r => r.data),
  get: (id: string) => api.get(`/pagos/${id}`).then(r => r.data),
  create: (data: any) => api.post("/pagos", data).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/pagos/${id}`, data).then(r => r.data),
  cancel: (id: string) => api.delete(`/pagos/${id}`).then(r => r.data),
  apply: (id: string, data: { factura_proveedor_id: string; amount: number }) =>
    api.post(`/pagos/${id}/apply`, data).then(r => r.data),
  summary: (params?: { tipo?: string }) => api.get("/pagos/summary", { params }).then(r => r.data),
};

export const facturasProveedorApi = {
  list: (params?: { proveedor_id?: string; status?: string; currency?: string; start_date?: string; end_date?: string }) =>
    api.get("/facturas-proveedor", { params }).then(r => r.data),
  get: (id: string) => api.get(`/facturas-proveedor/${id}`).then(r => r.data),
  create: (data: any) => api.post("/facturas-proveedor", data).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/facturas-proveedor/${id}`, data).then(r => r.data),
  cancel: (id: string) => api.delete(`/facturas-proveedor/${id}`).then(r => r.data),
  hardDelete: (id: string) => api.delete(`/facturas-proveedor/${id}/hard`).then(r => r.data),
};

export const diferenciasCambiariasApi = {
  list: (params?: { period?: string; proveedor_id?: string }) =>
    api.get("/diferencias-cambiarias", { params }).then(r => r.data),
  summary: (params?: { year?: number }) =>
    api.get("/diferencias-cambiarias/summary", { params }).then(r => r.data),
};
