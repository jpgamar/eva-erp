import api from "./client";

// ── Types ──────────────────────────────────────────────────────────

export interface PendingItem {
  id: string;
  title: string;
}

export type EmpresaHealthStatus = "healthy" | "unhealthy" | "unknown" | "not_linked";

export interface ChannelTypeHealth {
  present: boolean;
  healthy: boolean;
  count: number;
}

export interface EmpresaHealth {
  status: EmpresaHealthStatus;
  unhealthy_count: number;
  linked_account_name: string | null;
  messenger: ChannelTypeHealth;
  instagram: ChannelTypeHealth;
  whatsapp: ChannelTypeHealth;
}

export interface EmpresaListItem {
  id: string;
  name: string;
  logo_url: string | null;
  status: string;
  ball_on: string | null;
  summary_note: string | null;
  monthly_amount: number | null;
  payment_day: number | null;
  last_paid_date: string | null;
  eva_account_id: string | null;
  auto_match_attempted: boolean;
  subscription_status: string | null;
  current_period_end: string | null;
  item_count: number;
  pending_count: number;
  pending_items: PendingItem[];
  health: EmpresaHealth;
}

export interface CheckoutLinkRequest {
  amount_mxn: number;
  description: string;
  interval: "month" | "year";
  recipient_email: string;
}

export interface EmpresaItem {
  id: string;
  empresa_id: string;
  title: string;
  done: boolean;
  created_at: string;
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
  status: string;
  ball_on: string | null;
  summary_note: string | null;
  monthly_amount: number | null;
  payment_day: number | null;
  last_paid_date: string | null;
  eva_account_id: string | null;
  auto_match_attempted: boolean;
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
  status?: string;
  ball_on?: string | null;
  summary_note?: string | null;
  monthly_amount?: number | null;
  payment_day?: number | null;
  last_paid_date?: string | null;
  eva_account_id?: string | null;
}

// ── Channel health types (silent-channel-health plan) ──

export interface ChannelHealthEntry {
  id: string;
  channel_type: "messenger" | "instagram" | "whatsapp";
  display_name: string | null;
  is_healthy: boolean;
  health_status_reason: string | null;
  last_status_check: string | null;
}

export interface AccountChannelHealthResponse {
  account_id: string;
  messenger: ChannelHealthEntry[];
  instagram: ChannelHealthEntry[];
  whatsapp: ChannelHealthEntry[];
}

export interface EvaAccountForLink {
  id: string;
  name: string;
}

export interface EmpresaItemCreate {
  title: string;
}

export interface EmpresaHistory {
  id: string;
  field_changed: string;
  old_value: string | null;
  new_value: string | null;
  changed_by: string | null;
  changed_by_name: string | null;
  changed_at: string;
}

// ── API ────────────────────────────────────────────────────────────

export const empresasApi = {
  list: (search?: string) =>
    api.get<EmpresaListItem[]>("/empresas", { params: search ? { search } : undefined }).then((r) => r.data),

  get: (id: string) => api.get<Empresa>(`/empresas/${id}`).then((r) => r.data),

  create: (data: EmpresaCreate) => api.post<Empresa>("/empresas", data).then((r) => r.data),

  update: (id: string, data: Partial<EmpresaCreate>) => api.patch<Empresa>(`/empresas/${id}`, data).then((r) => r.data),

  delete: (id: string) => api.delete(`/empresas/${id}`),

  // Items
  createItem: (empresaId: string, data: EmpresaItemCreate) =>
    api.post<EmpresaItem>(`/empresas/${empresaId}/items`, data).then((r) => r.data),

  updateItem: (itemId: string, data: { title?: string; done?: boolean }) =>
    api.patch<EmpresaItem>(`/empresas/items/${itemId}`, data).then((r) => r.data),

  toggleItem: (itemId: string) =>
    api.patch<EmpresaItem>(`/empresas/items/${itemId}/toggle`).then((r) => r.data),

  deleteItem: (itemId: string) => api.delete(`/empresas/items/${itemId}`),

  // History
  getHistory: (empresaId: string) =>
    api.get<EmpresaHistory[]>(`/empresas/${empresaId}/history`).then((r) => r.data),

  // Channel health (silent-channel-health plan)
  getAccountChannelHealth: (accountId: string) =>
    api
      .get<AccountChannelHealthResponse>(`/eva-platform/accounts/${accountId}/channels/health`)
      .then((r) => r.data),

  listEvaAccountsForLink: () =>
    api
      .get<EvaAccountForLink[]>("/eva-platform/accounts/list-for-link")
      .then((r) => r.data),

  // Billing
  createCheckoutLink: (empresaId: string, data: CheckoutLinkRequest) =>
    api.post<{ checkout_url: string }>(`/empresas/${empresaId}/checkout-link`, data).then((r) => r.data),

  createPortalLink: (empresaId: string) =>
    api.post<{ portal_url: string }>(`/empresas/${empresaId}/portal-link`).then((r) => r.data),
};
