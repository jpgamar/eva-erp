"use client";

import { useEffect, useState } from "react";
import {
  Plus, Search, Handshake, ExternalLink, CheckCircle2,
  FileText, Users, Copy,
} from "lucide-react";
import { toast } from "sonner";
import { evaPlatformApi } from "@/lib/api/eva-platform";
import type { EvaPartner, EvaPartnerDetail, PartnerDeal, EvaAccount, AccountOnboarding } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";

/* ---------- Badge color maps ---------- */

const TYPE_COLORS: Record<string, string> = {
  WHITE_LABEL: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  SOLUTIONS: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
};

const STAGE_COLORS: Record<string, string> = {
  TO_CONTACT: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  CONTACTED: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  IMPLEMENTATION: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  WON: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  LOST: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

const STAGE_LABELS: Record<string, string> = {
  TO_CONTACT: "To Contact",
  CONTACTED: "Contacted",
  IMPLEMENTATION: "Implementation",
  WON: "Won",
  LOST: "Lost",
};

/* ---------- Initial form state ---------- */

const INITIAL_FORM = {
  name: "",
  brand_name: "",
  type: "WHITE_LABEL",
  owner_email: "",
  owner_name: "",
  contact_email: "",
};

const INITIAL_DEAL_ACCOUNT_FORM = {
  name: "",
  owner_email: "",
  plan_tier: "STANDARD",
  send_setup_email: true,
};

/* ---------- Component ---------- */

export default function PartnersPage() {
  const [partners, setPartners] = useState<EvaPartner[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");

  // New partner dialog
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ ...INITIAL_FORM });
  const [creating, setCreating] = useState(false);

  // Detail sheet
  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState<EvaPartnerDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [dealAccountOpen, setDealAccountOpen] = useState(false);
  const [activeDealForAccount, setActiveDealForAccount] = useState<PartnerDeal | null>(null);
  const [creatingDealAccount, setCreatingDealAccount] = useState(false);
  const [dealAccountForm, setDealAccountForm] = useState({ ...INITIAL_DEAL_ACCOUNT_FORM });
  const [dealOnboarding, setDealOnboarding] = useState<AccountOnboarding | null>(null);

  const copyOnboardingLink = async (link: string) => {
    try {
      await navigator.clipboard.writeText(link);
      toast.success("Setup link copied");
    } catch {
      toast.error("Failed to copy setup link");
    }
  };

  /* ---- Computed KPIs ---- */
  const totalPartners = partners.length;
  const activePartners = partners.filter((p) => p.is_active).length;
  const totalDeals = partners.reduce((sum, p) => sum + p.deal_count, 0);
  const totalAccounts = partners.reduce((sum, p) => sum + p.account_count, 0);

  /* ---- Data fetching ---- */

  const fetchPartners = async () => {
    try {
      const data = await evaPlatformApi.listPartners({
        search: search || undefined,
        type: typeFilter !== "all" ? typeFilter : undefined,
      });
      setPartners(data);
    } catch {
      toast.error("Failed to load partners");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPartners();
  }, [search, typeFilter]);

  /* ---- Create partner ---- */

  const handleCreate = async () => {
    setCreating(true);
    try {
      await evaPlatformApi.createPartner({
        name: form.name,
        brand_name: form.brand_name || null,
        type: form.type,
        owner_email: form.owner_email,
        owner_name: form.owner_name,
        contact_email: form.contact_email || null,
      });
      toast.success("Partner created");
      setAddOpen(false);
      setForm({ ...INITIAL_FORM });
      await fetchPartners();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to create partner");
    } finally {
      setCreating(false);
    }
  };

  /* ---- Open detail sheet ---- */

  const openDetail = async (partner: EvaPartner) => {
    setDetailOpen(true);
    setDetailLoading(true);
    try {
      const data = await evaPlatformApi.getPartner(partner.id);
      setDetail(data);
    } catch {
      toast.error("Failed to load partner details");
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  /* ---- Refresh detail after mutations ---- */

  const refreshDetail = async (partnerId: string) => {
    try {
      const data = await evaPlatformApi.getPartner(partnerId);
      setDetail(data);
      await fetchPartners();
    } catch {
      toast.error("Failed to refresh partner details");
    }
  };

  /* ---- Deal actions ---- */

  const handleMarkWon = async (deal: PartnerDeal) => {
    try {
      await evaPlatformApi.markDealWon(deal.id);
      toast.success(`Deal "${deal.company_name}" marked as won`);
      if (detail) await refreshDetail(detail.id);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to mark deal as won");
    }
  };

  const handleMarkLost = async (deal: PartnerDeal) => {
    try {
      await evaPlatformApi.markDealLost(deal.id);
      toast.success(`Deal "${deal.company_name}" marked as lost`);
      if (detail) await refreshDetail(detail.id);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to mark deal as lost");
    }
  };

  const handleCreateAccount = (deal: PartnerDeal) => {
    setActiveDealForAccount(deal);
    setDealOnboarding(null);
    setDealAccountForm({
      name: deal.company_name || "",
      owner_email: deal.contact_email || "",
      plan_tier: String(deal.plan_tier || "STANDARD").toUpperCase(),
      send_setup_email: true,
    });
    setDealAccountOpen(true);
  };

  const handleSubmitDealAccount = async () => {
    if (!activeDealForAccount) return;
    if (!dealAccountForm.name.trim() || !dealAccountForm.owner_email.trim()) {
      toast.error("Account name and owner email are required.");
      return;
    }

    setCreatingDealAccount(true);
    try {
      const result = await evaPlatformApi.createAccountFromDeal(activeDealForAccount.id, {
        name: dealAccountForm.name.trim(),
        owner_email: dealAccountForm.owner_email.trim().toLowerCase(),
        plan_tier: dealAccountForm.plan_tier,
        send_setup_email: dealAccountForm.send_setup_email,
      });
      setDealOnboarding(result.onboarding);
      toast.success(
        result.onboarding.email_status === "sent"
          ? `Account created for "${activeDealForAccount.company_name}" and setup email sent`
          : `Account created for "${activeDealForAccount.company_name}". Share setup link manually.`,
      );
      if (detail) await refreshDetail(detail.id);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to create account from deal");
    } finally {
      setCreatingDealAccount(false);
    }
  };

  /* ---- Impersonate ---- */

  const handleImpersonate = async (account: EvaAccount) => {
    try {
      const result = await evaPlatformApi.impersonateAccount(account.id);
      toast.success(`Impersonating ${result.account_name}`);
      window.open(result.magic_link_url, "_blank", "noopener,noreferrer");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to impersonate account");
    }
  };

  /* ---- Loading state ---- */

  if (loading) {
    return (
      <div className="space-y-6 animate-erp-entrance">
        {/* Skeleton header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Skeleton className="h-10 w-10 rounded-xl" />
            <div>
              <Skeleton className="h-4 w-24" />
              <Skeleton className="mt-1 h-3 w-40" />
            </div>
          </div>
          <Skeleton className="h-9 w-32 rounded-lg" />
        </div>
        {/* Skeleton KPI cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center gap-4">
                <Skeleton className="h-11 w-11 rounded-xl shrink-0" />
                <div className="space-y-1.5">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="h-5 w-10" />
                </div>
              </div>
            </div>
          ))}
        </div>
        {/* Skeleton filters */}
        <div className="flex gap-3 items-center">
          <Skeleton className="h-9 flex-1 max-w-sm rounded-lg" />
          <Skeleton className="h-9 w-[170px] rounded-lg" />
        </div>
        {/* Skeleton table */}
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <div className="space-y-3 p-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-erp-entrance">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-light">
            <Handshake className="h-5 w-5 text-accent" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Partners</p>
            <p className="text-xs text-muted">Manage partners and deal pipeline</p>
          </div>
        </div>
        <Button
          size="sm"
          className="rounded-lg bg-accent hover:bg-accent/90 text-white"
          onClick={() => setAddOpen(true)}
        >
          <Plus className="h-4 w-4 mr-2" /> New Partner
        </Button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border border-l-[3px] border-l-accent bg-card p-5">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-light">
              <Handshake className="h-5 w-5 text-accent" />
            </div>
            <div>
              <p className="text-xs font-medium text-muted">Total Partners</p>
              <p className="mt-0.5 font-mono text-xl font-bold text-foreground">
                {totalPartners}
              </p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-border border-l-[3px] border-l-green-500 bg-card p-5">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-green-50">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-muted">Active</p>
              <p className="mt-0.5 font-mono text-xl font-bold text-foreground">
                {activePartners}
              </p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-border border-l-[3px] border-l-blue-500 bg-card p-5">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50">
              <FileText className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-muted">Total Deals</p>
              <p className="mt-0.5 font-mono text-xl font-bold text-foreground">
                {totalDeals}
              </p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-border border-l-[3px] border-l-purple-500 bg-card p-5">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-purple-50">
              <Users className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-muted">Linked Accounts</p>
              <p className="mt-0.5 font-mono text-xl font-bold text-foreground">
                {totalAccounts}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
          <input
            placeholder="Search partners..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-full rounded-lg border-0 bg-gray-100 pl-9 pr-3 text-sm outline-none placeholder:text-muted focus:ring-2 focus:ring-accent/20"
          />
        </div>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-[170px] rounded-lg">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="WHITE_LABEL">White Label</SelectItem>
            <SelectItem value="SOLUTIONS">Solutions</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Partners Table */}
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50/80">
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Name</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Brand</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Type</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Status</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Deals</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Accounts</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {partners.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted py-12">
                  No partners yet.
                </TableCell>
              </TableRow>
            ) : (
              partners.map((p) => (
                <TableRow
                  key={p.id}
                  className="cursor-pointer hover:bg-gray-50/80"
                  onClick={() => openDetail(p)}
                >
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell>{p.brand_name || "\u2014"}</TableCell>
                  <TableCell>
                    <Badge className={`rounded-full text-xs ${TYPE_COLORS[p.type] || ""}`}>
                      {p.type === "WHITE_LABEL" ? "White Label" : p.type}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {p.is_active ? (
                      <span className="inline-flex items-center gap-1.5 text-xs">
                        <span className="h-2 w-2 rounded-full bg-green-500" />
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                        <span className="h-2 w-2 rounded-full bg-red-500" />
                        Inactive
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="font-medium">{p.deal_count}</TableCell>
                  <TableCell className="font-medium">{p.account_count}</TableCell>
                  <TableCell className="text-sm">
                    {new Date(p.created_at).toLocaleDateString()}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Detail Sheet */}
      <Sheet open={detailOpen} onOpenChange={setDetailOpen}>
        <SheetContent className="w-[500px] sm:w-[640px] overflow-y-auto">
          {detailLoading ? (
            <div className="space-y-4 pt-6">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-32" />
              <Separator />
              <div className="grid grid-cols-3 gap-4">
                <Skeleton className="h-20" />
                <Skeleton className="h-20" />
                <Skeleton className="h-20" />
              </div>
              <Separator />
              <Skeleton className="h-32" />
            </div>
          ) : detail ? (
            <div className="space-y-5 pt-4">
              <SheetHeader>
                <SheetTitle className="text-left">{detail.name}</SheetTitle>
              </SheetHeader>

              {/* Partner Info */}
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs text-muted-foreground">Brand</Label>
                    <p className="text-sm font-medium">{detail.brand_name || "\u2014"}</p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Type</Label>
                    <p className="text-sm">
                      <Badge className={`rounded-full text-xs ${TYPE_COLORS[detail.type] || ""}`}>
                        {detail.type === "WHITE_LABEL" ? "White Label" : detail.type}
                      </Badge>
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Status</Label>
                    <p className="text-sm">
                      {detail.is_active ? (
                        <span className="inline-flex items-center gap-1.5 text-xs">
                          <span className="h-2 w-2 rounded-full bg-green-500" />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                          <span className="h-2 w-2 rounded-full bg-red-500" />
                          Inactive
                        </span>
                      )}
                    </p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Contact Email</Label>
                    <p className="text-sm">{detail.contact_email || "\u2014"}</p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Custom Domain</Label>
                    <p className="text-sm">{detail.custom_domain || "\u2014"}</p>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Stats with icon containers */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  Stats
                </p>
                <div className="grid grid-cols-3 gap-3">
                  <div className="rounded-xl border border-border border-l-[3px] border-l-accent bg-card p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-light">
                        <FileText className="h-4 w-4 text-accent" />
                      </div>
                      <div>
                        <p className="text-xs font-medium text-muted">Deals</p>
                        <p className="font-mono text-lg font-bold text-foreground">
                          {detail.deal_count}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="rounded-xl border border-border border-l-[3px] border-l-green-500 bg-card p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-green-50">
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                      </div>
                      <div>
                        <p className="text-xs font-medium text-muted">Won</p>
                        <p className="font-mono text-lg font-bold text-green-600">
                          {detail.won_deals}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="rounded-xl border border-border border-l-[3px] border-l-blue-500 bg-card p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50">
                        <Users className="h-4 w-4 text-blue-600" />
                      </div>
                      <div>
                        <p className="text-xs font-medium text-muted">Accounts</p>
                        <p className="font-mono text-lg font-bold text-blue-600">
                          {detail.account_count}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Accounts List */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  Accounts
                </p>
                {detail.accounts.length === 0 ? (
                  <p className="text-sm text-muted py-4 text-center">No linked accounts</p>
                ) : (
                  <div className="overflow-hidden rounded-lg border border-border">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-gray-50/80">
                          <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">
                            Name
                          </TableHead>
                          <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">
                            Plan
                          </TableHead>
                          <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">
                            Status
                          </TableHead>
                          <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">
                            Actions
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detail.accounts.map((acc) => (
                          <TableRow key={acc.id}>
                            <TableCell className="font-medium text-sm">{acc.name}</TableCell>
                            <TableCell className="text-sm capitalize">
                              {acc.plan_tier || "\u2014"}
                            </TableCell>
                            <TableCell>
                              {acc.is_active ? (
                                <span className="inline-flex items-center gap-1.5 text-xs">
                                  <span className="h-2 w-2 rounded-full bg-green-500" />
                                  Active
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                                  <span className="h-2 w-2 rounded-full bg-red-500" />
                                  Inactive
                                </span>
                              )}
                            </TableCell>
                            <TableCell>
                              <Button
                                size="sm"
                                variant="outline"
                                className="rounded-lg text-xs h-7 border-accent/30 text-accent hover:bg-accent/10"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleImpersonate(acc);
                                }}
                              >
                                <ExternalLink className="h-3 w-3 mr-1" />
                                Impersonate
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>

              <Separator />

              {/* Deals Pipeline */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  Deals Pipeline
                </p>
                {detail.deals.length === 0 ? (
                  <p className="text-sm text-muted py-4 text-center">No deals yet</p>
                ) : (
                  <div className="overflow-hidden rounded-lg border border-border">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-gray-50/80">
                          <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">
                            Company
                          </TableHead>
                          <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">
                            Stage
                          </TableHead>
                          <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">
                            Plan
                          </TableHead>
                          <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">
                            Contact
                          </TableHead>
                          <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">
                            Actions
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detail.deals.map((deal) => (
                          <TableRow key={deal.id}>
                            <TableCell className="font-medium text-sm">
                              {deal.company_name}
                            </TableCell>
                            <TableCell>
                              <Badge
                                className={`rounded-full text-xs ${STAGE_COLORS[deal.stage] || ""}`}
                              >
                                {STAGE_LABELS[deal.stage] || deal.stage}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm capitalize">
                              {deal.plan_tier}
                            </TableCell>
                            <TableCell className="text-sm">
                              {deal.contact_name || deal.contact_email || "\u2014"}
                            </TableCell>
                            <TableCell>
                              <div className="flex gap-1.5 flex-wrap">
                                {deal.stage !== "WON" && deal.stage !== "LOST" && (
                                  <>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="rounded-lg text-xs h-7 border-green-200 text-green-700 hover:bg-green-50"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleMarkWon(deal);
                                      }}
                                    >
                                      Won
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="rounded-lg text-xs h-7 border-red-200 text-red-700 hover:bg-red-50"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleMarkLost(deal);
                                      }}
                                    >
                                      Lost
                                    </Button>
                                  </>
                                )}
                                {deal.stage === "WON" && !deal.linked_account_id && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="rounded-lg text-xs h-7 border-accent text-accent hover:bg-accent/10"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleCreateAccount(deal);
                                    }}
                                  >
                                    Create Account
                                  </Button>
                                )}
                                {deal.stage === "WON" && deal.linked_account_id && (
                                  <span className="text-xs text-green-600 font-medium">
                                    Account linked
                                  </span>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

      {/* Deal Create Account Dialog */}
      <Dialog
        open={dealAccountOpen}
        onOpenChange={(open) => {
          setDealAccountOpen(open);
          if (!open) {
            setActiveDealForAccount(null);
            setDealOnboarding(null);
          }
        }}
      >
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto p-0">
          <div className="border-b border-border bg-gray-50/80 px-6 py-4">
            <DialogHeader>
              <DialogTitle className="text-base font-semibold text-foreground">
                Create Account from Deal
              </DialogTitle>
            </DialogHeader>
            <p className="text-xs text-muted">
              {activeDealForAccount ? activeDealForAccount.company_name : "Confirm owner details before provisioning"}
            </p>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmitDealAccount();
            }}
            className="space-y-3 px-6 py-4"
          >
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
                Account Name *
              </Label>
              <Input
                className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                value={dealAccountForm.name}
                onChange={(e) => setDealAccountForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
                Owner Email *
              </Label>
              <Input
                className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                type="email"
                value={dealAccountForm.owner_email}
                onChange={(e) => setDealAccountForm((f) => ({ ...f, owner_email: e.target.value }))}
                required
              />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
                Plan Tier *
              </Label>
              <Select
                value={dealAccountForm.plan_tier}
                onValueChange={(value) => setDealAccountForm((f) => ({ ...f, plan_tier: value }))}
              >
                <SelectTrigger className="mt-1.5 rounded-lg">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="STARTER">Starter</SelectItem>
                  <SelectItem value="STANDARD">Standard</SelectItem>
                  <SelectItem value="PRO">Pro</SelectItem>
                  <SelectItem value="CUSTOM">Custom</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <label className="flex items-center gap-2 rounded-lg border border-border bg-gray-50/70 px-3 py-2 text-sm">
              <input
                type="checkbox"
                checked={dealAccountForm.send_setup_email}
                onChange={(e) =>
                  setDealAccountForm((f) => ({ ...f, send_setup_email: e.target.checked }))
                }
              />
              Send setup email to owner
            </label>

            {dealOnboarding && (
              <div className="rounded-lg border border-border bg-gray-50/80 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-foreground">Owner onboarding</p>
                  <Badge
                    className={
                      dealOnboarding.email_status === "sent"
                        ? "rounded-full text-xs bg-green-100 text-green-700"
                        : dealOnboarding.email_status === "failed"
                          ? "rounded-full text-xs bg-amber-100 text-amber-700"
                          : "rounded-full text-xs bg-gray-100 text-gray-700"
                    }
                  >
                    {dealOnboarding.email_status}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-muted">
                  {dealOnboarding.email_message || "Share the setup link with the owner."}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  className="mt-3 h-8 rounded-lg text-xs"
                  onClick={() => copyOnboardingLink(dealOnboarding.onboarding_link)}
                >
                  <Copy className="h-3.5 w-3.5 mr-1.5" />
                  Copy setup link
                </Button>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                className="rounded-lg"
                onClick={() => setDealAccountOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                className="rounded-lg bg-accent hover:bg-accent/90 text-white"
                disabled={creatingDealAccount}
              >
                {creatingDealAccount ? "Creating..." : "Create Account"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Add Partner Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto p-0">
          <div className="border-b border-border bg-gray-50/80 px-6 py-4">
            <DialogHeader>
              <DialogTitle className="text-base font-semibold text-foreground">
                New Partner
              </DialogTitle>
            </DialogHeader>
            <p className="text-xs text-muted">Register a new partner to start tracking deals</p>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleCreate();
            }}
            className="space-y-3 px-6 py-4"
          >
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Name *
                </Label>
                <Input
                  className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  required
                />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Brand Name
                </Label>
                <Input
                  className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                  value={form.brand_name}
                  onChange={(e) => setForm((f) => ({ ...f, brand_name: e.target.value }))}
                />
              </div>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
                Type *
              </Label>
              <Select
                value={form.type}
                onValueChange={(v) => setForm((f) => ({ ...f, type: v }))}
              >
                <SelectTrigger className="mt-1.5 rounded-lg">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="WHITE_LABEL">White Label</SelectItem>
                  <SelectItem value="SOLUTIONS">Solutions</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Owner Email *
                </Label>
                <Input
                  className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                  type="email"
                  value={form.owner_email}
                  onChange={(e) => setForm((f) => ({ ...f, owner_email: e.target.value }))}
                  required
                />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Owner Name *
                </Label>
                <Input
                  className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                  value={form.owner_name}
                  onChange={(e) => setForm((f) => ({ ...f, owner_name: e.target.value }))}
                  required
                />
              </div>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">
                Contact Email
              </Label>
              <Input
                className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                type="email"
                value={form.contact_email}
                onChange={(e) => setForm((f) => ({ ...f, contact_email: e.target.value }))}
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                className="rounded-lg"
                onClick={() => setAddOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                className="rounded-lg bg-accent hover:bg-accent/90 text-white"
                disabled={creating}
              >
                {creating ? "Creating..." : "Create Partner"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
