"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  ChevronDown,
  ImagePlus,
  Instagram,
  MessageCircle,
  MoreHorizontal,
  Phone,
  Plus,
  Search,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  empresasApi,
  type AccountChannelHealthResponse,
  type Empresa,
  type EmpresaCreate,
  type EmpresaHealthStatus,
  type EmpresaHistory,
  type EmpresaListItem,
  type EvaAccountForLink,
} from "@/lib/api/empresas";
import { CheckoutLinkModal } from "@/components/empresas/CheckoutLinkModal";
import { EmpresasKanban } from "@/components/empresas/EmpresasKanban";

// ── Constants ──────────────────────────────────────────────────────

// Renamed labels (silent-channel-health follow-up): "Fase: ..." disambiguates
// the manual customer-relationship phase from the auto-detected channel
// health (the colored dots / channel badges below). Without the prefix,
// "Requiere atención" reads like a health alert.
const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  operativo: { label: "Fase: Operativo", className: "bg-emerald-100 text-emerald-700" },
  en_implementacion: { label: "Fase: Implementación", className: "bg-amber-100 text-amber-700" },
  requiere_atencion: { label: "Fase: Atención", className: "bg-red-100 text-red-700" },
};

const BALL_ON_CONFIG: Record<string, { label: string; icon: typeof ArrowLeft }> = {
  nosotros: { label: "Nosotros", icon: ArrowLeft },
  cliente: { label: "Cliente", icon: ArrowRight },
};

const FIELD_LABELS: Record<string, string> = {
  status: "Status",
  ball_on: "Responsable",
  summary_note: "Nota de seguimiento",
};

const VALUE_LABELS: Record<string, string> = {
  operativo: "Operativo",
  en_implementacion: "En implementación",
  requiere_atencion: "Requiere atención",
  nosotros: "Nosotros",
  cliente: "Cliente",
};

const EMPTY_EMPRESA: EmpresaCreate = {
  name: "",
  logo_url: null,
  industry: null,
  email: null,
  phone: null,
  address: null,
  rfc: null,
  razon_social: null,
  regimen_fiscal: null,
  fiscal_postal_code: null,
  cfdi_use: "G03",
  person_type: null,
  status: "operativo",
  ball_on: null,
  summary_note: null,
  monthly_amount: null,
  payment_day: null,
  last_paid_date: null,
  eva_account_id: null,
};

// ── Channel health UI helpers ──────────────────────────────────────

const HEALTH_DOT_CLASS: Record<EmpresaHealthStatus, string> = {
  healthy: "bg-emerald-500",
  unhealthy: "bg-red-500",
  unknown: "bg-yellow-400",
  not_linked: "bg-muted-foreground/40",
};

const HEALTH_TOOLTIP: Record<EmpresaHealthStatus, string> = {
  healthy: "Todos los canales operando",
  unhealthy: "1+ canal desconectado",
  unknown: "No se pudo verificar el estado",
  not_linked: "Sin vincular a una cuenta de Eva",
};

function formatHealthTooltip(emp: EmpresaListItem): string {
  if (emp.health.status === "unhealthy") {
    const n = emp.health.unhealthy_count;
    return n === 1 ? "1 canal desconectado" : `${n} canales desconectados`;
  }
  return HEALTH_TOOLTIP[emp.health.status];
}

function formatRelativeTimeSpanish(iso: string | null): string {
  if (!iso) return "Nunca verificado";
  const then = new Date(iso).getTime();
  const diffMs = Date.now() - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "ahora";
  if (diffMin < 60) return `hace ${diffMin} min`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `hace ${diffHrs}h`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays === 1) return "ayer";
  if (diffDays < 30) return `hace ${diffDays} días`;
  const diffMonths = Math.floor(diffDays / 30);
  return `hace ${diffMonths} ${diffMonths === 1 ? "mes" : "meses"}`;
}

function getPaymentStatus(lastPaidDate: string | null, paymentDay: number | null): "paid" | "warning" | "overdue" | null {
  if (paymentDay == null) return null;
  const today = new Date();
  const currentMonth = today.getMonth();
  const currentYear = today.getFullYear();

  // Check if paid this month
  if (lastPaidDate) {
    const paid = new Date(lastPaidDate + "T00:00:00");
    if (paid.getMonth() === currentMonth && paid.getFullYear() === currentYear) return "paid";
  }

  // Not paid this month — check if overdue or warning
  const dayOfMonth = today.getDate();
  if (dayOfMonth > paymentDay) return "overdue"; // past payment day
  if (paymentDay - dayOfMonth <= 10) return "warning"; // within 10 days
  return null; // still far away, no indicator
}

const PAYMENT_STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  paid: { label: "Pagado", className: "text-emerald-600" },
  warning: { label: "Pendiente", className: "text-amber-600" },
  overdue: { label: "Vencido", className: "text-red-600" },
};

// ── Page ───────────────────────────────────────────────────────────

export default function EmpresasPage() {
  const [empresas, setEmpresas] = useState<EmpresaListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"grid" | "kanban">(() => {
    if (typeof window === "undefined") return "grid";
    const url = new URL(window.location.href);
    return url.searchParams.get("view") === "kanban" ? "kanban" : "grid";
  });
  const stageFilter = (() => {
    if (typeof window === "undefined") return null;
    return new URL(window.location.href).searchParams.get("stage");
  })();

  // Empresa modal
  const [empresaModalOpen, setEmpresaModalOpen] = useState(false);
  const [empresaForm, setEmpresaForm] = useState<EmpresaCreate>(EMPTY_EMPRESA);
  const [editingEmpresaId, setEditingEmpresaId] = useState<string | null>(null);
  const [extractingConstancia, setExtractingConstancia] = useState(false);

  // History modal
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [historyEmpresaName, setHistoryEmpresaName] = useState("");
  const [historyEntries, setHistoryEntries] = useState<EmpresaHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Checkout modal
  const [checkoutEmpresa, setCheckoutEmpresa] = useState<EmpresaListItem | null>(null);

  // Inline add item
  const [addingItemFor, setAddingItemFor] = useState<string | null>(null);
  const [newItemTitle, setNewItemTitle] = useState("");
  const addItemInputRef = useRef<HTMLInputElement>(null);

  // Items expanded (show all)
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  // Toggling items (for optimistic UI + disable)
  const [togglingItems, setTogglingItems] = useState<Set<string>>(new Set());

  // Channel health modal (silent-channel-health plan)
  const [healthModalOpen, setHealthModalOpen] = useState(false);
  const [healthModalEmpresa, setHealthModalEmpresa] = useState<EmpresaListItem | null>(null);
  const [healthModalLoading, setHealthModalLoading] = useState(false);
  const [healthModalData, setHealthModalData] = useState<AccountChannelHealthResponse | null>(null);

  // Eva accounts list (for the link dropdown in the edit modal)
  const [evaAccounts, setEvaAccounts] = useState<EvaAccountForLink[]>([]);
  const [loadingEvaAccounts, setLoadingEvaAccounts] = useState(false);

  // ── Data loading ────────────────────────────────────────────────

  const loadEmpresas = async () => {
    try {
      const data = await empresasApi.list(search || undefined);
      setEmpresas(data);
    } catch {
      toast.error("Error al cargar empresas");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEmpresas();
  }, [search]);

  // ── Empresa CRUD ────────────────────────────────────────────────

  const ensureEvaAccountsLoaded = async () => {
    if (evaAccounts.length > 0 || loadingEvaAccounts) return;
    setLoadingEvaAccounts(true);
    try {
      const data = await empresasApi.listEvaAccountsForLink();
      setEvaAccounts(data);
    } catch {
      // Silent fall-through — the dropdown will show "no accounts"
      setEvaAccounts([]);
    } finally {
      setLoadingEvaAccounts(false);
    }
  };

  const openCreateEmpresa = () => {
    setEmpresaForm(EMPTY_EMPRESA);
    setEditingEmpresaId(null);
    setEmpresaModalOpen(true);
    void ensureEvaAccountsLoaded();
  };

  const openEditEmpresa = async (emp: EmpresaListItem) => {
    try {
      const full = await empresasApi.get(emp.id);
      setEmpresaForm({
        name: full.name,
        logo_url: full.logo_url,
        industry: full.industry,
        email: full.email,
        phone: full.phone,
        address: full.address,
        rfc: full.rfc,
        razon_social: full.razon_social,
        regimen_fiscal: full.regimen_fiscal,
        fiscal_postal_code: full.fiscal_postal_code,
        cfdi_use: full.cfdi_use,
        person_type: full.person_type,
        status: full.status,
        ball_on: full.ball_on,
        summary_note: full.summary_note,
        monthly_amount: full.monthly_amount,
        payment_day: full.payment_day,
        last_paid_date: full.last_paid_date,
        eva_account_id: full.eva_account_id,
      });
      setEditingEmpresaId(full.id);
      setEmpresaModalOpen(true);
      void ensureEvaAccountsLoaded();
    } catch {
      toast.error("Error al cargar empresa");
    }
  };

  // ── Channel health modal ────────────────────────────────────────

  const openHealthModal = async (emp: EmpresaListItem) => {
    setHealthModalEmpresa(emp);
    setHealthModalData(null);
    setHealthModalOpen(true);

    if (emp.health.status === "not_linked" || !emp.eva_account_id) {
      // Nothing to fetch — modal renders the "not linked" hint.
      return;
    }

    setHealthModalLoading(true);
    try {
      const data = await empresasApi.getAccountChannelHealth(emp.eva_account_id);
      setHealthModalData(data);
    } catch {
      toast.error("No se pudo cargar el estado de los canales");
    } finally {
      setHealthModalLoading(false);
    }
  };

  const saveEmpresa = async () => {
    if (!empresaForm.name.trim()) {
      toast.error("El nombre es requerido");
      return;
    }
    try {
      if (editingEmpresaId) {
        await empresasApi.update(editingEmpresaId, empresaForm);
        toast.success("Empresa actualizada");
      } else {
        await empresasApi.create(empresaForm);
        toast.success("Empresa creada");
      }
      setEmpresaModalOpen(false);
      loadEmpresas();
    } catch {
      toast.error("Error al guardar empresa");
    }
  };

  const deleteEmpresa = async (id: string) => {
    try {
      await empresasApi.delete(id);
      toast.success("Empresa eliminada");
      loadEmpresas();
    } catch {
      toast.error("Error al eliminar empresa");
    }
  };

  // ── Items ───────────────────────────────────────────────────────

  const toggleItem = async (itemId: string, empresaId: string) => {
    if (togglingItems.has(itemId)) return;
    setTogglingItems((prev) => new Set(prev).add(itemId));

    // Optimistic: remove from pending list
    setEmpresas((prev) =>
      prev.map((emp) =>
        emp.id === empresaId
          ? {
              ...emp,
              pending_items: emp.pending_items.filter((i) => i.id !== itemId),
              pending_count: emp.pending_count - 1,
            }
          : emp
      )
    );

    try {
      await empresasApi.toggleItem(itemId);
    } catch {
      toast.error("Error al actualizar");
      loadEmpresas(); // revert
    } finally {
      setTogglingItems((prev) => {
        const next = new Set(prev);
        next.delete(itemId);
        return next;
      });
    }
  };

  const addItem = async (empresaId: string) => {
    if (!newItemTitle.trim()) return;
    try {
      await empresasApi.createItem(empresaId, { title: newItemTitle.trim() });
      setNewItemTitle("");
      setAddingItemFor(null);
      loadEmpresas();
    } catch {
      toast.error("Error al agregar pendiente");
    }
  };

  const startAddingItem = (empresaId: string) => {
    setAddingItemFor(empresaId);
    setNewItemTitle("");
    setTimeout(() => addItemInputRef.current?.focus(), 50);
  };

  // ── History ─────────────────────────────────────────────────────

  const openHistory = async (empresaId: string, empresaName: string) => {
    setHistoryEmpresaName(empresaName);
    setHistoryEntries([]);
    setHistoryLoading(true);
    setHistoryModalOpen(true);
    try {
      const data = await empresasApi.getHistory(empresaId);
      setHistoryEntries(data);
    } catch {
      toast.error("Error al cargar historial");
    } finally {
      setHistoryLoading(false);
    }
  };

  const openPortal = async (empresaId: string) => {
    try {
      const result = await empresasApi.createPortalLink(empresaId);
      window.open(result.portal_url, "_blank");
    } catch {
      toast.error("Error al abrir el portal de pago");
    }
  };

  // ── Render ──────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Empresas</h1>
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-border">
            <button
              type="button"
              className={`px-3 py-1.5 text-sm ${view === "grid" ? "bg-accent text-accent-foreground" : "text-muted-foreground"}`}
              onClick={() => {
                setView("grid");
                if (typeof window !== "undefined") {
                  const url = new URL(window.location.href);
                  url.searchParams.delete("view");
                  window.history.replaceState({}, "", url);
                }
              }}
            >
              Tarjetas
            </button>
            <button
              type="button"
              className={`px-3 py-1.5 text-sm ${view === "kanban" ? "bg-accent text-accent-foreground" : "text-muted-foreground"}`}
              onClick={() => {
                setView("kanban");
                if (typeof window !== "undefined") {
                  const url = new URL(window.location.href);
                  url.searchParams.set("view", "kanban");
                  window.history.replaceState({}, "", url);
                }
              }}
            >
              Pipeline
            </button>
          </div>
          <Button onClick={openCreateEmpresa}>
            <Plus className="mr-2 h-4 w-4" />
            Nueva Empresa
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Buscar empresa..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Kanban or cards grid */}
      {loading ? (
        <div className="py-12 text-center text-muted-foreground">Cargando...</div>
      ) : empresas.length === 0 ? (
        <div className="py-12 text-center text-muted-foreground">
          {search ? "No se encontraron empresas" : "No hay empresas aún. Crea la primera."}
        </div>
      ) : view === "kanban" ? (
        <EmpresasKanban
          empresas={empresas}
          onChanged={loadEmpresas}
          onCardClick={(emp) => openEditEmpresa(empresas.find((e) => e.id === emp.id) ?? emp)}
          stageFilter={stageFilter}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {empresas.map((emp) => {
            const statusCfg = STATUS_CONFIG[emp.status] || STATUS_CONFIG.operativo;
            const ballCfg = emp.ball_on ? BALL_ON_CONFIG[emp.ball_on] : null;
            const paymentStatus = getPaymentStatus(emp.last_paid_date, emp.payment_day);
            const paymentCfg = paymentStatus ? PAYMENT_STATUS_CONFIG[paymentStatus] : null;
            const isExpanded = expandedItems.has(emp.id);
            const visibleItems = isExpanded ? emp.pending_items : emp.pending_items.slice(0, 3);
            const overflowCount = emp.pending_items.length - 3;

            return (
              <div
                key={emp.id}
                className="rounded-xl border bg-card shadow-sm flex flex-col overflow-hidden"
              >
                {/* Status banner at top — with channel-health dot */}
                <div
                  className={`relative flex items-center justify-center gap-2 px-4 py-1.5 ${statusCfg.className}`}
                >
                  <span className="text-[11px] font-semibold">{statusCfg.label}</span>
                  {ballCfg && (
                    <span className="inline-flex items-center gap-0.5 text-[11px] opacity-80">
                      · <ballCfg.icon className="h-3 w-3" /> {ballCfg.label}
                    </span>
                  )}
                  {/* Channel-health status dot (silent-channel-health plan) */}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      void openHealthModal(emp);
                    }}
                    title={formatHealthTooltip(emp)}
                    aria-label={formatHealthTooltip(emp)}
                    data-testid={`empresa-health-dot-${emp.id}`}
                    data-status={emp.health.status}
                    className="absolute right-2 top-1/2 -translate-y-1/2 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full ring-1 ring-white/30 hover:ring-white/60 transition-shadow focus:outline-none focus:ring-2 focus:ring-white/80"
                  >
                    <span
                      className={`block h-2.5 w-2.5 rounded-full ${HEALTH_DOT_CLASS[emp.health.status]}`}
                    />
                  </button>
                </div>

                {/* Logo + name + linked-account line */}
                <div className="flex flex-col items-center gap-2 px-5 pt-5 pb-3">
                  <LogoAvatar url={emp.logo_url} name={emp.name} />
                  <h3 className="font-semibold text-lg truncate max-w-[220px] text-center">
                    {emp.name}
                  </h3>
                  {/* Linked Eva account line — shows the account name when
                      linked, or "Sin vincular" italics when not. Click to
                      open the edit modal pre-focused on the dropdown. */}
                  {emp.health.linked_account_name ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        void openEditEmpresa(emp);
                      }}
                      data-testid={`empresa-eva-account-${emp.id}`}
                      className="text-[11px] text-muted-foreground hover:text-foreground transition-colors truncate max-w-[220px]"
                      title={`Vinculada a la cuenta de Eva: ${emp.health.linked_account_name} (clic para editar)`}
                    >
                      Eva: <span className="font-medium">{emp.health.linked_account_name}</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        void openEditEmpresa(emp);
                      }}
                      data-testid={`empresa-eva-account-${emp.id}`}
                      className="text-[11px] text-muted-foreground/60 italic hover:text-foreground transition-colors"
                      title="Esta empresa no está vinculada a una cuenta de Eva (clic para editar)"
                    >
                      Sin vincular a Eva
                    </button>
                  )}
                </div>

                {/* Subscription status badge */}
                {emp.subscription_status && (
                  <div className="flex justify-center px-5 pb-1">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                        emp.subscription_status === "active"
                          ? "bg-green-100 text-green-700"
                          : emp.subscription_status === "past_due"
                          ? "bg-red-100 text-red-700"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {emp.subscription_status === "active"
                        ? "Suscripcion activa"
                        : emp.subscription_status === "past_due"
                        ? "Pago vencido"
                        : emp.subscription_status === "canceled"
                        ? "Cancelada"
                        : emp.subscription_status}
                    </span>
                  </div>
                )}

                {/* Payment line */}
                {emp.monthly_amount != null && (
                  <div className="flex items-center justify-center gap-1.5 text-xs px-5 pb-1">
                    <span className="font-medium">${emp.monthly_amount.toLocaleString("es-MX")}/mes</span>
                    {emp.status === "en_implementacion" ? (
                      <>
                        <span className="text-muted-foreground">·</span>
                        <span className="text-muted-foreground italic">Pago estimado</span>
                      </>
                    ) : (
                      <>
                        {paymentCfg && (
                          <>
                            <span className="text-muted-foreground">·</span>
                            <span className={`font-medium ${paymentCfg.className}`}>{paymentCfg.label}</span>
                          </>
                        )}
                        {emp.payment_day && (
                          <>
                            <span className="text-muted-foreground">·</span>
                            <span className="text-muted-foreground">Día {emp.payment_day}</span>
                          </>
                        )}
                      </>
                    )}
                  </div>
                )}

                {/* Channel-health badges row (silent-channel-health follow-up).
                    Renders Messenger / Instagram / WhatsApp badges only when the
                    empresa is linked to an Eva account that actually has channels
                    of that type. Each badge shows a count (e.g. "Instagram · 2")
                    when the linked account has multiple channels of the same type.
                    Click opens the same health modal as the dot. */}
                {emp.health.linked_account_name &&
                  (emp.health.messenger.present ||
                    emp.health.instagram.present ||
                    emp.health.whatsapp.present) && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        void openHealthModal(emp);
                      }}
                      data-testid={`empresa-channel-badges-${emp.id}`}
                      className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-[11px] px-5 pb-2 hover:opacity-80 transition-opacity"
                      title="Ver detalle de canales"
                    >
                      {emp.health.messenger.present && (
                        <ChannelBadge
                          icon={MessageCircle}
                          label="Messenger"
                          healthy={emp.health.messenger.healthy}
                          count={emp.health.messenger.count}
                          testId={`empresa-msg-badge-${emp.id}`}
                        />
                      )}
                      {emp.health.instagram.present && (
                        <ChannelBadge
                          icon={Instagram}
                          label="Instagram"
                          healthy={emp.health.instagram.healthy}
                          count={emp.health.instagram.count}
                          testId={`empresa-ig-badge-${emp.id}`}
                        />
                      )}
                      {emp.health.whatsapp.present && (
                        <ChannelBadge
                          icon={Phone}
                          label="WhatsApp"
                          healthy={emp.health.whatsapp.healthy}
                          count={emp.health.whatsapp.count}
                          testId={`empresa-wa-badge-${emp.id}`}
                        />
                      )}
                    </button>
                  )}

                {/* Summary note */}
                {emp.summary_note && (
                  <p className="px-5 pb-2 text-xs text-muted-foreground italic text-center">
                    {emp.summary_note}
                  </p>
                )}

                {/* Pending items */}
                <div className="px-4 pt-3 pb-2 flex-1 space-y-1">
                  {emp.pending_count === 0 ? (
                    <p className="text-xs text-muted-foreground text-center py-2">Sin pendientes</p>
                  ) : (
                    <>
                      {visibleItems.map((item) => (
                        <label
                          key={item.id}
                          className="flex items-start gap-2 group cursor-pointer rounded px-1.5 py-1 hover:bg-muted/50 transition-colors"
                        >
                          <button
                            type="button"
                            disabled={togglingItems.has(item.id)}
                            onClick={() => toggleItem(item.id, emp.id)}
                            className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border border-muted-foreground/30 transition-colors hover:border-foreground hover:bg-muted disabled:opacity-50"
                          >
                            {togglingItems.has(item.id) && (
                              <Check className="h-3 w-3 text-muted-foreground animate-pulse" />
                            )}
                          </button>
                          <span className="text-xs leading-tight truncate">{item.title}</span>
                        </label>
                      ))}
                      {!isExpanded && overflowCount > 0 && (
                        <button
                          onClick={() => setExpandedItems((prev) => new Set(prev).add(emp.id))}
                          className="text-[11px] text-muted-foreground hover:text-foreground transition-colors pl-1.5 pt-0.5"
                        >
                          +{overflowCount} más
                        </button>
                      )}
                      {isExpanded && overflowCount > 0 && (
                        <button
                          onClick={() => {
                            setExpandedItems((prev) => {
                              const next = new Set(prev);
                              next.delete(emp.id);
                              return next;
                            });
                          }}
                          className="text-[11px] text-muted-foreground hover:text-foreground transition-colors pl-1.5 pt-0.5"
                        >
                          Mostrar menos
                        </button>
                      )}
                    </>
                  )}
                </div>

                {/* Inline add item */}
                {addingItemFor === emp.id ? (
                  <div className="px-4 pb-2">
                    <div className="flex gap-1.5">
                      <Input
                        ref={addItemInputRef}
                        value={newItemTitle}
                        onChange={(e) => setNewItemTitle(e.target.value)}
                        placeholder="Nuevo pendiente..."
                        className="h-7 text-xs"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") addItem(emp.id);
                          if (e.key === "Escape") setAddingItemFor(null);
                        }}
                      />
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 shrink-0"
                        onClick={() => addItem(emp.id)}
                      >
                        <Check className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 shrink-0"
                        onClick={() => setAddingItemFor(null)}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                ) : null}

                {/* Footer: add + menu */}
                <div className="border-t px-3 py-2 flex items-center justify-between">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-xs text-muted-foreground"
                    onClick={() => startAddingItem(emp.id)}
                  >
                    <Plus className="mr-1 h-3 w-3" />
                    Agregar
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-7 w-7">
                        <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEditEmpresa(emp)}>
                        Editar empresa
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => openHistory(emp.id, emp.name)}>
                        Historial
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => setCheckoutEmpresa(emp)}>
                        Crear link de cobro
                      </DropdownMenuItem>
                      {emp.subscription_status === "active" && (
                        <DropdownMenuItem onClick={() => openPortal(emp.id)}>
                          Portal de pago
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => deleteEmpresa(emp.id)}
                      >
                        Eliminar empresa
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Empresa Modal ──────────────────────────────────────────── */}
      <Dialog open={empresaModalOpen} onOpenChange={setEmpresaModalOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingEmpresaId ? "Editar Empresa" : "Nueva Empresa"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {/* Name */}
            <div>
              <label className="text-sm font-medium">Nombre *</label>
              <Input
                value={empresaForm.name}
                onChange={(e) => setEmpresaForm({ ...empresaForm, name: e.target.value })}
                placeholder="Nombre de la empresa"
              />
            </div>

            {/* Logo */}
            <div>
              <label className="text-sm font-medium">Logo</label>
              <LogoPicker
                value={empresaForm.logo_url ?? null}
                onChange={(url) => setEmpresaForm({ ...empresaForm, logo_url: url })}
              />
            </div>

            {/* Status + Ball */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">Status</label>
                <Select
                  value={empresaForm.status || "operativo"}
                  onValueChange={(v) => setEmpresaForm({ ...empresaForm, status: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="operativo">Operativo</SelectItem>
                    <SelectItem value="en_implementacion">En implementación</SelectItem>
                    <SelectItem value="requiere_atencion">Requiere atención</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium">Responsable</label>
                <Select
                  value={empresaForm.ball_on || "_none"}
                  onValueChange={(v) => setEmpresaForm({ ...empresaForm, ball_on: v === "_none" ? null : v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_none">Sin asignar</SelectItem>
                    <SelectItem value="nosotros">← Nosotros</SelectItem>
                    <SelectItem value="cliente">→ Cliente</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Linked Eva Account (silent-channel-health plan) */}
            <div>
              <label className="text-sm font-medium">Cuenta de Eva vinculada</label>
              <Select
                value={empresaForm.eva_account_id ?? "_none"}
                onValueChange={(v) =>
                  setEmpresaForm({
                    ...empresaForm,
                    eva_account_id: v === "_none" ? null : v,
                  })
                }
              >
                <SelectTrigger data-testid="empresa-eva-account-select">
                  <SelectValue
                    placeholder={
                      loadingEvaAccounts ? "Cargando cuentas..." : "Sin vincular"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_none">Sin vincular</SelectItem>
                  {evaAccounts.map((acc) => (
                    <SelectItem key={acc.id} value={acc.id}>
                      {acc.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground mt-1">
                Vincula esta empresa con su cuenta correspondiente en Eva para
                ver el estado de los canales en tiempo real.
              </p>
            </div>

            {/* Summary note */}
            <div>
              <label className="text-sm font-medium">Nota de seguimiento</label>
              <Textarea
                value={empresaForm.summary_note ?? ""}
                onChange={(e) =>
                  setEmpresaForm({ ...empresaForm, summary_note: e.target.value || null })
                }
                placeholder="Resumen del estado actual..."
                rows={2}
              />
            </div>

            {/* Payment */}
            <div className={`grid gap-3 ${empresaForm.status === "en_implementacion" ? "grid-cols-1" : "grid-cols-3"}`}>
              <div>
                <label className="text-sm font-medium">
                  {empresaForm.status === "en_implementacion" ? "Monto estimado" : "Monto base (antes de IVA)"}
                </label>
                <Input
                  type="number"
                  value={empresaForm.monthly_amount ?? ""}
                  onChange={(e) =>
                    setEmpresaForm({ ...empresaForm, monthly_amount: e.target.value ? parseFloat(e.target.value) : null })
                  }
                  placeholder="0.00"
                />
              </div>
              {empresaForm.status !== "en_implementacion" && (
              <div>
                <label className="text-sm font-medium">Día de pago</label>
                <Input
                  type="number"
                  min={1}
                  max={31}
                  value={empresaForm.payment_day ?? ""}
                  onChange={(e) =>
                    setEmpresaForm({ ...empresaForm, payment_day: e.target.value ? parseInt(e.target.value) : null })
                  }
                  placeholder="1-31"
                />
              </div>
              )}
              {empresaForm.status !== "en_implementacion" && (
              <div>
                <label className="text-sm font-medium">Último pago</label>
                <Input
                  type="date"
                  value={empresaForm.last_paid_date ?? ""}
                  onChange={(e) =>
                    setEmpresaForm({ ...empresaForm, last_paid_date: e.target.value || null })
                  }
                />
              </div>
              )}
            </div>

            {/* Separator */}
            <div className="border-t pt-3">
              <button
                type="button"
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors w-full"
                onClick={(e) => {
                  const target = e.currentTarget.nextElementSibling;
                  if (target) target.classList.toggle("hidden");
                  const chevron = e.currentTarget.querySelector("svg");
                  if (chevron) chevron.classList.toggle("rotate-180");
                }}
              >
                <ChevronDown className="h-3 w-3 transition-transform" />
                Datos fiscales y contacto
              </button>
              <div className="hidden mt-3 space-y-3">
                {/* Constancia drag-and-drop upload */}
                <div
                  className={`relative rounded-lg border-2 border-dashed p-4 text-center transition-colors ${
                    extractingConstancia
                      ? "border-primary/50 bg-primary/5"
                      : "border-muted-foreground/25 hover:border-primary/50 hover:bg-accent/50"
                  }`}
                  onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("border-primary", "bg-primary/5"); }}
                  onDragLeave={(e) => { e.currentTarget.classList.remove("border-primary", "bg-primary/5"); }}
                  onDrop={async (e) => {
                    e.preventDefault();
                    e.currentTarget.classList.remove("border-primary", "bg-primary/5");
                    const file = e.dataTransfer.files?.[0];
                    if (!file || !editingEmpresaId || extractingConstancia) return;
                    setExtractingConstancia(true);
                    try {
                      const result = await empresasApi.extractConstancia(editingEmpresaId, file);
                      const ext = result.extracted;
                      setEmpresaForm((prev) => ({
                        ...prev,
                        rfc: ext.rfc || prev.rfc,
                        razon_social: ext.legal_name || prev.razon_social,
                        regimen_fiscal: ext.tax_regime || prev.regimen_fiscal,
                        fiscal_postal_code: ext.postal_code || prev.fiscal_postal_code,
                        person_type: ext.person_type || prev.person_type,
                      }));
                      if (result.warnings.length > 0) {
                        toast.warning(result.warnings.join(". "));
                      } else {
                        toast.success("Datos fiscales extraidos de la constancia");
                      }
                    } catch {
                      toast.error("Error al extraer datos de la constancia");
                    } finally {
                      setExtractingConstancia(false);
                    }
                  }}
                >
                  <input
                    type="file"
                    accept=".pdf,image/png,image/jpeg,image/webp"
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    disabled={extractingConstancia || !editingEmpresaId}
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file || !editingEmpresaId) return;
                      setExtractingConstancia(true);
                      try {
                        const result = await empresasApi.extractConstancia(editingEmpresaId, file);
                        const ext = result.extracted;
                        setEmpresaForm((prev) => ({
                          ...prev,
                          rfc: ext.rfc || prev.rfc,
                          razon_social: ext.legal_name || prev.razon_social,
                          regimen_fiscal: ext.tax_regime || prev.regimen_fiscal,
                          fiscal_postal_code: ext.postal_code || prev.fiscal_postal_code,
                          person_type: ext.person_type || prev.person_type,
                        }));
                        if (result.warnings.length > 0) {
                          toast.warning(result.warnings.join(". "));
                        } else {
                          toast.success("Datos fiscales extraidos de la constancia");
                        }
                      } catch {
                        toast.error("Error al extraer datos de la constancia");
                      } finally {
                        setExtractingConstancia(false);
                        e.target.value = "";
                      }
                    }}
                  />
                  <div className="pointer-events-none space-y-1">
                    <p className="text-sm font-medium">
                      {extractingConstancia ? "Extrayendo datos fiscales..." : "Arrastra tu constancia aqui"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {extractingConstancia
                        ? "Analizando documento con IA..."
                        : "o haz clic para seleccionar archivo (PDF o imagen)"}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-medium">RFC</label>
                    <Input
                      value={empresaForm.rfc ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, rfc: e.target.value || null })
                      }
                      maxLength={13}
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Razon Social</label>
                    <Input
                      value={empresaForm.razon_social ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, razon_social: e.target.value || null })
                      }
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Regimen Fiscal</label>
                    <Input
                      value={empresaForm.regimen_fiscal ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, regimen_fiscal: e.target.value || null })
                      }
                      placeholder="601"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">CP Fiscal</label>
                    <Input
                      value={empresaForm.fiscal_postal_code ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, fiscal_postal_code: e.target.value || null })
                      }
                      maxLength={5}
                      placeholder="11560"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Uso CFDI</label>
                    <Input
                      value={empresaForm.cfdi_use ?? "G03"}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, cfdi_use: e.target.value || null })
                      }
                      placeholder="G03"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Tipo de persona</label>
                    <select
                      className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                      value={empresaForm.person_type ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, person_type: e.target.value || null })
                      }
                    >
                      <option value="">Sin definir</option>
                      <option value="persona_moral">Persona Moral</option>
                      <option value="persona_fisica">Persona Fisica</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-medium">Email</label>
                    <Input
                      value={empresaForm.email ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, email: e.target.value || null })
                      }
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Telefono</label>
                    <Input
                      value={empresaForm.phone ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, phone: e.target.value || null })
                      }
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Industria</label>
                    <Input
                      value={empresaForm.industry ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, industry: e.target.value || null })
                      }
                    />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">Direccion</label>
                  <Textarea
                    value={empresaForm.address ?? ""}
                    onChange={(e) =>
                      setEmpresaForm({ ...empresaForm, address: e.target.value || null })
                    }
                    rows={2}
                  />
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setEmpresaModalOpen(false)}>
                Cancelar
              </Button>
              <Button onClick={saveEmpresa}>Guardar</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── History Modal ──────────────────────────────────────────── */}
      <Dialog open={historyModalOpen} onOpenChange={setHistoryModalOpen}>
        <DialogContent className="max-w-md max-h-[70vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Historial — {historyEmpresaName}</DialogTitle>
          </DialogHeader>
          {historyLoading ? (
            <p className="text-sm text-muted-foreground py-4 text-center">Cargando...</p>
          ) : historyEntries.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">Sin cambios registrados</p>
          ) : (
            <div className="space-y-3">
              {historyEntries.map((entry) => (
                <div key={entry.id} className="border-l-2 border-muted pl-3 py-1">
                  <p className="text-sm">
                    <span className="font-medium">{FIELD_LABELS[entry.field_changed] || entry.field_changed}</span>
                    {" cambiado de "}
                    <span className="text-muted-foreground">
                      {entry.old_value ? (VALUE_LABELS[entry.old_value] || entry.old_value) : "vacío"}
                    </span>
                    {" a "}
                    <span className="font-medium">
                      {entry.new_value ? (VALUE_LABELS[entry.new_value] || entry.new_value) : "vacío"}
                    </span>
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {entry.changed_by_name || "Sistema"} · {formatRelativeTime(entry.changed_at)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Channel Health Modal (silent-channel-health plan) ───────── */}
      <Dialog open={healthModalOpen} onOpenChange={setHealthModalOpen}>
        <DialogContent
          className="max-w-lg max-h-[80vh] overflow-y-auto"
          data-testid="empresa-health-modal"
        >
          <DialogHeader>
            <DialogTitle>
              Estado de canales — {healthModalEmpresa?.name ?? ""}
            </DialogTitle>
          </DialogHeader>

          {healthModalEmpresa?.health.status === "not_linked" || !healthModalEmpresa?.eva_account_id ? (
            <div className="space-y-3 py-2">
              <p className="text-sm text-muted-foreground">
                Esta empresa no está vinculada a una cuenta de Eva. Edita la
                empresa para vincularla y poder ver el estado de sus canales.
              </p>
              <Button
                size="sm"
                onClick={() => {
                  setHealthModalOpen(false);
                  if (healthModalEmpresa) {
                    void openEditEmpresa(healthModalEmpresa);
                  }
                }}
              >
                Editar empresa
              </Button>
            </div>
          ) : healthModalLoading ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              Cargando...
            </p>
          ) : !healthModalData ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No se pudo cargar el estado de los canales.
            </p>
          ) : healthModalData.messenger.length === 0 &&
            healthModalData.instagram.length === 0 &&
            healthModalData.whatsapp.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              Esta cuenta de Eva no tiene canales activos configurados.
            </p>
          ) : (
            <div className="space-y-4 py-2">
              {[
                ...healthModalData.messenger,
                ...healthModalData.instagram,
                ...healthModalData.whatsapp,
              ].map((ch) => (
                <div
                  key={ch.id}
                  className="border rounded-lg p-3 space-y-1"
                  data-testid={`channel-row-${ch.id}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className={`inline-block h-2.5 w-2.5 rounded-full ${
                          ch.is_healthy ? "bg-emerald-500" : "bg-red-500"
                        }`}
                      />
                      <span className="font-medium text-sm truncate">
                        {ch.display_name ?? "(sin nombre)"}
                      </span>
                      <span className="text-[11px] uppercase text-muted-foreground">
                        {ch.channel_type}
                      </span>
                    </div>
                    <span
                      className={`text-[11px] font-semibold px-2 py-0.5 rounded ${
                        ch.is_healthy
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {ch.is_healthy ? "Operando" : "Desconectado"}
                    </span>
                  </div>
                  {!ch.is_healthy && ch.health_status_reason && (
                    <p
                      className="text-xs text-muted-foreground italic"
                      title={ch.health_status_reason}
                    >
                      {ch.health_status_reason.length > 200
                        ? `${ch.health_status_reason.slice(0, 200)}...`
                        : ch.health_status_reason}
                    </p>
                  )}
                  <p className="text-[11px] text-muted-foreground">
                    Verificado: {formatRelativeTimeSpanish(ch.last_status_check)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Checkout link modal */}
      {checkoutEmpresa && (
        <CheckoutLinkModal
          empresa={checkoutEmpresa}
          open={!!checkoutEmpresa}
          onClose={() => setCheckoutEmpresa(null)}
        />
      )}
    </div>
  );
}

// ── Helper Components ──────────────────────────────────────────────

interface ChannelBadgeProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  healthy: boolean;
  count: number;
  testId: string;
}

function ChannelBadge({ icon: Icon, label, healthy, count, testId }: ChannelBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 ${
        healthy ? "text-emerald-600" : "text-red-600"
      }`}
      data-testid={testId}
      data-healthy={healthy}
      data-count={count}
    >
      <Icon className="h-3 w-3" />
      {label}
      {count > 1 && (
        <span className="text-muted-foreground">· {count}</span>
      )}
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          healthy ? "bg-emerald-500" : "bg-red-500"
        }`}
      />
    </span>
  );
}

function LogoAvatar({ url, name, size = "lg" }: { url: string | null; name: string; size?: "lg" | "sm" }) {
  const [failed, setFailed] = useState(false);
  const prevUrl = useRef(url);
  if (prevUrl.current !== url) {
    prevUrl.current = url;
    setFailed(false);
  }

  const dim = size === "lg" ? "h-20 w-20" : "h-10 w-10";
  const iconDim = size === "lg" ? "h-9 w-9" : "h-5 w-5";
  const radius = size === "lg" ? "rounded-2xl" : "rounded-xl";

  if (url && !failed) {
    return (
      <div className={`flex ${dim} items-center justify-center ${radius} bg-white shadow-sm p-1.5`}>
        <img
          src={url}
          alt={name}
          className="h-full w-full object-contain"
          onError={() => setFailed(true)}
        />
      </div>
    );
  }

  return (
    <div className={`flex ${dim} items-center justify-center ${radius} bg-muted shadow-sm`}>
      <Building2 className={`${iconDim} text-muted-foreground`} />
    </div>
  );
}

function LogoPicker({ value, onChange }: { value: string | null; onChange: (url: string | null) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 500_000) {
      alert("La imagen debe pesar menos de 500 KB");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      onChange(reader.result as string);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  return (
    <div className="flex items-center gap-3 mt-1">
      <LogoAvatar url={value} name="" size="sm" />
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-8 text-xs"
        onClick={() => inputRef.current?.click()}
      >
        <ImagePlus className="mr-1.5 h-3.5 w-3.5" />
        {value ? "Cambiar" : "Seleccionar imagen"}
      </Button>
      {value && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => onChange(null)}
        >
          <X className="h-3.5 w-3.5 text-muted-foreground" />
        </Button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFile}
      />
    </div>
  );
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "ahora";
  if (diffMin < 60) return `hace ${diffMin} min`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `hace ${diffHrs}h`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays === 1) return "ayer";
  if (diffDays < 30) return `hace ${diffDays} días`;
  const diffMonths = Math.floor(diffDays / 30);
  return `hace ${diffMonths} ${diffMonths === 1 ? "mes" : "meses"}`;
}
