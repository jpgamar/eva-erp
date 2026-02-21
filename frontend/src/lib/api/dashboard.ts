import api from "./client";

export interface DashboardData {
  mrr: number;
  arr: number;
  total_revenue: number;
  total_expenses_usd: number;
  net_profit: number;
  burn_rate: number;
  cash_balance_usd: number | null;
  runway_months: number | null;
  total_customers: number;
  new_customers: number;
  churned_customers: number;
  arpu: number;
  open_tasks: number;
  overdue_tasks: number;
  income_mrr: number;
  income_total_period: number;
  expense_total_usd: number;
  expense_by_category: Record<string, number>;
  expense_recurring_total: number;
  prospect_total: number;
  prospect_by_status: Record<string, number>;
  prospect_urgency: { urgent: number; soso: number; can_wait: number };
  recent_tasks: { id: string; title: string; status: string; due_date: string | null }[];
  vault_combined_usd: number;
  vault_service_count: number;
  vault_by_category: Record<string, number>;
}

export const dashboardApi = {
  summary: (): Promise<DashboardData> => api.get("/dashboard/summary").then(r => r.data),
};
