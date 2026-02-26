import api from "./client";

export interface DashboardData {
  period: string;
  period_label: string;
  is_current_period: boolean;
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
  income_mrr_by_currency: Record<string, number>;
  income_total_period: number;
  income_total_period_by_currency: Record<string, number>;
  expense_total_usd: number;
  expense_total_period_by_currency: Record<string, number>;
  expense_by_category: Record<string, number>;
  expense_recurring_total: number;
  net_profit_by_currency: Record<string, number>;
  prospect_total: number;
  prospect_by_status: Record<string, number>;
  prospect_urgency: { urgent: number; soso: number; can_wait: number };
  recent_tasks: { id: string; title: string; status: string; due_date: string | null }[];
  total_meetings: number;
  upcoming_meetings: number;
  meetings_this_month: number;
  vault_combined_usd: number;
  vault_service_count: number;
  vault_by_category: Record<string, number>;
}

export const dashboardApi = {
  summary: (period?: string): Promise<DashboardData> =>
    api
      .get("/dashboard/summary", { params: period ? { period } : undefined })
      .then(r => r.data),
};
