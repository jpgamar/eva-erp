"use client";

import { useEffect, useState } from "react";
import {
  TrendingUp, TrendingDown, Users, DollarSign,
  ArrowUpRight, Wallet, Target, Lock, Unlock, CheckSquare, CalendarDays,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { kpisApi } from "@/lib/api/kpis";
import { incomeApi, expenseApi } from "@/lib/api/finances";
import { prospectsApi } from "@/lib/api/prospects";
import { vaultApi } from "@/lib/api/vault";
import { tasksApi } from "@/lib/api/tasks";
import type { Task } from "@/types";

interface KPICurrent {
  mrr: number;
  arr: number;
  mrr_growth_pct: number | null;
  total_revenue: number;
  total_expenses_usd: number;
  net_profit: number;
  total_customers: number;
  new_customers: number;
  churned_customers: number;
  arpu: number;
  open_tasks: number;
  overdue_tasks: number;
  prospects_in_pipeline: number;
  cash_balance_usd: number | null;
}

interface IncomeSummary {
  mrr: number;
  arr: number;
  total_period: number;
  total_period_usd: number;
  mom_growth_pct: number | null;
}

interface ExpenseSummary {
  total_usd: number;
  by_category: Record<string, number>;
  by_person: Record<string, number>;
  recurring_total_usd: number;
}

interface ProspectSummary {
  total: number;
  by_status: Record<string, number>;
}

interface CostSummary {
  total_usd: number;
  total_mxn: number;
  combined_usd: number;
  by_category: Record<string, number>;
  service_count: number;
}

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
  const [current, setCurrent] = useState<KPICurrent | null>(null);
  const [incomeSummary, setIncomeSummary] = useState<IncomeSummary | null>(null);
  const [expenseSummary, setExpenseSummary] = useState<ExpenseSummary | null>(null);
  const [prospectSummary, setProspectSummary] = useState<ProspectSummary | null>(null);
  const [costSummary, setCostSummary] = useState<CostSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [urgencyCounts, setUrgencyCounts] = useState<{ urgent: number; soso: number; canWait: number }>({ urgent: 0, soso: 0, canWait: 0 });
  const [recentTasks, setRecentTasks] = useState<Task[]>([]);
  const [vaultPw, setVaultPw] = useState("");
  const [vaultUnlocking, setVaultUnlocking] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [c, inc, exp, pros, prospectList] = await Promise.all([
          kpisApi.current(),
          incomeApi.summary().catch(() => null),
          expenseApi.summary().catch(() => null),
          prospectsApi.summary().catch(() => null),
          prospectsApi.list().catch(() => []),
        ]);
        setCurrent(c);
        setIncomeSummary(inc);
        setExpenseSummary(exp);
        setProspectSummary(pros);

        if (Array.isArray(prospectList)) {
          let urgent = 0, soso = 0, canWait = 0;
          for (const p of prospectList) {
            const tags: string[] = p.tags || [];
            if (tags.includes("priority_high")) urgent++;
            else if (tags.includes("priority_medium")) soso++;
            else if (tags.includes("priority_low")) canWait++;
          }
          setUrgencyCounts({ urgent, soso, canWait });
        }

        try {
          const taskList = await tasksApi.list({ status: "todo" });
          const inProgress = await tasksApi.list({ status: "in_progress" });
          setRecentTasks([...inProgress, ...taskList].slice(0, 6));
        } catch { /* tasks optional */ }

        try {
          const v = await vaultApi.costSummary();
          setCostSummary(v);
        } catch { /* vault locked */ }
      } catch {
        toast.error("Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!current) return null;

  const allExpenses = expenseSummary
    ? Object.entries(expenseSummary.by_category).sort(([, a], [, b]) => b - a)
    : [];
  const expenseTotal = expenseSummary ? expenseSummary.total_usd : current.total_expenses_usd;
  const topExpenses = allExpenses.slice(0, 3);

  const topVaultCats = costSummary
    ? Object.entries(costSummary.by_category).sort(([, a], [, b]) => b - a).slice(0, 3)
    : [];

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
            <p className="font-mono text-2xl font-bold tracking-tight text-emerald-900">{fmt(current.mrr)}</p>
            {current.mrr_growth_pct != null && (
              <div className="mt-1.5 flex items-center gap-1.5">
                {current.mrr_growth_pct >= 0
                  ? <TrendingUp className="h-3 w-3 text-emerald-500" />
                  : <TrendingDown className="h-3 w-3 text-red-500" />}
                <span className={`text-xs font-semibold ${current.mrr_growth_pct >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                  {current.mrr_growth_pct > 0 ? "+" : ""}{current.mrr_growth_pct}% MoM
                </span>
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
            <p className="font-mono text-2xl font-bold tracking-tight text-indigo-900">{current.total_customers}</p>
            <div className="mt-1.5 flex items-center gap-3">
              <span className="text-xs text-indigo-600/70">
                <span className="font-semibold text-indigo-700">+{current.new_customers}</span> new
              </span>
              <span className="text-xs text-indigo-600/70">
                <span className="font-semibold text-indigo-700">-{current.churned_customers}</span> churned
              </span>
            </div>
          </div>
        </div>

        {/* Net P/L */}
        <div className={`relative overflow-hidden rounded-2xl border p-4 ${
          current.net_profit >= 0
            ? "border-green-200 bg-green-50"
            : "border-red-200 bg-red-50"
        }`}>
          <div className={`absolute -right-4 -top-4 h-20 w-20 rounded-full ${current.net_profit >= 0 ? "bg-green-100/60" : "bg-red-100/60"}`} />
          <div className={`absolute -right-2 -top-2 h-12 w-12 rounded-full ${current.net_profit >= 0 ? "bg-green-100/60" : "bg-red-100/60"}`} />
          <div className="relative">
            <div className="flex items-center gap-2 mb-0.5">
              {current.net_profit >= 0
                ? <TrendingUp className="h-3.5 w-3.5 text-green-500" />
                : <TrendingDown className="h-3.5 w-3.5 text-red-500" />}
              <p className={`text-xs font-medium ${current.net_profit >= 0 ? "text-green-600/70" : "text-red-600/70"}`}>Net P/L</p>
            </div>
            <p className={`font-mono text-2xl font-bold tracking-tight ${current.net_profit >= 0 ? "text-green-900" : "text-red-900"}`}>{fmt(current.net_profit)}</p>
            <div className="mt-1.5">
              <span className={`text-xs ${current.net_profit >= 0 ? "text-green-600/60" : "text-red-600/60"}`}>Revenue − Expenses</span>
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
                    {incomeSummary ? fmt(incomeSummary.total_period_usd) : fmt(current.total_revenue)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">Expenses</span>
                  <span className="font-mono text-sm font-semibold text-foreground">
                    {fmt(expenseTotal || 0)}
                  </span>
                </div>
                {current.cash_balance_usd != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Cash balance</span>
                    <span className="font-mono text-sm font-semibold text-foreground">{fmt(current.cash_balance_usd)}</span>
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
                    {prospectSummary ? prospectSummary.total : current.prospects_in_pipeline}
                  </span>
                </div>
                {prospectSummary && prospectSummary.by_status.won != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Won</span>
                    <span className="font-mono text-sm font-semibold text-green-600">{prospectSummary.by_status.won}</span>
                  </div>
                )}
                {prospectSummary && prospectSummary.by_status.lost != null && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted">Lost</span>
                    <span className="font-mono text-sm font-semibold text-red-500">{prospectSummary.by_status.lost}</span>
                  </div>
                )}
                <div className="pt-3 mt-auto border-t border-border/50">
                  <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2">By Urgency</p>
                  <div className="flex items-center justify-between py-0.5">
                    <div className="flex items-center gap-1.5">
                      <div className="h-2 w-2 rounded-full bg-red-500" />
                      <span className="text-xs text-muted">Urgent</span>
                    </div>
                    <span className="font-mono text-xs text-foreground">{urgencyCounts.urgent}</span>
                  </div>
                  <div className="flex items-center justify-between py-0.5">
                    <div className="flex items-center gap-1.5">
                      <div className="h-2 w-2 rounded-full bg-amber-500" />
                      <span className="text-xs text-muted">So-so</span>
                    </div>
                    <span className="font-mono text-xs text-foreground">{urgencyCounts.soso}</span>
                  </div>
                  <div className="flex items-center justify-between py-0.5">
                    <div className="flex items-center gap-1.5">
                      <div className="h-2 w-2 rounded-full bg-gray-400" />
                      <span className="text-xs text-muted">Can wait</span>
                    </div>
                    <span className="font-mono text-xs text-foreground">{urgencyCounts.canWait}</span>
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
                <span className="font-mono text-sm font-semibold text-foreground">{current.open_tasks}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted">Overdue</span>
                <span className={`font-mono text-sm font-semibold ${current.overdue_tasks > 0 ? "text-red-500" : "text-foreground"}`}>{current.overdue_tasks}</span>
              </div>
              {recentTasks.length > 0 && (
                <div className="pt-3 mt-auto border-t border-border/50">
                  <p className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-2">Active Tasks</p>
                  {recentTasks.map((task) => (
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
            {costSummary ? (
              <div className="space-y-3 flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">Monthly cost</span>
                  <span className="font-mono text-sm font-semibold text-foreground">{fmt(costSummary.combined_usd)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted">Services</span>
                  <span className="font-mono text-sm font-semibold text-foreground">{costSummary.service_count}</span>
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
            ) : (
              <div className="flex flex-col items-center justify-center flex-1 text-center">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 mb-2">
                  <Lock className="h-4 w-4 text-amber-400" />
                </div>
                <p className="text-xs font-medium text-muted mb-3">Vault is locked</p>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (!vaultPw.trim()) return;
                    setVaultUnlocking(true);
                    try {
                      await vaultApi.unlock(vaultPw);
                      const v = await vaultApi.costSummary();
                      setCostSummary(v);
                      setVaultPw("");
                      toast.success("Vault unlocked");
                    } catch {
                      toast.error("Wrong password");
                    } finally {
                      setVaultUnlocking(false);
                    }
                  }}
                  className="flex items-center gap-1.5 w-full max-w-[200px]"
                >
                  <input
                    type="password"
                    placeholder="Master password"
                    value={vaultPw}
                    onChange={(e) => setVaultPw(e.target.value)}
                    className="flex-1 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs outline-none transition-all focus:border-amber-300 focus:ring-2 focus:ring-amber-100"
                  />
                  <button
                    type="submit"
                    disabled={vaultUnlocking || !vaultPw.trim()}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600 transition-colors hover:bg-amber-100 disabled:opacity-40"
                  >
                    <Unlock className="h-3.5 w-3.5" />
                  </button>
                </form>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
