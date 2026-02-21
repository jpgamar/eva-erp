"use client";

import { useEffect, useState } from "react";
import {
  TrendingUp, TrendingDown, Users, DollarSign,
  ArrowUpRight, Wallet, Target, Lock, CheckSquare,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { dashboardApi, type DashboardData } from "@/lib/api/dashboard";

function fmt(amount: number | null | undefined, currency = "USD") {
  if (amount == null) return "\u2014";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })} ${currency}`;
}

const EXPENSE_LABELS: Record<string, string> = {
  infrastructure: "Infrastructure",
  ai_apis: "AI APIs",
  communication: "Communication",
  payment_fees: "Payment Fees",
  domains_hosting: "Domains/Hosting",
  marketing: "Marketing",
  legal_accounting: "Legal & Accounting",
  contractors: "Contractors",
  office: "Office",
  software_tools: "Software Tools",
  other: "Other",
};

const EXPENSE_COLORS: Record<string, string> = {
  infrastructure: "bg-blue-500",
  ai_apis: "bg-violet-500",
  communication: "bg-cyan-500",
  payment_fees: "bg-orange-500",
  domains_hosting: "bg-teal-500",
  marketing: "bg-pink-500",
  legal_accounting: "bg-slate-500",
  contractors: "bg-amber-500",
  office: "bg-lime-500",
  software_tools: "bg-indigo-500",
  other: "bg-gray-400",
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardApi.summary()
      .then(setData)
      .catch(() => toast.error("Failed to load dashboard data"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!data) return null;

  const allExpenses = Object.entries(data.expense_by_category).sort(([, a], [, b]) => b - a);
  const topExpenses = allExpenses.slice(0, 3);

  const topVaultCats = Object.entries(data.vault_by_category).sort(([, a], [, b]) => b - a).slice(0, 3);

  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-7rem)] animate-erp-entrance">

      {/* ── KPI Hero Row ────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 shrink-0">

        {/* MRR */}
        <div className="relative overflow-hidden rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="absolute -right-4 -top-4 h-20 w-20 rounded-full bg-emerald-100/60" />
          <div className="absolute -right-2 -top-2 h-12 w-12 rounded-full bg-emerald-100/60" />
          <div className="relative">
            <div className="flex items-center gap-2 mb-0.5">
              <DollarSign className="h-3.5 w-3.5 text-emerald-500" />
              <p className="text-xs font-medium text-emerald-600/70">MRR</p>
            </div>
            <p className="font-mono text-2xl font-bold tracking-tight text-emerald-900">{fmt(data.mrr)}</p>
          </div>
        </div>

        {/* Customers */}
        <div className="relative overflow-hidden rounded-2xl border border-indigo-200 bg-indigo-50 p-4">
          <div className="absolute -right-4 -top-4 h-20 w-20 rounded-full bg-indigo-100/60" />
          <div className="absolute -right-2 -top-2 h-12 w-12 rounded-full bg-indigo-100/60" />
          <div className="relative">
            <div className="flex items-center gap-2 mb-0.5">
              <Users className="h-3.5 w-3.5 text-indigo-500" />
              <p className="text-xs font-medium text-indigo-600/70">Active Customers</p>
            </div>
            <p className="font-mono text-2xl font-bold tracking-tight text-indigo-900">{data.total_customers}</p>
            <div className="mt-1.5 flex items-center gap-3">
              <span className="text-xs text-indigo-600/70">
                <span className="font-semibold text-indigo-700">+{data.new_customers}</span> new
              </span>
              <span className="text-xs text-indigo-600/70">
                <span className="font-semibold text-indigo-700">-{data.churned_customers}</span> churned
              </span>
            </div>
          </div>
        </div>

        {/* Net P/L */}
        <div className={`relative overflow-hidden rounded-2xl border p-4 ${
          data.net_profit >= 0
            ? "border-green-200 bg-green-50"
            : "border-red-200 bg-red-50"
        }`}>
          <div className={`absolute -right-4 -top-4 h-20 w-20 rounded-full ${data.net_profit >= 0 ? "bg-green-100/60" : "bg-red-100/60"}`} />
          <div className={`absolute -right-2 -top-2 h-12 w-12 rounded-full ${data.net_profit >= 0 ? "bg-green-100/60" : "bg-red-100/60"}`} />
          <div className="relative">
            <div className="flex items-center gap-2 mb-0.5">
              {data.net_profit >= 0
                ? <TrendingUp className="h-3.5 w-3.5 text-green-500" />
                : <TrendingDown className="h-3.5 w-3.5 text-red-500" />}
              <p className={`text-xs font-medium ${data.net_profit >= 0 ? "text-green-600/70" : "text-red-600/70"}`}>Net P/L</p>
            </div>
            <p className={`font-mono text-2xl font-bold tracking-tight ${data.net_profit >= 0 ? "text-green-900" : "text-red-900"}`}>{fmt(data.net_profit)}</p>
            <div className="mt-1.5">
              <span className={`text-xs ${data.net_profit >= 0 ? "text-green-600/60" : "text-red-600/60"}`}>Revenue − Expenses</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Section Cards — stretch to fill remaining height ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 flex-1 min-h-0">

        {/* Finances */}
        <Link href="/finances" className="group flex">
          <div className="rounded-2xl border border-border bg-card overflow-hidden transition-all hover:shadow-lg hover:border-accent/40 w-full flex flex-col">
            <div className="h-1 bg-gradient-to-r from-emerald-400 to-emerald-500 shrink-0" />
            <div className="p-5 flex flex-col flex-1">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50">
                    <Wallet className="h-4 w-4 text-emerald-600" />
                  </div>
                  <p className="text-sm font-semibold text-foreground">Finances</p>
                </div>
                <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </div>
              <div className="space-y-3 flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">Revenue</span>
                  <span className="font-mono text-sm font-semibold text-foreground">
                    {fmt(data.income_total_period)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">Expenses</span>
                  <span className="font-mono text-sm font-semibold text-foreground">
                    {fmt(data.expense_total_usd)}
                  </span>
                </div>
                {data.cash_balance_usd != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Cash balance</span>
                    <span className="font-mono text-sm font-semibold text-foreground">{fmt(data.cash_balance_usd)}</span>
                  </div>
                )}
                {topExpenses.length > 0 && (
                  <div className="pt-3 mt-auto border-t border-border/50">
                    <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2">Top Expenses</p>
                    {topExpenses.map(([cat, amount]) => (
                      <div key={cat} className="flex items-center justify-between py-0.5">
                        <div className="flex items-center gap-1.5">
                          <div className={`h-2 w-2 rounded-full ${EXPENSE_COLORS[cat] || "bg-gray-400"}`} />
                          <span className="text-xs text-muted">{EXPENSE_LABELS[cat] || cat}</span>
                        </div>
                        <span className="font-mono text-xs text-foreground">{fmt(amount)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </Link>

        {/* Prospects */}
        <Link href="/prospects" className="group flex">
          <div className="rounded-2xl border border-border bg-card overflow-hidden transition-all hover:shadow-lg hover:border-accent/40 w-full flex flex-col">
            <div className="h-1 bg-gradient-to-r from-indigo-400 to-indigo-500 shrink-0" />
            <div className="p-5 flex flex-col flex-1">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50">
                    <Target className="h-4 w-4 text-indigo-600" />
                  </div>
                  <p className="text-sm font-semibold text-foreground">Prospects</p>
                </div>
                <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </div>
              <div className="space-y-3 flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">In pipeline</span>
                  <span className="font-mono text-sm font-semibold text-foreground">
                    {data.prospect_total}
                  </span>
                </div>
                {data.prospect_by_status.won != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Won</span>
                    <span className="font-mono text-sm font-semibold text-green-600">{data.prospect_by_status.won}</span>
                  </div>
                )}
                {data.prospect_by_status.lost != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Lost</span>
                    <span className="font-mono text-sm font-semibold text-red-500">{data.prospect_by_status.lost}</span>
                  </div>
                )}
                <div className="pt-3 mt-auto border-t border-border/50">
                  <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2">By Urgency</p>
                  <div className="flex items-center justify-between py-0.5">
                    <div className="flex items-center gap-1.5">
                      <div className="h-2 w-2 rounded-full bg-red-500" />
                      <span className="text-xs text-muted">Urgent</span>
                    </div>
                    <span className="font-mono text-xs text-foreground">{data.prospect_urgency.urgent}</span>
                  </div>
                  <div className="flex items-center justify-between py-0.5">
                    <div className="flex items-center gap-1.5">
                      <div className="h-2 w-2 rounded-full bg-amber-500" />
                      <span className="text-xs text-muted">So-so</span>
                    </div>
                    <span className="font-mono text-xs text-foreground">{data.prospect_urgency.soso}</span>
                  </div>
                  <div className="flex items-center justify-between py-0.5">
                    <div className="flex items-center gap-1.5">
                      <div className="h-2 w-2 rounded-full bg-gray-400" />
                      <span className="text-xs text-muted">Can wait</span>
                    </div>
                    <span className="font-mono text-xs text-foreground">{data.prospect_urgency.can_wait}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Link>

        {/* Tasks */}
        <div className="rounded-2xl border border-border bg-card overflow-hidden transition-all hover:shadow-lg hover:border-accent/40 flex flex-col">
          <div className="h-1 bg-gradient-to-r from-sky-400 to-sky-500 shrink-0" />
          <div className="p-5 flex flex-col flex-1">
            <Link href="/tasks" className="group">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-50">
                    <CheckSquare className="h-4 w-4 text-sky-600" />
                  </div>
                  <p className="text-sm font-semibold text-foreground">Tasks</p>
                </div>
                <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </div>
            </Link>
            <div className="space-y-3 flex-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted">Open</span>
                <span className="font-mono text-sm font-semibold text-foreground">{data.open_tasks}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted">Overdue</span>
                <span className={`font-mono text-sm font-semibold ${data.overdue_tasks > 0 ? "text-red-500" : "text-foreground"}`}>{data.overdue_tasks}</span>
              </div>
              {data.recent_tasks.length > 0 && (
                <div className="pt-3 mt-auto border-t border-border/50">
                  <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2">Active Tasks</p>
                  {data.recent_tasks.map((task) => (
                    <div key={task.id} className="flex items-center gap-2 py-1">
                      <div className={`h-2 w-2 rounded-full shrink-0 ${task.status === "in_progress" ? "bg-blue-500" : "bg-gray-400"}`} />
                      <span className="text-xs text-foreground truncate flex-1">{task.title}</span>
                      {task.due_date && (
                        <span className={`text-[10px] shrink-0 ${new Date(task.due_date) < new Date() && task.status !== "done" ? "text-red-500" : "text-muted-foreground"}`}>
                          {new Date(task.due_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                        </span>
                      )}
                    </div>
                  ))}
                  <Link href="/tasks" className="text-[10px] text-sky-600 hover:text-sky-700 font-medium mt-1 block">
                    View all tasks
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Vault */}
        <div className="rounded-2xl border border-border bg-card overflow-hidden transition-all hover:shadow-lg hover:border-accent/40 flex flex-col">
          <div className="h-1 bg-gradient-to-r from-amber-400 to-amber-500 shrink-0" />
          <div className="p-5 flex flex-col flex-1">
            <Link href="/vault" className="group">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50">
                    <Lock className="h-4 w-4 text-amber-600" />
                  </div>
                  <p className="text-sm font-semibold text-foreground">Vault</p>
                </div>
                <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </div>
            </Link>
            <div className="space-y-3 flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">Monthly cost</span>
                  <span className="font-mono text-sm font-semibold text-foreground">{fmt(data.vault_combined_usd)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">Services</span>
                  <span className="font-mono text-sm font-semibold text-foreground">{data.vault_service_count}</span>
                </div>
                {topVaultCats.length > 0 && (
                  <div className="pt-3 mt-auto border-t border-border/50">
                    <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2">Top Categories</p>
                    {topVaultCats.map(([cat, amount]) => (
                      <div key={cat} className="flex items-center justify-between py-0.5">
                        <span className="text-xs text-muted capitalize">{cat.replace(/_/g, " ")}</span>
                        <span className="font-mono text-xs text-foreground">{fmt(amount)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
          </div>
        </div>
      </div>
    </div>
  );
}
