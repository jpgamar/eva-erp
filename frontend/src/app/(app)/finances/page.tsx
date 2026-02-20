"use client";

import { useEffect, useState } from "react";
import {
  Plus, Wallet,
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

function fmt(amount: number | null | undefined, currency = "MXN") {
  if (amount == null) return "—";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

const EXPENSE_CATEGORIES = [
  "infrastructure", "ai_apis", "communication", "payment_fees",
  "domains_hosting", "marketing", "legal_accounting", "contractors",
  "office", "software_tools", "other",
];

const INCOME_CATEGORIES = ["subscription", "addon", "consulting", "custom_deal", "refund", "other"];

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  sent: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  paid: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  overdue: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  cancelled: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
};

export default function FinancesPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState("overview");
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

  const [incomeForm, setIncomeForm] = useState({ description: "", amount: "", currency: "MXN", category: "subscription", date: new Date().toISOString().split("T")[0], is_recurring: false });
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
      await incomeApi.create({ ...incomeForm, amount: parseFloat(incomeForm.amount) });
      toast.success("Income added");
      setAddIncomeOpen(false);
      setIncomeForm({ description: "", amount: "", currency: "MXN", category: "subscription", date: new Date().toISOString().split("T")[0], is_recurring: false });
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

  const netProfit = (incomeSummary?.total_period_mxn ?? 0) - (expenseSummary?.total_mxn ?? 0);
  const burnRate = expenseSummary?.recurring_total_mxn ?? 0;
  const runway = cashBalance && burnRate > 0 ? cashBalance.amount_mxn / burnRate : null;

  if (loading) {
    return <div className="flex items-center justify-center h-[calc(100vh-8rem)]"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>;
  }

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">Finances</h1>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="income">Income</TabsTrigger>
          <TabsTrigger value="expenses">Expenses</TabsTrigger>
          <TabsTrigger value="invoices">Invoices</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">MRR</div><div className="text-xl font-bold">{fmt(incomeSummary?.mrr)}</div></CardContent></Card>
            <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">Revenue (month)</div><div className="text-xl font-bold">{fmt(incomeSummary?.total_period_mxn)}</div></CardContent></Card>
            <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">Expenses</div><div className="text-xl font-bold">{fmt(expenseSummary?.total_mxn)}</div></CardContent></Card>
            <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">Net P/L</div><div className={`text-xl font-bold ${netProfit >= 0 ? "text-green-600" : "text-red-600"}`}>{fmt(netProfit)}</div></CardContent></Card>
            <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">Burn Rate/mo</div><div className="text-xl font-bold">{fmt(burnRate)}</div></CardContent></Card>
            <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">Runway</div><div className="text-xl font-bold">{runway != null ? `${runway.toFixed(1)} mo` : "—"}</div></CardContent></Card>
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Cash Balance</CardTitle>
              <Button size="sm" variant="outline" onClick={() => setCashOpen(true)}><Wallet className="h-4 w-4 mr-1" /> Update</Button>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{cashBalance ? fmt(cashBalance.amount_mxn) : "Not set"}</div>
              {cashBalance && <p className="text-xs text-muted-foreground mt-1">As of {new Date(cashBalance.date).toLocaleDateString()}{cashBalance.notes && ` — ${cashBalance.notes}`}</p>}
            </CardContent>
          </Card>

          {expenseSummary && Object.keys(expenseSummary.by_category).length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-base">Expenses by Category</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(expenseSummary.by_category).sort(([, a], [, b]) => b - a).map(([cat, amount]) => {
                    const pct = Number(expenseSummary.total_mxn) > 0 ? (amount / Number(expenseSummary.total_mxn)) * 100 : 0;
                    return (
                      <div key={cat} className="flex items-center gap-3">
                        <div className="w-32 text-sm truncate capitalize">{cat.replace(/_/g, " ")}</div>
                        <div className="flex-1 h-3 bg-muted rounded-full overflow-hidden"><div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} /></div>
                        <div className="w-28 text-sm text-right font-medium">{fmt(amount)}</div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="income" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Income</h2>
            <Button size="sm" onClick={() => setAddIncomeOpen(true)}><Plus className="h-4 w-4 mr-2" /> Add Entry</Button>
          </div>
          <Card>
            <Table>
              <TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Description</TableHead><TableHead>Amount</TableHead><TableHead>MXN eq.</TableHead><TableHead>Source</TableHead><TableHead>Category</TableHead></TableRow></TableHeader>
              <TableBody>
                {incomeList.length === 0 ? (
                  <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-8">No income entries yet.</TableCell></TableRow>
                ) : incomeList.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="text-sm">{new Date(e.date).toLocaleDateString()}</TableCell>
                    <TableCell className="font-medium">{e.description}</TableCell>
                    <TableCell>{fmt(e.amount, e.currency)}</TableCell>
                    <TableCell>{fmt(e.amount_mxn)}</TableCell>
                    <TableCell><Badge variant="secondary">{e.source}</Badge></TableCell>
                    <TableCell className="capitalize">{e.category}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        <TabsContent value="expenses" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Expenses</h2>
            <Button size="sm" onClick={() => setAddExpenseOpen(true)}><Plus className="h-4 w-4 mr-2" /> Add Expense</Button>
          </div>
          <Card>
            <Table>
              <TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Name</TableHead><TableHead>Amount</TableHead><TableHead>MXN eq.</TableHead><TableHead>Category</TableHead><TableHead>Vendor</TableHead><TableHead>Recurring</TableHead></TableRow></TableHeader>
              <TableBody>
                {expenseList.length === 0 ? (
                  <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground py-8">No expenses yet.</TableCell></TableRow>
                ) : expenseList.map((exp) => (
                  <TableRow key={exp.id}>
                    <TableCell className="text-sm">{new Date(exp.date).toLocaleDateString()}</TableCell>
                    <TableCell className="font-medium">{exp.name}</TableCell>
                    <TableCell>{fmt(exp.amount, exp.currency)}</TableCell>
                    <TableCell>{fmt(exp.amount_mxn)}</TableCell>
                    <TableCell className="capitalize">{exp.category.replace(/_/g, " ")}</TableCell>
                    <TableCell>{exp.vendor || "—"}</TableCell>
                    <TableCell>{exp.is_recurring ? <Badge variant="secondary">Recurring</Badge> : "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        <TabsContent value="invoices" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Invoices</h2>
            <Button size="sm" onClick={() => setAddInvoiceOpen(true)}><Plus className="h-4 w-4 mr-2" /> New Invoice</Button>
          </div>
          <Card>
            <Table>
              <TableHeader><TableRow><TableHead>Invoice #</TableHead><TableHead>Customer</TableHead><TableHead>Total</TableHead><TableHead>Status</TableHead><TableHead>Issue Date</TableHead><TableHead>Due Date</TableHead></TableRow></TableHeader>
              <TableBody>
                {invoiceList.length === 0 ? (
                  <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-8">No invoices yet.</TableCell></TableRow>
                ) : invoiceList.map((inv) => (
                  <TableRow key={inv.id}>
                    <TableCell className="font-medium">{inv.invoice_number}</TableCell>
                    <TableCell>{inv.customer_name}</TableCell>
                    <TableCell>{fmt(inv.total, inv.currency)}</TableCell>
                    <TableCell><Badge className={STATUS_COLORS[inv.status] || ""}>{inv.status}</Badge></TableCell>
                    <TableCell>{new Date(inv.issue_date).toLocaleDateString()}</TableCell>
                    <TableCell>{new Date(inv.due_date).toLocaleDateString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      <Dialog open={addIncomeOpen} onOpenChange={setAddIncomeOpen}>
        <DialogContent><DialogHeader><DialogTitle>Add Income</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleAddIncome(); }} className="space-y-3">
            <div><Label>Description *</Label><Input value={incomeForm.description} onChange={(e) => setIncomeForm(f => ({ ...f, description: e.target.value }))} required /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Amount *</Label><Input type="number" step="0.01" value={incomeForm.amount} onChange={(e) => setIncomeForm(f => ({ ...f, amount: e.target.value }))} required /></div>
              <div><Label>Currency</Label><Select value={incomeForm.currency} onValueChange={(v) => setIncomeForm(f => ({ ...f, currency: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="MXN">MXN</SelectItem><SelectItem value="USD">USD</SelectItem></SelectContent></Select></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Category</Label><Select value={incomeForm.category} onValueChange={(v) => setIncomeForm(f => ({ ...f, category: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{INCOME_CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select></div>
              <div><Label>Date</Label><Input type="date" value={incomeForm.date} onChange={(e) => setIncomeForm(f => ({ ...f, date: e.target.value }))} /></div>
            </div>
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setAddIncomeOpen(false)}>Cancel</Button><Button type="submit">Add</Button></div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={addExpenseOpen} onOpenChange={setAddExpenseOpen}>
        <DialogContent><DialogHeader><DialogTitle>Add Expense</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleAddExpense(); }} className="space-y-3">
            <div><Label>Name *</Label><Input value={expenseForm.name} onChange={(e) => setExpenseForm(f => ({ ...f, name: e.target.value }))} required /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Amount *</Label><Input type="number" step="0.01" value={expenseForm.amount} onChange={(e) => setExpenseForm(f => ({ ...f, amount: e.target.value }))} required /></div>
              <div><Label>Currency</Label><Select value={expenseForm.currency} onValueChange={(v) => setExpenseForm(f => ({ ...f, currency: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="USD">USD</SelectItem><SelectItem value="MXN">MXN</SelectItem></SelectContent></Select></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Category</Label><Select value={expenseForm.category} onValueChange={(v) => setExpenseForm(f => ({ ...f, category: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{EXPENSE_CATEGORIES.map(c => <SelectItem key={c} value={c}>{c.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select></div>
              <div><Label>Vendor</Label><Input value={expenseForm.vendor} onChange={(e) => setExpenseForm(f => ({ ...f, vendor: e.target.value }))} /></div>
            </div>
            <div><Label>Date</Label><Input type="date" value={expenseForm.date} onChange={(e) => setExpenseForm(f => ({ ...f, date: e.target.value }))} /></div>
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setAddExpenseOpen(false)}>Cancel</Button><Button type="submit">Add</Button></div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={addInvoiceOpen} onOpenChange={setAddInvoiceOpen}>
        <DialogContent><DialogHeader><DialogTitle>New Invoice</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleAddInvoice(); }} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Customer *</Label><Input value={invoiceForm.customer_name} onChange={(e) => setInvoiceForm(f => ({ ...f, customer_name: e.target.value }))} required /></div>
              <div><Label>Email</Label><Input value={invoiceForm.customer_email} onChange={(e) => setInvoiceForm(f => ({ ...f, customer_email: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label>Item *</Label><Input value={invoiceForm.item_desc} onChange={(e) => setInvoiceForm(f => ({ ...f, item_desc: e.target.value }))} required /></div>
              <div><Label>Qty</Label><Input type="number" value={invoiceForm.item_qty} onChange={(e) => setInvoiceForm(f => ({ ...f, item_qty: e.target.value }))} /></div>
              <div><Label>Price *</Label><Input type="number" step="0.01" value={invoiceForm.item_price} onChange={(e) => setInvoiceForm(f => ({ ...f, item_price: e.target.value }))} required /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label>Issue Date</Label><Input type="date" value={invoiceForm.issue_date} onChange={(e) => setInvoiceForm(f => ({ ...f, issue_date: e.target.value }))} /></div>
              <div><Label>Due Date *</Label><Input type="date" value={invoiceForm.due_date} onChange={(e) => setInvoiceForm(f => ({ ...f, due_date: e.target.value }))} required /></div>
              <div><Label>Tax</Label><Input type="number" step="0.01" value={invoiceForm.tax} onChange={(e) => setInvoiceForm(f => ({ ...f, tax: e.target.value }))} /></div>
            </div>
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setAddInvoiceOpen(false)}>Cancel</Button><Button type="submit">Create</Button></div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={cashOpen} onOpenChange={setCashOpen}>
        <DialogContent><DialogHeader><DialogTitle>Update Cash Balance</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleUpdateCash(); }} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Amount *</Label><Input type="number" step="0.01" value={cashForm.amount} onChange={(e) => setCashForm(f => ({ ...f, amount: e.target.value }))} required /></div>
              <div><Label>Currency</Label><Select value={cashForm.currency} onValueChange={(v) => setCashForm(f => ({ ...f, currency: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="MXN">MXN</SelectItem><SelectItem value="USD">USD</SelectItem></SelectContent></Select></div>
            </div>
            <div><Label>Date</Label><Input type="date" value={cashForm.date} onChange={(e) => setCashForm(f => ({ ...f, date: e.target.value }))} /></div>
            <div><Label>Notes</Label><Textarea value={cashForm.notes} onChange={(e) => setCashForm(f => ({ ...f, notes: e.target.value }))} rows={2} /></div>
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setCashOpen(false)}>Cancel</Button><Button type="submit">Update</Button></div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
