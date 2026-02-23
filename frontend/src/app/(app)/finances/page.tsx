"use client";

import { useEffect, useState } from "react";
import {
  Plus, Wallet, DollarSign, TrendingDown, TrendingUp,
  ArrowDownRight, ArrowUpRight,
} from "lucide-react";
import { toast } from "sonner";
import { incomeApi, expenseApi, invoiceApi, cashBalanceApi } from "@/lib/api/finances";
import { useAuth } from "@/lib/auth/context";
import type {
  IncomeEntry, IncomeSummary, Expense as ExpenseType, ExpenseSummary,
  InvoiceEntry, CashBalanceEntry,
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
  if (amount == null) return "\u2014";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
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
  const [expenseSummary, setExpenseSummary] = useState<ExpenseSummary | null>(null);
  const [incomeList, setIncomeList] = useState<IncomeEntry[]>([]);
  const [expenseList, setExpenseList] = useState<ExpenseType[]>([]);
  const [invoiceList, setInvoiceList] = useState<InvoiceEntry[]>([]);
  const [cashBalance, setCashBalance] = useState<CashBalanceEntry | null>(null);

  const [addIncomeOpen, setAddIncomeOpen] = useState(false);
  const [addExpenseOpen, setAddExpenseOpen] = useState(false);
  const [addInvoiceOpen, setAddInvoiceOpen] = useState(false);
  const [cashOpen, setCashOpen] = useState(false);

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
      const [iSum, eSum, iList, eList, invList, cash] = await Promise.all([
        incomeApi.summary(), expenseApi.summary(), incomeApi.list(),
        expenseApi.list(), invoiceApi.list(), cashBalanceApi.current(),
      ]);
      setIncomeSummary(iSum);
      setExpenseSummary(eSum);
      setIncomeList(iList);
      setExpenseList(eList);
      setInvoiceList(invList);
      setCashBalance(cash);
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

  const netProfit = (incomeSummary?.total_period_usd ?? 0) - (expenseSummary?.total_usd ?? 0);

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
          {/* KPI row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-xl border border-border border-l-[3px] border-l-green-500 bg-card p-5">
              <div className="flex items-center gap-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-green-50">
                  <ArrowUpRight className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted">MRR (Monthly Recurring Revenue)</p>
                  <p className="mt-0.5 font-mono text-xl font-bold text-foreground">{fmt(incomeSummary?.mrr)}</p>
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
                  <p className="mt-0.5 font-mono text-xl font-bold text-foreground">{fmt(incomeSummary?.total_period_usd)}</p>
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
                  <p className="mt-0.5 font-mono text-xl font-bold text-foreground">{fmt(expenseSummary?.total_usd)}</p>
                </div>
              </div>
            </div>

            <div className={cn(
              "rounded-xl border border-border border-l-[3px] bg-card p-5",
              netProfit >= 0 ? "border-l-green-500" : "border-l-red-500"
            )}>
              <div className="flex items-center gap-4">
                <div className={cn(
                  "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
                  netProfit >= 0 ? "bg-green-50" : "bg-red-50"
                )}>
                  {netProfit >= 0 ? <TrendingUp className="h-5 w-5 text-green-600" /> : <TrendingDown className="h-5 w-5 text-red-600" />}
                </div>
                <div>
                  <p className="text-xs font-medium text-muted">Net P/L (Revenue - Expenses)</p>
                  <p className={cn("mt-0.5 font-mono text-xl font-bold", netProfit >= 0 ? "text-green-600" : "text-red-600")}>{fmt(netProfit)}</p>
                </div>
              </div>
            </div>
          </div>

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
            <p className="font-mono text-3xl font-bold text-foreground">{cashBalance ? fmt(cashBalance.amount_usd) : "Not set"}</p>
            {cashBalance && (
              <p className="mt-1 text-xs text-muted">
                As of {new Date(cashBalance.date).toLocaleDateString()}
                {cashBalance.notes && ` \u2014 ${cashBalance.notes}`}
              </p>
            )}
          </div>

          {/* Expenses by Category */}
          {expenseSummary && Object.keys(expenseSummary.by_category).length > 0 && (
            <div className="rounded-xl border border-border bg-card p-6">
              <p className="mb-4 text-sm font-semibold text-foreground">Expenses by Category</p>
              <div className="space-y-3">
                {Object.entries(expenseSummary.by_category).sort(([, a], [, b]) => b - a).map(([cat, amount]) => {
                  const pct = Number(expenseSummary.total_usd) > 0 ? (amount / Number(expenseSummary.total_usd)) * 100 : 0;
                  return (
                    <div key={cat} className="flex items-center gap-3">
                      <span className="w-32 text-sm capitalize truncate text-foreground">{cat.replace(/_/g, " ")}</span>
                      <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                        <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="w-32 text-right font-mono text-sm font-medium text-foreground">{fmt(amount)}</span>
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
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">USD eq.</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Source</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Category</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Recurrence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {incomeList.length === 0 ? (
                  <TableRow><TableCell colSpan={7} className="text-center text-muted py-12">No income entries yet.</TableCell></TableRow>
                ) : incomeList.map((e) => (
                  <TableRow key={e.id} className="hover:bg-gray-50/80">
                    <TableCell className="text-sm text-muted">{new Date(e.date).toLocaleDateString()}</TableCell>
                    <TableCell className="font-medium">{e.description}</TableCell>
                    <TableCell className="font-mono text-sm">{fmt(e.amount, e.currency)}</TableCell>
                    <TableCell className="font-mono text-sm">{fmt(e.amount_usd)}</TableCell>
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
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">USD eq.</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Category</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Vendor</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Recurring</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {expenseList.length === 0 ? (
                  <TableRow><TableCell colSpan={7} className="text-center text-muted py-12">No expenses yet.</TableCell></TableRow>
                ) : expenseList.map((exp) => (
                  <TableRow key={exp.id} className="hover:bg-gray-50/80">
                    <TableCell className="text-sm text-muted">{new Date(exp.date).toLocaleDateString()}</TableCell>
                    <TableCell className="font-medium">{exp.name}</TableCell>
                    <TableCell className="font-mono text-sm">{fmt(exp.amount, exp.currency)}</TableCell>
                    <TableCell className="font-mono text-sm">{fmt(exp.amount_usd)}</TableCell>
                    <TableCell className="capitalize text-sm">{exp.category.replace(/_/g, " ")}</TableCell>
                    <TableCell className="text-sm">{exp.vendor || "\u2014"}</TableCell>
                    <TableCell>{exp.is_recurring ? <Badge variant="secondary" className="rounded-full text-xs">Recurring</Badge> : "\u2014"}</TableCell>
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
            <div className="grid grid-cols-2 gap-3">
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
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Custom interval (months)</Label>
                <Input
                  className="mt-1.5 rounded-lg"
                  type="number"
                  min={1}
                  step={1}
                  value={incomeForm.custom_interval_months}
                  disabled={incomeForm.recurrence_type !== "custom"}
                  onChange={(e) => setIncomeForm(f => ({ ...f, custom_interval_months: e.target.value }))}
                  required={incomeForm.recurrence_type === "custom"}
                />
              </div>
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
