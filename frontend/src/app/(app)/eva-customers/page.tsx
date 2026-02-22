"use client";

import { useEffect, useState } from "react";
import {
  Plus, Search, Building2, FileText, Trash2, Check,
  Eye, ExternalLink, X, CheckCircle2, Handshake, Users,
} from "lucide-react";
import { toast } from "sonner";
import { evaPlatformApi } from "@/lib/api/eva-platform";
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

export default function EvaCustomersPage() {
  const [accounts, setAccounts] = useState<EvaAccount[]>([]);
  const [drafts, setDrafts] = useState<AccountDraft[]>([]);
  const [dashboard, setDashboard] = useState<PlatformDashboard | null>(null);
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
  const [impersonating, setImpersonating] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [accts, drfts, dash] = await Promise.all([
        evaPlatformApi.listAccounts({ search: search || undefined }),
        evaPlatformApi.listDrafts(),
        evaPlatformApi.dashboard(),
      ]);
      setAccounts(accts);
      setDrafts(drfts);
      setDashboard(dash);
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
    try {
      await evaPlatformApi.createAccount({
        ...accountForm,
        facturapi_org_api_key: accountForm.facturapi_org_api_key || null,
      });
      toast.success("Account created successfully");
      setAddAccountOpen(false);
      setAccountForm({ ...INITIAL_ACCOUNT_FORM });
      await fetchData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to create account");
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
    setImpersonating(account.id);
    try {
      const result = await evaPlatformApi.impersonateAccount(account.id);
      toast.success(`Impersonating ${result.account_name}`);
      window.open(result.magic_link_url, "_blank");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to impersonate account");
    } finally {
      setImpersonating(null);
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
                            disabled={impersonating === a.id}
                          >
                            <ExternalLink className="h-3 w-3 mr-1" />
                            {impersonating === a.id ? "..." : "Impersonate"}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 rounded-lg text-xs"
                            onClick={() => openDetail(a)}
                          >
                            <Eye className="h-3 w-3 mr-1" />
                            View
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
            <div className="space-y-5 pt-4">
              {/* Sheet Header */}
              <div className="flex items-start justify-between">
                <div className="space-y-1.5">
                  <SheetTitle className="text-left text-lg font-semibold">
                    {selectedAccount.name}
                  </SheetTitle>
                  <div className="flex items-center gap-2">
                    {selectedAccount.plan_tier && (
                      <Badge className={`rounded-full text-xs ${PLAN_COLORS[selectedAccount.plan_tier] || ""}`}>
                        {selectedAccount.plan_tier}
                      </Badge>
                    )}
                    {selectedAccount.is_active ? (
                      <span className="inline-flex items-center gap-1.5 text-xs text-green-600">
                        <span className="h-2 w-2 rounded-full bg-green-500" />
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                        <span className="h-2 w-2 rounded-full bg-red-500" />
                        Inactive
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <Separator />

              {/* Info Grid */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground">Account Type</p>
                  <p className="mt-0.5 text-sm font-medium capitalize">
                    {selectedAccount.account_type?.toLowerCase().replace("_", " ") || "\u2014"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Plan</p>
                  <p className="mt-0.5 text-sm font-medium capitalize">
                    {selectedAccount.plan_tier || "\u2014"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Billing Cycle</p>
                  <p className="mt-0.5 text-sm font-medium capitalize">
                    {selectedAccount.billing_interval || "\u2014"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Created</p>
                  <p className="mt-0.5 text-sm font-medium">
                    {new Date(selectedAccount.created_at).toLocaleDateString()}
                  </p>
                </div>
                {selectedAccount.partner_id && (
                  <div>
                    <p className="text-xs text-muted-foreground">Partner ID</p>
                    <p className="mt-0.5 text-sm font-medium font-mono">
                      {selectedAccount.partner_id}
                    </p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-muted-foreground">Subscription</p>
                  <p className="mt-0.5 text-sm font-medium capitalize">
                    {selectedAccount.subscription_status || "\u2014"}
                  </p>
                </div>
              </div>

              <Separator />

              {/* Impersonate Button */}
              <Button
                className="w-full rounded-lg bg-accent hover:bg-accent/90 text-white"
                onClick={() => handleImpersonate(selectedAccount)}
                disabled={impersonating === selectedAccount.id}
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                {impersonating === selectedAccount.id ? "Opening..." : "Impersonate Account"}
              </Button>
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
              <Button type="submit" className="rounded-lg bg-accent hover:bg-accent/90 text-white">
                Create Account
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
