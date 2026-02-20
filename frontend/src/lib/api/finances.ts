import api from "./client";

export const exchangeRateApi = {
  current: () => api.get("/finances/exchange-rates/current").then(r => r.data),
  update: (data: { rate: number; effective_date?: string }) => api.patch("/finances/exchange-rates", data).then(r => r.data),
};

export const incomeApi = {
  list: (params?: { start_date?: string; end_date?: string; source?: string; category?: string }) =>
    api.get("/finances/income", { params }).then(r => r.data),
  create: (data: any) => api.post("/finances/income", data).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/finances/income/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/finances/income/${id}`).then(r => r.data),
  summary: () => api.get("/finances/income/summary").then(r => r.data),
};

export const expenseApi = {
  list: (params?: { start_date?: string; end_date?: string; category?: string; paid_by?: string; recurring?: boolean }) =>
    api.get("/finances/expenses", { params }).then(r => r.data),
  create: (data: any) => api.post("/finances/expenses", data).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/finances/expenses/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/finances/expenses/${id}`).then(r => r.data),
  summary: () => api.get("/finances/expenses/summary").then(r => r.data),
  partnerSummary: () => api.get("/finances/expenses/partner-summary").then(r => r.data),
};

export const invoiceApi = {
  list: (params?: { status?: string; customer_id?: string }) =>
    api.get("/finances/invoices", { params }).then(r => r.data),
  create: (data: any) => api.post("/finances/invoices", data).then(r => r.data),
  get: (id: string) => api.get(`/finances/invoices/${id}`).then(r => r.data),
  update: (id: string, data: any) => api.patch(`/finances/invoices/${id}`, data).then(r => r.data),
  delete: (id: string) => api.delete(`/finances/invoices/${id}`).then(r => r.data),
};

export const cashBalanceApi = {
  current: () => api.get("/finances/cash-balance/current").then(r => r.data),
  update: (data: any) => api.post("/finances/cash-balance", data).then(r => r.data),
};
