"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Plus, Search, Users,
  Phone, Building2, Trash2,
  Save, X, ChevronRight, ChevronLeft,
  ShoppingBag, Home, Check,
  LayoutList, Columns3,
} from "lucide-react";
import { toast } from "sonner";
import { prospectsApi } from "@/lib/api/prospects";
import { useAuth } from "@/lib/auth/context";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { KanbanBoard } from "@/components/kanban/kanban-board";

const STATUSES = ["identified", "contacted", "interested", "demo_scheduled", "demo_done", "proposal_sent", "negotiating", "won", "lost"];

const STATUS_COLORS: Record<string, string> = {
  identified: "bg-gray-100 text-gray-700",
  contacted: "bg-blue-50 text-blue-700",
  interested: "bg-cyan-50 text-cyan-700",
  demo_scheduled: "bg-purple-50 text-purple-700",
  demo_done: "bg-indigo-50 text-indigo-700",
  proposal_sent: "bg-orange-50 text-orange-700",
  negotiating: "bg-yellow-50 text-yellow-700",
  won: "bg-green-50 text-green-700",
  lost: "bg-red-50 text-red-700",
};

const STATUS_LABELS: Record<string, string> = {
  identified: "Identified",
  contacted: "Contacted",
  interested: "Interested",
  demo_scheduled: "Demo Scheduled",
  demo_done: "Demo Done",
  proposal_sent: "Proposal Sent",
  negotiating: "Negotiating",
  won: "Won",
  lost: "Lost",
};

const URGENCY_OPTIONS = [
  { value: "priority_high", label: "Urgent", color: "bg-red-50 text-red-700 border-red-200" },
  { value: "priority_medium", label: "So-so", color: "bg-amber-50 text-amber-700 border-amber-200" },
  { value: "priority_low", label: "Not urgent", color: "bg-gray-100 text-gray-500 border-gray-300" },
];

const URGENCY_COLORS: Record<string, string> = {
  priority_high: "bg-red-50 text-red-700",
  priority_medium: "bg-amber-50 text-amber-700",
  priority_low: "bg-gray-100 text-gray-500",
};

const URGENCY_LABELS: Record<string, string> = {
  priority_high: "Urgent",
  priority_medium: "So-so",
  priority_low: "Not urgent",
};

const URGENCY_SORT_ORDER: Record<string, number> = {
  priority_high: 0,
  priority_medium: 1,
  priority_low: 2,
};

function getUrgency(tags: string[] | null): string | null {
  if (!tags) return null;
  return tags.find(t => t.startsWith("priority_")) || null;
}

interface Prospect {
  id: string;
  company_name: string;
  contact_name: string;
  contact_email: string | null;
  contact_phone: string | null;
  contact_role: string | null;
  website: string | null;
  industry: string | null;
  status: string;
  source: string;
  referred_by: string | null;
  estimated_plan: string | null;
  estimated_mrr: number | null;
  estimated_mrr_currency: string;
  estimated_mrr_usd: number | null;
  notes: string | null;
  next_follow_up: string | null;
  assigned_to: string | null;
  tags: string[] | null;
  lost_reason: string | null;
  converted_to_customer_id: string | null;
  created_at: string;
  updated_at: string;
}

type EditForm = {
  company_name: string;
  contact_name: string;
  contact_phone: string;
  website: string;
  status: string;
  notes: string;
  products: string[];
  urgency: string;
};

function prospectToForm(p: Prospect): EditForm {
  return {
    company_name: p.company_name,
    contact_name: p.contact_name,
    contact_phone: p.contact_phone || "",
    website: p.website || "",
    status: p.status,
    notes: p.notes || "",
    products: (p.tags || []).filter(t => t === "eva_commerce" || t === "eva_rents"),
    urgency: getUrgency(p.tags) || "",
  };
}

function buildTags(products: string[], urgency: string): string[] | null {
  const tags = [...products];
  if (urgency) tags.push(urgency);
  return tags.length > 0 ? tags : null;
}

function sortByUrgency(a: Prospect, b: Prospect): number {
  const ua = getUrgency(a.tags);
  const ub = getUrgency(b.tags);
  const oa = ua ? URGENCY_SORT_ORDER[ua] : 3;
  const ob = ub ? URGENCY_SORT_ORDER[ub] : 3;
  return oa - ob;
}

export default function ProspectsPage() {
  const { user } = useAuth();
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<"table" | "board">("board");

  // Add wizard
  const [addOpen, setAddOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);
  const [form, setForm] = useState({
    company_name: "", contact_name: "", contact_phone: "",
    notes: "", products: [] as string[], urgency: "",
  });

  // Detail sheet
  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState<Prospect | null>(null);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [editStep, setEditStep] = useState(0);
  const [saving, setSaving] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [list, sum] = await Promise.all([
        prospectsApi.list({ search: search || undefined }),
        prospectsApi.summary(),
      ]);
      setProspects([...list].sort(sortByUrgency));
      setSummary(sum);
    } catch {
      toast.error("Failed to load prospects");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const resetWizard = () => {
    setWizardStep(0);
    setForm({
      company_name: "", contact_name: "", contact_phone: "",
      notes: "", products: [], urgency: "",
    });
  };

  const handleCreate = async () => {
    try {
      const { products, urgency, ...rest } = form;
      await prospectsApi.create({
        ...rest,
        contact_phone: rest.contact_phone || null,
        notes: rest.notes || null,
        assigned_to: user?.id,
        tags: buildTags(products, urgency),
      });
      toast.success("Prospect added");
      setAddOpen(false);
      resetWizard();
      await fetchData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to create prospect");
    }
  };

  const openDetail = (p: Prospect) => {
    setDetail(p);
    setEditForm(prospectToForm(p));
    setEditStep(0);
    setDetailOpen(true);
  };

  const handleSave = async () => {
    if (!detail || !editForm) return;
    setSaving(true);
    try {
      const updated = await prospectsApi.update(detail.id, {
        company_name: editForm.company_name,
        contact_name: editForm.contact_name,
        contact_phone: editForm.contact_phone || null,
        website: editForm.website || null,
        status: editForm.status,
        notes: editForm.notes || null,
        tags: buildTags(editForm.products, editForm.urgency),
      });
      setDetail(updated);
      setEditForm(prospectToForm(updated));
      toast.success("Prospect updated");
      setDetailOpen(false);
      await fetchData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to update");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!detail) return;
    try {
      await prospectsApi.delete(detail.id);
      toast.success("Prospect deleted");
      setDetailOpen(false);
      await fetchData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to delete");
    }
  };

  // Kanban helpers
  const kanbanColumns = STATUSES.map((s) => ({
    id: s,
    label: STATUS_LABELS[s] || s,
    color: STATUS_COLORS[s] || "bg-gray-100 text-gray-700",
  }));

  const handleKanbanStatusChange = async (prospectId: string, newStatus: string) => {
    setProspects((prev) =>
      prev.map((p) => (p.id === prospectId ? { ...p, status: newStatus } : p))
    );
    try {
      await prospectsApi.update(prospectId, { status: newStatus });
    } catch {
      await fetchData();
      toast.error("Failed to update status");
    }
  };

  const renderProspectCard = (p: Prospect) => {
    const urgency = getUrgency(p.tags);
    return (
      <div className="space-y-1.5">
        <p className="text-sm font-semibold text-foreground leading-tight">{p.company_name}</p>
        <p className="text-xs text-muted">{p.contact_name}</p>
        <div className="flex flex-wrap items-center gap-1">
          {urgency && (
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", URGENCY_COLORS[urgency])}>
              {URGENCY_LABELS[urgency]}
            </span>
          )}
          {p.tags?.includes("eva_commerce") && (
            <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold text-indigo-600">Commerce</span>
          )}
          {p.tags?.includes("eva_rents") && (
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-600">Rents</span>
          )}
        </div>
        {p.estimated_mrr != null && (
          <p className="text-[11px] font-mono text-muted">
            ${p.estimated_mrr.toLocaleString()} /mo
          </p>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <div className="animate-spin h-8 w-8 border-4 border-accent border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-5 animate-erp-entrance">
      {/* KPI row */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="rounded-xl border border-border border-l-[3px] border-l-accent bg-card p-5">
            <div className="flex items-center gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-light">
                <Users className="h-5 w-5 text-accent" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">Total Prospects</p>
                <p className="mt-0.5 font-mono text-xl font-bold text-foreground">{summary.total}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-border border-l-[3px] border-l-green-500 bg-card p-5">
            <div className="flex items-center gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-green-50">
                <Check className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">Won</p>
                <p className="mt-0.5 font-mono text-xl font-bold text-green-600">{summary.by_status?.won || 0}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-end gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search..."
              className="h-9 w-48 rounded-lg bg-gray-100 pl-9 pr-3 text-sm outline-none transition-colors placeholder:text-muted focus:bg-white focus:ring-2 focus:ring-accent/20"
            />
          </div>
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
          <button
            onClick={() => setAddOpen(true)}
            className="flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98]"
          >
            <Plus className="h-4 w-4" />
            New
          </button>
      </div>

      {/* Table / Board */}
      {viewMode === "board" ? (
        <KanbanBoard
          columns={kanbanColumns}
          items={prospects}
          renderCard={renderProspectCard}
          onStatusChange={handleKanbanStatusChange}
          onCardClick={(p) => openDetail(p)}
          columnWidth="w-60"
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="bg-gray-50/80">
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Urgency</TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Company</TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Contact</TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Product</TableHead>
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {prospects.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted py-12">
                    No prospects yet.
                  </TableCell>
                </TableRow>
              ) : (
                prospects.map((p) => {
                  const urgency = getUrgency(p.tags);
                  return (
                    <TableRow
                      key={p.id}
                      className="cursor-pointer transition-colors hover:bg-gray-50/60"
                      onClick={() => openDetail(p)}
                    >
                      <TableCell>
                        {urgency ? (
                          <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", URGENCY_COLORS[urgency])}>
                            {URGENCY_LABELS[urgency]}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-300">{"\u2014"}</span>
                        )}
                      </TableCell>
                      <TableCell className="font-medium text-foreground">{p.company_name}</TableCell>
                      <TableCell className="text-sm text-foreground">{p.contact_name}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {p.tags?.includes("eva_commerce") && (
                            <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold text-indigo-600">Commerce</span>
                          )}
                          {p.tags?.includes("eva_rents") && (
                            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-600">Rents</span>
                          )}
                          {(!p.tags || !p.tags.some(t => t === "eva_commerce" || t === "eva_rents")) && <span className="text-xs text-gray-300">{"\u2014"}</span>}
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", STATUS_COLORS[p.status])}>
                          {STATUS_LABELS[p.status] || p.status}
                        </span>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* ---------- Detail / Edit Sheet ---------- */}
      <Sheet open={detailOpen} onOpenChange={setDetailOpen}>
        <SheetContent className="w-[480px] sm:w-[560px] overflow-y-auto border-l border-border p-0">
          <SheetTitle className="sr-only">Prospect Details</SheetTitle>
          {detail && editForm && (
            <div className="flex h-full flex-col">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-border bg-gray-50/80 px-6 py-4">
                <div>
                  <h2 className="text-base font-bold text-foreground">{editForm.company_name || detail.company_name}</h2>
                  <p className="text-xs text-muted">{editForm.contact_name || detail.contact_name}</p>
                </div>
                <button
                  onClick={() => setDetailOpen(false)}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-muted transition-colors hover:bg-gray-200 hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Step dots */}
              <div className="flex items-center justify-center gap-3 border-b border-border bg-white px-6 py-3">
                {["Product", "Contact"].map((label, i) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => setEditStep(i)}
                    className={cn(
                      "flex items-center gap-1.5 text-xs font-medium transition-colors",
                      i === editStep ? "text-accent" : "text-gray-300 hover:text-gray-500"
                    )}
                  >
                    <div className={cn(
                      "h-2 w-2 rounded-full transition-colors",
                      i === editStep ? "bg-accent" : "bg-gray-200"
                    )} />
                    {label}
                  </button>
                ))}
              </div>

              <div className="flex-1 px-6 py-5">
                {/* Step 0: Product + Urgency */}
                {editStep === 0 && (
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-sm font-bold text-foreground">Product Interest</h3>
                      <p className="mt-1 text-xs text-muted">Which EVA products is this prospect interested in?</p>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { key: "eva_commerce", label: "EVA Commerce", desc: "E-commerce & inventory", icon: ShoppingBag },
                        { key: "eva_rents", label: "EVA Rents", desc: "Property & lease mgmt", icon: Home },
                      ].map((product) => {
                        const selected = editForm.products.includes(product.key);
                        return (
                          <button
                            key={product.key}
                            type="button"
                            onClick={() => setEditForm(f => f && ({
                              ...f,
                              products: selected
                                ? f.products.filter(p => p !== product.key)
                                : [...f.products, product.key],
                            }))}
                            className={cn(
                              "relative flex flex-col items-center gap-3 rounded-xl border-2 p-6 text-center transition-all hover:shadow-md",
                              selected
                                ? "border-accent bg-accent-light shadow-sm"
                                : "border-gray-200 bg-white hover:border-gray-300"
                            )}
                          >
                            {selected && (
                              <div className="absolute right-2.5 top-2.5 flex h-5 w-5 items-center justify-center rounded-full bg-accent">
                                <Check className="h-3 w-3 text-white" />
                              </div>
                            )}
                            <div className={cn(
                              "flex h-12 w-12 items-center justify-center rounded-xl",
                              selected ? "bg-accent/20" : "bg-gray-100"
                            )}>
                              <product.icon className={cn("h-6 w-6", selected ? "text-accent" : "text-gray-400")} />
                            </div>
                            <div>
                              <p className={cn("text-sm font-semibold", selected ? "text-accent" : "text-foreground")}>{product.label}</p>
                              <p className="mt-0.5 text-[11px] text-muted">{product.desc}</p>
                            </div>
                          </button>
                        );
                      })}
                    </div>

                    {/* Urgency */}
                    <div>
                      <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Urgency</label>
                      <div className="flex gap-2">
                        {URGENCY_OPTIONS.map((opt) => (
                          <button
                            key={opt.value}
                            type="button"
                            onClick={() => setEditForm(f => f && ({ ...f, urgency: f.urgency === opt.value ? "" : opt.value }))}
                            className={cn(
                              "rounded-full border px-3.5 py-1.5 text-xs font-medium transition-all",
                              editForm.urgency === opt.value
                                ? opt.color
                                : "border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-600"
                            )}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Status quick-change */}
                    <div>
                      <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Status</label>
                      <div className="flex flex-wrap gap-1.5">
                        {STATUSES.map((s) => (
                          <button
                            key={s}
                            type="button"
                            onClick={() => setEditForm(f => f && ({ ...f, status: s }))}
                            className={cn(
                              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                              editForm.status === s
                                ? STATUS_COLORS[s]
                                : "border border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-600"
                            )}
                          >
                            {STATUS_LABELS[s] || s}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-2">
                      <button
                        type="button"
                        onClick={handleDelete}
                        className="flex h-9 items-center gap-1.5 rounded-lg border border-red-200 px-3 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 active:scale-[0.98]"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </button>
                      <button type="button" onClick={() => setEditStep(1)} className="flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98]">
                        Next <ChevronRight className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )}

                {/* Step 1: Contact (final step with Save) */}
                {editStep === 1 && (
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-sm font-bold text-foreground">Company & Contact</h3>
                      <p className="mt-1 text-xs text-muted">Edit company details and contact information.</p>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <FieldInput icon={Building2} label="Company" value={editForm.company_name} onChange={(v) => setEditForm(f => f && ({ ...f, company_name: v }))} />
                      <FieldInput icon={Users} label="Contact Name" value={editForm.contact_name} onChange={(v) => setEditForm(f => f && ({ ...f, contact_name: v }))} />
                    </div>
                    <FieldInput icon={Phone} label="Phone" value={editForm.contact_phone} onChange={(v) => setEditForm(f => f && ({ ...f, contact_phone: v }))} placeholder="+52 ..." />
                    <div>
                      <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Notes</label>
                      <Textarea
                        value={editForm.notes}
                        onChange={(e) => setEditForm(f => f && ({ ...f, notes: e.target.value }))}
                        placeholder="Add notes about this prospect..."
                        rows={3}
                        className="rounded-lg border-gray-200 bg-gray-50/80 text-sm placeholder:text-gray-300"
                      />
                    </div>

                    <div className="flex justify-between pt-2">
                      <button type="button" onClick={() => setEditStep(0)} className="flex h-9 items-center gap-1.5 rounded-lg border border-gray-200 px-4 text-sm font-medium text-muted transition-colors hover:bg-gray-50 hover:text-foreground">
                        <ChevronLeft className="h-4 w-4" /> Back
                      </button>
                      <button
                        type="button"
                        onClick={handleSave}
                        disabled={saving}
                        className="flex h-9 items-center gap-1.5 rounded-lg bg-accent px-5 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
                      >
                        <Save className="h-3.5 w-3.5" />
                        {saving ? "Saving..." : "Save"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* ---------- Add Prospect Wizard ---------- */}
      <Dialog open={addOpen} onOpenChange={(open) => { setAddOpen(open); if (!open) resetWizard(); }}>
        <DialogContent className="max-w-lg overflow-hidden rounded-xl p-0">
          <DialogHeader className="sr-only">
            <DialogTitle>New Prospect</DialogTitle>
          </DialogHeader>

          {/* Progress bar */}
          <div className="flex items-center gap-0 border-b border-border bg-gray-50/80 px-6 py-4">
            {["Product", "Company & Contact"].map((label, i) => (
              <div key={label} className="flex items-center">
                {i > 0 && <div className={cn("mx-2 h-px w-6", i <= wizardStep ? "bg-accent" : "bg-gray-200")} />}
                <div className="flex items-center gap-2">
                  <div className={cn(
                    "flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold transition-colors",
                    i < wizardStep ? "bg-accent text-white" : i === wizardStep ? "bg-accent text-white" : "bg-gray-200 text-gray-500"
                  )}>
                    {i < wizardStep ? <Check className="h-3.5 w-3.5" /> : i + 1}
                  </div>
                  <span className={cn("text-xs font-medium", i <= wizardStep ? "text-foreground" : "text-gray-400")}>{label}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="px-6 pb-6 pt-5">
            {/* Step 0: Product + Urgency Selection */}
            {wizardStep === 0 && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-bold text-foreground">What product are they interested in?</h3>
                  <p className="mt-1 text-xs text-muted">Select one or both products for this prospect.</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { key: "eva_commerce", label: "EVA Commerce", desc: "E-commerce & inventory management", icon: ShoppingBag },
                    { key: "eva_rents", label: "EVA Rents", desc: "Property & lease management", icon: Home },
                  ].map((product) => {
                    const selected = form.products.includes(product.key);
                    return (
                      <button
                        key={product.key}
                        type="button"
                        onClick={() => setForm(f => ({
                          ...f,
                          products: selected
                            ? f.products.filter(p => p !== product.key)
                            : [...f.products, product.key],
                        }))}
                        className={cn(
                          "relative flex flex-col items-center gap-3 rounded-xl border-2 p-6 text-center transition-all hover:shadow-md",
                          selected
                            ? "border-accent bg-accent-light shadow-sm"
                            : "border-gray-200 bg-white hover:border-gray-300"
                        )}
                      >
                        {selected && (
                          <div className="absolute right-2.5 top-2.5 flex h-5 w-5 items-center justify-center rounded-full bg-accent">
                            <Check className="h-3 w-3 text-white" />
                          </div>
                        )}
                        <div className={cn(
                          "flex h-12 w-12 items-center justify-center rounded-xl",
                          selected ? "bg-accent/20" : "bg-gray-100"
                        )}>
                          <product.icon className={cn("h-6 w-6", selected ? "text-accent" : "text-gray-400")} />
                        </div>
                        <div>
                          <p className={cn("text-sm font-semibold", selected ? "text-accent" : "text-foreground")}>{product.label}</p>
                          <p className="mt-0.5 text-[11px] text-muted">{product.desc}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>

                {/* Urgency */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">How urgent is this prospect?</label>
                  <div className="flex gap-2">
                    {URGENCY_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setForm(f => ({ ...f, urgency: f.urgency === opt.value ? "" : opt.value }))}
                        className={cn(
                          "rounded-full border px-3.5 py-1.5 text-xs font-medium transition-all",
                          form.urgency === opt.value
                            ? opt.color
                            : "border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-600"
                        )}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button type="button" onClick={() => setAddOpen(false)} className="h-9 rounded-lg border border-gray-200 px-4 text-sm font-medium text-muted transition-colors hover:bg-gray-50 hover:text-foreground">
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={() => setWizardStep(1)}
                    disabled={form.products.length === 0}
                    className="flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-40"
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}

            {/* Step 1: Company & Contact (final step) */}
            {wizardStep === 1 && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-bold text-foreground">Company & Contact Info</h3>
                  <p className="mt-1 text-xs text-muted">Who are we reaching out to?</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-[11px] font-semibold uppercase tracking-wider text-muted">Company *</Label>
                    <input value={form.company_name} onChange={(e) => setForm(f => ({ ...f, company_name: e.target.value }))} className="mt-1.5 h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20" />
                  </div>
                  <div>
                    <Label className="text-[11px] font-semibold uppercase tracking-wider text-muted">Contact Name *</Label>
                    <input value={form.contact_name} onChange={(e) => setForm(f => ({ ...f, contact_name: e.target.value }))} className="mt-1.5 h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20" />
                  </div>
                </div>
                <div>
                  <Label className="text-[11px] font-semibold uppercase tracking-wider text-muted">Phone</Label>
                  <input value={form.contact_phone} onChange={(e) => setForm(f => ({ ...f, contact_phone: e.target.value }))} className="mt-1.5 h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20" placeholder="+52 ..." />
                </div>

                {/* Summary chips */}
                <div className="flex flex-wrap items-center gap-1.5 rounded-lg bg-gray-50 px-3 py-2.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">Adding:</span>
                  <span className="rounded-full bg-white px-2.5 py-0.5 text-xs font-medium text-foreground shadow-sm">{form.company_name || "..."}</span>
                  <span className="text-[10px] text-muted">/</span>
                  <span className="rounded-full bg-white px-2.5 py-0.5 text-xs font-medium text-foreground shadow-sm">{form.contact_name || "..."}</span>
                  {form.products.map(p => (
                    <span key={p} className="rounded-full bg-accent-light px-2.5 py-0.5 text-[10px] font-semibold text-accent">
                      {p === "eva_commerce" ? "Commerce" : "Rents"}
                    </span>
                  ))}
                  {form.urgency && (
                    <span className={cn("rounded-full px-2.5 py-0.5 text-[10px] font-semibold", URGENCY_COLORS[form.urgency])}>
                      {URGENCY_LABELS[form.urgency]}
                    </span>
                  )}
                </div>

                <div className="flex justify-between pt-1">
                  <button type="button" onClick={() => setWizardStep(0)} className="flex h-9 items-center gap-1.5 rounded-lg border border-gray-200 px-4 text-sm font-medium text-muted transition-colors hover:bg-gray-50 hover:text-foreground">
                    <ChevronLeft className="h-4 w-4" />
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={handleCreate}
                    disabled={!form.company_name.trim() || !form.contact_name.trim()}
                    className="flex h-9 items-center gap-1.5 rounded-lg bg-accent px-5 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-40"
                  >
                    <Check className="h-4 w-4" />
                    Add Prospect
                  </button>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ---------- Reusable inline field ---------- */
function FieldInput({
  label, value, onChange, placeholder, type = "text", icon: Icon,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  icon?: React.ElementType;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">{label}</label>
      <div className="relative">
        {Icon && (
          <Icon className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400" />
        )}
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={cn(
            "h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 text-sm text-foreground outline-none transition-all placeholder:text-gray-300 focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20",
            Icon ? "pl-8 pr-3" : "px-3"
          )}
        />
      </div>
    </div>
  );
}
