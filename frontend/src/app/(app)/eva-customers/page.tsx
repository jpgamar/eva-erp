"use client";

import { useEffect, useState } from "react";
import {
  Plus, Search, Building2, FileText, Trash2, Check,
  ExternalLink, CheckCircle2, Handshake, DollarSign, TrendingDown,
  CalendarDays, CreditCard, Hash, User2, ShieldAlert, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { evaPlatformApi } from "@/lib/api/eva-platform";
import { dashboardApi, type DashboardData } from "@/lib/api/dashboard";
import type { EvaAccount, AccountDraft, PlatformDashboard } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const TABS = [
  { key: "active", label: "Active Accounts" },
  { key: "drafts", label: "Draft Accounts" },
];

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  inactive: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

const DRAFT_STATUS_COLORS: Record<string, string> = {
  draft: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  approved: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

const PLAN_COLORS: Record<string, string> = {
  starter: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  standard: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  pro: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  custom: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
};

const INITIAL_ACCOUNT_FORM = {
  name: "",
  owner_email: "",
  owner_name: "",
  account_type: "COMMERCE" as string,
  plan_tier: "starter",
  billing_cycle: "monthly",
  facturapi_org_api_key: "",
};

const INITIAL_DRAFT_FORM = {
  name: "",
  owner_email: "",
  owner_name: "",
  account_type: "COMMERCE" as string,
  plan_tier: "starter",
  billing_cycle: "monthly",
  facturapi_org_api_key: "",
  notes: "",
};

const getApiErrorMessage = (error: any, fallback: string): string => {
  const detail = error?.response?.data?.detail;
  const errorCode = error?.response?.data?.error_code || detail?.code;
  if (typeof errorCode === "string") {
    if (errorCode === "owner_duplicate_unresolved") {
      return "Owner email exists but could not be linked. Please retry in a few seconds.";
    }
    if (errorCode === "supabase_upstream_unavailable") {
      return "Provisioning service is temporarily unavailable. Please try again.";
    }
  }
  if (detail && typeof detail === "object") {
    const detailMessage = detail.message || detail.msg;
    if (typeof detailMessage === "string" && detailMessage.trim()) {
      return detailMessage;
    }
  }
  if (typeof detail === "string" && detail.trim()) {
    if (detail.includes("already registered but could not be linked")) {
      return "Owner email exists but could not be linked. Please retry in a few seconds.";
    }
    if (detail.includes("temporarily unavailable")) {
      return "Provisioning service is temporarily unavailable. Please try again.";
    }
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (typeof first?.msg === "string" && first.msg.trim()) {
      return first.msg;
    }
  }
  if (typeof error?.message === "string" && error.message.trim()) {
    return error.message;
  }
  return fallback;
};

export default function EvaCustomersPage() {
  const [accounts, setAccounts] = useState<EvaAccount[]>([]);
  const [drafts, setDrafts] = useState<AccountDraft[]>([]);
  const [dashboard, setDashboard] = useState<PlatformDashboard | null>(null);
  const [metrics, setMetrics] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState("active");

  // Dialogs
  const [addAccountOpen, setAddAccountOpen] = useState(false);
  const [addDraftOpen, setAddDraftOpen] = useState(false);

  // Detail sheet
  const [selectedAccount, setSelectedAccount] = useState<EvaAccount | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  // Forms
  const [accountForm, setAccountForm] = useState({ ...INITIAL_ACCOUNT_FORM });
  const [draftForm, setDraftForm] = useState({ ...INITIAL_DRAFT_FORM });

  // Action loading
  const [approving, setApproving] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [creatingAccount, setCreatingAccount] = useState(false);
  const [deletingAccount, setDeletingAccount] = useState(false);


  const fetchData = async () => {
    try {
      const [accts, drfts, dash, met] = await Promise.all([
        evaPlatformApi.listAccounts({ search: search || undefined }),
        evaPlatformApi.listDrafts(),
        evaPlatformApi.dashboard(),
        dashboardApi.summary().catch(() => null),
      ]);
      setAccounts(accts);
      setDrafts(drfts);
      setDashboard(dash);
      setMetrics(met);
    } catch {
      toast.error("Failed to load Eva accounts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [search]);

  const handleCreateAccount = async () => {
    if (creatingAccount) return;
    setCreatingAccount(true);
    try {
      await evaPlatformApi.createAccount({
        ...accountForm,
        name: accountForm.name.trim(),
        owner_email: accountForm.owner_email.trim().toLowerCase(),
        owner_name: accountForm.owner_name.trim(),
        facturapi_org_api_key: accountForm.facturapi_org_api_key || null,
      });
      toast.success("Account created successfully");
      setAddAccountOpen(false);
      setAccountForm({ ...INITIAL_ACCOUNT_FORM });
      await fetchData();
    } catch (e: any) {
      toast.error(getApiErrorMessage(e, "Failed to create account"));
    } finally {
      setCreatingAccount(false);
    }
  };

  const handleCreateDraft = async () => {
    try {
      await evaPlatformApi.createDraft({
        ...draftForm,
        facturapi_org_api_key: draftForm.facturapi_org_api_key || null,
        notes: draftForm.notes || null,
      });
      toast.success("Draft created successfully");
      setAddDraftOpen(false);
      setDraftForm({ ...INITIAL_DRAFT_FORM });
      await fetchData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to create draft");
    }
  };

  const handleApproveDraft = async (id: string) => {
    setApproving(id);
    try {
      await evaPlatformApi.approveDraft(id);
      toast.success("Draft approved and account provisioned");
      await fetchData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to approve draft");
    } finally {
      setApproving(null);
    }
  };

  const handleDeleteDraft = async (id: string) => {
    setDeleting(id);
    try {
      await evaPlatformApi.deleteDraft(id);
      toast.success("Draft deleted");
      await fetchData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to delete draft");
    } finally {
      setDeleting(null);
    }
  };

  const handleImpersonate = async (account: EvaAccount) => {
    try {
      const result = await evaPlatformApi.impersonateAccount(account.id);
      toast.success(`Impersonating ${result.account_name}`);
      const win = window.open(result.magic_link_url, "_blank", "noopener,noreferrer");
      if (!win) {
        window.location.href = result.magic_link_url;
      }
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to impersonate account");
    }
  };

  const handleDeleteAccount = async (account: EvaAccount) => {
    const confirmed = window.confirm(
      `Are you sure you want to deactivate "${account.name}"? This will set the account to inactive.`
    );
    if (!confirmed) return;
    setDeletingAccount(true);
    try {
      await evaPlatformApi.deleteAccount(account.id);
      toast.success(`Account "${account.name}" deactivated`);
      setSheetOpen(false);
      setSelectedAccount(null);
      await fetchData();
    } catch (e: any) {
      toast.error(getApiErrorMessage(e, "Failed to deactivate account"));
    } finally {
      setDeletingAccount(false);
    }
  };

  const openDetail = (account: EvaAccount) => {
    setSelectedAccount(account);
    setSheetOpen(true);
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-erp-entrance">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Skeleton className="h-10 w-10 rounded-xl" />
            <div>
              <Skeleton className="h-4 w-32" />
              <Skeleton className="mt-1 h-3 w-48" />
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
                  <Skeleton className="h-5 w-12" />
                </div>
              </div>
            </div>
          ))}
        </div>
        <Skeleton className="h-10 w-64 rounded-lg" />
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
            <Building2 className="h-5 w-5 text-accent" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Eva Accounts</p>
            <p className="text-xs text-muted">Manage platform accounts and drafts</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            className="rounded-lg"
            onClick={() => setAddDraftOpen(true)}
          >
            <FileText className="h-4 w-4 mr-2" /> New Draft
          </Button>
          <Button
            size="sm"
            className="rounded-lg bg-accent hover:bg-accent/90 text-white"
            onClick={() => setAddAccountOpen(true)}
          >
            <Plus className="h-4 w-4 mr-2" /> New Account
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      {dashboard && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-xl border border-border border-l-[3px] border-l-accent bg-card p-5">
            <div className="flex items-center gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-light">
                <Building2 className="h-5 w-5 text-accent" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">Total Accounts</p>
                <p className="mt-0.5 font-mono text-xl font-bold text-foreground">
                  {dashboard.total_accounts}
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
                  {dashboard.active_accounts}
                </p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-border border-l-[3px] border-l-amber-500 bg-card p-5">
            <div className="flex items-center gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-50">
                <FileText className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">Drafts Pending</p>
                <p className="mt-0.5 font-mono text-xl font-bold text-foreground">
                  {dashboard.draft_accounts_pending}
                </p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-border border-l-[3px] border-l-blue-500 bg-card p-5">
            <div className="flex items-center gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50">
                <Handshake className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">Partners</p>
                <p className="mt-0.5 font-mono text-xl font-bold text-foreground">
                  {dashboard.active_partners}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SaaS Metrics */}
      {metrics && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-xl border border-border border-l-[3px] border-l-emerald-500 bg-card p-5">
            <div className="flex items-center gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50">
                <DollarSign className="h-5 w-5 text-emerald-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">MRR</p>
                <p className="mt-0.5 font-mono text-xl font-bold text-foreground">
                  ${Number(metrics.mrr).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-border border-l-[3px] border-l-violet-500 bg-card p-5">
            <div className="flex items-center gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-violet-50">
                <DollarSign className="h-5 w-5 text-violet-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">ARPU</p>
                <p className="mt-0.5 font-mono text-xl font-bold text-foreground">
                  ${Number(metrics.arpu).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-border border-l-[3px] border-l-red-500 bg-card p-5">
            <div className="flex items-center gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-red-50">
                <TrendingDown className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">Churn Rate</p>
                <p className="mt-0.5 font-mono text-xl font-bold text-foreground">
                  {metrics.total_customers > 0
                    ? ((metrics.churned_customers / metrics.total_customers) * 100).toFixed(1)
                    : "0.0"}%
                </p>
                <p className="text-[10px] text-muted">{metrics.churned_customers} churned this month</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex w-fit items-center gap-1 rounded-lg border border-border bg-card p-1">
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

      {/* Active Accounts */}
      {tab === "active" && (
        <div className="space-y-4">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
            <input
              placeholder="Search accounts..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 w-full rounded-lg border-0 bg-gray-100 pl-9 pr-3 text-sm outline-none placeholder:text-muted focus:ring-2 focus:ring-accent/20"
            />
          </div>

          <div className="overflow-hidden rounded-xl border border-border bg-card">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50/80">
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Name</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Type</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Plan</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Status</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Created</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[180px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted py-12">
                      No accounts found.
                    </TableCell>
                  </TableRow>
                ) : (
                  accounts.map((a) => (
                    <TableRow
                      key={a.id}
                      className="cursor-pointer hover:bg-gray-50/80"
                      onClick={() => openDetail(a)}
                    >
                      <TableCell className="font-medium text-foreground">{a.name}</TableCell>
                      <TableCell className="text-sm capitalize">{a.account_type?.toLowerCase().replace("_", " ") || "\u2014"}</TableCell>
                      <TableCell>
                        {a.plan_tier ? (
                          <Badge className={`rounded-full text-xs ${PLAN_COLORS[a.plan_tier] || ""}`}>
                            {a.plan_tier}
                          </Badge>
                        ) : (
                          "\u2014"
                        )}
                      </TableCell>
                      <TableCell>
                        {a.is_active ? (
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
                      <TableCell className="text-sm">
                        {new Date(a.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 rounded-lg text-xs border-accent/30 text-accent hover:bg-accent/10"
                            onClick={() => handleImpersonate(a)}
                          >
                            <ExternalLink className="h-3 w-3 mr-1" />
                            Impersonate
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Draft Accounts */}
      {tab === "drafts" && (
        <div className="space-y-4">
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50/80">
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Name</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Email</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Plan</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Status</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Prospect</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {drafts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted py-12">
                      No drafts found.
                    </TableCell>
                  </TableRow>
                ) : (
                  drafts.map((d) => (
                    <TableRow key={d.id} className="hover:bg-gray-50/80">
                      <TableCell className="font-medium text-foreground">{d.name}</TableCell>
                      <TableCell className="text-sm">{d.owner_email}</TableCell>
                      <TableCell>
                        {d.plan_tier ? (
                          <Badge className={`rounded-full text-xs ${PLAN_COLORS[d.plan_tier] || ""}`}>
                            {d.plan_tier}
                          </Badge>
                        ) : (
                          "\u2014"
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge className={`rounded-full text-xs ${DRAFT_STATUS_COLORS[d.status] || ""}`}>
                          {d.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">{d.prospect_id || "\u2014"}</TableCell>
                      <TableCell>
                        {d.status === "draft" ? (
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-green-200 text-green-700 hover:bg-green-50 hover:text-green-800"
                              onClick={() => handleApproveDraft(d.id)}
                              disabled={approving === d.id}
                            >
                              <Check className="h-3.5 w-3.5 mr-1" />
                              {approving === d.id ? "..." : "Approve"}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-red-200 text-red-700 hover:bg-red-50 hover:text-red-800"
                              onClick={() => handleDeleteDraft(d.id)}
                              disabled={deleting === d.id}
                            >
                              <Trash2 className="h-3.5 w-3.5 mr-1" />
                              {deleting === d.id ? "..." : "Delete"}
                            </Button>
                          </div>
                        ) : (
                          <span className="text-xs text-muted">{"\u2014"}</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Detail Sheet */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="w-[480px] sm:w-[560px] overflow-y-auto">
          {selectedAccount && (
            <div className="space-y-6 pt-4">
              {/* Header */}
              <div>
                <SheetTitle className="text-left text-lg font-semibold">
                  {selectedAccount.name}
                </SheetTitle>
                <div className="mt-2 flex items-center gap-2">
                  {selectedAccount.is_active ? (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
                      <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                      Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                      <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                      Inactive
                    </span>
                  )}
                  {selectedAccount.plan_tier && (
                    <Badge className={`rounded-full text-xs ${PLAN_COLORS[selectedAccount.plan_tier] || ""}`}>
                      {selectedAccount.plan_tier}
                    </Badge>
                  )}
                </div>
              </div>

              <Separator />

              {/* Account Info */}
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Account Info</p>
                <div className="space-y-3 pt-1">
                  <div className="flex items-center gap-3">
                    <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground w-28 shrink-0">Type</span>
                    <span className="text-sm font-medium capitalize">
                      {selectedAccount.account_type?.toLowerCase().replace("_", " ") || "\u2014"}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <CreditCard className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground w-28 shrink-0">Plan</span>
                    <span className="text-sm font-medium capitalize">{selectedAccount.plan_tier || "\u2014"}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <RefreshCw className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground w-28 shrink-0">Billing Cycle</span>
                    <span className="text-sm font-medium capitalize">{selectedAccount.billing_interval || "\u2014"}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <ShieldAlert className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground w-28 shrink-0">Subscription</span>
                    <span className="text-sm font-medium capitalize">{selectedAccount.subscription_status || "\u2014"}</span>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Dates */}
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Dates</p>
                <div className="space-y-3 pt-1">
                  <div className="flex items-center gap-3">
                    <CalendarDays className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground w-28 shrink-0">Created</span>
                    <span className="text-sm font-medium">
                      {new Date(selectedAccount.created_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}
                    </span>
                  </div>
                  {selectedAccount.updated_at && (
                    <div className="flex items-center gap-3">
                      <CalendarDays className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground w-28 shrink-0">Updated</span>
                      <span className="text-sm font-medium">
                        {new Date(selectedAccount.updated_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <Separator />

              {/* IDs */}
              <div className="space-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Identifiers</p>
                <div className="space-y-3 pt-1">
                  <div className="flex items-center gap-3">
                    <Hash className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground w-28 shrink-0">Account ID</span>
                    <span className="text-sm font-mono text-muted-foreground truncate" title={selectedAccount.id}>
                      {selectedAccount.id.slice(0, 8)}...{selectedAccount.id.slice(-4)}
                    </span>
                  </div>
                  {selectedAccount.owner_user_id && (
                    <div className="flex items-center gap-3">
                      <User2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground w-28 shrink-0">Owner User</span>
                      <span className="text-sm font-mono text-muted-foreground truncate" title={selectedAccount.owner_user_id}>
                        {selectedAccount.owner_user_id.slice(0, 8)}...{selectedAccount.owner_user_id.slice(-4)}
                      </span>
                    </div>
                  )}
                  {selectedAccount.partner_id && (
                    <div className="flex items-center gap-3">
                      <Handshake className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground w-28 shrink-0">Partner ID</span>
                      <span className="text-sm font-mono text-muted-foreground truncate" title={selectedAccount.partner_id}>
                        {selectedAccount.partner_id.slice(0, 8)}...{selectedAccount.partner_id.slice(-4)}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <Separator />

              {/* Actions */}
              <div className="space-y-2.5">
                <Button
                  className="w-full rounded-lg bg-accent hover:bg-accent/90 text-white"
                  onClick={() => handleImpersonate(selectedAccount)}
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Impersonate Account
                </Button>
                {selectedAccount.is_active && (
                  <Button
                    variant="outline"
                    className="w-full rounded-lg border-red-200 text-red-700 hover:bg-red-50 hover:text-red-800"
                    onClick={() => handleDeleteAccount(selectedAccount)}
                    disabled={deletingAccount}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    {deletingAccount ? "Deactivating..." : "Deactivate Account"}
                  </Button>
                )}
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* New Account Dialog */}
      <Dialog open={addAccountOpen} onOpenChange={setAddAccountOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto p-0">
          <div className="border-b border-border bg-gray-50/80 px-6 py-4">
            <DialogHeader>
              <DialogTitle className="text-base font-semibold text-foreground">New Account</DialogTitle>
            </DialogHeader>
            <p className="text-xs text-muted">Create a new Eva platform account</p>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleCreateAccount();
            }}
            className="space-y-3 px-6 py-4"
          >
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Account Name *</Label>
              <Input
                className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                value={accountForm.name}
                onChange={(e) => setAccountForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Owner Email *</Label>
                <Input
                  className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                  type="email"
                  value={accountForm.owner_email}
                  onChange={(e) => setAccountForm((f) => ({ ...f, owner_email: e.target.value }))}
                  required
                />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Owner Name *</Label>
                <Input
                  className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                  value={accountForm.owner_name}
                  onChange={(e) => setAccountForm((f) => ({ ...f, owner_name: e.target.value }))}
                  required
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Account Type *</Label>
                <Select
                  value={accountForm.account_type}
                  onValueChange={(v) => setAccountForm((f) => ({ ...f, account_type: v }))}
                >
                  <SelectTrigger className="mt-1.5 rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="COMMERCE">Commerce</SelectItem>
                    <SelectItem value="PROPERTY_MANAGEMENT">Property Management</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Plan Tier *</Label>
                <Select
                  value={accountForm.plan_tier}
                  onValueChange={(v) => setAccountForm((f) => ({ ...f, plan_tier: v }))}
                >
                  <SelectTrigger className="mt-1.5 rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="starter">Starter</SelectItem>
                    <SelectItem value="standard">Standard</SelectItem>
                    <SelectItem value="pro">Pro</SelectItem>
                    <SelectItem value="custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Billing Cycle *</Label>
                <Select
                  value={accountForm.billing_cycle}
                  onValueChange={(v) => setAccountForm((f) => ({ ...f, billing_cycle: v }))}
                >
                  <SelectTrigger className="mt-1.5 rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="yearly">Yearly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Facturapi Org API Key</Label>
                <Input
                  className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                  value={accountForm.facturapi_org_api_key}
                  onChange={(e) => setAccountForm((f) => ({ ...f, facturapi_org_api_key: e.target.value }))}
                  placeholder="Optional"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                className="rounded-lg"
                onClick={() => setAddAccountOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={creatingAccount}
                className="rounded-lg bg-accent hover:bg-accent/90 text-white disabled:opacity-70"
              >
                {creatingAccount ? "Creating..." : "Create Account"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* New Draft Dialog */}
      <Dialog open={addDraftOpen} onOpenChange={setAddDraftOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto p-0">
          <div className="border-b border-border bg-gray-50/80 px-6 py-4">
            <DialogHeader>
              <DialogTitle className="text-base font-semibold text-foreground">New Draft</DialogTitle>
            </DialogHeader>
            <p className="text-xs text-muted">Create a draft account for review before provisioning</p>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleCreateDraft();
            }}
            className="space-y-3 px-6 py-4"
          >
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Account Name *</Label>
              <Input
                className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                value={draftForm.name}
                onChange={(e) => setDraftForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Owner Email *</Label>
                <Input
                  className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                  type="email"
                  value={draftForm.owner_email}
                  onChange={(e) => setDraftForm((f) => ({ ...f, owner_email: e.target.value }))}
                  required
                />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Owner Name *</Label>
                <Input
                  className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                  value={draftForm.owner_name}
                  onChange={(e) => setDraftForm((f) => ({ ...f, owner_name: e.target.value }))}
                  required
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Account Type *</Label>
                <Select
                  value={draftForm.account_type}
                  onValueChange={(v) => setDraftForm((f) => ({ ...f, account_type: v }))}
                >
                  <SelectTrigger className="mt-1.5 rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="COMMERCE">Commerce</SelectItem>
                    <SelectItem value="PROPERTY_MANAGEMENT">Property Management</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Plan Tier *</Label>
                <Select
                  value={draftForm.plan_tier}
                  onValueChange={(v) => setDraftForm((f) => ({ ...f, plan_tier: v }))}
                >
                  <SelectTrigger className="mt-1.5 rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="starter">Starter</SelectItem>
                    <SelectItem value="standard">Standard</SelectItem>
                    <SelectItem value="pro">Pro</SelectItem>
                    <SelectItem value="custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Billing Cycle *</Label>
                <Select
                  value={draftForm.billing_cycle}
                  onValueChange={(v) => setDraftForm((f) => ({ ...f, billing_cycle: v }))}
                >
                  <SelectTrigger className="mt-1.5 rounded-lg">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="yearly">Yearly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Facturapi Org API Key</Label>
                <Input
                  className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                  value={draftForm.facturapi_org_api_key}
                  onChange={(e) => setDraftForm((f) => ({ ...f, facturapi_org_api_key: e.target.value }))}
                  placeholder="Optional"
                />
              </div>
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Notes</Label>
              <Textarea
                className="mt-1.5 rounded-lg bg-gray-50/80 border-border focus:border-accent focus:ring-2 focus:ring-accent/20"
                value={draftForm.notes}
                onChange={(e) => setDraftForm((f) => ({ ...f, notes: e.target.value }))}
                rows={3}
                placeholder="Any additional notes about this draft..."
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                className="rounded-lg"
                onClick={() => setAddDraftOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" className="rounded-lg bg-accent hover:bg-accent/90 text-white">
                Create Draft
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
