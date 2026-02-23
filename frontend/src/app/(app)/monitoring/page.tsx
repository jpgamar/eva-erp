"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  AlertCircle, Activity,
  RefreshCw, Eye, CheckCheck, Clock,
  Server, Globe, Database,
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
};

type MonitoringGroup = {
  key: string;
  title: string;
  description: string;
  checks: MonitoringGroupCheck[];
};

const MONITORING_GROUPS: MonitoringGroup[] = [
  {
    key: "erp",
    title: "ERP",
    description: "Frontend, backend and database status",
    checks: [
      { checkKey: "erp-frontend", label: "Frontend", icon: Globe },
      { checkKey: "erp-api", label: "Backend", icon: Server },
      { checkKey: "erp-db", label: "Database", icon: Database },
    ],
  },
  {
    key: "fmac-erp",
    title: "FMAccesorios ERP",
    description: "Frontend, backend and database status",
    checks: [
      { checkKey: "fmac-erp-frontend", label: "Frontend", icon: Globe },
      { checkKey: "fmac-erp-backend", label: "Backend API", icon: Server },
      { checkKey: "fmac-erp-db", label: "Database", icon: Database },
    ],
  },
];

const FACTURAPI_GROUPS: MonitoringGroup[] = [
  {
    key: "facturapi-fmac-erp",
    title: "FacturAPI - FMAccesorios ERP",
    description: "FM ERP invoicing integration",
    checks: [{ checkKey: "facturapi-fmac-erp", label: "FacturAPI", icon: Server }],
  },
  {
    key: "facturapi-eva-erp",
    title: "FacturAPI - EVA ERP",
    description: "EVA ERP invoicing integration",
    checks: [{ checkKey: "facturapi-eva-erp", label: "FacturAPI", icon: Server }],
  },
  {
    key: "facturapi-eva-app",
    title: "FacturAPI - EVA app",
    description: "EVA app invoicing integration",
    checks: [{ checkKey: "facturapi-eva-app", label: "FacturAPI", icon: Server }],
  },
];

/* ── Unified Group Card ─────────────────────────────── */

function UnifiedGroupCard({ group, services }: { group: MonitoringGroup; services: ServiceStatus[] }) {
  const rows = group.checks.map((check) => {
    const service = services.find((svc) => svc.check_key === check.checkKey);
    const isUp = Boolean(service && service.status === "up" && !service.stale);
    const detail = !service
      ? "Check not returned by API."
      : service.stale
        ? "Status is stale."
        : service.error;
    return { ...check, service, isUp, detail };
  });

  const isHealthy = rows.every((row) => row.isUp);

  return (
    <div className={cn(
      "rounded-xl border p-4 transition-shadow hover:shadow-sm",
      isHealthy
        ? "border-green-200 bg-green-50/70"
        : "border-red-200 bg-red-50/70",
    )}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{group.title}</p>
          <p className="text-xs text-muted">{group.description}</p>
        </div>
        <span className={cn(
          "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
          isHealthy ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700",
        )}>
          <span className={cn("h-2 w-2 rounded-full", isHealthy ? "bg-green-500" : "bg-red-500")} />
          {isHealthy ? "Healthy" : "Issues"}
        </span>
      </div>

      <div className="mt-3 space-y-2">
        {rows.map((row) => {
          const Icon = row.icon;
          return (
            <div
              key={row.checkKey}
              className={cn(
                "rounded-lg border px-3 py-2",
                row.isUp ? "border-green-200/80 bg-green-100/40" : "border-red-200/80 bg-red-100/40",
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Icon className={cn("h-4 w-4", row.isUp ? "text-green-700" : "text-red-700")} />
                  <span className="text-xs font-medium text-foreground">{row.label}</span>
                </div>
                <span className={cn(
                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
                  row.isUp ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700",
                )}>
                  <span className={cn("h-1.5 w-1.5 rounded-full", row.isUp ? "bg-green-500" : "bg-red-500")} />
                  {row.isUp ? "Up" : "Down"}
                </span>
              </div>
              {!row.isUp && row.detail && (
                <p className="mt-1 text-[11px] text-red-700 truncate">{row.detail}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GroupCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <div className="space-y-1.5">
          <Skeleton className="h-3.5 w-28" />
          <Skeleton className="h-3 w-44" />
        </div>
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <div className="mt-3 space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-border/80 p-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Skeleton className="h-4 w-4 rounded" />
                <Skeleton className="h-3 w-20" />
              </div>
              <Skeleton className="h-4 w-10 rounded-full" />
            </div>
          </div>
        ))}
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

  return (
    <div className="space-y-6 animate-erp-entrance">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-light">
            <Activity className="h-5 w-5 text-accent" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Monitoring</p>
            <p className="text-xs text-muted">
              {checkedAt ? `Last checked ${timeAgo(checkedAt)}` : "Checking services..."}
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
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {servicesError}
        </div>
      )}
      {issuesError && (
        <div className="rounded-xl border border-orange-200 bg-orange-50 px-4 py-3 text-sm text-orange-700">
          {issuesError}
        </div>
      )}

      {/* ── Unified ERP and FMAccesorios Cards ── */}
      <div>
        <div className="mb-3">
          <h2 className="text-sm font-bold text-foreground">Core Platforms</h2>
          <p className="text-xs text-muted">Unified service health by platform</p>
        </div>
        {servicesLoading ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <GroupCardSkeleton />
            <GroupCardSkeleton />
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {MONITORING_GROUPS.map((group) => (
              <UnifiedGroupCard
                key={group.key}
                group={group}
                services={services}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── FacturAPI Integration Cards ── */}
      <div>
        <div className="mb-3">
          <h2 className="text-sm font-bold text-foreground">FacturAPI Integrations</h2>
          <p className="text-xs text-muted">Separated by product usage</p>
        </div>
        {servicesLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <GroupCardSkeleton />
            <GroupCardSkeleton />
            <GroupCardSkeleton />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {FACTURAPI_GROUPS.map((group) => (
              <UnifiedGroupCard
                key={group.key}
                group={group}
                services={services}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Issues Table ── */}
      <div>
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-light">
              <AlertCircle className="h-4 w-4 text-accent" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-foreground">Issues</h2>
              <p className="text-xs text-muted">Track and resolve platform issues</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {["all", "open", "acknowledged", "resolved"].map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={cn(
                    "rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
                    statusFilter === s
                      ? s === "all"
                        ? "bg-gray-200 text-foreground"
                        : STATUS_CONFIG[s]?.color || "bg-gray-200 text-foreground"
                      : "text-gray-400 hover:text-gray-600"
                  )}
                >
                  {s === "all" ? "All Status" : STATUS_CONFIG[s]?.label || s}
                </button>
              ))}
            </div>
            <div className="h-5 w-px bg-gray-200" />
            <div className="flex gap-1">
              {["all", "critical", "high", "medium", "low"].map((s) => (
                <button
                  key={s}
                  onClick={() => setSeverityFilter(s)}
                  className={cn(
                    "rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
                    severityFilter === s
                      ? s === "all"
                        ? "bg-gray-200 text-foreground"
                        : SEVERITY_CONFIG[s]?.color || "bg-gray-200 text-foreground"
                      : "text-gray-400 hover:text-gray-600"
                  )}
                >
                  {s === "all" ? "All Severity" : SEVERITY_CONFIG[s]?.label || s}
                </button>
              ))}
            </div>
          </div>
        </div>

        {issuesLoading ? (
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50/80">
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[100px]">Severity</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Title</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[110px]">Category</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[100px]">Source</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[90px] text-right">Occurrences</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[100px]">Last Seen</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[110px]">Status</TableHead>
                  <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[160px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {issues.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center text-muted py-12">
                      No issues found.
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
                          <div>
                            <p className="font-medium text-foreground text-sm">{issue.title}</p>
                            {issue.summary && (
                              <p className="mt-0.5 text-xs text-muted truncate max-w-xs">{issue.summary}</p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">{issue.category}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">{issue.source}</TableCell>
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
