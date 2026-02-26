"use client";

import { useEffect, useState } from "react";
import {
  Plus, Wallet, DollarSign, TrendingDown, TrendingUp,
  ArrowDownRight, ArrowUpRight, Trash2, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { incomeApi, expenseApi, invoiceApi, cashBalanceApi, stripeFinanceApi } from "@/lib/api/finances";
import { dashboardApi, type DashboardData } from "@/lib/api/dashboard";
import { useAuth } from "@/lib/auth/context";
import type {
  IncomeEntry, IncomeSummary, Expense as ExpenseType,
  InvoiceEntry, CashBalanceEntry, StripeReconciliationSummary,
} from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

function fmt(amount: number | null | undefined, currency = "USD") {
  if (amount == null) return "-";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
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

function incomeMonthlyAmount(entry: IncomeEntry): number {
  if (entry.recurrence_type === "one_time") return 0;
  if (entry.recurrence_type === "custom") return entry.amount / Math.max(entry.custom_interval_months || 1, 1);
  return entry.amount;
}

const EXPENSE_CATEGORIES = [
  "infrastructure", "ai_apis", "communication", "payment_fees",
  "domains_hosting", "marketing", "legal_accounting", "contractors",
  "office", "software_tools", "other",
];

const INCOME_CATEGORIES = ["subscription", "addon", "consulting", "custom_deal", "refund", "other"];
const STATUS_STYLES: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  sent: "bg-blue-50 text-blue-700",
  paid: "bg-green-50 text-green-700",
  overdue: "bg-red-50 text-red-700",
  cancelled: "bg-gray-100 text-gray-500",
};

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "income", label: "Income" },
  { key: "expenses", label: "Expenses" },
  { key: "invoices", label: "Invoices" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function FinancesPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<TabKey>("overview");
  const [loading, setLoading] = useState(true);

  const [incomeSummary, setIncomeSummary] = useState<IncomeSummary | null>(null);
  const [incomeList, setIncomeList] = useState<IncomeEntry[]>([]);
  const [expenseList, setExpenseList] = useState<ExpenseType[]>([]);
  const [invoiceList, setInvoiceList] = useState<InvoiceEntry[]>([]);
  const [cashBalance, setCashBalance] = useState<CashBalanceEntry | null>(null);
  const [stripeSummary, setStripeSummary] = useState<StripeReconciliationSummary | null>(null);
  const [lifecycleSummary, setLifecycleSummary] = useState<DashboardData | null>(null);
  const [syncingStripe, setSyncingStripe] = useState(false);

  const [addIncomeOpen, setAddIncomeOpen] = useState(false);
  const [addExpenseOpen, setAddExpenseOpen] = useState(false);
  const [addInvoiceOpen, setAddInvoiceOpen] = useState(false);
  const [cashOpen, setCashOpen] = useState(false);
  const [deletingIncomeId, setDeletingIncomeId] = useState<string | null>(null);

  const [incomeForm, setIncomeForm] = useState({
    description: "",
    amount: "",
    currency: "MXN",
    category: "subscription",
    date: new Date().toISOString().split("T")[0],
    recurrence_type: "one_time",
    custom_interval_months: "2",
  });
  const [expenseForm, setExpenseForm] = useState({ name: "", amount: "", currency: "USD", category: "infrastructure", vendor: "", date: new Date().toISOString().split("T")[0], is_recurring: false, recurrence: "monthly" });
  const [invoiceForm, setInvoiceForm] = useState({ customer_name: "", customer_email: "", description: "", currency: "MXN", issue_date: new Date().toISOString().split("T")[0], due_date: "", item_desc: "", item_qty: "1", item_price: "", tax: "" });
  const [cashForm, setCashForm] = useState({ amount: "", currency: "MXN", date: new Date().toISOString().split("T")[0], notes: "" });

  const fetchAll = async () => {
    try {
      const [iSum, iList, eList, invList, cash, lifecycle] = await Promise.all([
        incomeApi.summary(), incomeApi.list(),
        expenseApi.list(), invoiceApi.list(), cashBalanceApi.current(),
        dashboardApi.summary().catch(() => null),
      ]);
      setIncomeSummary(iSum);
      setIncomeList(iList);
      setExpenseList(eList);
      setInvoiceList(invList);
      setCashBalance(cash);
      setLifecycleSummary(lifecycle);
      const stripe = await stripeFinanceApi.reconciliation().catch(() => null);
      setStripeSummary(stripe);
    } catch { toast.error("Failed to load financial data"); } finally { setLoading(false); }
  };

  useEffect(() => { fetchAll(); }, []);

  const handleAddIncome = async () => {
    try {
      const recurrenceType = incomeForm.recurrence_type;
      const customIntervalMonths = recurrenceType === "custom" ? parseInt(incomeForm.custom_interval_months, 10) : null;
      if (recurrenceType === "custom" && (!Number.isFinite(customIntervalMonths) || (customIntervalMonths ?? 0) < 1)) {
        toast.error("Custom interval must be at least 1 month");
        return;
      }
      await incomeApi.create({
        ...incomeForm,
        amount: parseFloat(incomeForm.amount),
        recurrence_type: recurrenceType,
        custom_interval_months: customIntervalMonths,
        is_recurring: recurrenceType !== "one_time",
      });
      toast.success("Income added");
      setAddIncomeOpen(false);
      setIncomeForm({
        description: "",
        amount: "",
        currency: "MXN",
        category: "subscription",
        date: new Date().toISOString().split("T")[0],
        recurrence_type: "one_time",
        custom_interval_months: "2",
      });
      await fetchAll();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const handleAddExpense = async () => {
    try {
      await expenseApi.create({ ...expenseForm, amount: parseFloat(expenseForm.amount), paid_by: user?.id });
      toast.success("Expense added");
      setAddExpenseOpen(false);
      setExpenseForm({ name: "", amount: "", currency: "USD", category: "infrastructure", vendor: "", date: new Date().toISOString().split("T")[0], is_recurring: false, recurrence: "monthly" });
      await fetchAll();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const handleDeleteIncome = async (income: IncomeEntry) => {
    if (income.source !== "manual") {
      toast.error("Only manual income entries can be deleted");
      return;
    }
    const confirmed = window.confirm(`Delete income "${income.description}"?`);
    if (!confirmed) return;

    setDeletingIncomeId(income.id);
    try {
      await incomeApi.delete(income.id);
      toast.success("Income entry deleted");
      await fetchAll();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to delete");
    } finally {
      setDeletingIncomeId(null);
    }
  };

  const handleAddInvoice = async () => {
    try {
      const unitPrice = parseFloat(invoiceForm.item_price);
      const qty = parseInt(invoiceForm.item_qty);
      await invoiceApi.create({
        customer_name: invoiceForm.customer_name,
        customer_email: invoiceForm.customer_email || null,
        description: invoiceForm.description || null,
        currency: invoiceForm.currency,
        issue_date: invoiceForm.issue_date,
        due_date: invoiceForm.due_date,
        tax: invoiceForm.tax ? parseFloat(invoiceForm.tax) : null,
        line_items: [{ description: invoiceForm.item_desc, quantity: qty, unit_price: unitPrice, total: unitPrice * qty }],
      });
      toast.success("Invoice created");
      setAddInvoiceOpen(false);
      await fetchAll();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const handleUpdateCash = async () => {
    try {
      await cashBalanceApi.update({ ...cashForm, amount: parseFloat(cashForm.amount) });
      toast.success("Cash balance updated");
      setCashOpen(false);
      await fetchAll();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const handleStripeSync = async (backfill = false) => {
    setSyncingStripe(true);
    try {
      const result = await stripeFinanceApi.reconcile({
        backfill,
        max_events: backfill ? 5000 : 500,
      });
      toast.success(
        `Stripe sync complete: ${result.processed_events} processed, ${result.duplicate_events} duplicates`
      );
      await fetchAll();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Stripe sync failed");
    } finally {
      setSyncingStripe(false);
    }
  };

  const currentMonth = new Date().getMonth();
  const currentYear = new Date().getFullYear();
  const mrrByCurrency = sortedCurrencyEntries(incomeSummary?.mrr_by_currency);
  const revenueByCurrency = sortedCurrencyEntries(incomeSummary?.total_period_by_currency);

  const expensePeriodByCurrency = expenseList.reduce<Record<string, number>>((acc, expense) => {
    const d = new Date(expense.date);
    if (d.getMonth() !== currentMonth || d.getFullYear() !== currentYear) return acc;
    acc[expense.currency] = (acc[expense.currency] || 0) + Number(expense.amount || 0);
    return acc;
  }, {});
  const expensesByCurrency = sortedCurrencyEntries(expensePeriodByCurrency);

  const netProfitByCurrencyMap = Array.from(new Set([
    ...Object.keys(incomeSummary?.total_period_by_currency || {}),
    ...Object.keys(expensePeriodByCurrency),
  ])).reduce<Record<string, number>>((acc, currency) => {
    const revenue = incomeSummary?.total_period_by_currency?.[currency] || 0;
    const expense = expensePeriodByCurrency[currency] || 0;
    acc[currency] = revenue - expense;
    return acc;
  }, {});
  const netProfitByCurrency = sortedCurrencyEntries(netProfitByCurrencyMap);
  const hasNegativeNet = netProfitByCurrency.some(([, value]) => value < 0);
  const expenseByCurrencyCategory = expenseList.reduce<Record<string, Record<string, number>>>((acc, expense) => {
    const currencyBucket = (acc[expense.currency] ||= {});
    currencyBucket[expense.category] = (currencyBucket[expense.category] || 0) + Number(expense.amount || 0);
    return acc;
  }, {});

  if (loading) {
    return <div className="flex items-center justify-center h-[calc(100vh-8rem)]"><div className="animate-spin h-8 w-8 border-4 border-accent border-t-transparent rounded-full" /></div>;
  }

  return (
    <div className="space-y-6 animate-erp-entrance">
      {/* Tab bar */}
      <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "rounded-md px-4 py-2 text-sm font-medium transition-colors",
              tab === t.key
                ? "bg-accent text-white shadow-sm"
                : "text-muted hover:text-foreground"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* OVERVIEW */}
      {tab === "overview" && (
        <div className="space-y-6">
          {lifecycleSummary && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-emerald-700/80">Projected Revenue</p>
                <p className="mt-1 font-mono text-base font-bold text-emerald-900">{fmt(lifecycleSummary.projected_revenue_mxn, "MXN")}</p>
              </div>
              <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-blue-700/80">Invoiced (SAT)</p>
                <p className="mt-1 font-mono text-base font-bold text-blue-900">{fmt(lifecycleSummary.invoiced_sat_mxn, "MXN")}</p>
              </div>
              <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-indigo-700/80">Payments Received</p>
                <p className="mt-1 font-mono text-base font-bold text-indigo-900">{fmt(lifecycleSummary.payments_received_mxn, "MXN")}</p>
              </div>
              <div className="rounded-xl border border-cyan-200 bg-cyan-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-cyan-700/80">Bank Deposits</p>
                <p className="mt-1 font-mono text-base font-bold text-cyan-900">{fmt(lifecycleSummary.bank_deposits_mxn, "MXN")}</p>
              </div>
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-amber-700/80">Gap To Collect</p>
                <p className="mt-1 font-mono text-base font-bold text-amber-900">{fmt(lifecycleSummary.gap_to_collect_mxn, "MXN")}</p>
              </div>
              <div className="rounded-xl border border-orange-200 bg-orange-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-orange-700/80">Gap To Deposit</p>
                <p className="mt-1 font-mono text-base font-bold text-orange-900">{fmt(lifecycleSummary.gap_to_deposit_mxn, "MXN")}</p>
              </div>
            </div>
          )}

          {/* KPI row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-xl border border-border border-l-[3px] border-l-green-500 bg-card p-5">
              <div className="flex items-center gap-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-green-50">
                  <ArrowUpRight className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted">MRR (Monthly Recurring Revenue)</p>
                  {mrrByCurrency.length === 0 ? (
                    <p className="mt-0.5 font-mono text-xl font-bold text-foreground">-</p>
                  ) : (
                    <div className="mt-0.5 space-y-0.5">
                      {mrrByCurrency.map(([currency, amount]) => (
                        <p key={currency} className="font-mono text-base font-bold text-foreground">{fmt(amount, currency)}</p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-border border-l-[3px] border-l-green-500 bg-card p-5">
              <div className="flex items-center gap-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-green-50">
                  <DollarSign className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted">Revenue This Month</p>
                  {revenueByCurrency.length === 0 ? (
                    <p className="mt-0.5 font-mono text-xl font-bold text-foreground">-</p>
                  ) : (
                    <div className="mt-0.5 space-y-0.5">
                      {revenueByCurrency.map(([currency, amount]) => (
                        <p key={currency} className="font-mono text-base font-bold text-foreground">{fmt(amount, currency)}</p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-border border-l-[3px] border-l-red-500 bg-card p-5">
              <div className="flex items-center gap-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-red-50">
                  <ArrowDownRight className="h-5 w-5 text-red-600" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted">Expenses This Month</p>
                  {expensesByCurrency.length === 0 ? (
                    <p className="mt-0.5 font-mono text-xl font-bold text-foreground">-</p>
                  ) : (
                    <div className="mt-0.5 space-y-0.5">
                      {expensesByCurrency.map(([currency, amount]) => (
                        <p key={currency} className="font-mono text-base font-bold text-foreground">{fmt(amount, currency)}</p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className={cn(
              "rounded-xl border border-border border-l-[3px] bg-card p-5",
              hasNegativeNet ? "border-l-red-500" : "border-l-green-500"
            )}>
              <div className="flex items-center gap-4">
                <div className={cn(
                  "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
                  hasNegativeNet ? "bg-red-50" : "bg-green-50"
                )}>
                  {hasNegativeNet ? <TrendingDown className="h-5 w-5 text-red-600" /> : <TrendingUp className="h-5 w-5 text-green-600" />}
                </div>
                <div>
                  <p className="text-xs font-medium text-muted">Net P/L (Revenue - Expenses)</p>
                  {netProfitByCurrency.length === 0 ? (
                    <p className="mt-0.5 font-mono text-xl font-bold text-foreground">-</p>
                  ) : (
                    <div className="mt-0.5 space-y-0.5">
                      {netProfitByCurrency.map(([currency, amount]) => (
                        <p key={currency} className={cn("font-mono text-base font-bold", amount >= 0 ? "text-green-600" : "text-red-600")}>
                          {fmt(amount, currency)}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Stripe Reconciliation */}
          {stripeSummary && (
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-foreground">Stripe Reconciliation</p>
                  <p className="text-xs text-muted">Period {stripeSummary.period}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="rounded-lg"
                    onClick={() => handleStripeSync(false)}
                    disabled={syncingStripe}
                  >
                    <RefreshCw className={cn("mr-2 h-4 w-4", syncingStripe ? "animate-spin" : "")} />
                    Sync
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="rounded-lg"
                    onClick={() => handleStripeSync(true)}
                    disabled={syncingStripe}
                  >
                    Backfill
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-lg border border-border p-3">
                  <p className="text-[11px] uppercase tracking-wider text-muted">Payments Received</p>
                  <p className="font-mono text-base font-semibold">{fmt(stripeSummary.payments_received, "MXN")}</p>
                </div>
                <div className="rounded-lg border border-border p-3">
                  <p className="text-[11px] uppercase tracking-wider text-muted">Refunds</p>
                  <p className="font-mono text-base font-semibold text-red-600">{fmt(stripeSummary.refunds, "MXN")}</p>
                </div>
                <div className="rounded-lg border border-border p-3">
                  <p className="text-[11px] uppercase tracking-wider text-muted">Bank Deposits</p>
                  <p className="font-mono text-base font-semibold">{fmt(stripeSummary.payouts_paid, "MXN")}</p>
                </div>
                <div className="rounded-lg border border-border p-3">
                  <p className="text-[11px] uppercase tracking-wider text-muted">Gap To Deposit</p>
                  <p className={cn("font-mono text-base font-semibold", stripeSummary.gap_to_deposit >= 0 ? "text-amber-600" : "text-green-600")}>
                    {fmt(stripeSummary.gap_to_deposit, "MXN")}
                  </p>
                </div>
              </div>
              {lifecycleSummary && (
                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-lg border border-border p-3">
                    <p className="text-[11px] uppercase tracking-wider text-muted">Projected</p>
                    <p className="font-mono text-base font-semibold">{fmt(lifecycleSummary.projected_revenue_mxn, "MXN")}</p>
                  </div>
                  <div className="rounded-lg border border-border p-3">
                    <p className="text-[11px] uppercase tracking-wider text-muted">Invoiced SAT</p>
                    <p className="font-mono text-base font-semibold">{fmt(lifecycleSummary.invoiced_sat_mxn, "MXN")}</p>
                  </div>
                  <div className="rounded-lg border border-border p-3">
                    <p className="text-[11px] uppercase tracking-wider text-muted">Unlinked Revenue</p>
                    <p className="font-mono text-base font-semibold">{fmt(lifecycleSummary.unlinked_revenue_mxn, "MXN")}</p>
                  </div>
                  <div className="rounded-lg border border-border p-3">
                    <p className="text-[11px] uppercase tracking-wider text-muted">Manual Adjustments</p>
                    <p className="font-mono text-base font-semibold">{fmt(lifecycleSummary.manual_adjustments_mxn, "MXN")}</p>
                  </div>
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <Badge variant="outline">Net Received: {fmt(stripeSummary.net_received, "MXN")}</Badge>
                <Badge variant="outline">Manual Deposits: {fmt(stripeSummary.manual_deposits, "MXN")}</Badge>
                <Badge variant="outline">Unlinked Payments: {stripeSummary.unlinked_payment_events}</Badge>
                <Badge variant="outline">Unlinked Payouts: {stripeSummary.unlinked_payout_events}</Badge>
              </div>
            </div>
          )}

          {/* Cash Balance */}
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-light">
                  <Wallet className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">Cash Balance</p>
                  <p className="text-xs text-muted">Current available cash</p>
                </div>
              </div>
              <Button size="sm" variant="outline" className="rounded-lg" onClick={() => setCashOpen(true)}>
                Update
              </Button>
            </div>
            <p className="font-mono text-3xl font-bold text-foreground">{cashBalance ? fmt(cashBalance.amount, cashBalance.currency) : "Not set"}</p>
            {cashBalance && (
              <p className="mt-1 text-xs text-muted">
                As of {new Date(cashBalance.date).toLocaleDateString()}
                {cashBalance.notes && ` - ${cashBalance.notes}`}
              </p>
            )}
          </div>

          {/* Expenses by Category */}
          {Object.keys(expenseByCurrencyCategory).length > 0 && (
            <div className="rounded-xl border border-border bg-card p-6">
              <p className="mb-4 text-sm font-semibold text-foreground">Expenses by Category</p>
              <div className="space-y-6">
                {sortedCurrencyEntries(
                  Object.fromEntries(Object.keys(expenseByCurrencyCategory).map((currency) => [currency, 1]))
                ).map(([currency]) => {
                  const categories = Object.entries(expenseByCurrencyCategory[currency] || {}).sort(([, a], [, b]) => b - a);
                  const total = categories.reduce((acc, [, amount]) => acc + amount, 0);
                  return (
                    <div key={currency} className="space-y-3">
                      <p className="text-xs font-semibold uppercase tracking-wider text-muted">{currency}</p>
                      {categories.map(([cat, amount]) => {
                        const pct = total > 0 ? (amount / total) * 100 : 0;
                        return (
                          <div key={`${currency}-${cat}`} className="flex items-center gap-3">
                            <span className="w-32 text-sm capitalize truncate text-foreground">{cat.replace(/_/g, " ")}</span>
                            <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                              <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
                            </div>
                            <span className="w-32 text-right font-mono text-sm font-medium text-foreground">{fmt(amount, currency)}</span>
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* INCOME */}
      {tab === "income" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button size="sm" className="rounded-lg" onClick={() => setAddIncomeOpen(true)}>
              <Plus className="h-4 w-4 mr-2" /> Add Entry
            </Button>
          </div>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50/80">
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Date</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Description</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Amount</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Monthly eq.</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Source</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Category</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Recurrence</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {incomeList.length === 0 ? (
                  <TableRow><TableCell colSpan={8} className="text-center text-muted py-12">No income entries yet.</TableCell></TableRow>
                ) : incomeList.map((e) => (
                  <TableRow key={e.id} className="hover:bg-gray-50/80">
                    <TableCell className="text-sm text-muted">{new Date(e.date).toLocaleDateString()}</TableCell>
                    <TableCell className="font-medium">{e.description}</TableCell>
                    <TableCell className="font-mono text-sm">{fmt(e.amount, e.currency)}</TableCell>
                    <TableCell className="font-mono text-sm">
                      {e.recurrence_type === "one_time" ? "-" : fmt(incomeMonthlyAmount(e), e.currency)}
                    </TableCell>
                    <TableCell><Badge variant="secondary" className="rounded-full text-xs">{e.source}</Badge></TableCell>
                    <TableCell className="capitalize text-sm">{e.category}</TableCell>
                    <TableCell className="text-sm">
                      <Badge variant="secondary" className="rounded-full text-xs capitalize">
                        {e.recurrence_type === "one_time" ? "One Time" : e.recurrence_type}
                      </Badge>
                      {e.recurrence_type === "custom" && e.custom_interval_months && (
                        <span className="ml-2 text-xs text-muted">every {e.custom_interval_months} months</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {e.source === "manual" ? (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-600 hover:text-red-700"
                          onClick={() => handleDeleteIncome(e)}
                          disabled={deletingIncomeId === e.id}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : (
                        <span className="text-sm text-muted">-</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* EXPENSES */}
      {tab === "expenses" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button size="sm" className="rounded-lg" onClick={() => setAddExpenseOpen(true)}>
              <Plus className="h-4 w-4 mr-2" /> Add Expense
            </Button>
          </div>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50/80">
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Date</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Name</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Amount</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Category</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Vendor</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Recurring</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {expenseList.length === 0 ? (
                  <TableRow><TableCell colSpan={6} className="text-center text-muted py-12">No expenses yet.</TableCell></TableRow>
                ) : expenseList.map((exp) => (
                  <TableRow key={exp.id} className="hover:bg-gray-50/80">
                    <TableCell className="text-sm text-muted">{new Date(exp.date).toLocaleDateString()}</TableCell>
                    <TableCell className="font-medium">{exp.name}</TableCell>
                    <TableCell className="font-mono text-sm">{fmt(exp.amount, exp.currency)}</TableCell>
                    <TableCell className="capitalize text-sm">{exp.category.replace(/_/g, " ")}</TableCell>
                    <TableCell className="text-sm">{exp.vendor || "-"}</TableCell>
                    <TableCell>{exp.is_recurring ? <Badge variant="secondary" className="rounded-full text-xs">Recurring</Badge> : "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* INVOICES */}
      {tab === "invoices" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Button size="sm" className="rounded-lg" onClick={() => setAddInvoiceOpen(true)}>
              <Plus className="h-4 w-4 mr-2" /> New Invoice
            </Button>
          </div>
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50/80">
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Invoice #</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Customer</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Total</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Status</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Issue Date</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Due Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoiceList.length === 0 ? (
                  <TableRow><TableCell colSpan={6} className="text-center text-muted py-12">No invoices yet.</TableCell></TableRow>
                ) : invoiceList.map((inv) => (
                  <TableRow key={inv.id} className="hover:bg-gray-50/80">
                    <TableCell className="font-mono font-medium text-sm">{inv.invoice_number}</TableCell>
                    <TableCell className="font-medium">{inv.customer_name}</TableCell>
                    <TableCell className="font-mono text-sm">{fmt(inv.total, inv.currency)}</TableCell>
                    <TableCell>
                      <Badge className={cn("rounded-full text-xs font-medium", STATUS_STYLES[inv.status] || "")}>
                        {inv.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted">{new Date(inv.issue_date).toLocaleDateString()}</TableCell>
                    <TableCell className="text-sm text-muted">{new Date(inv.due_date).toLocaleDateString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Dialogs */}
      <Dialog open={addIncomeOpen} onOpenChange={setAddIncomeOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Income</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleAddIncome(); }} className="space-y-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Description *</Label>
              <Input className="mt-1.5 rounded-lg" value={incomeForm.description} onChange={(e) => setIncomeForm(f => ({ ...f, description: e.target.value }))} required />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Amount *</Label>
                <Input className="mt-1.5 rounded-lg" type="number" step="0.01" value={incomeForm.amount} onChange={(e) => setIncomeForm(f => ({ ...f, amount: e.target.value }))} required />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Currency</Label>
                <Select value={incomeForm.currency} onValueChange={(v) => setIncomeForm(f => ({ ...f, currency: v }))}>
                  <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="MXN">MXN</SelectItem><SelectItem value="USD">USD</SelectItem></SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Category</Label>
                <Select value={incomeForm.category} onValueChange={(v) => setIncomeForm(f => ({ ...f, category: v }))}>
                  <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                  <SelectContent>{INCOME_CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Date</Label>
                <Input className="mt-1.5 rounded-lg" type="date" value={incomeForm.date} onChange={(e) => setIncomeForm(f => ({ ...f, date: e.target.value }))} />
              </div>
            </div>
            <div className={`grid gap-3 ${incomeForm.recurrence_type === "custom" ? "grid-cols-2" : "grid-cols-1"}`}>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Recurrence</Label>
                <Select value={incomeForm.recurrence_type} onValueChange={(v: "one_time" | "monthly" | "custom") => setIncomeForm(f => ({ ...f, recurrence_type: v }))}>
                  <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="one_time">One time</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {incomeForm.recurrence_type === "custom" && (
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Custom interval (months)</Label>
                  <Input
                    className="mt-1.5 rounded-lg"
                    type="number"
                    min={1}
                    step={1}
                    value={incomeForm.custom_interval_months}
                    onChange={(e) => setIncomeForm(f => ({ ...f, custom_interval_months: e.target.value }))}
                    required
                  />
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" className="rounded-lg" onClick={() => setAddIncomeOpen(false)}>Cancel</Button>
              <Button type="submit" className="rounded-lg">Add</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={addExpenseOpen} onOpenChange={setAddExpenseOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Expense</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleAddExpense(); }} className="space-y-4">
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Name *</Label>
              <Input className="mt-1.5 rounded-lg" value={expenseForm.name} onChange={(e) => setExpenseForm(f => ({ ...f, name: e.target.value }))} required />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Amount *</Label>
                <Input className="mt-1.5 rounded-lg" type="number" step="0.01" value={expenseForm.amount} onChange={(e) => setExpenseForm(f => ({ ...f, amount: e.target.value }))} required />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Currency</Label>
                <Select value={expenseForm.currency} onValueChange={(v) => setExpenseForm(f => ({ ...f, currency: v }))}>
                  <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="USD">USD</SelectItem><SelectItem value="MXN">MXN</SelectItem></SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Category</Label>
                <Select value={expenseForm.category} onValueChange={(v) => setExpenseForm(f => ({ ...f, category: v }))}>
                  <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                  <SelectContent>{EXPENSE_CATEGORIES.map(c => <SelectItem key={c} value={c}>{c.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Vendor</Label>
                <Input className="mt-1.5 rounded-lg" value={expenseForm.vendor} onChange={(e) => setExpenseForm(f => ({ ...f, vendor: e.target.value }))} />
              </div>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Date</Label>
              <Input className="mt-1.5 rounded-lg" type="date" value={expenseForm.date} onChange={(e) => setExpenseForm(f => ({ ...f, date: e.target.value }))} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" className="rounded-lg" onClick={() => setAddExpenseOpen(false)}>Cancel</Button>
              <Button type="submit" className="rounded-lg">Add</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={addInvoiceOpen} onOpenChange={setAddInvoiceOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New Invoice</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleAddInvoice(); }} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Customer *</Label>
                <Input className="mt-1.5 rounded-lg" value={invoiceForm.customer_name} onChange={(e) => setInvoiceForm(f => ({ ...f, customer_name: e.target.value }))} required />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Email</Label>
                <Input className="mt-1.5 rounded-lg" value={invoiceForm.customer_email} onChange={(e) => setInvoiceForm(f => ({ ...f, customer_email: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Item *</Label>
                <Input className="mt-1.5 rounded-lg" value={invoiceForm.item_desc} onChange={(e) => setInvoiceForm(f => ({ ...f, item_desc: e.target.value }))} required />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Qty</Label>
                <Input className="mt-1.5 rounded-lg" type="number" value={invoiceForm.item_qty} onChange={(e) => setInvoiceForm(f => ({ ...f, item_qty: e.target.value }))} />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Price *</Label>
                <Input className="mt-1.5 rounded-lg" type="number" step="0.01" value={invoiceForm.item_price} onChange={(e) => setInvoiceForm(f => ({ ...f, item_price: e.target.value }))} required />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Issue Date</Label>
                <Input className="mt-1.5 rounded-lg" type="date" value={invoiceForm.issue_date} onChange={(e) => setInvoiceForm(f => ({ ...f, issue_date: e.target.value }))} />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Due Date *</Label>
                <Input className="mt-1.5 rounded-lg" type="date" value={invoiceForm.due_date} onChange={(e) => setInvoiceForm(f => ({ ...f, due_date: e.target.value }))} required />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Tax</Label>
                <Input className="mt-1.5 rounded-lg" type="number" step="0.01" value={invoiceForm.tax} onChange={(e) => setInvoiceForm(f => ({ ...f, tax: e.target.value }))} />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" className="rounded-lg" onClick={() => setAddInvoiceOpen(false)}>Cancel</Button>
              <Button type="submit" className="rounded-lg">Create</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={cashOpen} onOpenChange={setCashOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Update Cash Balance</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleUpdateCash(); }} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Amount *</Label>
                <Input className="mt-1.5 rounded-lg" type="number" step="0.01" value={cashForm.amount} onChange={(e) => setCashForm(f => ({ ...f, amount: e.target.value }))} required />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Currency</Label>
                <Select value={cashForm.currency} onValueChange={(v) => setCashForm(f => ({ ...f, currency: v }))}>
                  <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="MXN">MXN</SelectItem><SelectItem value="USD">USD</SelectItem></SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Date</Label>
              <Input className="mt-1.5 rounded-lg" type="date" value={cashForm.date} onChange={(e) => setCashForm(f => ({ ...f, date: e.target.value }))} />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Notes</Label>
              <Textarea className="mt-1.5 rounded-lg" value={cashForm.notes} onChange={(e) => setCashForm(f => ({ ...f, notes: e.target.value }))} rows={2} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" className="rounded-lg" onClick={() => setCashOpen(false)}>Cancel</Button>
              <Button type="submit" className="rounded-lg">Update</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
