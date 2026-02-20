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
  monthly_cost_mxn: number | null;
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
  combined_mxn: number;
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

// Tasks / Kanban
export interface Board {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  position: number;
  created_by: string;
  created_at: string;
}

export interface BoardDetail extends Board {
  columns: Column[];
}

export interface Column {
  id: string;
  board_id: string;
  name: string;
  position: number;
  color: string;
  tasks: Task[];
}

export interface Task {
  id: string;
  column_id: string;
  board_id: string;
  title: string;
  description: string | null;
  assignee_id: string | null;
  priority: string;
  due_date: string | null;
  labels: string[] | null;
  position: number;
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
  description: string;
  amount: number;
  currency: string;
  amount_mxn: number;
  category: string;
  date: string;
  is_recurring: boolean;
  created_at: string;
}

export interface IncomeSummary {
  mrr: number;
  arr: number;
  total_period: number;
  total_period_mxn: number;
  mom_growth_pct: number | null;
}

export interface Expense {
  id: string;
  name: string;
  description: string | null;
  amount: number;
  currency: string;
  amount_mxn: number;
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
  total_mxn: number;
  by_category: Record<string, number>;
  by_person: Record<string, number>;
  recurring_total_mxn: number;
}

export interface InvoiceEntry {
  id: string;
  invoice_number: string;
  customer_id: string | null;
  customer_name: string;
  customer_email: string | null;
  description: string | null;
  line_items_json: any[] | null;
  subtotal: number;
  tax: number | null;
  total: number;
  currency: string;
  total_mxn: number;
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
  amount_mxn: number;
  date: string;
  notes: string | null;
  created_at: string;
}

// Customers
export interface Customer {
  id: string;
  company_name: string;
  contact_name: string;
  contact_email: string | null;
  contact_phone: string | null;
  industry: string | null;
  website: string | null;
  plan_tier: string | null;
  mrr: number | null;
  mrr_currency: string;
  mrr_mxn: number | null;
  arr: number | null;
  billing_interval: string | null;
  signup_date: string | null;
  status: string;
  churn_date: string | null;
  churn_reason: string | null;
  stripe_customer_id: string | null;
  lifetime_value: number | null;
  lifetime_value_mxn: number | null;
  referral_source: string | null;
  notes: string | null;
  tags: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerSummary {
  total_customers: number;
  active_customers: number;
  mrr_mxn: number;
  arpu_mxn: number;
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
