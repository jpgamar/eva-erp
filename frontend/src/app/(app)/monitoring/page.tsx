"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  AlertTriangle, AlertCircle, CheckCircle2, Activity,
  RefreshCw, Eye, CheckCheck, Clock, Wifi, WifiOff,
} from "lucide-react";
import { toast } from "sonner";
import { evaPlatformApi } from "@/lib/api/eva-platform";
import type { MonitoringOverview, MonitoringIssue, ServiceStatus, ServiceStatusResponse } from "@/types";
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

/* ── Service Card ─────────────────────────────────────── */

function ServiceCard({ svc }: { svc: ServiceStatus }) {
  const isUp = svc.status === "up";
  const isDegraded = svc.status === "degraded";
  return (
    <div className={cn(
      "rounded-xl border border-border bg-card p-4 transition-shadow hover:shadow-sm",
      isUp && "border-l-[3px] border-l-green-500",
      isDegraded && "border-l-[3px] border-l-yellow-500",
      !isUp && !isDegraded && "border-l-[3px] border-l-red-500",
    )}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn(
            "flex h-9 w-9 items-center justify-center rounded-lg",
            isUp ? "bg-green-50" : isDegraded ? "bg-yellow-50" : "bg-red-50",
          )}>
            {isUp ? (
              <Wifi className="h-4 w-4 text-green-600" />
            ) : (
              <WifiOff className={cn("h-4 w-4", isDegraded ? "text-yellow-600" : "text-red-600")} />
            )}
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">{svc.name}</p>
            {svc.latency_ms !== null && (
              <p className="text-xs text-muted">{svc.latency_ms}ms</p>
            )}
          </div>
        </div>
        <span className={cn(
          "inline-flex items-center gap-1.5 text-xs font-medium",
          isUp ? "text-green-600" : isDegraded ? "text-yellow-600" : "text-red-600",
        )}>
          <span className={cn(
            "h-2 w-2 rounded-full",
            isUp ? "bg-green-500" : isDegraded ? "bg-yellow-500" : "bg-red-500",
          )} />
          {isUp ? "Operational" : isDegraded ? "Degraded" : "Down"}
        </span>
      </div>
      {svc.error && (
        <p className="mt-2 rounded-md bg-red-50 px-2.5 py-1.5 text-xs text-red-700 truncate">
          {svc.error}
        </p>
      )}
    </div>
  );
}

/* ── Page ────────────────────────────────────────────── */

export default function MonitoringPage() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [servicesLoading, setServicesLoading] = useState(true);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);

  const [overview, setOverview] = useState<MonitoringOverview | null>(null);
  const [issues, setIssues] = useState<MonitoringIssue[]>([]);
  const [issuesLoading, setIssuesLoading] = useState(true);

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
    } catch {
      // silent — cards just stay empty
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

      const [ov, iss] = await Promise.all([
        evaPlatformApi.monitoringOverview(),
        evaPlatformApi.listIssues(issueParams),
      ]);
      setOverview(ov);
      setIssues(iss);
    } catch {
      // silent
    } finally {
      setIssuesLoading(false);
    }
  }, [statusFilter, severityFilter]);

  /* ── Initial load: services first (fast), issues in background ── */
  useEffect(() => {
    fetchServices();
    fetchIssues();
  }, [fetchServices, fetchIssues]);

  /* ── Auto-refresh every 30s ── */
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      fetchServices();
    }, 30_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchServices]);

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

      {/* ── Service Status Cards ── */}
      {servicesLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-center gap-3">
                <Skeleton className="h-9 w-9 rounded-lg" />
                <div className="space-y-1.5">
                  <Skeleton className="h-3.5 w-24" />
                  <Skeleton className="h-3 w-14" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {services.map((svc) => (
            <ServiceCard key={svc.name} svc={svc} />
          ))}
        </div>
      )}

      {/* ── KPI Summary ── */}
      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className={cn(
            "rounded-xl border border-border bg-card p-4 text-center",
            overview.open_critical > 0 && "border-red-200 bg-red-50/40"
          )}>
            <p className="text-xs font-medium text-muted">Critical</p>
            <p className={cn(
              "mt-1 font-mono text-2xl font-bold",
              overview.open_critical > 0 ? "text-red-600" : "text-foreground"
            )}>
              {overview.open_critical}
            </p>
          </div>
          <div className={cn(
            "rounded-xl border border-border bg-card p-4 text-center",
            overview.open_high > 0 && "border-orange-200 bg-orange-50/40"
          )}>
            <p className="text-xs font-medium text-muted">High</p>
            <p className={cn(
              "mt-1 font-mono text-2xl font-bold",
              overview.open_high > 0 ? "text-orange-600" : "text-foreground"
            )}>
              {overview.open_high}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center">
            <p className="text-xs font-medium text-muted">Total Open</p>
            <p className="mt-1 font-mono text-2xl font-bold text-foreground">
              {overview.total_open}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4 text-center">
            <p className="text-xs font-medium text-muted">Resolved Today</p>
            <p className="mt-1 font-mono text-2xl font-bold text-green-600">
              {overview.resolved_today}
            </p>
          </div>
        </div>
      )}

      {/* ── Issues Table ── */}
      <div>
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="text-sm font-bold text-foreground">Issues</h2>
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
