export interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "member";
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Notification {
  id: string;
  user_id: string;
  type: string;
  title: string;
  body: string;
  link: string | null;
  read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
}

export interface UnreadCountResponse {
  count: number;
}

// Vault
export interface VaultStatus {
  is_setup: boolean;
  is_unlocked: boolean;
}

export interface Credential {
  id: string;
  name: string;
  category: string;
  url: string | null;
  monthly_cost: number | null;
  cost_currency: string;
  monthly_cost_usd: number | null;
  billing_cycle: string | null;
  who_has_access: string[] | null;
  created_at: string;
}

export interface CredentialDetail extends Credential {
  login_url: string | null;
  username: string | null;
  password: string | null;
  api_keys: string | null;
  notes: string | null;
  updated_at: string;
}

export interface CostSummary {
  total_mxn: number;
  total_usd: number;
  combined_usd: number;
  by_category: Record<string, number>;
  service_count: number;
}

export interface AuditLogEntry {
  id: string;
  user_id: string;
  credential_id: string;
  action: string;
  ip_address: string | null;
  created_at: string;
}

// Tasks
export interface Board {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  created_by: string;
  created_at: string;
}

export interface Task {
  id: string;
  board_id: string | null;
  title: string;
  description: string | null;
  status: string;
  assignee_id: string | null;
  priority: string;
  due_date: string | null;
  labels: string[] | null;
  source_meeting_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface TaskDetail extends Task {
  comments: TaskComment[];
}

export interface TaskComment {
  id: string;
  task_id: string;
  user_id: string;
  content: string;
  created_at: string;
}

// Finances
export interface ExchangeRate {
  id: string;
  from_currency: string;
  to_currency: string;
  rate: number;
  effective_date: string;
  source: string;
}

export interface IncomeEntry {
  id: string;
  source: string;
  stripe_payment_id: string | null;
  customer_id: string | null;
  account_id: string | null;
  description: string;
  amount: number;
  currency: string;
  amount_usd: number;
  category: string;
  date: string;
  is_recurring: boolean;
  recurrence_type: "monthly" | "one_time" | "custom";
  custom_interval_months: number | null;
  manual_reason: "offline_transfer" | "cash" | "adjustment" | "correction";
  monthly_amount_usd: number;
  created_at: string;
}

export interface IncomeSummary {
  mrr: number;
  arr: number;
  total_period: number;
  total_period_usd: number;
  mrr_by_currency: Record<string, number>;
  arr_by_currency: Record<string, number>;
  total_period_by_currency: Record<string, number>;
  mom_growth_pct: number | null;
}

export interface Expense {
  id: string;
  name: string;
  description: string | null;
  amount: number;
  currency: string;
  amount_usd: number;
  category: string;
  vendor: string | null;
  paid_by: string;
  is_recurring: boolean;
  recurrence: string | null;
  date: string;
  receipt_url: string | null;
  vault_credential_id: string | null;
  created_at: string;
}

export interface ExpenseSummary {
  total_usd: number;
  by_category: Record<string, number>;
  by_person: Record<string, number>;
  recurring_total_usd: number;
}

export interface InvoiceEntry {
  id: string;
  invoice_number: string;
  customer_id: string | null;
  customer_name: string;
  customer_email: string | null;
  description: string | null;
  line_items_json: unknown[] | null;
  subtotal: number;
  tax: number | null;
  total: number;
  currency: string;
  total_usd: number;
  status: string;
  issue_date: string;
  due_date: string;
  paid_date: string | null;
  notes: string | null;
  created_at: string;
}

export interface CashBalanceEntry {
  id: string;
  amount: number;
  currency: string;
  amount_usd: number;
  date: string;
  notes: string | null;
  created_at: string;
}

export interface ManualDepositEntry {
  id: string;
  amount: number;
  currency: string;
  date: string;
  reason: "manual_bank_deposit" | "adjustment";
  notes: string | null;
  account_id: string | null;
  created_by: string | null;
  created_at: string;
}

export interface StripeReconciliationSummary {
  period: string;
  payments_received: number;
  refunds: number;
  net_received: number;
  payouts_paid: number;
  payouts_failed: number;
  manual_deposits: number;
  manual_adjustments: number;
  gap_to_deposit: number;
  unlinked_payment_events: number;
  unlinked_payout_events: number;
}

export interface StripeReconcileResult {
  fetched_events: number;
  processed_events: number;
  duplicate_events: number;
  ignored_events: number;
  failed_events: number;
}

export interface StripeUnlinkedPaymentEvent {
  stripe_event_id: string;
  stripe_event_type: string;
  stripe_payment_intent_id: string | null;
  stripe_customer_id: string | null;
  customer_id: string | null;
  account_id: string | null;
  amount: number;
  currency: string;
  occurred_at: string;
  unlinked: boolean;
  source: string;
}

export interface StripeUnlinkedPayoutEvent {
  stripe_event_id: string;
  stripe_event_type: string;
  stripe_payout_id: string;
  status: string;
  account_id: string | null;
  amount: number;
  currency: string;
  created_at: string;
  unlinked: boolean;
  source: string;
}

export interface StripeUnlinkedEventsResponse {
  payment_events: StripeUnlinkedPaymentEvent[];
  payout_events: StripeUnlinkedPayoutEvent[];
  payment_count: number;
  payout_count: number;
}

export interface FinanceParityCheck {
  period: string;
  lifecycle_payments_mxn: number;
  legacy_income_mxn: number;
  difference_mxn: number;
  within_threshold: boolean;
}

// Customers
export interface Customer {
  id: string;
  company_name: string;
  contact_name: string;
  contact_email: string | null;
  contact_phone: string | null;
  legal_name: string | null;
  rfc: string | null;
  tax_regime: string | null;
  fiscal_zip: string | null;
  default_cfdi_use: string | null;
  fiscal_email: string | null;
  industry: string | null;
  website: string | null;
  plan_tier: string | null;
  mrr: number | null;
  mrr_currency: string;
  mrr_usd: number | null;
  arr: number | null;
  billing_interval: string | null;
  signup_date: string | null;
  status: string;
  churn_date: string | null;
  churn_reason: string | null;
  stripe_customer_id: string | null;
  lifetime_value: number | null;
  lifetime_value_usd: number | null;
  referral_source: string | null;
  notes: string | null;
  tags: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerSummary {
  total_customers: number;
  active_customers: number;
  mrr_usd: number;
  arpu_usd: number;
  churn_rate_pct: number;
}

// OKRs
export interface KeyResult {
  id: string;
  objective_id: string;
  title: string;
  target_value: number;
  current_value: number;
  unit: string;
  tracking_mode: string;
  auto_metric: string | null;
  start_value: number;
  progress_pct: number;
  created_at: string;
}

export interface Objective {
  id: string;
  period_id: string;
  title: string;
  description: string | null;
  owner_id: string;
  position: number;
  status: string;
  key_results: KeyResult[];
  created_at: string;
}

export interface OKRPeriod {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: string;
  objectives: Objective[];
  created_at: string;
}

// Eva Platform
export interface EvaAccount {
  id: string;
  name: string;
  owner_user_id: string;
  account_type: string;
  partner_id: string | null;
  plan_tier: string | null;
  billing_interval: string | null;
  subscription_status: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AccountDraft {
  id: string;
  name: string;
  account_type: string;
  owner_email: string;
  owner_name: string;
  partner_id: string | null;
  plan_tier: string;
  billing_cycle: string;
  billing_amount: number | null;
  billing_currency: string;
  is_billable: boolean;
  facturapi_org_api_key: string | null;
  notes: string | null;
  status: string;
  prospect_id: string | null;
  provisioned_account_id: string | null;
  created_by: string;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MonitoringOverview {
  open_critical: number;
  open_high: number;
  total_open: number;
  resolved_today: number;
}

export interface MonitoringIssue {
  id: string;
  fingerprint: string;
  source: string;
  category: string;
  severity: string;
  status: string;
  title: string;
  summary: string | null;
  occurrences: number;
  first_seen_at: string;
  last_seen_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export interface ServiceStatus {
  check_key: string | null;
  name: string;
  url: string;
  status: "up" | "down" | "degraded";
  latency_ms: number | null;
  http_status: number | null;
  error: string | null;
  checked_at: string | null;
  critical: boolean | null;
  consecutive_failures: number | null;
  consecutive_successes: number | null;
  last_success_at: string | null;
  stale: boolean | null;
}

export interface ServiceStatusResponse {
  services: ServiceStatus[];
  checked_at: string;
}

export interface MonitoringCheck {
  id: string;
  check_key: string;
  service: string;
  target: string;
  status: string;
  http_status: number | null;
  latency_ms: number | null;
  error_message: string | null;
  details: Record<string, unknown> | null;
  consecutive_failures: number | null;
  consecutive_successes: number | null;
  last_success_at: string | null;
  critical: boolean | null;
  checked_at: string;
}

export interface EvaPartner {
  id: string;
  name: string;
  slug: string;
  brand_name: string | null;
  type: string;
  is_active: boolean;
  contact_email: string | null;
  deal_count: number;
  account_count: number;
  created_at: string;
  updated_at: string;
}

export interface EvaPartnerDetail extends EvaPartner {
  logo_url: string | null;
  primary_color: string | null;
  custom_domain: string | null;
  won_deals: number;
  accounts: EvaAccount[];
  deals: PartnerDeal[];
}

export interface PartnerDeal {
  id: string;
  partner_id: string | null;
  company_name: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  stage: string;
  plan_tier: string;
  billing_cycle: string;
  won_at: string | null;
  lost_at: string | null;
  lost_reason: string | null;
  linked_account_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlatformDashboard {
  active_accounts: number;
  total_accounts: number;
  active_partners: number;
  open_issues: number;
  critical_issues: number;
  draft_accounts_pending: number;
  pricing_billable_accounts: number;
  pricing_configured_accounts: number;
  pricing_coverage_pct: number;
}

export interface AccountPricing {
  account_id: string;
  account_name: string;
  account_is_active: boolean;
  billing_amount: number | null;
  billing_currency: string;
  billing_interval: string;
  is_billable: boolean;
  notes: string | null;
  pricing_complete: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface AccountPricingCoverage {
  active_accounts: number;
  billable_accounts: number;
  configured_accounts: number;
  missing_accounts: number;
  coverage_pct: number;
}

// Infrastructure
export interface RuntimeHost {
  id: string;
  provider_host_id: string;
  name: string;
  region: string;
  host_class: string;
  state: string;
  public_ip: string | null;
  vcpu: number;
  ram_mb: number;
  disk_gb: number;
  max_tenants: number;
  tenant_count: number;
  saturation: number;
  last_heartbeat_at: string | null;
  created_at: string;
}

export interface RuntimeEmployee {
  id: string;
  agent_id: string;
  account_id: string;
  account_name: string | null;
  label: string;
  status: string;
  phone_number: string | null;
  allocation_state: string | null;
  container_name: string | null;
  gateway_port: number | null;
  cpu_reservation_mcpu: number | null;
  ram_reservation_mb: number | null;
  reconnect_risk: string | null;
  whatsapp_connected: boolean;
  telegram_connected: boolean;
  vps_ip: string | null;
}

export interface RuntimeEmployeeDetail extends RuntimeEmployee {
  status_detail: string | null;
  error: string | null;
  connections_state: Record<string, unknown>;
  provisioning_started_at: string | null;
  provisioning_completed_at: string | null;
  host_name: string | null;
  host_ip: string | null;
  queued_reason: string | null;
  placed_at: string | null;
  started_at: string | null;
  recent_events: RuntimeEvent[];
}

export interface RuntimeEvent {
  id: string;
  source: string;
  event_type: string;
  severity: string;
  reason_code: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface DockerContainer {
  name: string;
  state: string;
  status: string;
  ports: string;
  image: string;
  created_at: string;
}

export interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number | null;
  modified_at: string | null;
}

export interface FileContent {
  path: string;
  content: string;
  size: number;
  truncated: boolean;
}

export interface DockerLogs {
  container_name: string;
  lines: string;
  tail: number;
}

// Assistant
export interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantConversation {
  id: string;
  title: string | null;
  messages_json: AssistantMessage[];
  created_at: string;
  updated_at: string;
}
