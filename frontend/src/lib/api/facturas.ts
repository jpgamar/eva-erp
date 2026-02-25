import api from "./client";

export const facturasApi = {
  list: (params?: { status?: string }) =>
    api.get("/facturas", { params }).then(r => r.data),
  create: (data: any) =>
    api.post("/facturas", data).then(r => r.data),
  get: (id: string) =>
    api.get(`/facturas/${id}`).then(r => r.data),
  stamp: (id: string) =>
    api.post(`/facturas/${id}/stamp`).then(r => r.data),
  delete: (id: string, motive?: string) =>
    api.delete(`/facturas/${id}`, { params: { motive: motive || "02" } }).then(r => r.data),
  downloadPdf: (id: string) =>
    api.get(`/facturas/${id}/pdf`, { responseType: "blob" }).then(r => r.data),
  downloadXml: (id: string) =>
    api.get(`/facturas/${id}/xml`, { responseType: "blob" }).then(r => r.data),
  apiStatus: () =>
    api.get("/facturas/api-status").then(r => r.data),
};
