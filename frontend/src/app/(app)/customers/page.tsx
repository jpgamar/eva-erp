"use client";

import { useEffect, useState } from "react";
import { Plus, Search, Users, TrendingUp, DollarSign, BarChart3 } from "lucide-react";
import { toast } from "sonner";
import { customersApi } from "@/lib/api/customers";
import type { Customer, CustomerSummary } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";

function fmt(amount: number | null | undefined, currency = "MXN") {
  if (amount == null) return "—";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

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

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [summary, setSummary] = useState<CustomerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [addOpen, setAddOpen] = useState(false);
  const [detailCustomer, setDetailCustomer] = useState<Customer | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const [form, setForm] = useState({
    company_name: "", contact_name: "", contact_email: "", contact_phone: "",
    industry: "", website: "", plan_tier: "starter", mrr: "", mrr_currency: "MXN",
    billing_interval: "monthly", signup_date: new Date().toISOString().split("T")[0],
    referral_source: "", notes: "",
  });

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
        industry: form.industry || null,
        website: form.website || null,
        referral_source: form.referral_source || null,
        notes: form.notes || null,
      });
      toast.success("Customer added");
      setAddOpen(false);
      setForm({ company_name: "", contact_name: "", contact_email: "", contact_phone: "", industry: "", website: "", plan_tier: "starter", mrr: "", mrr_currency: "MXN", billing_interval: "monthly", signup_date: new Date().toISOString().split("T")[0], referral_source: "", notes: "" });
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

  if (loading) {
    return <div className="flex items-center justify-center h-[calc(100vh-8rem)]"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>;
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Customers</h1>
          <p className="text-muted-foreground text-sm">Customer registry and subscription tracking</p>
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)}><Plus className="h-4 w-4 mr-2" /> Add Customer</Button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">Total</div><div className="text-2xl font-bold flex items-center gap-2"><Users className="h-5 w-5 text-muted-foreground" />{summary.total_customers}</div></CardContent></Card>
          <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">Active</div><div className="text-2xl font-bold text-green-600">{summary.active_customers}</div></CardContent></Card>
          <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">MRR</div><div className="text-2xl font-bold">{fmt(summary.mrr_mxn)}</div></CardContent></Card>
          <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">ARPU</div><div className="text-2xl font-bold">{fmt(summary.arpu_mxn)}</div></CardContent></Card>
          <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">Churn Rate</div><div className="text-2xl font-bold">{summary.churn_rate_pct.toFixed(1)}%</div></CardContent></Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search customers..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[150px]"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="churned">Churned</SelectItem>
            <SelectItem value="paused">Paused</SelectItem>
            <SelectItem value="trial">Trial</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Customer Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Company</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Plan</TableHead>
              <TableHead>MRR</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Signup</TableHead>
              <TableHead>Referral</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {customers.length === 0 ? (
              <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground py-8">No customers yet.</TableCell></TableRow>
            ) : customers.map((c) => (
              <TableRow key={c.id} className="cursor-pointer hover:bg-accent/50" onClick={() => openDetail(c)}>
                <TableCell className="font-medium">{c.company_name}</TableCell>
                <TableCell>{c.contact_name}</TableCell>
                <TableCell>{c.plan_tier ? <Badge className={PLAN_COLORS[c.plan_tier] || ""}>{c.plan_tier}</Badge> : "—"}</TableCell>
                <TableCell className="font-medium">{fmt(c.mrr, c.mrr_currency)}</TableCell>
                <TableCell><Badge className={STATUS_COLORS[c.status] || ""}>{c.status}</Badge></TableCell>
                <TableCell className="text-sm">{c.signup_date ? new Date(c.signup_date).toLocaleDateString() : "—"}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{c.referral_source || "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

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
                  <div><Label className="text-xs text-muted-foreground">Email</Label><p className="text-sm">{detailCustomer.contact_email || "—"}</p></div>
                  <div><Label className="text-xs text-muted-foreground">Phone</Label><p className="text-sm">{detailCustomer.contact_phone || "—"}</p></div>
                  <div><Label className="text-xs text-muted-foreground">Industry</Label><p className="text-sm">{detailCustomer.industry || "—"}</p></div>
                </div>
                <Separator />
                <div className="grid grid-cols-3 gap-3">
                  <div><Label className="text-xs text-muted-foreground">Plan</Label><p className="text-sm font-medium capitalize">{detailCustomer.plan_tier || "—"}</p></div>
                  <div><Label className="text-xs text-muted-foreground">MRR</Label><p className="text-sm font-medium">{fmt(detailCustomer.mrr, detailCustomer.mrr_currency)}</p></div>
                  <div><Label className="text-xs text-muted-foreground">ARR</Label><p className="text-sm">{fmt(detailCustomer.arr, detailCustomer.mrr_currency)}</p></div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-xs text-muted-foreground">Billing</Label><p className="text-sm capitalize">{detailCustomer.billing_interval || "—"}</p></div>
                  <div><Label className="text-xs text-muted-foreground">LTV</Label><p className="text-sm">{fmt(detailCustomer.lifetime_value_mxn)}</p></div>
                </div>
                <Separator />
                <div><Label className="text-xs text-muted-foreground">Referral Source</Label><p className="text-sm">{detailCustomer.referral_source || "—"}</p></div>
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
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Add Customer</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleCreate(); }} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Company Name *</Label><Input value={form.company_name} onChange={(e) => setForm(f => ({ ...f, company_name: e.target.value }))} required /></div>
              <div><Label>Contact Name *</Label><Input value={form.contact_name} onChange={(e) => setForm(f => ({ ...f, contact_name: e.target.value }))} required /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Email</Label><Input value={form.contact_email} onChange={(e) => setForm(f => ({ ...f, contact_email: e.target.value }))} /></div>
              <div><Label>Phone</Label><Input value={form.contact_phone} onChange={(e) => setForm(f => ({ ...f, contact_phone: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Plan</Label>
                <Select value={form.plan_tier} onValueChange={(v) => setForm(f => ({ ...f, plan_tier: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="starter">Starter ($999 MXN)</SelectItem>
                    <SelectItem value="standard">Standard ($3,999 MXN)</SelectItem>
                    <SelectItem value="pro">Pro ($9,999 MXN)</SelectItem>
                    <SelectItem value="custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label>MRR</Label><Input type="number" step="0.01" value={form.mrr} onChange={(e) => setForm(f => ({ ...f, mrr: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Industry</Label><Input value={form.industry} onChange={(e) => setForm(f => ({ ...f, industry: e.target.value }))} /></div>
              <div><Label>Signup Date</Label><Input type="date" value={form.signup_date} onChange={(e) => setForm(f => ({ ...f, signup_date: e.target.value }))} /></div>
            </div>
            <div><Label>Referral Source</Label><Input value={form.referral_source} onChange={(e) => setForm(f => ({ ...f, referral_source: e.target.value }))} placeholder="Who referred them?" /></div>
            <div><Label>Notes</Label><Textarea value={form.notes} onChange={(e) => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} /></div>
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button><Button type="submit">Add Customer</Button></div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
