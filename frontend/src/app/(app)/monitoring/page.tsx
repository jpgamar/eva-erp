"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  AlertCircle, Activity,
  RefreshCw, Eye, CheckCheck, Clock,
  Server, Globe, Database, Shield, MessageCircle, Receipt,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { evaPlatformApi } from "@/lib/api/eva-platform";
import type { MonitoringIssue, ServiceStatus } from "@/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const SEVERITY_CONFIG: Record<string, { label: string; color: string }> = {
  critical: { label: "Critical", color: "bg-red-100 text-red-800" },
  high: { label: "High", color: "bg-orange-100 text-orange-800" },
  medium: { label: "Medium", color: "bg-yellow-100 text-yellow-800" },
  low: { label: "Low", color: "bg-gray-100 text-gray-600" },
};

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  open: { label: "Open", color: "bg-blue-50 text-blue-700" },
  acknowledged: { label: "Acknowledged", color: "bg-purple-50 text-purple-700" },
  resolved: { label: "Resolved", color: "bg-green-50 text-green-700" },
};

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${diffDay}d ago`;
}

type MonitoringGroupCheck = {
  checkKey: string;
  label: string;
  icon: LucideIcon;
  optional?: boolean;
};

type MonitoringGroup = {
  key: string;
  title: string;
  description: string;
  gradient: string;
  iconBg: string;
  iconColor: string;
  checks: MonitoringGroupCheck[];
};

const PLATFORM_GROUPS: MonitoringGroup[] = [
  {
    key: "erp",
    title: "EVA ERP",
    description: "Frontend, backend, database and invoicing",
    gradient: "from-indigo-400 to-indigo-500",
    iconBg: "bg-indigo-50",
    iconColor: "text-indigo-600",
    checks: [
      { checkKey: "erp-frontend", label: "Frontend", icon: Globe },
      { checkKey: "erp-api", label: "Backend", icon: Server },
      { checkKey: "erp-db", label: "Database", icon: Database },
      { checkKey: "facturapi-eva-erp", label: "FacturAPI", icon: Receipt },
    ],
  },
  {
    key: "fmac-erp",
    title: "FM Accessories ERP",
    description: "Frontend, backend, database and invoicing",
    gradient: "from-teal-400 to-teal-500",
    iconBg: "bg-teal-50",
    iconColor: "text-teal-600",
    checks: [
      { checkKey: "fmac-erp-frontend", label: "Frontend", icon: Globe },
      { checkKey: "fmac-erp-backend", label: "Backend API", icon: Server },
      { checkKey: "fmac-erp-db", label: "Database", icon: Database },
      { checkKey: "facturapi-fmac-erp", label: "FacturAPI", icon: Receipt },
    ],
  },
  {
    key: "eva-app",
    title: "EVA App",
    description: "Frontend, API, DB, auth, messaging, AI and billing",
    gradient: "from-violet-400 to-violet-500",
    iconBg: "bg-violet-50",
    iconColor: "text-violet-600",
    checks: [
      { checkKey: "eva-app-frontend", label: "Frontend", icon: Globe },
      { checkKey: "eva-api", label: "Backend API", icon: Server },
      { checkKey: "eva-db", label: "Database", icon: Database },
      { checkKey: "supabase-auth", label: "Supabase Auth", icon: Shield },
      { checkKey: "supabase-admin", label: "Supabase Admin", icon: Shield },
      { checkKey: "openai-api", label: "OpenAI API", icon: Activity },
      { checkKey: "eva-whatsapp", label: "WhatsApp", icon: MessageCircle, optional: true },
      { checkKey: "facturapi-eva-app", label: "FacturAPI", icon: Receipt },
    ],
  },
];

/* ── Platform Card ──────────────────────────────────── */

function PlatformCard({ group, services }: { group: MonitoringGroup; services: ServiceStatus[] }) {
  const rows = group.checks.map((check) => {
    const service = services.find((svc) => svc.check_key === check.checkKey);
    if (!service && check.optional) {
      return { ...check, service, state: "na" as const, detail: "Not configured" };
    }
    const isUp = Boolean(service && service.status === "up" && !service.stale);
    const detail = !service
      ? "No response"
      : service.stale
        ? "Stale"
        : service.error;
    return { ...check, service, state: isUp ? ("up" as const) : ("down" as const), detail };
  });

  const isHealthy = rows.every((row) => row.state !== "down");
  const downCount = rows.filter((r) => r.state === "down").length;

  return (
    <div className="rounded-2xl bg-card overflow-hidden transition-all hover:shadow-lg">
      <div className={cn("h-1 bg-gradient-to-r", isHealthy ? "from-green-400 to-emerald-500" : "from-red-400 to-red-500")} />
      <div className="p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className={cn("flex h-9 w-9 items-center justify-center rounded-lg", group.iconBg)}>
              <Server className={cn("h-4 w-4", group.iconColor)} />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">{group.title}</p>
              <p className="text-[11px] text-muted">{group.description}</p>
            </div>
          </div>
          <span className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
            isHealthy ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700",
          )}>
            <span className={cn(
              "h-2 w-2 rounded-full",
              isHealthy ? "bg-green-500 animate-pulse" : "bg-red-500",
            )} />
            {isHealthy ? "Healthy" : `${downCount} down`}
          </span>
        </div>

        <div className="divide-y divide-border/50">
          {rows.map((row) => {
            const Icon = row.icon;
            return (
              <div key={row.checkKey} className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0">
                <div className="flex items-center gap-2.5">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-foreground">{row.label}</span>
                  {row.detail && row.state !== "up" && (
                    <span className={cn(
                      "text-[11px] truncate max-w-[140px]",
                      row.state === "na" ? "text-muted" : "text-red-600",
                    )}>
                      {row.detail}
                    </span>
                  )}
                </div>
                <span className={cn(
                  "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium",
                  row.state === "up"
                    ? "bg-green-50 text-green-700"
                    : row.state === "na"
                      ? "bg-gray-100 text-gray-500"
                      : "bg-red-50 text-red-700",
                )}>
                  <span className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    row.state === "up"
                      ? "bg-green-500"
                      : row.state === "na"
                        ? "bg-gray-400"
                        : "bg-red-500",
                  )} />
                  {row.state === "up" ? "Up" : row.state === "na" ? "N/A" : "Down"}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function CardSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="rounded-2xl bg-card overflow-hidden">
      <div className="h-1 bg-gray-200" />
      <div className="p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <Skeleton className="h-9 w-9 rounded-lg" />
            <div className="space-y-1.5">
              <Skeleton className="h-3.5 w-28" />
              <Skeleton className="h-3 w-44" />
            </div>
          </div>
          <Skeleton className="h-6 w-16 rounded-full" />
        </div>
        <div className="divide-y divide-border/50">
          {Array.from({ length: rows }).map((_, i) => (
            <div key={i} className="flex items-center justify-between py-2.5">
              <div className="flex items-center gap-2.5">
                <Skeleton className="h-4 w-4 rounded" />
                <Skeleton className="h-3.5 w-20" />
              </div>
              <Skeleton className="h-5 w-10 rounded-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────── */

export default function MonitoringPage() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [servicesLoading, setServicesLoading] = useState(true);
  const [servicesError, setServicesError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);

  const [issues, setIssues] = useState<MonitoringIssue[]>([]);
  const [issuesLoading, setIssuesLoading] = useState(true);
  const [issuesError, setIssuesError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /* ── Fetch services (fast) ── */
  const fetchServices = useCallback(async () => {
    try {
      const data = await evaPlatformApi.serviceStatus();
      setServices(data.services);
      setCheckedAt(data.checked_at);
      setServicesError(null);
    } catch {
      setServicesError("Could not fetch service status");
    } finally {
      setServicesLoading(false);
    }
  }, []);

  /* ── Fetch issues (slower, from Eva DB) ── */
  const fetchIssues = useCallback(async () => {
    try {
      const issueParams: Record<string, string> = {};
      if (statusFilter !== "all") issueParams.status = statusFilter;
      if (severityFilter !== "all") issueParams.severity = severityFilter;

      const iss = await evaPlatformApi.listIssues(issueParams);
      setIssues(iss);
      setIssuesError(null);
    } catch {
      setIssuesError("Could not fetch monitoring issues");
    } finally {
      setIssuesLoading(false);
    }
  }, [statusFilter, severityFilter]);

  /* ── Initial load ── */
  useEffect(() => {
    fetchServices();
    fetchIssues();
  }, [fetchServices, fetchIssues]);

  /* ── Auto-refresh every 30s ── */
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      fetchServices();
      fetchIssues();
    }, 30_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchServices, fetchIssues]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchServices(), fetchIssues()]);
    setRefreshing(false);
  };

  const handleAcknowledge = async (id: string) => {
    setActionLoading(id);
    try {
      await evaPlatformApi.acknowledgeIssue(id);
      toast.success("Issue acknowledged");
      await fetchIssues();
    } catch {
      toast.error("Failed to acknowledge issue");
    } finally {
      setActionLoading(null);
    }
  };

  const handleResolve = async (id: string) => {
    setActionLoading(id);
    try {
      await evaPlatformApi.resolveIssue(id);
      toast.success("Issue resolved");
      await fetchIssues();
    } catch {
      toast.error("Failed to resolve issue");
    } finally {
      setActionLoading(null);
    }
  };

  const totalChecks = PLATFORM_GROUPS.reduce((sum, g) => sum + g.checks.length, 0);
  const upChecks = PLATFORM_GROUPS.reduce((sum, g) => {
    return sum + g.checks.filter((c) => {
      const svc = services.find((s) => s.check_key === c.checkKey);
      return svc && svc.status === "up" && !svc.stale;
    }).length;
  }, 0);

  return (
    <div className="flex flex-col gap-6 animate-erp-entrance">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-light">
            <Activity className="h-5 w-5 text-accent" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Monitoring</p>
            <p className="text-xs text-muted">
              {servicesLoading
                ? "Checking services..."
                : checkedAt
                  ? `${upChecks}/${totalChecks} services up \u00b7 ${timeAgo(checkedAt)}`
                  : "Waiting for data..."}
            </p>
          </div>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted transition-colors hover:bg-gray-50 hover:text-foreground disabled:opacity-40"
          title="Refresh"
        >
          <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
        </button>
      </div>

      {servicesError && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {servicesError}
        </div>
      )}
      {issuesError && (
        <div className="rounded-2xl border border-orange-200 bg-orange-50 px-4 py-3 text-sm text-orange-700">
          {issuesError}
        </div>
      )}

      {/* ── Platform Cards ── */}
      {servicesLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <CardSkeleton rows={4} />
          <CardSkeleton rows={4} />
          <CardSkeleton rows={8} />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {PLATFORM_GROUPS.map((group) => (
            <PlatformCard key={group.key} group={group} services={services} />
          ))}
        </div>
      )}

      {/* ── Issues ── */}
      <div className="rounded-2xl bg-card overflow-hidden">
        <div className="flex items-center justify-between gap-3 p-5 pb-0">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50">
              <AlertCircle className="h-4 w-4 text-amber-600" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">Issues</p>
              <p className="text-[11px] text-muted">Track and resolve platform issues</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {["all", "open", "acknowledged", "resolved"].map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={cn(
                    "rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
                    statusFilter === s
                      ? s === "all"
                        ? "bg-gray-900 text-white"
                        : STATUS_CONFIG[s]?.color || "bg-gray-900 text-white"
                      : "text-muted hover:text-foreground"
                  )}
                >
                  {s === "all" ? "All" : STATUS_CONFIG[s]?.label || s}
                </button>
              ))}
            </div>
            <div className="h-4 w-px bg-border" />
            <div className="flex gap-1">
              {["all", "critical", "high", "medium", "low"].map((s) => (
                <button
                  key={s}
                  onClick={() => setSeverityFilter(s)}
                  className={cn(
                    "rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
                    severityFilter === s
                      ? s === "all"
                        ? "bg-gray-900 text-white"
                        : SEVERITY_CONFIG[s]?.color || "bg-gray-900 text-white"
                      : "text-muted hover:text-foreground"
                  )}
                >
                  {s === "all" ? "All" : SEVERITY_CONFIG[s]?.label || s}
                </button>
              ))}
            </div>
          </div>
        </div>

        {issuesLoading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : (
          <div className="mt-4">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50/80">
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-muted w-[100px]">Severity</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-muted">Title</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-muted w-[110px]">Category</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-muted w-[90px] text-right">Count</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-muted w-[100px]">Last Seen</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-muted w-[110px]">Status</TableHead>
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wider text-muted w-[140px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {issues.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-16">
                      <CheckCheck className="h-8 w-8 mx-auto mb-2 text-green-400" />
                      <p className="text-sm font-medium text-foreground">All clear</p>
                      <p className="text-xs text-muted mt-0.5">No issues match your filters</p>
                    </TableCell>
                  </TableRow>
                ) : (
                  issues.map((issue) => {
                    const sevCfg = SEVERITY_CONFIG[issue.severity] || SEVERITY_CONFIG.low;
                    const staCfg = STATUS_CONFIG[issue.status] || STATUS_CONFIG.open;
                    const isLoading = actionLoading === issue.id;
                    const canAcknowledge = issue.status === "open";
                    const canResolve = issue.status === "open" || issue.status === "acknowledged";

                    return (
                      <TableRow key={issue.id} className="transition-colors hover:bg-gray-50/60">
                        <TableCell>
                          <span className={cn("rounded-full px-2.5 py-0.5 text-[11px] font-medium", sevCfg.color)}>
                            {sevCfg.label}
                          </span>
                        </TableCell>
                        <TableCell>
                          <p className="font-medium text-foreground text-sm">{issue.title}</p>
                          {issue.summary && (
                            <p className="mt-0.5 text-xs text-muted truncate max-w-sm">{issue.summary}</p>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground capitalize">{issue.category}</TableCell>
                        <TableCell className="text-right font-mono text-sm text-foreground">{issue.occurrences}</TableCell>
                        <TableCell>
                          <span className="flex items-center gap-1 text-xs text-muted-foreground" title={new Date(issue.last_seen_at).toLocaleDateString()}>
                            <Clock className="h-3 w-3" />
                            {timeAgo(issue.last_seen_at)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className={cn("rounded-full px-2.5 py-0.5 text-[11px] font-medium", staCfg.color)}>
                            {staCfg.label}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1.5">
                            {canAcknowledge && (
                              <button
                                onClick={() => handleAcknowledge(issue.id)}
                                disabled={isLoading}
                                className="flex h-7 items-center gap-1 rounded-md border border-gray-200 px-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-gray-50 hover:text-foreground disabled:opacity-40"
                              >
                                <Eye className="h-3 w-3" />
                                Ack
                              </button>
                            )}
                            {canResolve && (
                              <button
                                onClick={() => handleResolve(issue.id)}
                                disabled={isLoading}
                                className="flex h-7 items-center gap-1 rounded-md border border-green-200 px-2 text-xs font-medium text-green-700 transition-colors hover:bg-green-50 disabled:opacity-40"
                              >
                                <CheckCheck className="h-3 w-3" />
                                Resolve
                              </button>
                            )}
                            {!canAcknowledge && !canResolve && (
                              <span className="text-xs text-gray-300">&mdash;</span>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}
