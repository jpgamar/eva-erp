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
