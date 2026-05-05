import api from "./client";

// ── Types ──────────────────────────────────────────────────────────

export interface PendingItem {
  id: string;
  title: string;
  kind: EmpresaItemKind;
  due_at: string | null;
  start_at: string | null;
  completed_at: string | null;
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

export type LifecycleStage =
  | "prospecto"
  | "interesado"
  | "demo"
  | "negociacion"
  | "implementacion"
  | "operativo"
  | "churn_risk"
  | "inactivo";

export type EmpresaBillingInterval = "monthly" | "annual";

export interface EmpresaListItem {
  id: string;
  name: string;
  logo_url: string | null;
  status: string;
  lifecycle_stage: LifecycleStage;
  ball_on: string | null;
  summary_note: string | null;
  monthly_amount: number | null;
  billing_interval: EmpresaBillingInterval;
  payment_day: number | null;
  last_paid_date: string | null;
  expected_close_date: string | null;
  cancellation_scheduled_at: string | null;
  eva_account_id: string | null;
  auto_match_attempted: boolean;
  grandfathered: boolean;
  version: number;
  subscription_status: string | null;
  current_period_end: string | null;
  person_type: string | null;
  rfc: string | null;
  item_count: number;
  pending_count: number;
  pending_items: PendingItem[];
  next_action: PendingItem | null;
  overdue_count: number;
  health: EmpresaHealth;
}

export interface PreviewCheckoutRequest {
  amount_mxn: number;
}

export interface PreviewCheckoutResponse {
  retention_applicable: boolean;
  base_subtotal_minor: number;
  iva_minor: number;
  isr_retention_minor: number;
  iva_retention_minor: number;
  payable_total_minor: number;
  stripe_charges_tax: boolean;
}

export interface CheckoutLinkRequest {
  amount_mxn: number;
  description: string;
  interval: "month" | "year";
  recipient_email: string;
}

export interface CheckoutLinkResponse {
  checkout_url: string;
  quote: PreviewCheckoutResponse;
}

export interface EmpresaItem {
  id: string;
  empresa_id: string;
  title: string;
  kind: EmpresaItemKind;
  description: string | null;
  contact_method: EmpresaContactMethod | null;
  due_at: string | null;
  start_at: string | null;
  end_at: string | null;
  reminder_at: string | null;
  assigned_to: string | null;
  done: boolean;
  completed_at: string | null;
  created_at: string;
}

export type EmpresaItemKind = "todo" | "event" | "note" | "outreach";
export type EmpresaContactMethod = "sms" | "whatsapp" | "call" | "email" | "visit" | "other";

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
  fiscal_postal_code: string | null;
  cfdi_use: string | null;
  person_type: string | null;
  status: string;
  lifecycle_stage: LifecycleStage;
  ball_on: string | null;
  summary_note: string | null;
  monthly_amount: number | null;
  billing_interval: EmpresaBillingInterval;
  payment_day: number | null;
  last_paid_date: string | null;
  expected_close_date: string | null;
  cancellation_scheduled_at: string | null;
  constancia_object_key: string | null;
  version: number;
  fiscal_sync_pending_at: string | null;
  fiscal_sync_error: string | null;
  grandfathered: boolean;
  eva_account_id: string | null;
  auto_match_attempted: boolean;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  subscription_status: string | null;
  current_period_end: string | null;
  billing_recipient_emails: string[];
  website: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  contact_role: string | null;
  source: string | null;
  referred_by: string | null;
  estimated_plan: string | null;
  estimated_mrr_currency: string | null;
  estimated_mrr_usd: number | null;
  prospect_notes: string | null;
  next_follow_up: string | null;
  assigned_to: string | null;
  tags: string[] | null;
  lost_reason: string | null;
  legacy_prospect_id: string | null;
  created_at: string;
  updated_at: string;
  items: EmpresaItem[];
}

export interface ConstanciaExtractResponse {
  extracted: {
    rfc: string | null;
    legal_name: string | null;
    tax_regime: string | null;
    postal_code: string | null;
    person_type: string | null;
  };
  warnings: string[];
  source: string;
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
  fiscal_postal_code?: string | null;
  cfdi_use?: string | null;
  person_type?: string | null;
  status?: string;
  lifecycle_stage?: LifecycleStage;
  ball_on?: string | null;
  summary_note?: string | null;
  monthly_amount?: number | null;
  billing_interval?: EmpresaBillingInterval;
  payment_day?: number | null;
  last_paid_date?: string | null;
  expected_close_date?: string | null;
  constancia_object_key?: string | null;
  eva_account_id?: string | null;
  website?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  contact_role?: string | null;
  source?: string | null;
  referred_by?: string | null;
  estimated_plan?: string | null;
  estimated_mrr_currency?: string | null;
  estimated_mrr_usd?: number | null;
  prospect_notes?: string | null;
  next_follow_up?: string | null;
  assigned_to?: string | null;
  tags?: string[] | null;
  lost_reason?: string | null;
  billing_recipient_emails?: string[] | null;
}

export interface EmpresaUpdate extends Partial<EmpresaCreate> {
  cancellation_scheduled_at?: string | null;
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
  kind?: EmpresaItemKind;
  description?: string | null;
  contact_method?: EmpresaContactMethod | null;
  due_at?: string | null;
  start_at?: string | null;
  end_at?: string | null;
  reminder_at?: string | null;
  assigned_to?: string | null;
}

export interface EmpresaCalendarItem extends EmpresaItem {
  empresa_name: string;
  logo_url: string | null;
  lifecycle_stage: LifecycleStage;
}

export interface CreateEvaAccountForEmpresaRequest {
  owner_email: string;
  owner_name?: string;
  account_type?: string;
  plan_tier?: string;
  billing_cycle?: string;
  temporary_password?: string | null;
  send_setup_email?: boolean;
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

export interface EmpresaInteraction {
  id: string;
  empresa_id: string;
  type: string;
  summary: string;
  date: string;
  created_by: string;
  created_at: string;
}

// ── API ────────────────────────────────────────────────────────────

export const empresasApi = {
  list: (search?: string) =>
    api.get<EmpresaListItem[]>("/empresas", { params: search ? { search } : undefined }).then((r) => r.data),

  get: (id: string) => api.get<Empresa>(`/empresas/${id}`).then((r) => r.data),

  calendar: (params: { start: string; end: string; include_completed?: boolean }) =>
    api.get<EmpresaCalendarItem[]>("/empresas/calendar", { params }).then((r) => r.data),

  create: (data: EmpresaCreate) => api.post<Empresa>("/empresas", data).then((r) => r.data),

  update: (id: string, data: Partial<EmpresaCreate>, version?: number) =>
    api
      .patch<Empresa>(`/empresas/${id}`, data, {
        headers: version !== undefined ? { "If-Match": String(version) } : undefined,
      })
      .then((r) => r.data),

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

  getInteractions: (empresaId: string) =>
    api.get<EmpresaInteraction[]>(`/empresas/${empresaId}/interactions`).then((r) => r.data),

  // Channel health (silent-channel-health plan)
  getAccountChannelHealth: (accountId: string) =>
    api
      .get<AccountChannelHealthResponse>(`/eva-platform/accounts/${accountId}/channels/health`)
      .then((r) => r.data),

  listEvaAccountsForLink: () =>
    api
      .get<EvaAccountForLink[]>("/eva-platform/accounts/list-for-link")
      .then((r) => r.data),

  linkEvaAccount: (empresaId: string, accountId: string, expectedVersion?: number) =>
    api
      .post<Empresa>(`/empresas/${empresaId}/link-eva-account`, {
        account_id: accountId,
        expected_version: expectedVersion,
      })
      .then((r) => r.data),

  createEvaAccount: (empresaId: string, data: CreateEvaAccountForEmpresaRequest) =>
    api.post(`/empresas/${empresaId}/eva-account`, data).then((r) => r.data),

  // Billing
  previewCheckout: (empresaId: string, data: PreviewCheckoutRequest) =>
    api.post<PreviewCheckoutResponse>(`/empresas/${empresaId}/preview-checkout`, data).then((r) => r.data),

  createCheckoutLink: (empresaId: string, data: CheckoutLinkRequest) =>
    api.post<CheckoutLinkResponse>(`/empresas/${empresaId}/checkout-link`, data).then((r) => r.data),

  createPortalLink: (empresaId: string) =>
    api.post<{ portal_url: string }>(`/empresas/${empresaId}/portal-link`).then((r) => r.data),

  extractConstancia: (empresaId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api
      .post<ConstanciaExtractResponse>(`/empresas/${empresaId}/extract-constancia`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
};
