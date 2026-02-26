"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Server,
  Cpu,
  HardDrive,
  Phone,
  MessageSquare,
  RefreshCw,
  FolderOpen,
  File,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  Clock,
  Container,
  Terminal,
  Info,
  Wifi,
  WifiOff,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { evaPlatformApi } from "@/lib/api/eva-platform";
import type {
  RuntimeHost,
  RuntimeEmployee,
  RuntimeEmployeeDetail,
  DockerContainer,
  FileEntry,
  FileContent,
} from "@/types";

// ── Helpers ─────────────────────────────────────────────

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "never";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const STATE_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  running: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  placed: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  draining: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  recovering: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  offline: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  error: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  queued: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400",
  provisioning: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "text-red-600 dark:text-red-400",
  warning: "text-amber-600 dark:text-amber-400",
  info: "text-blue-600 dark:text-blue-400",
  debug: "text-gray-500",
};

function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : "";
}

// ── Host Card ───────────────────────────────────────────

function HostCard({
  host,
  selected,
  onClick,
}: {
  host: RuntimeHost;
  selected: boolean;
  onClick: () => void;
}) {
  const occupancy = host.max_tenants > 0 ? host.tenant_count / host.max_tenants : 0;
  const barColor =
    occupancy >= 0.95
      ? "bg-red-500"
      : occupancy >= 0.85
        ? "bg-amber-500"
        : "bg-green-500";

  return (
    <Card
      className={cn(
        "cursor-pointer p-4 transition-colors hover:bg-muted/50",
        selected && "ring-2 ring-primary bg-muted/30"
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{host.name}</p>
          <p className="text-xs text-muted-foreground font-mono">{host.public_ip}</p>
        </div>
        <Badge variant="outline" className={cn("text-[10px] shrink-0", STATE_COLORS[host.state])}>
          {host.state}
        </Badge>
      </div>
      <div className="mt-3">
        <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
          <span>
            {host.tenant_count}/{host.max_tenants} employees
          </span>
          <span>{Math.round(occupancy * 100)}%</span>
        </div>
        <div className="h-2 w-full rounded-full bg-muted">
          <div
            className={cn("h-full rounded-full transition-all", barColor)}
            style={{ width: `${Math.min(occupancy * 100, 100)}%` }}
          />
        </div>
      </div>
      <div className="mt-2 flex items-center gap-3 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <Cpu className="h-3 w-3" />
          {host.vcpu} vCPU
        </span>
        <span className="flex items-center gap-1">
          <HardDrive className="h-3 w-3" />
          {host.ram_mb / 1024} GB
        </span>
        <span className="flex items-center gap-1 ml-auto">
          <Clock className="h-3 w-3" />
          {timeAgo(host.last_heartbeat_at)}
        </span>
      </div>
    </Card>
  );
}

// ── Employee Row ────────────────────────────────────────

function EmployeeRow({
  employee,
  onClick,
}: {
  employee: RuntimeEmployee;
  onClick: () => void;
}) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition-colors hover:bg-muted/50"
      onClick={onClick}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium truncate">{employee.label}</p>
          {employee.account_name && (
            <span className="text-xs text-muted-foreground truncate">({employee.account_name})</span>
          )}
        </div>
        <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
          {employee.container_name && (
            <span className="font-mono">{employee.container_name}</span>
          )}
          {employee.gateway_port && <span>port {employee.gateway_port}</span>}
          {employee.phone_number && (
            <span className="flex items-center gap-1">
              <Phone className="h-3 w-3" />
              {employee.phone_number}
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span title={employee.whatsapp_connected ? "WhatsApp connected" : "WhatsApp disconnected"}>
          {employee.whatsapp_connected ? (
            <MessageSquare className="h-4 w-4 text-green-500" />
          ) : (
            <MessageSquare className="h-4 w-4 text-muted-foreground/30" />
          )}
        </span>
        <span title={employee.telegram_connected ? "Telegram connected" : "Telegram disconnected"}>
          {employee.telegram_connected ? (
            <Wifi className="h-4 w-4 text-blue-500" />
          ) : (
            <WifiOff className="h-4 w-4 text-muted-foreground/30" />
          )}
        </span>
        <Badge variant="outline" className={cn("text-[10px]", STATE_COLORS[employee.allocation_state || employee.status])}>
          {employee.allocation_state || employee.status}
        </Badge>
        <ChevronRight className="h-4 w-4 text-muted-foreground" />
      </div>
    </div>
  );
}

// ── Docker Tab ──────────────────────────────────────────

function DockerTab({ hostIp }: { hostIp: string | null }) {
  const [containers, setContainers] = useState<DockerContainer[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchContainers = useCallback(async () => {
    if (!hostIp) return;
    setLoading(true);
    setError(null);
    try {
      const data = await evaPlatformApi.getDockerStatus(hostIp);
      setContainers(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [hostIp]);

  useEffect(() => {
    fetchContainers();
  }, [fetchContainers]);

  if (loading) return <div className="space-y-3 p-4">{[1, 2].map((i) => <Skeleton key={i} className="h-20 w-full" />)}</div>;
  if (error) return <div className="p-4 text-sm text-red-500 flex items-center gap-2"><AlertCircle className="h-4 w-4" />{error}</div>;

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">{containers.length} containers</p>
        <Button variant="ghost" size="sm" onClick={fetchContainers}>
          <RefreshCw className="h-3.5 w-3.5 mr-1" />
          Refresh
        </Button>
      </div>
      {containers.map((c) => (
        <Card key={c.name} className="p-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Container className="h-4 w-4 text-muted-foreground shrink-0" />
                <p className="text-sm font-mono font-medium truncate">{c.name}</p>
              </div>
              <p className="text-xs text-muted-foreground mt-1 truncate">{c.image}</p>
            </div>
            <Badge variant="outline" className={cn("text-[10px] shrink-0", STATE_COLORS[c.state])}>
              {c.state}
            </Badge>
          </div>
          <div className="flex items-center gap-4 mt-2 text-[11px] text-muted-foreground">
            <span>{c.status}</span>
            {c.ports && <span className="font-mono truncate">{c.ports}</span>}
          </div>
        </Card>
      ))}
      {containers.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-6">No containers found</p>
      )}
    </div>
  );
}

// ── Logs Tab ────────────────────────────────────────────

function LogsTab({
  hostIp,
  containerName,
}: {
  hostIp: string | null;
  containerName: string | null;
}) {
  const [logs, setLogs] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLPreElement>(null);

  const fetchLogs = useCallback(async () => {
    if (!hostIp || !containerName) return;
    setLoading(true);
    setError(null);
    try {
      const data = await evaPlatformApi.getDockerLogs(hostIp, containerName, 100);
      setLogs(data.lines);
      setTimeout(() => {
        scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
      }, 50);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load logs";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [hostIp, containerName]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  if (!containerName) {
    return <p className="p-4 text-sm text-muted-foreground">No container assigned</p>;
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 border-b">
        <p className="text-xs font-mono text-muted-foreground">{containerName}</p>
        <Button variant="ghost" size="sm" onClick={fetchLogs} disabled={loading}>
          <RefreshCw className={cn("h-3.5 w-3.5 mr-1", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>
      {error ? (
        <div className="p-4 text-sm text-red-500 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      ) : loading && !logs ? (
        <div className="p-4 space-y-2">
          {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-4 w-full" />)}
        </div>
      ) : (
        <pre
          ref={scrollRef}
          className="flex-1 overflow-auto bg-gray-950 text-green-400 text-xs font-mono p-4 whitespace-pre-wrap leading-relaxed"
        >
          {logs || "No logs available"}
        </pre>
      )}
    </div>
  );
}

// ── Files Tab ───────────────────────────────────────────

function FilesTab({ hostIp }: { hostIp: string | null }) {
  const [currentPath, setCurrentPath] = useState("/root/.openclaw/");
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [loadingDir, setLoadingDir] = useState(false);
  const [loadingFile, setLoadingFile] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDir = useCallback(
    async (path: string) => {
      if (!hostIp) return;
      setLoadingDir(true);
      setError(null);
      setFileContent(null);
      try {
        const data = await evaPlatformApi.listFiles(hostIp, path);
        setEntries(data);
        setCurrentPath(path);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Failed to list directory";
        setError(msg);
      } finally {
        setLoadingDir(false);
      }
    },
    [hostIp]
  );

  const fetchFile = useCallback(
    async (path: string) => {
      if (!hostIp) return;
      setLoadingFile(true);
      try {
        const data = await evaPlatformApi.getFileContent(hostIp, path);
        setFileContent(data);
      } catch (e: unknown) {
        toast.error(e instanceof Error ? e.message : "Failed to read file");
      } finally {
        setLoadingFile(false);
      }
    },
    [hostIp]
  );

  useEffect(() => {
    fetchDir(currentPath);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hostIp]);

  // Breadcrumb segments
  const pathParts = currentPath.split("/").filter(Boolean);

  return (
    <div className="flex flex-col h-full">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1 px-4 py-2 border-b text-xs overflow-x-auto">
        <button
          className="text-muted-foreground hover:text-foreground shrink-0"
          onClick={() => fetchDir("/")}
        >
          /
        </button>
        {pathParts.map((part, i) => {
          const fullPath = "/" + pathParts.slice(0, i + 1).join("/") + "/";
          return (
            <span key={fullPath} className="flex items-center gap-1">
              <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
              <button
                className="text-muted-foreground hover:text-foreground truncate max-w-[120px]"
                onClick={() => fetchDir(fullPath)}
              >
                {part}
              </button>
            </span>
          );
        })}
      </div>

      {error ? (
        <div className="p-4 text-sm text-red-500 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      ) : (
        <div className="flex flex-1 min-h-0">
          {/* File list */}
          <div className="w-2/5 border-r overflow-auto">
            {loadingDir ? (
              <div className="p-3 space-y-2">
                {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-7 w-full" />)}
              </div>
            ) : (
              <div className="py-1">
                {currentPath !== "/" && (
                  <button
                    className="flex items-center gap-2 w-full px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted/50"
                    onClick={() => {
                      const parent = currentPath.replace(/\/[^/]+\/$/, "/") || "/";
                      fetchDir(parent);
                    }}
                  >
                    <FolderOpen className="h-3.5 w-3.5" />
                    ..
                  </button>
                )}
                {entries.map((entry) => (
                  <button
                    key={entry.path}
                    className={cn(
                      "flex items-center gap-2 w-full px-3 py-1.5 text-xs hover:bg-muted/50 text-left",
                      fileContent?.path === entry.path && "bg-muted"
                    )}
                    onClick={() => {
                      if (entry.is_dir) {
                        fetchDir(entry.path.endsWith("/") ? entry.path : entry.path + "/");
                      } else {
                        fetchFile(entry.path);
                      }
                    }}
                  >
                    {entry.is_dir ? (
                      <FolderOpen className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                    ) : (
                      <File className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    )}
                    <span className="truncate flex-1">{entry.name}</span>
                    {!entry.is_dir && entry.size !== null && (
                      <span className="text-[10px] text-muted-foreground shrink-0">
                        {formatBytes(entry.size)}
                      </span>
                    )}
                  </button>
                ))}
                {entries.length === 0 && (
                  <p className="px-3 py-4 text-xs text-muted-foreground text-center">Empty directory</p>
                )}
              </div>
            )}
          </div>

          {/* File content viewer */}
          <div className="w-3/5 overflow-auto">
            {loadingFile ? (
              <div className="p-4 space-y-2">
                {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-4 w-full" />)}
              </div>
            ) : fileContent ? (
              <div className="flex flex-col h-full">
                <div className="flex items-center justify-between px-3 py-1.5 border-b bg-muted/30">
                  <span className="text-[11px] font-mono text-muted-foreground truncate">
                    {fileContent.path}
                  </span>
                  <span className="text-[10px] text-muted-foreground shrink-0 ml-2">
                    {formatBytes(fileContent.size)}
                    {fileContent.truncated && " (truncated)"}
                  </span>
                </div>
                <pre className="flex-1 overflow-auto text-xs font-mono p-3 whitespace-pre-wrap leading-relaxed bg-gray-950 text-gray-300">
                  {fileContent.content}
                </pre>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
                Select a file to view
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Employee Detail Sheet ───────────────────────────────

function EmployeeDetailSheet({
  employee,
  open,
  onClose,
}: {
  employee: RuntimeEmployee | null;
  open: boolean;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<RuntimeEmployeeDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("info");

  useEffect(() => {
    if (!employee || !open) {
      setDetail(null);
      setActiveTab("info");
      return;
    }
    setLoading(true);
    evaPlatformApi
      .getEmployeeDetail(employee.id)
      .then(setDetail)
      .catch(() => toast.error("Failed to load employee details"))
      .finally(() => setLoading(false));
  }, [employee, open]);

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="w-[600px] sm:max-w-[600px] p-0 flex flex-col">
        <SheetHeader className="px-6 py-4 border-b shrink-0">
          <div className="flex items-center gap-3">
            <SheetTitle className="text-base">{employee?.label || "Employee"}</SheetTitle>
            {employee && (
              <Badge variant="outline" className={cn("text-[10px]", STATE_COLORS[employee.allocation_state || employee.status])}>
                {employee.allocation_state || employee.status}
              </Badge>
            )}
          </div>
          {employee?.account_name && (
            <p className="text-xs text-muted-foreground">{employee.account_name}</p>
          )}
        </SheetHeader>

        {loading ? (
          <div className="p-6 space-y-4">
            {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-6 w-full" />)}
          </div>
        ) : (
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col flex-1 min-h-0">
            <TabsList className="mx-6 mt-2 shrink-0">
              <TabsTrigger value="info" className="text-xs gap-1.5">
                <Info className="h-3.5 w-3.5" />
                Info
              </TabsTrigger>
              <TabsTrigger value="docker" className="text-xs gap-1.5">
                <Container className="h-3.5 w-3.5" />
                Docker
              </TabsTrigger>
              <TabsTrigger value="logs" className="text-xs gap-1.5">
                <Terminal className="h-3.5 w-3.5" />
                Logs
              </TabsTrigger>
              <TabsTrigger value="files" className="text-xs gap-1.5">
                <FolderOpen className="h-3.5 w-3.5" />
                Files
              </TabsTrigger>
            </TabsList>

            <TabsContent value="info" className="flex-1 overflow-auto mt-0 px-6 py-4">
              {detail && <InfoTabContent detail={detail} />}
            </TabsContent>

            <TabsContent value="docker" className="flex-1 overflow-auto mt-0">
              <DockerTab hostIp={detail?.host_ip || employee?.vps_ip || null} />
            </TabsContent>

            <TabsContent value="logs" className="flex-1 min-h-0 mt-0">
              <LogsTab
                hostIp={detail?.host_ip || employee?.vps_ip || null}
                containerName={detail?.container_name || employee?.container_name || null}
              />
            </TabsContent>

            <TabsContent value="files" className="flex-1 min-h-0 mt-0">
              <FilesTab hostIp={detail?.host_ip || employee?.vps_ip || null} />
            </TabsContent>
          </Tabs>
        )}
      </SheetContent>
    </Sheet>
  );
}

// ── Info Tab Content ────────────────────────────────────

function InfoTabContent({ detail }: { detail: RuntimeEmployeeDetail }) {
  return (
    <div className="space-y-5">
      {/* Status */}
      <section>
        <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-2">Status</h4>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <InfoField label="Status" value={detail.status} />
          <InfoField label="Allocation" value={detail.allocation_state || "none"} />
          {detail.status_detail && (
            <InfoField label="Detail" value={detail.status_detail} className="col-span-2" />
          )}
          {detail.error && (
            <div className="col-span-2 rounded-lg bg-red-50 dark:bg-red-900/10 p-3 text-xs text-red-700 dark:text-red-400">
              {detail.error}
            </div>
          )}
        </div>
      </section>

      <Separator />

      {/* Connection */}
      <section>
        <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-2">Channels</h4>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="flex items-center gap-2">
            {detail.whatsapp_connected ? (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            ) : (
              <AlertCircle className="h-4 w-4 text-muted-foreground/40" />
            )}
            <span>WhatsApp</span>
          </div>
          <div className="flex items-center gap-2">
            {detail.telegram_connected ? (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            ) : (
              <AlertCircle className="h-4 w-4 text-muted-foreground/40" />
            )}
            <span>Telegram</span>
          </div>
          {detail.phone_number && <InfoField label="Phone" value={detail.phone_number} />}
        </div>
      </section>

      <Separator />

      {/* Runtime */}
      <section>
        <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-2">Runtime</h4>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <InfoField label="Container" value={detail.container_name || "none"} mono />
          <InfoField label="Port" value={detail.gateway_port?.toString() || "none"} mono />
          <InfoField label="Host" value={detail.host_name || "none"} mono />
          <InfoField label="Host IP" value={detail.host_ip || "none"} mono />
          {detail.cpu_reservation_mcpu && (
            <InfoField label="CPU" value={`${detail.cpu_reservation_mcpu} mCPU`} />
          )}
          {detail.ram_reservation_mb && (
            <InfoField label="RAM" value={`${detail.ram_reservation_mb} MB`} />
          )}
          {detail.reconnect_risk && detail.reconnect_risk !== "safe" && (
            <InfoField label="Reconnect Risk" value={detail.reconnect_risk} />
          )}
          {detail.queued_reason && (
            <InfoField label="Queue Reason" value={detail.queued_reason} className="col-span-2" />
          )}
        </div>
      </section>

      <Separator />

      {/* Identifiers */}
      <section>
        <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-2">Identifiers</h4>
        <div className="grid grid-cols-1 gap-2 text-sm">
          <InfoField label="OpenClaw Agent ID" value={detail.id} mono />
          <InfoField label="Agent ID" value={detail.agent_id} mono />
          <InfoField label="Account ID" value={detail.account_id} mono />
        </div>
      </section>

      <Separator />

      {/* Timestamps */}
      <section>
        <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-2">Timestamps</h4>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {detail.provisioning_started_at && (
            <InfoField label="Provisioning Started" value={new Date(detail.provisioning_started_at).toLocaleString()} />
          )}
          {detail.provisioning_completed_at && (
            <InfoField label="Provisioning Completed" value={new Date(detail.provisioning_completed_at).toLocaleString()} />
          )}
          {detail.placed_at && <InfoField label="Placed" value={new Date(detail.placed_at).toLocaleString()} />}
          {detail.started_at && <InfoField label="Started" value={new Date(detail.started_at).toLocaleString()} />}
        </div>
      </section>

      {/* Recent Events */}
      {detail.recent_events.length > 0 && (
        <>
          <Separator />
          <section>
            <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-2">
              Recent Events ({detail.recent_events.length})
            </h4>
            <div className="space-y-2">
              {detail.recent_events.map((evt) => (
                <div key={evt.id} className="rounded border p-2 text-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={cn("font-medium", SEVERITY_COLORS[evt.severity])}>
                        {evt.severity}
                      </span>
                      <span className="font-mono">{evt.event_type}</span>
                    </div>
                    <span className="text-muted-foreground">{timeAgo(evt.created_at)}</span>
                  </div>
                  {evt.reason_code && (
                    <p className="text-muted-foreground mt-1">{evt.reason_code}</p>
                  )}
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function InfoField({
  label,
  value,
  mono,
  className,
}: {
  label: string;
  value: string;
  mono?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className={cn("text-sm truncate", mono && "font-mono text-xs")}>{value}</p>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────

export default function InfrastructurePage() {
  const [hosts, setHosts] = useState<RuntimeHost[]>([]);
  const [selectedHost, setSelectedHost] = useState<RuntimeHost | null>(null);
  const [employees, setEmployees] = useState<RuntimeEmployee[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<RuntimeEmployee | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingEmployees, setLoadingEmployees] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const hasSelectedRef = useRef(false);

  const fetchHosts = useCallback(async () => {
    try {
      const data = await evaPlatformApi.listHosts();
      setHosts(data);
      // Auto-select first host only on initial load
      if (data.length > 0 && !hasSelectedRef.current) {
        hasSelectedRef.current = true;
        setSelectedHost(data[0]);
      }
    } catch {
      toast.error("Failed to load hosts");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchEmployees = useCallback(async (hostId: string) => {
    setLoadingEmployees(true);
    try {
      const data = await evaPlatformApi.listHostEmployees(hostId);
      setEmployees(data);
    } catch {
      toast.error("Failed to load employees");
    } finally {
      setLoadingEmployees(false);
    }
  }, []);

  // Initial load + auto-refresh every 30s
  useEffect(() => {
    fetchHosts();
    intervalRef.current = setInterval(fetchHosts, 30000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchHosts]);

  // Load employees when host changes
  useEffect(() => {
    if (selectedHost) {
      fetchEmployees(selectedHost.id);
    } else {
      setEmployees([]);
    }
  }, [selectedHost, fetchEmployees]);

  const totalSlots = hosts.reduce((sum, h) => sum + h.max_tenants, 0);
  const usedSlots = hosts.reduce((sum, h) => sum + h.tenant_count, 0);

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        <SummaryCard
          label="Active Hosts"
          value={hosts.filter((h) => h.state === "active").length}
          icon={<Server className="h-5 w-5" />}
          color="text-blue-600 dark:text-blue-400"
        />
        <SummaryCard
          label="Total Employees"
          value={usedSlots}
          icon={<Cpu className="h-5 w-5" />}
          color="text-green-600 dark:text-green-400"
        />
        <SummaryCard
          label="Slots Available"
          value={totalSlots - usedSlots}
          icon={<HardDrive className="h-5 w-5" />}
          color="text-amber-600 dark:text-amber-400"
        />
        <SummaryCard
          label="Total Capacity"
          value={`${usedSlots}/${totalSlots}`}
          icon={<Server className="h-5 w-5" />}
          color="text-purple-600 dark:text-purple-400"
        />
      </div>

      {/* Two-panel layout */}
      <div className="flex gap-6 min-h-[600px]">
        {/* Left: Host list */}
        <div className="w-80 shrink-0 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Hosts</h3>
            <Button variant="ghost" size="sm" onClick={fetchHosts}>
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
          {loading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => <Skeleton key={i} className="h-32 w-full" />)}
            </div>
          ) : hosts.length === 0 ? (
            <Card className="p-8 text-center">
              <Server className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No active hosts</p>
            </Card>
          ) : (
            <ScrollArea className="h-[calc(100vh-320px)]">
              <div className="space-y-3 pr-3">
                {hosts.map((host) => (
                  <HostCard
                    key={host.id}
                    host={host}
                    selected={selectedHost?.id === host.id}
                    onClick={() => setSelectedHost(host)}
                  />
                ))}
              </div>
            </ScrollArea>
          )}
        </div>

        {/* Right: Employee list */}
        <div className="flex-1 min-w-0">
          {selectedHost ? (
            <>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold">
                    Employees on {selectedHost.name}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {selectedHost.public_ip} &middot;{" "}
                    {selectedHost.tenant_count}/{selectedHost.max_tenants} slots used &middot;{" "}
                    {selectedHost.max_tenants - selectedHost.tenant_count} available
                  </p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => fetchEmployees(selectedHost.id)}>
                  <RefreshCw className="h-3.5 w-3.5" />
                </Button>
              </div>
              {loadingEmployees ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 w-full" />)}
                </div>
              ) : employees.length === 0 ? (
                <Card className="p-8 text-center">
                  <Cpu className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">No employees on this host</p>
                </Card>
              ) : (
                <div className="space-y-2">
                  {employees.map((emp) => (
                    <EmployeeRow
                      key={emp.id}
                      employee={emp}
                      onClick={() => {
                        setSelectedEmployee(emp);
                        setSheetOpen(true);
                      }}
                    />
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-sm text-muted-foreground">Select a host to view employees</p>
            </div>
          )}
        </div>
      </div>

      {/* Detail sheet */}
      <EmployeeDetailSheet
        employee={selectedEmployee}
        open={sheetOpen}
        onClose={() => {
          setSheetOpen(false);
          setSelectedEmployee(null);
        }}
      />
    </div>
  );
}

function SummaryCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
        </div>
        <div className={cn("p-2 rounded-lg bg-muted/50", color)}>{icon}</div>
      </div>
    </Card>
  );
}
