"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  AlertTriangle, AlertCircle, CheckCircle2, Activity,
  RefreshCw, Eye, CheckCheck, Clock,
} from "lucide-react";
import { toast } from "sonner";
import { evaPlatformApi } from "@/lib/api/eva-platform";
import type { MonitoringOverview, MonitoringIssue, MonitoringCheck } from "@/types";
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

const CHECK_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  up: { label: "Up", color: "bg-green-100 text-green-800" },
  down: { label: "Down", color: "bg-red-100 text-red-800" },
  degraded: { label: "Degraded", color: "bg-yellow-100 text-yellow-800" },
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

export default function MonitoringPage() {
  const [overview, setOverview] = useState<MonitoringOverview | null>(null);
  const [issues, setIssues] = useState<MonitoringIssue[]>([]);
  const [checks, setChecks] = useState<MonitoringCheck[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const issueParams: Record<string, string> = {};
      if (statusFilter !== "all") issueParams.status = statusFilter;
      if (severityFilter !== "all") issueParams.severity = severityFilter;

      const [ov, iss, chk] = await Promise.all([
        evaPlatformApi.monitoringOverview(),
        evaPlatformApi.listIssues(issueParams),
        evaPlatformApi.listChecks(),
      ]);
      setOverview(ov);
      setIssues(iss);
      setChecks(chk);
    } catch {
      toast.error("Failed to load monitoring data");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, severityFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      fetchData();
    }, 30_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData]);

  const handleAcknowledge = async (id: string) => {
    setActionLoading(id);
    try {
      await evaPlatformApi.acknowledgeIssue(id);
      toast.success("Issue acknowledged");
      await fetchData();
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
      await fetchData();
    } catch {
      toast.error("Failed to resolve issue");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="space-y-5 animate-erp-entrance">
        {/* KPI skeleton */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-5">
              <div className="flex items-center gap-4">
                <Skeleton className="h-11 w-11 rounded-xl" />
                <div className="space-y-2">
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="h-6 w-12" />
                </div>
              </div>
            </div>
          ))}
        </div>
        {/* Table skeleton */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-erp-entrance">
      {/* ── KPI Cards ── */}
      {overview && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Critical Issues */}
          <div className={cn(
            "rounded-xl border border-border border-l-[3px] bg-card p-5",
            overview.open_critical > 0 ? "border-l-red-500" : "border-l-gray-300"
          )}>
            <div className="flex items-center gap-4">
              <div className={cn(
                "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
                overview.open_critical > 0 ? "bg-red-50" : "bg-gray-50"
              )}>
                <AlertCircle className={cn(
                  "h-5 w-5",
                  overview.open_critical > 0 ? "text-red-600" : "text-gray-400"
                )} />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">Critical Issues</p>
                <p className={cn(
                  "mt-0.5 font-mono text-xl font-bold",
                  overview.open_critical > 0 ? "text-red-600" : "text-foreground"
                )}>
                  {overview.open_critical}
                </p>
              </div>
            </div>
          </div>

          {/* High Issues */}
          <div className={cn(
            "rounded-xl border border-border border-l-[3px] bg-card p-5",
            overview.open_high > 0 ? "border-l-orange-500" : "border-l-gray-300"
          )}>
            <div className="flex items-center gap-4">
              <div className={cn(
                "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
                overview.open_high > 0 ? "bg-orange-50" : "bg-gray-50"
              )}>
                <AlertTriangle className={cn(
                  "h-5 w-5",
                  overview.open_high > 0 ? "text-orange-600" : "text-gray-400"
                )} />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">High Issues</p>
                <p className={cn(
                  "mt-0.5 font-mono text-xl font-bold",
                  overview.open_high > 0 ? "text-orange-600" : "text-foreground"
                )}>
                  {overview.open_high}
                </p>
              </div>
            </div>
          </div>

          {/* Total Open */}
          <div className="rounded-xl border border-border border-l-[3px] border-l-blue-500 bg-card p-5">
            <div className="flex items-center gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50">
                <Activity className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">Total Open</p>
                <p className="mt-0.5 font-mono text-xl font-bold text-foreground">
                  {overview.total_open}
                </p>
              </div>
            </div>
          </div>

          {/* Resolved Today */}
          <div className="rounded-xl border border-border border-l-[3px] border-l-green-500 bg-card p-5">
            <div className="flex items-center gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-green-50">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-xs font-medium text-muted">Resolved Today</p>
                <p className="mt-0.5 font-mono text-xl font-bold text-green-600">
                  {overview.resolved_today}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Issues Table ── */}
      <div>
        {/* Filters toolbar */}
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="text-sm font-bold text-foreground">Issues</h2>
          <div className="flex items-center gap-2">
            {/* Status filter */}
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

            {/* Severity filter */}
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

            {/* Manual refresh */}
            <div className="h-5 w-px bg-gray-200" />
            <button
              onClick={() => fetchData()}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-muted transition-colors hover:bg-gray-100 hover:text-foreground"
              title="Refresh"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

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
      </div>

      {/* ── Health Checks Grid ── */}
      <div>
        <h2 className="text-sm font-bold text-foreground mb-4">Health Checks</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {checks.length === 0 ? (
            <div className="col-span-full rounded-xl border border-border bg-card p-8 text-center text-muted text-sm">
              No health checks configured.
            </div>
          ) : (
            checks.map((check) => {
              const chkCfg = CHECK_STATUS_CONFIG[check.status] || CHECK_STATUS_CONFIG.down;
              return (
                <div
                  key={check.id}
                  className={cn(
                    "rounded-xl border border-border bg-card p-5 transition-shadow hover:shadow-sm",
                    check.status === "down" && "border-l-[3px] border-l-red-500",
                    check.status === "degraded" && "border-l-[3px] border-l-yellow-500",
                    check.status === "up" && "border-l-[3px] border-l-green-500"
                  )}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="text-sm font-semibold text-foreground">{check.service}</p>
                      <p className="mt-0.5 text-xs text-muted truncate max-w-[200px]">{check.target}</p>
                    </div>
                    <span className={cn("rounded-full px-2.5 py-0.5 text-[11px] font-medium", chkCfg.color)}>
                      {chkCfg.label}
                    </span>
                  </div>

                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    {check.latency_ms !== null && (
                      <span className="flex items-center gap-1">
                        <Activity className="h-3 w-3" />
                        {check.latency_ms}ms
                      </span>
                    )}
                    {check.http_status !== null && (
                      <span className="font-mono">{check.http_status}</span>
                    )}
                    <span className="flex items-center gap-1 ml-auto">
                      <Clock className="h-3 w-3" />
                      {timeAgo(check.checked_at)}
                    </span>
                  </div>

                  {check.error_message && (
                    <p className="mt-2 rounded-md bg-red-50 px-2.5 py-1.5 text-xs text-red-700">
                      {check.error_message}
                    </p>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
