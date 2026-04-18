import api from "./client";

export interface CfdiPayment {
  id: string;
  factura_id: string;
  facturapi_id: string | null;
  cfdi_uuid: string | null;
  payment_date: string;
  payment_form: string;
  payment_amount: string;
  currency: string;
  exchange_rate: string | null;
  installment: number;
  last_balance: string | null;
  status: string;
  stamp_retry_count: number;
  last_stamp_error: string | null;
  next_retry_at: string | null;
  pdf_url: string | null;
  xml_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface CfdiPaymentCreate {
  payment_date: string; // YYYY-MM-DD
  payment_form: string;
  payment_amount: string | number;
  currency?: string;
  exchange_rate?: string | number | null;
  installment?: number;
  last_balance?: string | number | null;
  notes?: string | null;
}

export const facturasApi = {
  list: (params?: { status?: string }) =>
    api.get("/facturas", { params }).then(r => r.data),
  create: (data: any, opts?: { draft?: boolean }) =>
    api.post("/facturas", data, { params: opts?.draft ? { draft: "true" } : undefined }).then(r => r.data),
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
  reconcile: () =>
    api.post("/facturas/reconcile").then(r => r.data),
  listPayments: (facturaId: string) =>
    api.get<CfdiPayment[]>(`/facturas/${facturaId}/payments`).then(r => r.data),
  registerPayment: (facturaId: string, data: CfdiPaymentCreate) =>
    api.post<CfdiPayment>(`/facturas/${facturaId}/payments`, data).then(r => r.data),
};
