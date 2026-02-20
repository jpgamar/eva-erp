"use client";

import { useEffect, useState, useCallback } from "react";
import { Lock, Unlock, Plus, Search, DollarSign, Server, Eye, EyeOff, Copy, ExternalLink, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { vaultApi } from "@/lib/api/vault";
import type { VaultStatus, Credential, CredentialDetail, CostSummary } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const CATEGORIES = [
  { value: "infrastructure", label: "Infrastructure", color: "#3b82f6" },
  { value: "ai_llm", label: "AI / LLM", color: "#8b5cf6" },
  { value: "communication", label: "Communication", color: "#22c55e" },
  { value: "payment", label: "Payment", color: "#f59e0b" },
  { value: "dev_tools", label: "Dev Tools", color: "#6b7280" },
  { value: "marketing", label: "Marketing", color: "#ec4899" },
  { value: "legal_accounting", label: "Legal / Accounting", color: "#14b8a6" },
  { value: "other", label: "Other", color: "#9ca3af" },
];

function categoryLabel(cat: string) {
  return CATEGORIES.find((c) => c.value === cat)?.label ?? cat;
}
function categoryColor(cat: string) {
  return CATEGORIES.find((c) => c.value === cat)?.color ?? "#6b7280";
}

function formatCurrency(amount: number | null, currency: string) {
  if (amount == null) return "—";
  return `$${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

export default function VaultPage() {
  const [status, setStatus] = useState<VaultStatus | null>(null);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [costSummary, setCostSummary] = useState<CostSummary | null>(null);
  const [masterPassword, setMasterPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [unlocking, setUnlocking] = useState(false);

  // Filters
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sortBy, setSortBy] = useState<"name" | "cost" | "date">("name");

  // Modals
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailCred, setDetailCred] = useState<CredentialDetail | null>(null);
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [addOpen, setAddOpen] = useState(false);

  // Add form state
  const [form, setForm] = useState({
    name: "", category: "infrastructure", url: "", login_url: "",
    username: "", password: "", api_keys: "", notes: "",
    monthly_cost: "", cost_currency: "USD", billing_cycle: "monthly",
  });

  const fetchStatus = useCallback(async () => {
    try {
      const s = await vaultApi.status();
      setStatus(s);
      return s;
    } catch {
      return null;
    }
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const [creds, costs] = await Promise.all([
        vaultApi.list({ category: categoryFilter !== "all" ? categoryFilter : undefined, search: search || undefined }),
        vaultApi.costSummary(),
      ]);
      setCredentials(creds);
      setCostSummary(costs);
    } catch {
      // vault might be locked
    }
  }, [categoryFilter, search]);

  useEffect(() => {
    (async () => {
      const s = await fetchStatus();
      if (s?.is_unlocked) await fetchData();
      setLoading(false);
    })();
  }, [fetchStatus, fetchData]);

  const handleUnlock = async () => {
    setUnlocking(true);
    try {
      if (!status?.is_setup) {
        await vaultApi.setup(masterPassword);
        toast.success("Vault created successfully");
      } else {
        await vaultApi.unlock(masterPassword);
      }
      setMasterPassword("");
      await fetchStatus();
      await fetchData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Invalid password");
    } finally {
      setUnlocking(false);
    }
  };

  const handleLock = async () => {
    await vaultApi.lock();
    setStatus((s) => s ? { ...s, is_unlocked: false } : s);
    setCredentials([]);
    setCostSummary(null);
    toast.success("Vault locked");
  };

  const openDetail = async (id: string) => {
    try {
      const detail = await vaultApi.get(id);
      setDetailCred(detail);
      setDetailOpen(true);
      setShowSecrets({});
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to load credential");
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied`);
  };

  const handleAddCredential = async () => {
    try {
      await vaultApi.create({
        ...form,
        monthly_cost: form.monthly_cost ? parseFloat(form.monthly_cost) : null,
        url: form.url || null,
        login_url: form.login_url || null,
        username: form.username || null,
        password: form.password || null,
        api_keys: form.api_keys || null,
        notes: form.notes || null,
      });
      toast.success("Credential added");
      setAddOpen(false);
      setForm({ name: "", category: "infrastructure", url: "", login_url: "", username: "", password: "", api_keys: "", notes: "", monthly_cost: "", cost_currency: "USD", billing_cycle: "monthly" });
      await fetchData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to add credential");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await vaultApi.delete(id);
      toast.success("Credential deleted");
      setDetailOpen(false);
      await fetchData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to delete");
    }
  };

  // Sorting
  const sortedCredentials = [...credentials].sort((a, b) => {
    if (sortBy === "cost") return (b.monthly_cost_mxn ?? 0) - (a.monthly_cost_mxn ?? 0);
    if (sortBy === "date") return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    return a.name.localeCompare(b.name);
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  // Unlock / Setup screen
  if (!status?.is_unlocked) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <Card className="max-w-md w-full">
          <CardHeader className="text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 mb-2">
              <Lock className="h-8 w-8 text-primary" />
            </div>
            <CardTitle>{status?.is_setup ? "Unlock Vault" : "Set Up Vault"}</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              {status?.is_setup
                ? "Enter your master password to access credentials."
                : "Create a master password to encrypt your credentials."}
            </p>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => { e.preventDefault(); handleUnlock(); }}
              className="space-y-4"
            >
              <Input
                type="password"
                placeholder="Master password"
                value={masterPassword}
                onChange={(e) => setMasterPassword(e.target.value)}
                autoFocus
              />
              <Button type="submit" className="w-full" disabled={!masterPassword || unlocking}>
                <Unlock className="h-4 w-4 mr-2" />
                {status?.is_setup ? "Unlock" : "Create Vault"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Main vault view
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Credential Vault</h1>
          <p className="text-muted-foreground text-sm">Manage service credentials and track costs</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleLock}>
            <Lock className="h-4 w-4 mr-2" /> Lock Vault
          </Button>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4 mr-2" /> Add Credential
          </Button>
        </div>
      </div>

      {/* Cost Summary Cards */}
      {costSummary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm text-muted-foreground">Total Monthly (MXN eq.)</div>
              <div className="text-2xl font-bold">{formatCurrency(costSummary.combined_mxn, "MXN")}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm text-muted-foreground">USD Services</div>
              <div className="text-2xl font-bold">{formatCurrency(costSummary.total_usd, "USD")}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm text-muted-foreground">MXN Services</div>
              <div className="text-2xl font-bold">{formatCurrency(costSummary.total_mxn, "MXN")}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm text-muted-foreground">Services</div>
              <div className="text-2xl font-bold flex items-center gap-2">
                <Server className="h-5 w-5 text-muted-foreground" />
                {costSummary.service_count}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Category Breakdown */}
      {costSummary && Object.keys(costSummary.by_category).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Cost by Category (MXN eq.)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(costSummary.by_category)
                .sort(([, a], [, b]) => b - a)
                .map(([cat, amount]) => {
                  const pct = costSummary.combined_mxn > 0 ? (amount / costSummary.combined_mxn) * 100 : 0;
                  return (
                    <div key={cat} className="flex items-center gap-3">
                      <div className="w-32 text-sm truncate">{categoryLabel(cat)}</div>
                      <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${pct}%`, backgroundColor: categoryColor(cat) }}
                        />
                      </div>
                      <div className="w-28 text-sm text-right font-medium">
                        {formatCurrency(amount, "MXN")}
                      </div>
                    </div>
                  );
                })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search credentials..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {CATEGORIES.map((c) => (
              <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={sortBy} onValueChange={(v) => setSortBy(v as any)}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="name">Name</SelectItem>
            <SelectItem value="cost">Cost (High→Low)</SelectItem>
            <SelectItem value="date">Date Added</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Credentials Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>URL</TableHead>
              <TableHead className="text-right">Monthly Cost</TableHead>
              <TableHead>Billing</TableHead>
              <TableHead className="w-[60px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedCredentials.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                  {credentials.length === 0 ? "No credentials yet. Add your first one." : "No results match your search."}
                </TableCell>
              </TableRow>
            ) : (
              sortedCredentials.map((cred) => (
                <TableRow key={cred.id} className="cursor-pointer hover:bg-accent/50" onClick={() => openDetail(cred.id)}>
                  <TableCell className="font-medium">{cred.name}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" style={{ backgroundColor: categoryColor(cred.category) + "20", color: categoryColor(cred.category) }}>
                      {categoryLabel(cred.category)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {cred.url ? (
                      <a
                        href={cred.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-primary hover:underline flex items-center gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {new URL(cred.url).hostname} <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : "—"}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {formatCurrency(cred.monthly_cost, cred.cost_currency)}
                  </TableCell>
                  <TableCell className="capitalize">{cred.billing_cycle ?? "—"}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={(e) => { e.stopPropagation(); openDetail(cred.id); }}>
                      <Eye className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Detail Modal */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {detailCred?.name}
              <Badge variant="secondary" style={{ backgroundColor: categoryColor(detailCred?.category ?? "") + "20", color: categoryColor(detailCred?.category ?? "") }}>
                {categoryLabel(detailCred?.category ?? "")}
              </Badge>
            </DialogTitle>
          </DialogHeader>
          {detailCred && (
            <div className="space-y-4">
              {/* URLs */}
              {detailCred.url && (
                <div>
                  <Label className="text-xs text-muted-foreground">URL</Label>
                  <div className="flex items-center gap-2">
                    <a href={detailCred.url} target="_blank" rel="noreferrer" className="text-primary hover:underline text-sm">{detailCred.url}</a>
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyToClipboard(detailCred.url!, "URL")}>
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              )}
              {detailCred.login_url && (
                <div>
                  <Label className="text-xs text-muted-foreground">Login URL</Label>
                  <div className="flex items-center gap-2">
                    <a href={detailCred.login_url} target="_blank" rel="noreferrer" className="text-primary hover:underline text-sm">{detailCred.login_url}</a>
                  </div>
                </div>
              )}

              {/* Secrets */}
              {detailCred.username && (
                <div>
                  <Label className="text-xs text-muted-foreground">Username</Label>
                  <div className="flex items-center gap-2">
                    <code className="text-sm bg-muted px-2 py-1 rounded flex-1">{detailCred.username}</code>
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyToClipboard(detailCred.username!, "Username")}>
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              )}
              {detailCred.password && (
                <div>
                  <Label className="text-xs text-muted-foreground">Password</Label>
                  <div className="flex items-center gap-2">
                    <code className="text-sm bg-muted px-2 py-1 rounded flex-1">
                      {showSecrets.password ? detailCred.password : "••••••••"}
                    </code>
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setShowSecrets((s) => ({ ...s, password: !s.password }))}>
                      {showSecrets.password ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                    </Button>
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyToClipboard(detailCred.password!, "Password")}>
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              )}
              {detailCred.api_keys && (
                <div>
                  <Label className="text-xs text-muted-foreground">API Keys</Label>
                  <div className="flex items-center gap-2">
                    <code className="text-sm bg-muted px-2 py-1 rounded flex-1 break-all">
                      {showSecrets.api_keys ? detailCred.api_keys : "••••••••••••••••"}
                    </code>
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setShowSecrets((s) => ({ ...s, api_keys: !s.api_keys }))}>
                      {showSecrets.api_keys ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                    </Button>
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyToClipboard(detailCred.api_keys!, "API Keys")}>
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              )}
              {detailCred.notes && (
                <div>
                  <Label className="text-xs text-muted-foreground">Notes</Label>
                  <p className="text-sm whitespace-pre-wrap">{detailCred.notes}</p>
                </div>
              )}

              {/* Cost */}
              <div className="flex gap-4">
                <div>
                  <Label className="text-xs text-muted-foreground">Monthly Cost</Label>
                  <p className="text-sm font-medium">{formatCurrency(detailCred.monthly_cost, detailCred.cost_currency)}</p>
                </div>
                {detailCred.cost_currency === "USD" && detailCred.monthly_cost_mxn != null && (
                  <div>
                    <Label className="text-xs text-muted-foreground">MXN Equivalent</Label>
                    <p className="text-sm">{formatCurrency(detailCred.monthly_cost_mxn, "MXN")}</p>
                  </div>
                )}
                <div>
                  <Label className="text-xs text-muted-foreground">Billing Cycle</Label>
                  <p className="text-sm capitalize">{detailCred.billing_cycle ?? "—"}</p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-2 border-t">
                <Button variant="destructive" size="sm" onClick={() => handleDelete(detailCred.id)}>
                  <Trash2 className="h-4 w-4 mr-1" /> Delete
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Add Credential Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Add Credential</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(e) => { e.preventDefault(); handleAddCredential(); }}
            className="space-y-4"
          >
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <Label>Name *</Label>
                <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
              </div>
              <div>
                <Label>Category</Label>
                <Select value={form.category} onValueChange={(v) => setForm((f) => ({ ...f, category: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map((c) => (
                      <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Billing Cycle</Label>
                <Select value={form.billing_cycle} onValueChange={(v) => setForm((f) => ({ ...f, billing_cycle: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="annual">Annual</SelectItem>
                    <SelectItem value="one-time">One-time</SelectItem>
                    <SelectItem value="usage-based">Usage-based</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>URL</Label>
                <Input value={form.url} onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))} placeholder="https://..." />
              </div>
              <div>
                <Label>Login URL</Label>
                <Input value={form.login_url} onChange={(e) => setForm((f) => ({ ...f, login_url: e.target.value }))} placeholder="https://..." />
              </div>
              <div>
                <Label>Username</Label>
                <Input value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} />
              </div>
              <div>
                <Label>Password</Label>
                <Input type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
              </div>
              <div className="col-span-2">
                <Label>API Keys</Label>
                <Textarea value={form.api_keys} onChange={(e) => setForm((f) => ({ ...f, api_keys: e.target.value }))} rows={2} />
              </div>
              <div>
                <Label>Monthly Cost</Label>
                <Input type="number" step="0.01" value={form.monthly_cost} onChange={(e) => setForm((f) => ({ ...f, monthly_cost: e.target.value }))} />
              </div>
              <div>
                <Label>Currency</Label>
                <Select value={form.cost_currency} onValueChange={(v) => setForm((f) => ({ ...f, cost_currency: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="USD">USD</SelectItem>
                    <SelectItem value="MXN">MXN</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="col-span-2">
                <Label>Notes</Label>
                <Textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} rows={2} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={!form.name}>Add Credential</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
