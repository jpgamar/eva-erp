import api from "./client";

export interface EmpresaListItem {
  id: string;
  name: string;
  logo_url: string | null;
  item_count: number;
}

export interface EmpresaItem {
  id: string;
  empresa_id: string;
  type: "need" | "task";
  title: string;
  description: string | null;
  status: string;
  priority: string | null;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface Empresa {
  id: string;
  name: string;
  logo_url: string | null;
  industry: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  rfc: string | null;
  razon_social: string | null;
  regimen_fiscal: string | null;
  created_at: string;
  updated_at: string;
  items: EmpresaItem[];
}

export interface EmpresaCreate {
  name: string;
  logo_url?: string | null;
  industry?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  rfc?: string | null;
  razon_social?: string | null;
  regimen_fiscal?: string | null;
}

export interface EmpresaItemCreate {
  type: "need" | "task";
  title: string;
  description?: string | null;
  status?: string;
  priority?: string | null;
  due_date?: string | null;
}

export const empresasApi = {
  list: (search?: string) =>
    api.get<EmpresaListItem[]>("/empresas", { params: search ? { search } : undefined }).then((r) => r.data),

  get: (id: string) => api.get<Empresa>(`/empresas/${id}`).then((r) => r.data),

  create: (data: EmpresaCreate) => api.post<Empresa>("/empresas", data).then((r) => r.data),

  update: (id: string, data: Partial<EmpresaCreate>) => api.patch<Empresa>(`/empresas/${id}`, data).then((r) => r.data),

  delete: (id: string) => api.delete(`/empresas/${id}`),

  createItem: (empresaId: string, data: EmpresaItemCreate) =>
    api.post<EmpresaItem>(`/empresas/${empresaId}/items`, data).then((r) => r.data),

  updateItem: (itemId: string, data: Partial<Omit<EmpresaItemCreate, "type">>) =>
    api.patch<EmpresaItem>(`/empresas/items/${itemId}`, data).then((r) => r.data),

  deleteItem: (itemId: string) => api.delete(`/empresas/items/${itemId}`),
};
