"use client";

import { useEffect, useState } from "react";
import {
  TrendingUp, TrendingDown, Users, DollarSign,
  ArrowUpRight, Wallet, Target, CheckSquare, CalendarDays,
  Building2, Activity, Handshake, AlertTriangle, FileText,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { dashboardApi, type DashboardData } from "@/lib/api/dashboard";
import { evaPlatformApi } from "@/lib/api/eva-platform";
import type { PlatformDashboard } from "@/types";

function fmt(amount: number | null | undefined, currency = "USD") {
  if (amount == null) return "\u2014";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })} ${currency}`;
}

function sortedCurrencyEntries(values: Record<string, number> | null | undefined): [string, number][] {
  const entries = Object.entries(values || {})
    .map(([currency, amount]) => [currency, Number(amount)] as [string, number])
    .filter(([, amount]) => Number.isFinite(amount));
  return entries.sort(([a], [b]) => {
    if (a === "MXN") return -1;
    if (b === "MXN") return 1;
    if (a === "USD") return -1;
    if (b === "USD") return 1;
    return a.localeCompare(b);
  });
}

const PERIOD_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/;

function isValidPeriod(value: string | null): value is string {
  return value != null && PERIOD_PATTERN.test(value);
}

function toPeriodKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
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
  const [platform, setPlatform] = useState<PlatformDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const searchParams = useSearchParams();
  const requestedPeriod = searchParams.get("period");
  const period = isValidPeriod(requestedPeriod) ? requestedPeriod : undefined;
  const currentPeriod = toPeriodKey(new Date());

  useEffect(() => {
    const loadPlatform = !period || period === currentPeriod;
    setLoading(true);
    Promise.all([
      dashboardApi.summary(period),
      loadPlatform ? evaPlatformApi.dashboard().catch(() => null) : Promise.resolve(null),
    ])
      .then(([d, p]) => { setData(d); setPlatform(p); })
      .catch(() => toast.error("Failed to load dashboard data"))
      .finally(() => setLoading(false));
  }, [period, currentPeriod]);

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
  const incomeMrrByCurrency = sortedCurrencyEntries(data.income_mrr_by_currency);
  const incomeMonthByCurrency = sortedCurrencyEntries(data.income_total_period_by_currency);
  const expenseMonthByCurrency = sortedCurrencyEntries(data.expense_total_period_by_currency);
  const netProfitByCurrency = sortedCurrencyEntries(data.net_profit_by_currency);
  const hasNegativeNet = netProfitByCurrency.some(([, amount]) => amount < 0);

  const topVaultCats = Object.entries(data.vault_by_category).sort(([, a], [, b]) => b - a).slice(0, 3);

  return (
    <div className="flex flex-col gap-4 animate-erp-entrance">
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
            {incomeMrrByCurrency.length === 0 ? (
              <p className="font-mono text-2xl font-bold tracking-tight text-emerald-900">-</p>
            ) : (
              <div className="space-y-0.5">
                {incomeMrrByCurrency.map(([currency, amount]) => (
                  <p key={currency} className="font-mono text-xl font-bold tracking-tight text-emerald-900">{fmt(amount, currency)}</p>
                ))}
              </div>
            )}
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
          hasNegativeNet ? "border-red-200 bg-red-50" : "border-green-200 bg-green-50"
        }`}>
          <div className={`absolute -right-4 -top-4 h-20 w-20 rounded-full ${hasNegativeNet ? "bg-red-100/60" : "bg-green-100/60"}`} />
          <div className={`absolute -right-2 -top-2 h-12 w-12 rounded-full ${hasNegativeNet ? "bg-red-100/60" : "bg-green-100/60"}`} />
          <div className="relative">
            <div className="flex items-center gap-2 mb-0.5">
              {hasNegativeNet
                ? <TrendingDown className="h-3.5 w-3.5 text-red-500" />
                : <TrendingUp className="h-3.5 w-3.5 text-green-500" />}
              <p className={`text-xs font-medium ${hasNegativeNet ? "text-red-600/70" : "text-green-600/70"}`}>Net P/L</p>
            </div>
            {netProfitByCurrency.length === 0 ? (
              <p className="font-mono text-2xl font-bold tracking-tight text-foreground">-</p>
            ) : (
              <div className="space-y-0.5">
                {netProfitByCurrency.map(([currency, amount]) => (
                  <p key={currency} className={`font-mono text-xl font-bold tracking-tight ${amount >= 0 ? "text-green-900" : "text-red-900"}`}>
                    {fmt(amount, currency)}
                  </p>
                ))}
              </div>
            )}
            <div className="mt-1.5">
              <span className={`text-xs ${hasNegativeNet ? "text-red-600/60" : "text-green-600/60"}`}>Revenue − Expenses</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Section Cards — stretch to fill remaining height ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

        {/* Finances */}
        {(() => {
          const expTotal = allExpenses.reduce((s, [, v]) => s + v, 0) || 1;
          return (
            <Link href="/finances" className="group flex">
              <div className="rounded-2xl bg-card overflow-hidden transition-all hover:shadow-lg w-full">
                <div className="h-1 bg-gradient-to-r from-emerald-400 to-emerald-500" />
                <div className="p-6">
                  <div className="flex items-center justify-between mb-5">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50">
                        <Wallet className="h-4 w-4 text-emerald-600" />
                      </div>
                      <p className="text-sm font-semibold text-foreground">Finances</p>
                    </div>
                    <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                  </div>

                  {/* Revenue vs Expenses bars */}
                  <div className="space-y-2.5">
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] text-muted">Revenue</span>
                        <span className="font-mono text-xs font-semibold text-emerald-700">
                          {incomeMonthByCurrency.length === 0 ? "-" : `${incomeMonthByCurrency.length} currencies`}
                        </span>
                      </div>
                      <div className="space-y-0.5">
                        {incomeMonthByCurrency.length === 0 ? (
                          <p className="font-mono text-xs text-muted">-</p>
                        ) : incomeMonthByCurrency.map(([currency, amount]) => (
                          <p key={`rev-${currency}`} className="font-mono text-xs font-semibold text-emerald-700">{fmt(amount, currency)}</p>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] text-muted">Expenses</span>
                        <span className="font-mono text-xs font-semibold text-red-600">
                          {expenseMonthByCurrency.length === 0 ? "-" : `${expenseMonthByCurrency.length} currencies`}
                        </span>
                      </div>
                      <div className="space-y-0.5">
                        {expenseMonthByCurrency.length === 0 ? (
                          <p className="font-mono text-xs text-muted">-</p>
                        ) : expenseMonthByCurrency.map(([currency, amount]) => (
                          <p key={`exp-${currency}`} className="font-mono text-xs font-semibold text-red-600">{fmt(amount, currency)}</p>
                        ))}
                      </div>
                    </div>
                    {data.cash_balance_usd != null && (
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[11px] text-muted">Cash balance</span>
                        <span className="font-mono text-xs font-bold text-foreground">{fmt(data.cash_balance_usd)}</span>
                      </div>
                    )}
                  </div>

                  {/* Expense breakdown stacked bar */}
                  {allExpenses.length > 0 && (
                    <div className="pt-4 mt-4 border-t border-border/50">
                      <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2">Expense Breakdown</p>
                      <div className="h-3 rounded-full overflow-hidden flex">
                        {allExpenses.map(([cat, amount]) => (
                          <div
                            key={cat}
                            className={`h-full first:rounded-l-full last:rounded-r-full ${EXPENSE_COLORS[cat] || "bg-gray-400"}`}
                            style={{ width: `${(amount / expTotal) * 100}%` }}
                            title={`${EXPENSE_LABELS[cat] || cat}: ${fmt(amount)}`}
                          />
                        ))}
                      </div>
                      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2">
                        {topExpenses.map(([cat]) => (
                          <div key={cat} className="flex items-center gap-1">
                            <div className={`h-1.5 w-1.5 rounded-full ${EXPENSE_COLORS[cat] || "bg-gray-400"}`} />
                            <span className="text-[10px] text-muted">{EXPENSE_LABELS[cat] || cat}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </Link>
          );
        })()}

        {/* Prospects */}
        {(() => {
          const { urgent, soso, can_wait } = data.prospect_urgency;
          const urgTotal = urgent + soso + can_wait || 1;
          const statusEntries = Object.entries(data.prospect_by_status).sort(([, a], [, b]) => b - a);
          const STATUS_COLORS: Record<string, string> = {
            new: "bg-blue-500", contacted: "bg-cyan-500", qualified: "bg-indigo-500",
            proposal: "bg-violet-500", negotiation: "bg-purple-500", won: "bg-emerald-500",
            lost: "bg-red-500", inactive: "bg-gray-400",
          };
          return (
            <Link href="/prospects" className="group flex">
              <div className="rounded-2xl bg-card overflow-hidden transition-all hover:shadow-lg w-full">
                <div className="h-1 bg-gradient-to-r from-indigo-400 to-indigo-500" />
                <div className="p-6">
                  <div className="flex items-center justify-between mb-5">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50">
                        <Target className="h-4 w-4 text-indigo-600" />
                      </div>
                      <p className="text-sm font-semibold text-foreground">Prospects</p>
                    </div>
                    <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                  </div>

                  {/* Pipeline hero number */}
                  <div className="text-center mb-4">
                    <p className="font-mono text-3xl font-bold text-foreground">{data.prospect_total}</p>
                    <p className="text-[10px] text-muted uppercase tracking-wider mt-0.5">In Pipeline</p>
                  </div>

                  {/* Status funnel bars */}
                  {statusEntries.length > 0 && (
                    <div className="space-y-2 mb-4">
                      {statusEntries.slice(0, 4).map(([status, count]) => (
                        <div key={status} className="flex items-center gap-2">
                          <span className="text-[10px] text-muted w-16 truncate capitalize">{status}</span>
                          <div className="flex-1 h-1.5 rounded-full bg-muted/20 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${STATUS_COLORS[status] || "bg-gray-400"} transition-all duration-700`}
                              style={{ width: `${(count / data.prospect_total) * 100}%` }}
                            />
                          </div>
                          <span className="font-mono text-[10px] font-semibold text-foreground w-5 text-right">{count}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Urgency segmented bar */}
                  <div className="pt-4 mt-4 border-t border-border/50">
                    <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2">Urgency</p>
                    <div className="h-3 rounded-full overflow-hidden flex">
                      {urgent > 0 && <div className="h-full bg-red-500" style={{ width: `${(urgent / urgTotal) * 100}%` }} />}
                      {soso > 0 && <div className="h-full bg-amber-400" style={{ width: `${(soso / urgTotal) * 100}%` }} />}
                      {can_wait > 0 && <div className="h-full bg-gray-300" style={{ width: `${(can_wait / urgTotal) * 100}%` }} />}
                    </div>
                    <div className="flex justify-between mt-1.5">
                      <span className="text-[10px] text-red-600 font-medium">{urgent} urgent</span>
                      <span className="text-[10px] text-amber-600 font-medium">{soso} so-so</span>
                      <span className="text-[10px] text-muted font-medium">{can_wait} wait</span>
                    </div>
                  </div>
                </div>
              </div>
            </Link>
          );
        })()}

        {/* Tasks */}
        {(() => {
          const total = data.open_tasks || 1;
          const overdueRatio = Math.min(data.overdue_tasks / total, 1);
          const healthyRatio = 1 - overdueRatio;
          const circumference = 2 * Math.PI * 36;
          return (
            <div className="rounded-2xl bg-card overflow-hidden transition-all hover:shadow-lg">
              <div className="h-1 bg-gradient-to-r from-sky-400 to-sky-500" />
              <div className="p-6">
                <Link href="/tasks" className="group">
                  <div className="flex items-center justify-between mb-5">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-50">
                        <CheckSquare className="h-4 w-4 text-sky-600" />
                      </div>
                      <p className="text-sm font-semibold text-foreground">Tasks</p>
                    </div>
                    <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                  </div>
                </Link>

                {/* Ring chart + stats */}
                <div className="flex items-center gap-4 mb-4">
                  <div className="relative h-[76px] w-[76px] shrink-0">
                    <svg viewBox="0 0 80 80" className="h-full w-full -rotate-90">
                      <circle cx="40" cy="40" r="36" fill="none" stroke="currentColor" className="text-muted/15" strokeWidth="7" />
                      <circle cx="40" cy="40" r="36" fill="none" stroke="currentColor" className="text-sky-500" strokeWidth="7" strokeLinecap="round"
                        strokeDasharray={`${healthyRatio * circumference} ${circumference}`} />
                      {data.overdue_tasks > 0 && (
                        <circle cx="40" cy="40" r="36" fill="none" stroke="currentColor" className="text-red-500" strokeWidth="7" strokeLinecap="round"
                          strokeDasharray={`${overdueRatio * circumference} ${circumference}`}
                          strokeDashoffset={`${-healthyRatio * circumference}`} />
                      )}
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="font-mono text-lg font-bold text-foreground">{data.open_tasks}</span>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <div className="h-2.5 w-2.5 rounded-full bg-sky-500" />
                      <span className="text-xs text-muted">On track</span>
                      <span className="font-mono text-xs font-semibold text-foreground ml-auto">{data.open_tasks - data.overdue_tasks}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="h-2.5 w-2.5 rounded-full bg-red-500" />
                      <span className="text-xs text-muted">Overdue</span>
                      <span className={`font-mono text-xs font-semibold ml-auto ${data.overdue_tasks > 0 ? "text-red-500" : "text-foreground"}`}>{data.overdue_tasks}</span>
                    </div>
                  </div>
                </div>

                {/* Active task list */}
                {data.recent_tasks.length > 0 && (
                  <div className="pt-4 mt-4 border-t border-border/50">
                    <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2">Active Tasks</p>
                    {data.recent_tasks.map((task) => (
                      <div key={task.id} className="flex items-center gap-2 py-1">
                        <div className={`h-2 w-2 rounded-full shrink-0 ${task.status === "in_progress" ? "bg-blue-500 ring-2 ring-blue-500/20" : "bg-gray-300"}`} />
                        <span className="text-xs text-foreground truncate flex-1">{task.title}</span>
                        {task.due_date && (
                          <span className={`text-[10px] shrink-0 font-medium px-1.5 py-0.5 rounded ${
                            new Date(task.due_date) < new Date() && task.status !== "done"
                              ? "bg-red-50 text-red-600"
                              : "text-muted-foreground"
                          }`}>
                            {new Date(task.due_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                          </span>
                        )}
                      </div>
                    ))}
                    <Link href="/tasks" className="text-[10px] text-sky-600 hover:text-sky-700 font-medium mt-1.5 block">
                      View all tasks
                    </Link>
                  </div>
                )}
              </div>
            </div>
          );
        })()}

        {/* Meetings */}
        <Link href="/meetings" className="group flex">
          <div className="rounded-2xl bg-card overflow-hidden transition-all hover:shadow-lg w-full">
            <div className="h-1 bg-gradient-to-r from-cyan-400 to-cyan-500" />
            <div className="p-6">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-50">
                    <CalendarDays className="h-4 w-4 text-cyan-600" />
                  </div>
                  <p className="text-sm font-semibold text-foreground">Meetings</p>
                </div>
                <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </div>

              <div className="text-center mb-4">
                <p className="font-mono text-3xl font-bold text-foreground">{data.upcoming_meetings}</p>
                <p className="text-[10px] text-muted uppercase tracking-wider mt-0.5">Upcoming</p>
              </div>

              <div className="pt-4 mt-4 border-t border-border/50 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">This month</span>
                  <span className="font-mono text-xs font-semibold text-foreground">{data.meetings_this_month}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">Total scheduled</span>
                  <span className="font-mono text-xs font-semibold text-foreground">{data.total_meetings}</span>
                </div>
              </div>
            </div>
          </div>
        </Link>

        {/* Vault / Eva Platform */}
        {(() => {
          const vaultMax = topVaultCats.length > 0 ? topVaultCats[0][1] : 1;
          const VAULT_CAT_COLORS: Record<string, string> = {
            infrastructure: "from-blue-400 to-blue-500",
            ai: "from-violet-400 to-violet-500",
            communication: "from-cyan-400 to-cyan-500",
            marketing: "from-pink-400 to-pink-500",
            analytics: "from-teal-400 to-teal-500",
            development: "from-indigo-400 to-indigo-500",
            design: "from-fuchsia-400 to-fuchsia-500",
            security: "from-orange-400 to-orange-500",
          };
          return (
            <div className="rounded-2xl bg-card overflow-hidden transition-all hover:shadow-lg">
              <div className="h-1 bg-gradient-to-r from-amber-400 to-amber-500" />
              <div className="p-6">
                <Link href="/vault" className="group">
                  <div className="flex items-center justify-between mb-5">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50">
                        <Wallet className="h-4 w-4 text-amber-600" />
                      </div>
                      <p className="text-sm font-semibold text-foreground">Vault</p>
                    </div>
                    <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                  </div>
                </Link>

                {/* Hero cost + services badge */}
                <div className="text-center mb-4">
                  <p className="font-mono text-2xl font-bold text-foreground">{fmt(data.vault_combined_usd)}</p>
                  <p className="text-[10px] text-muted uppercase tracking-wider mt-0.5">Monthly Cost</p>
                  <div className="inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200/60">
                    <Wallet className="h-2.5 w-2.5 text-amber-500" />
                    <span className="text-[10px] font-semibold text-amber-700">{data.vault_service_count} services</span>
                  </div>
                </div>

                {/* Category horizontal bars */}
                {topVaultCats.length > 0 && (
                  <div className="pt-4 mt-4 border-t border-border/50">
                    <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2.5">Cost by Category</p>
                    <div className="space-y-2.5">
                      {topVaultCats.map(([cat, amount]) => (
                        <div key={cat}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] text-muted capitalize">{cat.replace(/_/g, " ")}</span>
                            <span className="font-mono text-[10px] font-semibold text-foreground">{fmt(amount)}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-muted/20 overflow-hidden">
                            <div
                              className={`h-full rounded-full bg-gradient-to-r ${VAULT_CAT_COLORS[cat] || "from-amber-400 to-amber-500"} transition-all duration-700`}
                              style={{ width: `${(amount / vaultMax) * 100}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })()}
      </div>

      {/* ── Eva Platform ─────────────────────────────── */}
      {platform && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link href="/eva-customers" className="group">
            <div className="rounded-2xl bg-card overflow-hidden transition-all hover:shadow-lg">
              <div className="h-1 bg-gradient-to-r from-violet-400 to-violet-500" />
              <div className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-50">
                      <Building2 className="h-4 w-4 text-violet-600" />
                    </div>
                    <p className="text-sm font-semibold text-foreground">Accounts</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </div>
                <p className="font-mono text-2xl font-bold text-foreground">{platform.active_accounts}</p>
                <p className="text-[10px] text-muted mt-0.5">{platform.total_accounts} total</p>
              </div>
            </div>
          </Link>

          <Link href="/partners" className="group">
            <div className="rounded-2xl bg-card overflow-hidden transition-all hover:shadow-lg">
              <div className="h-1 bg-gradient-to-r from-teal-400 to-teal-500" />
              <div className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-50">
                      <Handshake className="h-4 w-4 text-teal-600" />
                    </div>
                    <p className="text-sm font-semibold text-foreground">Partners</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </div>
                <p className="font-mono text-2xl font-bold text-foreground">{platform.active_partners}</p>
                <p className="text-[10px] text-muted mt-0.5">active partners</p>
              </div>
            </div>
          </Link>

          <Link href="/monitoring" className="group">
            <div className="rounded-2xl bg-card overflow-hidden transition-all hover:shadow-lg">
              <div
                className={`h-1 bg-gradient-to-r ${
                  platform.critical_issues > 0
                    ? "from-red-400 to-red-500"
                    : platform.open_issues > 0
                      ? "from-amber-400 to-amber-500"
                      : "from-green-400 to-green-500"
                }`}
              />
              <div className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`flex h-9 w-9 items-center justify-center rounded-lg ${
                        platform.critical_issues > 0
                          ? "bg-red-50"
                          : platform.open_issues > 0
                            ? "bg-amber-50"
                            : "bg-green-50"
                      }`}
                    >
                      {platform.critical_issues > 0 ? (
                        <AlertTriangle className="h-4 w-4 text-red-600" />
                      ) : platform.open_issues > 0 ? (
                        <AlertTriangle className="h-4 w-4 text-amber-600" />
                      ) : (
                        <Activity className="h-4 w-4 text-green-600" />
                      )}
                    </div>
                    <p className="text-sm font-semibold text-foreground">Issues</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </div>
                <p
                  className={`font-mono text-2xl font-bold ${
                    platform.critical_issues > 0
                      ? "text-red-600"
                      : platform.open_issues > 0
                        ? "text-amber-600"
                        : "text-foreground"
                  }`}
                >
                  {platform.open_issues}
                </p>
                {platform.critical_issues > 0 && (
                  <p className="text-[10px] text-red-600 font-medium mt-0.5">{platform.critical_issues} critical</p>
                )}
                {platform.critical_issues === 0 && platform.open_issues > 0 && (
                  <p className="text-[10px] text-amber-600 font-medium mt-0.5">{platform.open_issues} non-critical open</p>
                )}
                {platform.open_issues === 0 && (
                  <p className="text-[10px] text-green-600 mt-0.5">All clear</p>
                )}
              </div>
            </div>
          </Link>

          <Link href="/eva-customers" className="group">
            <div className="rounded-2xl bg-card overflow-hidden transition-all hover:shadow-lg">
              <div className="h-1 bg-gradient-to-r from-amber-400 to-amber-500" />
              <div className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50">
                      <FileText className="h-4 w-4 text-amber-600" />
                    </div>
                    <p className="text-sm font-semibold text-foreground">Pending Drafts</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 text-muted opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </div>
                <p className="font-mono text-2xl font-bold text-foreground">{platform.draft_accounts_pending}</p>
                <p className="text-[10px] text-muted mt-0.5">awaiting approval</p>
              </div>
            </div>
          </Link>
        </div>
      )}
    </div>
  );
}
