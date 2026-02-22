"use client";

import { useEffect, useState } from "react";
import { Plus, Search, Users, LayoutList, Columns3 } from "lucide-react";
import { toast } from "sonner";
import { customersApi } from "@/lib/api/customers";
import { TAX_SYSTEMS, CFDI_USES } from "@/lib/constants/sat";
import type { Customer, CustomerSummary } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { KanbanBoard } from "@/components/kanban/kanban-board";
import { cn } from "@/lib/utils";

function fmt(amount: number | null | undefined, currency = "USD") {
  if (amount == null) return "\u2014";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

const CUSTOMER_STATUSES = ["active", "trial", "paused", "churned"];

const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  trial: "Trial",
  paused: "Paused",
  churned: "Churned",
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  churned: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  paused: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  trial: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
};

const PLAN_COLORS: Record<string, string> = {
  starter: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  standard: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  pro: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  custom: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
};

const INITIAL_FORM = {
  company_name: "", contact_name: "", contact_email: "", contact_phone: "",
  legal_name: "", rfc: "", tax_regime: "", fiscal_zip: "", default_cfdi_use: "", fiscal_email: "",
  industry: "", website: "", plan_tier: "starter", mrr: "", mrr_currency: "MXN",
  billing_interval: "monthly", signup_date: new Date().toISOString().split("T")[0],
  referral_source: "", notes: "",
};

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [summary, setSummary] = useState<CustomerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [viewMode, setViewMode] = useState<"table" | "board">("board");
  const [addOpen, setAddOpen] = useState(false);
  const [detailCustomer, setDetailCustomer] = useState<Customer | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const [form, setForm] = useState({ ...INITIAL_FORM });

  const fetchData = async () => {
    try {
      const [custs, sum] = await Promise.all([
        customersApi.list({ status: statusFilter !== "all" ? statusFilter : undefined, search: search || undefined }),
        customersApi.summary(),
      ]);
      setCustomers(custs);
      setSummary(sum);
    } catch { toast.error("Failed to load customers"); } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [statusFilter, search]);

  const handleCreate = async () => {
    try {
      await customersApi.create({
        ...form,
        mrr: form.mrr ? parseFloat(form.mrr) : null,
        contact_email: form.contact_email || null,
        contact_phone: form.contact_phone || null,
        legal_name: form.legal_name || null,
        rfc: form.rfc ? form.rfc.toUpperCase() : null,
        tax_regime: form.tax_regime || null,
        fiscal_zip: form.fiscal_zip || null,
        default_cfdi_use: form.default_cfdi_use || null,
        fiscal_email: form.fiscal_email || null,
        industry: form.industry || null,
        website: form.website || null,
        referral_source: form.referral_source || null,
        notes: form.notes || null,
      });
      toast.success("Customer added");
      setAddOpen(false);
      setForm({ ...INITIAL_FORM });
      await fetchData();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const openDetail = async (customer: Customer) => {
    try {
      const detail = await customersApi.get(customer.id);
      setDetailCustomer(detail);
      setDetailOpen(true);
    } catch { toast.error("Failed to load customer"); }
  };

  const handleChurn = async () => {
    if (!detailCustomer) return;
    const reason = prompt("Churn reason?");
    try {
      await customersApi.update(detailCustomer.id, {
        status: "churned",
        churn_date: new Date().toISOString().split("T")[0],
        churn_reason: reason || null,
      });
      toast.success("Customer marked as churned");
      setDetailOpen(false);
      await fetchData();
    } catch { toast.error("Failed"); }
  };

  // Kanban helpers
  const kanbanColumns = (statusFilter === "all" ? CUSTOMER_STATUSES : [statusFilter]).map((s) => ({
    id: s,
    label: STATUS_LABELS[s] || s,
    color: STATUS_COLORS[s] || "bg-gray-100 text-gray-700",
  }));

  const handleKanbanStatusChange = async (customerId: string, newStatus: string) => {
    setCustomers((prev) =>
      prev.map((c) => (c.id === customerId ? { ...c, status: newStatus } : c))
    );
    try {
      await customersApi.update(customerId, { status: newStatus });
    } catch {
      await fetchData();
      toast.error("Failed to update status");
    }
  };

  const renderCustomerCard = (c: Customer) => (
    <div className="space-y-1.5">
      <p className="text-sm font-semibold text-foreground leading-tight">{c.company_name}</p>
      <p className="text-xs text-muted">{c.contact_name}</p>
      <div className="flex flex-wrap items-center gap-1">
        {c.plan_tier && (
          <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", PLAN_COLORS[c.plan_tier] || "bg-gray-100 text-gray-700")}>
            {c.plan_tier}
          </span>
        )}
      </div>
      {c.mrr != null && (
        <p className="text-[11px] font-mono text-muted">
          {fmt(c.mrr, c.mrr_currency)}
        </p>
      )}
    </div>
  );

  if (loading) {
    return <div className="flex items-center justify-center h-[calc(100vh-8rem)]"><div className="animate-spin h-8 w-8 border-4 border-accent border-t-transparent rounded-full" /></div>;
  }

  return (
    <div className="space-y-6 animate-erp-entrance">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-light">
            <Users className="h-5 w-5 text-accent" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Customers</p>
            <p className="text-xs text-muted">Registry and subscription tracking</p>
          </div>
        </div>
        <Button size="sm" className="rounded-lg bg-accent hover:bg-accent/90 text-white" onClick={() => setAddOpen(true)}><Plus className="h-4 w-4 mr-2" /> Add Customer</Button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-4">
          <div className="rounded-xl border border-border border-l-[3px] border-l-accent bg-card p-5">
            <p className="text-xs font-medium text-muted">Total</p>
            <p className="mt-0.5 font-mono text-xl font-bold text-foreground">{summary.total_customers}</p>
          </div>
          <div className="rounded-xl border border-border border-l-[3px] border-l-green-500 bg-card p-5">
            <p className="text-xs font-medium text-muted">Active</p>
            <p className="mt-0.5 font-mono text-xl font-bold text-green-600">{summary.active_customers}</p>
          </div>
          <div className="rounded-xl border border-border border-l-[3px] border-l-accent bg-card p-5">
            <p className="text-xs font-medium text-muted">MRR</p>
            <p className="mt-0.5 font-mono text-xl font-bold text-foreground">{fmt(summary.mrr_usd)}</p>
          </div>
          <div className="rounded-xl border border-border border-l-[3px] border-l-accent bg-card p-5">
            <p className="text-xs font-medium text-muted">ARPU</p>
            <p className="mt-0.5 font-mono text-xl font-bold text-foreground">{fmt(summary.arpu_usd)}</p>
          </div>
          <div className="rounded-xl border border-border border-l-[3px] border-l-red-500 bg-card p-5">
            <p className="text-xs font-medium text-muted">Churn Rate</p>
            <p className="mt-0.5 font-mono text-xl font-bold text-foreground">{summary.churn_rate_pct.toFixed(1)}%</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
          <input
            placeholder="Search customers..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-full rounded-lg border-0 bg-gray-100 pl-9 pr-3 text-sm outline-none placeholder:text-muted focus:ring-2 focus:ring-accent/20"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[150px] rounded-lg"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="churned">Churned</SelectItem>
            <SelectItem value="paused">Paused</SelectItem>
            <SelectItem value="trial">Trial</SelectItem>
          </SelectContent>
        </Select>
        {/* View toggle */}
        <div className="flex h-9 items-center rounded-lg border border-border bg-gray-50 p-0.5">
          <button
            onClick={() => setViewMode("board")}
            className={cn(
              "flex h-7 w-8 items-center justify-center rounded-md transition-colors",
              viewMode === "board" ? "bg-white shadow-sm text-foreground" : "text-muted hover:text-foreground"
            )}
            title="Board view"
          >
            <Columns3 className="h-4 w-4" />
          </button>
          <button
            onClick={() => setViewMode("table")}
            className={cn(
              "flex h-7 w-8 items-center justify-center rounded-md transition-colors",
              viewMode === "table" ? "bg-white shadow-sm text-foreground" : "text-muted hover:text-foreground"
            )}
            title="Table view"
          >
            <LayoutList className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Customer Table / Board */}
      {viewMode === "board" ? (
        <KanbanBoard
          columns={kanbanColumns}
          items={customers}
          renderCard={renderCustomerCard}
          onStatusChange={handleKanbanStatusChange}
          onCardClick={(c) => openDetail(c)}
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="bg-gray-50/80">
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Company</TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Contact</TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Plan</TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">MRR</TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Fiscal</TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Status</TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Signup</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {customers.length === 0 ? (
                <TableRow><TableCell colSpan={7} className="text-center text-muted py-12">No customers yet.</TableCell></TableRow>
              ) : customers.map((c) => (
                <TableRow key={c.id} className="cursor-pointer hover:bg-gray-50/80" onClick={() => openDetail(c)}>
                  <TableCell className="font-medium">{c.company_name}</TableCell>
                  <TableCell>{c.contact_name}</TableCell>
                  <TableCell>{c.plan_tier ? <Badge className={`rounded-full text-xs ${PLAN_COLORS[c.plan_tier] || ""}`}>{c.plan_tier}</Badge> : "\u2014"}</TableCell>
                  <TableCell className="font-medium">{fmt(c.mrr, c.mrr_currency)}</TableCell>
                  <TableCell>
                    {c.rfc && c.legal_name ? (
                      <span className="inline-flex items-center gap-1.5 text-xs">
                        <span className="h-2 w-2 rounded-full bg-green-500" />
                        Complete
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                        <span className="h-2 w-2 rounded-full bg-gray-300" />
                        Pending
                      </span>
                    )}
                  </TableCell>
                  <TableCell><Badge className={`rounded-full text-xs ${STATUS_COLORS[c.status] || ""}`}>{c.status}</Badge></TableCell>
                  <TableCell className="text-sm">{c.signup_date ? new Date(c.signup_date).toLocaleDateString() : "\u2014"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Detail Sheet */}
      <Sheet open={detailOpen} onOpenChange={setDetailOpen}>
        <SheetContent className="w-[450px] sm:w-[550px] overflow-y-auto">
          {detailCustomer && (
            <div className="space-y-5 pt-4">
              <SheetHeader>
                <SheetTitle className="text-left">{detailCustomer.company_name}</SheetTitle>
              </SheetHeader>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-xs text-muted-foreground">Contact</Label><p className="text-sm font-medium">{detailCustomer.contact_name}</p></div>
                  <div><Label className="text-xs text-muted-foreground">Email</Label><p className="text-sm">{detailCustomer.contact_email || "\u2014"}</p></div>
                  <div><Label className="text-xs text-muted-foreground">Phone</Label><p className="text-sm">{detailCustomer.contact_phone || "\u2014"}</p></div>
                  <div><Label className="text-xs text-muted-foreground">Industry</Label><p className="text-sm">{detailCustomer.industry || "\u2014"}</p></div>
                </div>
                <Separator />
                <div className="grid grid-cols-3 gap-3">
                  <div><Label className="text-xs text-muted-foreground">Plan</Label><p className="text-sm font-medium capitalize">{detailCustomer.plan_tier || "\u2014"}</p></div>
                  <div><Label className="text-xs text-muted-foreground">MRR</Label><p className="text-sm font-medium">{fmt(detailCustomer.mrr, detailCustomer.mrr_currency)}</p></div>
                  <div><Label className="text-xs text-muted-foreground">ARR</Label><p className="text-sm">{fmt(detailCustomer.arr, detailCustomer.mrr_currency)}</p></div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-xs text-muted-foreground">Billing</Label><p className="text-sm capitalize">{detailCustomer.billing_interval || "\u2014"}</p></div>
                  <div><Label className="text-xs text-muted-foreground">LTV</Label><p className="text-sm">{fmt(detailCustomer.lifetime_value_usd)}</p></div>
                </div>
                <Separator />
                {/* Fiscal Info Section */}
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Fiscal Info</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div><Label className="text-xs text-muted-foreground">Legal Name</Label><p className="text-sm">{detailCustomer.legal_name || "\u2014"}</p></div>
                    <div><Label className="text-xs text-muted-foreground">RFC</Label><p className="text-sm font-mono">{detailCustomer.rfc || "\u2014"}</p></div>
                    <div><Label className="text-xs text-muted-foreground">Tax Regime</Label><p className="text-sm">{detailCustomer.tax_regime ? TAX_SYSTEMS.find(t => t.value === detailCustomer.tax_regime)?.label || detailCustomer.tax_regime : "\u2014"}</p></div>
                    <div><Label className="text-xs text-muted-foreground">Fiscal ZIP</Label><p className="text-sm">{detailCustomer.fiscal_zip || "\u2014"}</p></div>
                    <div><Label className="text-xs text-muted-foreground">Default CFDI Use</Label><p className="text-sm">{detailCustomer.default_cfdi_use ? CFDI_USES.find(u => u.value === detailCustomer.default_cfdi_use)?.label || detailCustomer.default_cfdi_use : "\u2014"}</p></div>
                    <div><Label className="text-xs text-muted-foreground">Fiscal Email</Label><p className="text-sm">{detailCustomer.fiscal_email || "\u2014"}</p></div>
                  </div>
                </div>
                <Separator />
                <div><Label className="text-xs text-muted-foreground">Referral Source</Label><p className="text-sm">{detailCustomer.referral_source || "\u2014"}</p></div>
                {detailCustomer.notes && <div><Label className="text-xs text-muted-foreground">Notes</Label><p className="text-sm whitespace-pre-wrap">{detailCustomer.notes}</p></div>}
                {detailCustomer.tags && detailCustomer.tags.length > 0 && (
                  <div><Label className="text-xs text-muted-foreground">Tags</Label><div className="flex flex-wrap gap-1.5 mt-1">{detailCustomer.tags.map(t => <Badge key={t} variant="secondary">{t}</Badge>)}</div></div>
                )}
              </div>
              <Separator />
              {detailCustomer.status === "active" && (
                <Button variant="destructive" size="sm" onClick={handleChurn} className="w-full">Mark as Churned</Button>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* Add Customer Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto p-0">
          <div className="border-b border-border bg-gray-50/80 px-6 py-4">
            <h2 className="text-base font-semibold text-foreground">Add Customer</h2>
            <p className="text-xs text-muted">Fill in the details to register a new customer</p>
          </div>
          <form onSubmit={(e) => { e.preventDefault(); handleCreate(); }} className="space-y-3 px-6 py-4">
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Company Name *</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" value={form.company_name} onChange={(e) => setForm(f => ({ ...f, company_name: e.target.value }))} required /></div>
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Contact Name *</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" value={form.contact_name} onChange={(e) => setForm(f => ({ ...f, contact_name: e.target.value }))} required /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Email</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" value={form.contact_email} onChange={(e) => setForm(f => ({ ...f, contact_email: e.target.value }))} /></div>
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Phone</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" value={form.contact_phone} onChange={(e) => setForm(f => ({ ...f, contact_phone: e.target.value }))} /></div>
            </div>

            {/* Fiscal Info Section */}
            <Separator />
            <p className="text-xs font-semibold uppercase tracking-wider text-muted">Fiscal Info (for CFDI)</p>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Legal Name</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" value={form.legal_name} onChange={(e) => setForm(f => ({ ...f, legal_name: e.target.value }))} /></div>
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">RFC</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" value={form.rfc} maxLength={13} onChange={(e) => setForm(f => ({ ...f, rfc: e.target.value.toUpperCase() }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Tax Regime</Label>
                <Select value={form.tax_regime} onValueChange={(v) => setForm(f => ({ ...f, tax_regime: v }))}>
                  <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="Select..." /></SelectTrigger>
                  <SelectContent>{TAX_SYSTEMS.map(ts => <SelectItem key={ts.value} value={ts.value}>{ts.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Fiscal ZIP</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" value={form.fiscal_zip} maxLength={5} onChange={(e) => setForm(f => ({ ...f, fiscal_zip: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Default CFDI Use</Label>
                <Select value={form.default_cfdi_use} onValueChange={(v) => setForm(f => ({ ...f, default_cfdi_use: v }))}>
                  <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="Select..." /></SelectTrigger>
                  <SelectContent>{CFDI_USES.map(u => <SelectItem key={u.value} value={u.value}>{u.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Fiscal Email</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" type="email" value={form.fiscal_email} onChange={(e) => setForm(f => ({ ...f, fiscal_email: e.target.value }))} /></div>
            </div>
            <Separator />

            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Plan</Label>
                <Select value={form.plan_tier} onValueChange={(v) => setForm(f => ({ ...f, plan_tier: v }))}>
                  <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="starter">Starter ($50 USD)</SelectItem>
                    <SelectItem value="standard">Standard ($200 USD)</SelectItem>
                    <SelectItem value="pro">Pro ($500 USD)</SelectItem>
                    <SelectItem value="custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">MRR</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" type="number" step="0.01" value={form.mrr} onChange={(e) => setForm(f => ({ ...f, mrr: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Industry</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" value={form.industry} onChange={(e) => setForm(f => ({ ...f, industry: e.target.value }))} /></div>
              <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Signup Date</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" type="date" value={form.signup_date} onChange={(e) => setForm(f => ({ ...f, signup_date: e.target.value }))} /></div>
            </div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Referral Source</Label><Input className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" value={form.referral_source} onChange={(e) => setForm(f => ({ ...f, referral_source: e.target.value }))} placeholder="Who referred them?" /></div>
            <div><Label className="text-xs font-semibold uppercase tracking-wider text-muted">Notes</Label><Textarea className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20" value={form.notes} onChange={(e) => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} /></div>
            <div className="flex justify-end gap-2 pt-2"><Button type="button" variant="outline" className="rounded-lg" onClick={() => setAddOpen(false)}>Cancel</Button><Button type="submit" className="rounded-lg bg-accent hover:bg-accent/90 text-white">Add Customer</Button></div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
