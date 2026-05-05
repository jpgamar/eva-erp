"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CalendarDays,
  Check,
  ChevronDown,
  Copy,
  CreditCard,
  ExternalLink,
  ImagePlus,
  Instagram,
  Mail,
  MessageCircle,
  MoreHorizontal,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Trash2,
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
  type EmpresaCreate,
  type EmpresaHealthStatus,
  type EmpresaHistory,
  type EmpresaInteraction,
  type EmpresaCalendarItem,
  type EmpresaListItem,
  type EvaAccountForLink,
} from "@/lib/api/empresas";
import { CheckoutLinkModal } from "@/components/empresas/CheckoutLinkModal";
import { EmpresasKanban } from "@/components/empresas/EmpresasKanban";
import { evaPlatformApi } from "@/lib/api/eva-platform";
import type {
  AccountDraft,
  AccountOnboarding,
  AccountPricing,
  EvaAccount,
  EvaBillingAdminStatus,
  EvaBillingDocument,
} from "@/types";

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

const MAX_BILLING_RECIPIENTS = 5;

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

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
  billing_recipient_emails: [],
};

const DEFAULT_ACCOUNT_TYPE = "COMMERCE";
const DEFAULT_PLAN_TIER = "starter";
const DEFAULT_BILLING_CYCLE = "monthly";

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

function formatDueLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("es-MX", { month: "short", day: "numeric" });
}

function monthBounds(month: Date): { start: string; end: string } {
  const start = new Date(month.getFullYear(), month.getMonth(), 1);
  const end = new Date(month.getFullYear(), month.getMonth() + 1, 0);
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  };
}

// ── Billing recipients chip input ──────────────────────────────────

function BillingRecipientsInput({
  emails,
  onChange,
}: {
  emails: string[];
  onChange: (next: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  const tryAdd = (raw: string): boolean => {
    const cleaned = raw.trim().toLowerCase();
    if (!cleaned) return false;
    if (!EMAIL_REGEX.test(cleaned)) {
      toast.error("Correo inválido");
      return false;
    }
    if (emails.some((e) => e.toLowerCase() === cleaned)) {
      toast.error("Ese correo ya está en la lista");
      return false;
    }
    if (emails.length >= MAX_BILLING_RECIPIENTS) {
      toast.error(`Máximo ${MAX_BILLING_RECIPIENTS} correos`);
      return false;
    }
    onChange([...emails, cleaned]);
    return true;
  };

  const commit = () => {
    if (tryAdd(draft)) setDraft("");
  };

  const makePrimary = (idx: number) => {
    if (idx <= 0 || idx >= emails.length) return;
    const next = [...emails];
    const [picked] = next.splice(idx, 1);
    next.unshift(picked);
    onChange(next);
  };

  const remove = (idx: number) => {
    const next = emails.filter((_, i) => i !== idx);
    onChange(next);
  };

  return (
    <div className="rounded-md border border-input bg-transparent px-2 py-1.5">
      <div className="flex flex-wrap gap-1.5">
        {emails.map((email, idx) => {
          const isPrimary = idx === 0;
          return (
            <span
              key={`${email}-${idx}`}
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
                isPrimary
                  ? "bg-primary/10 text-primary ring-1 ring-primary/30"
                  : "bg-muted text-foreground"
              }`}
            >
              {isPrimary && <span className="text-[10px] font-semibold uppercase tracking-wide">Principal</span>}
              <span className="break-all">{email}</span>
              {!isPrimary && (
                <button
                  type="button"
                  onClick={() => makePrimary(idx)}
                  className="text-[10px] text-muted-foreground hover:text-primary"
                  title="Hacer principal"
                >
                  ★
                </button>
              )}
              <button
                type="button"
                onClick={() => remove(idx)}
                className="text-muted-foreground hover:text-red-600"
                title="Quitar"
                aria-label="Quitar correo"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          );
        })}
        <input
          type="email"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === "," || e.key === " ") {
              e.preventDefault();
              commit();
            } else if (e.key === "Backspace" && !draft && emails.length > 0) {
              remove(emails.length - 1);
            }
          }}
          onBlur={() => {
            if (draft.trim()) commit();
          }}
          placeholder={emails.length === 0 ? "correo@ejemplo.com" : "Añadir otro…"}
          className="flex-1 min-w-[160px] bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────

export default function EmpresasPage() {
  const [empresas, setEmpresas] = useState<EmpresaListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"grid" | "kanban" | "calendar" | "accounts">(() => {
    if (typeof window === "undefined") return "grid";
    const url = new URL(window.location.href);
    const viewParam = url.searchParams.get("view");
    return viewParam === "kanban" || viewParam === "calendar" || viewParam === "accounts" ? viewParam : "grid";
  });
  const stageFilter = (() => {
    if (typeof window === "undefined") return null;
    return new URL(window.location.href).searchParams.get("stage");
  })();

  // Empresa modal
  const [empresaModalOpen, setEmpresaModalOpen] = useState(false);
  const [empresaForm, setEmpresaForm] = useState<EmpresaCreate>(EMPTY_EMPRESA);
  const [editingEmpresaId, setEditingEmpresaId] = useState<string | null>(null);
  const [editingEmpresaVersion, setEditingEmpresaVersion] = useState<number>(0);
  const [extractingConstancia, setExtractingConstancia] = useState(false);
  const [creatingEvaAccount, setCreatingEvaAccount] = useState(false);

  // History modal
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [historyEmpresaName, setHistoryEmpresaName] = useState("");
  const [historyEntries, setHistoryEntries] = useState<EmpresaHistory[]>([]);
  const [interactionEntries, setInteractionEntries] = useState<EmpresaInteraction[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Checkout modal
  const [checkoutEmpresa, setCheckoutEmpresa] = useState<EmpresaListItem | null>(null);

  // Inline add item
  const [addingItemFor, setAddingItemFor] = useState<string | null>(null);
  const [newItemTitle, setNewItemTitle] = useState("");
  const [newItemDueAt, setNewItemDueAt] = useState("");
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
  const [calendarMonth, setCalendarMonth] = useState(() => new Date());
  const [calendarItems, setCalendarItems] = useState<EmpresaCalendarItem[]>([]);
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [accounts, setAccounts] = useState<EvaAccount[]>([]);
  const [accountDrafts, setAccountDrafts] = useState<AccountDraft[]>([]);
  const [accountPricing, setAccountPricing] = useState<AccountPricing[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(false);
  const [approvingDrafts, setApprovingDrafts] = useState<Set<string>>(new Set());
  const [accountOnboarding, setAccountOnboarding] = useState<Record<string, AccountOnboarding>>({});
  const [billingByAccount, setBillingByAccount] = useState<Record<string, EvaBillingAdminStatus>>({});
  const [checkoutLinkByAccount, setCheckoutLinkByAccount] = useState<Record<string, string>>({});
  const [accountActionLoading, setAccountActionLoading] = useState<string | null>(null);

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

  useEffect(() => {
    if (view !== "calendar") return;
    const loadCalendar = async () => {
      setCalendarLoading(true);
      try {
        const bounds = monthBounds(calendarMonth);
        const data = await empresasApi.calendar(bounds);
        setCalendarItems(data);
      } catch {
        toast.error("Error al cargar calendario");
      } finally {
        setCalendarLoading(false);
      }
    };
    void loadCalendar();
  }, [view, calendarMonth]);

  const loadAccountAdmin = async () => {
    setAccountsLoading(true);
    try {
      const [activeAccounts, inactiveAccounts, drafts, pricing] = await Promise.all([
        evaPlatformApi.listAccounts({ search: search || undefined }),
        evaPlatformApi.listAccounts({ search: search || undefined }).then((items) => items.filter((account) => !account.is_active)),
        evaPlatformApi.listDrafts(),
        evaPlatformApi.listAccountPricing(),
      ]);
      const byId = new Map<string, EvaAccount>();
      [...activeAccounts, ...inactiveAccounts].forEach((account) => byId.set(account.id, account));
      setAccounts([...byId.values()]);
      setAccountDrafts(drafts);
      setAccountPricing(pricing);
    } catch {
      toast.error("Error al cargar cuentas de Eva");
    } finally {
      setAccountsLoading(false);
    }
  };

  useEffect(() => {
    if (view !== "accounts") return;
    void loadAccountAdmin();
  }, [view, search]);

  const runAccountAction = async (key: string, action: () => Promise<void>) => {
    setAccountActionLoading(key);
    try {
      await action();
      await loadAccountAdmin();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message ?? err?.message ?? "Error en cuentas de Eva");
    } finally {
      setAccountActionLoading(null);
    }
  };

  const createAccountFromAccountsTab = async () => {
    const name = window.prompt("Nombre de la cuenta Eva");
    if (!name?.trim()) return;
    const ownerEmail = window.prompt("Email del owner");
    if (!ownerEmail?.trim()) return;
    const ownerName = window.prompt("Nombre del owner") ?? name.trim();
    await runAccountAction("create-account", async () => {
      const result = await evaPlatformApi.createAccount({
        name: name.trim(),
        owner_email: ownerEmail.trim().toLowerCase(),
        owner_name: ownerName.trim(),
        account_type: DEFAULT_ACCOUNT_TYPE,
        plan_tier: DEFAULT_PLAN_TIER,
        billing_cycle: DEFAULT_BILLING_CYCLE,
        send_setup_email: true,
      });
      setAccountOnboarding((current) => ({ ...current, [result.account.id]: result.onboarding }));
      toast.success("Cuenta Eva creada");
    });
  };

  const createDraftFromAccountsTab = async () => {
    const name = window.prompt("Nombre del borrador");
    if (!name?.trim()) return;
    const ownerEmail = window.prompt("Email del owner");
    if (!ownerEmail?.trim()) return;
    const ownerName = window.prompt("Nombre del owner") ?? name.trim();
    await runAccountAction("create-draft", async () => {
      await evaPlatformApi.createDraft({
        name: name.trim(),
        owner_email: ownerEmail.trim().toLowerCase(),
        owner_name: ownerName.trim(),
        account_type: DEFAULT_ACCOUNT_TYPE,
        plan_tier: DEFAULT_PLAN_TIER,
        billing_cycle: DEFAULT_BILLING_CYCLE,
      });
      toast.success("Borrador creado");
    });
  };

  const updateDraftFromAccountsTab = async (draft: AccountDraft) => {
    const notes = window.prompt("Notas del borrador", draft.notes ?? "");
    if (notes == null) return;
    await runAccountAction(`draft-${draft.id}`, async () => {
      await evaPlatformApi.updateDraft(draft.id, { notes });
      toast.success("Borrador actualizado");
    });
  };

  const deleteDraftFromAccountsTab = async (draft: AccountDraft) => {
    if (!window.confirm(`Eliminar borrador ${draft.name}?`)) return;
    await runAccountAction(`draft-${draft.id}`, async () => {
      await evaPlatformApi.deleteDraft(draft.id);
      toast.success("Borrador eliminado");
    });
  };

  const updatePricingFromAccountsTab = async (accountId: string) => {
    const current = accountPricing.find((item) => item.account_id === accountId);
    const amount = window.prompt("Monto de facturación", current?.billing_amount?.toString() ?? "");
    if (amount == null) return;
    const parsed = amount.trim() ? Number(amount) : null;
    if (parsed != null && Number.isNaN(parsed)) {
      toast.error("Monto inválido");
      return;
    }
    await runAccountAction(`pricing-${accountId}`, async () => {
      await evaPlatformApi.updateAccountPricing(accountId, {
        billing_amount: parsed,
        billing_currency: current?.billing_currency ?? "MXN",
        billing_interval: current?.billing_interval ?? "MONTHLY",
        is_billable: current?.is_billable ?? true,
      });
      toast.success("Pricing actualizado");
    });
  };

  const openImpersonation = async (account: EvaAccount) => {
    await runAccountAction(`impersonate-${account.id}`, async () => {
      const result = await evaPlatformApi.impersonateAccount(account.id);
      window.open(result.magic_link_url, "_blank", "noopener,noreferrer");
    });
  };

  const resendOnboarding = async (account: EvaAccount) => {
    await runAccountAction(`onboarding-${account.id}`, async () => {
      const onboarding = await evaPlatformApi.resendAccountOnboarding(account.id, { send_setup_email: true });
      setAccountOnboarding((current) => ({ ...current, [account.id]: onboarding }));
      toast.success("Onboarding reenviado");
    });
  };

  const loadBillingStatus = async (account: EvaAccount) => {
    await runAccountAction(`billing-${account.id}`, async () => {
      const billing = await evaPlatformApi.getAccountBillingStatus(account.id);
      setBillingByAccount((current) => ({ ...current, [account.id]: billing }));
    });
  };

  const createCheckoutLink = async (account: EvaAccount) => {
    await runAccountAction(`checkout-${account.id}`, async () => {
      const result = await evaPlatformApi.createAccountCheckoutLink(account.id, {
        plan_tier: account.plan_tier,
        billing_interval: account.billing_interval,
      });
      setCheckoutLinkByAccount((current) => ({ ...current, [account.id]: result.checkout_url }));
      toast.success("Checkout creado");
    });
  };

  const retryBillingDocument = async (account: EvaAccount, document: EvaBillingDocument) => {
    await runAccountAction(`retry-${document.id}`, async () => {
      await evaPlatformApi.retryAccountBillingDocument(account.id, document.id);
      await loadBillingStatus(account);
    });
  };

  const resendBillingEmail = async (account: EvaAccount, document: EvaBillingDocument) => {
    if (!document.cfdi_uuid) {
      toast.error("La factura no tiene UUID CFDI");
      return;
    }
    await runAccountAction(`invoice-email-${document.id}`, async () => {
      await evaPlatformApi.resendAccountBillingEmail(account.id, { cfdi_uuid: document.cfdi_uuid! });
      await loadBillingStatus(account);
    });
  };

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
    setEditingEmpresaVersion(0);
    setEmpresaModalOpen(true);
    void ensureEvaAccountsLoaded();
  };

  const openEditEmpresa = async (emp: EmpresaListItem) => {
    try {
      const full = await empresasApi.get(emp.id);
      const seededRecipients =
        full.billing_recipient_emails && full.billing_recipient_emails.length > 0
          ? full.billing_recipient_emails
          : full.email
          ? [full.email]
          : [];
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
        lifecycle_stage: full.lifecycle_stage,
        ball_on: full.ball_on,
        summary_note: full.summary_note,
        monthly_amount: full.monthly_amount,
        payment_day: full.payment_day,
        last_paid_date: full.last_paid_date,
        expected_close_date: full.expected_close_date,
        eva_account_id: full.eva_account_id,
        website: full.website,
        contact_name: full.contact_name,
        contact_email: full.contact_email,
        contact_phone: full.contact_phone,
        contact_role: full.contact_role,
        billing_recipient_emails: seededRecipients,
      });
      setEditingEmpresaId(full.id);
      setEditingEmpresaVersion(full.version ?? 0);
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
    const recipients = empresaForm.billing_recipient_emails ?? [];
    const payload: EmpresaCreate = {
      ...empresaForm,
      billing_recipient_emails: recipients,
      // Mirror primary recipient into legacy empresa.email so old code paths
      // (fallback read, historic reports) stay consistent.
      email: recipients[0] ?? empresaForm.email ?? null,
    };
    try {
      if (editingEmpresaId) {
        await empresasApi.update(editingEmpresaId, payload, editingEmpresaVersion);
        toast.success("Empresa actualizada");
      } else {
        await empresasApi.create(payload);
        toast.success("Empresa creada");
      }
      setEmpresaModalOpen(false);
      loadEmpresas();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const reason = detail?.reason;
      const message = detail?.message;
      if (reason === "OptimisticLockMismatch") {
        toast.error("Otra persona cambió esta empresa. Recarga e inténtalo de nuevo.");
      } else if (reason === "OperativoRequiresActiveSubscription") {
        toast.error(
          message ??
            "Para marcar esta empresa como Operativo necesita estar vinculada a una cuenta de Eva con suscripción activa."
        );
      } else if (reason === "ExpectedCloseDateRequired") {
        toast.error(message ?? "Define la fecha de cierre esperada antes de guardar.");
      } else if (reason === "UseSubscriptionApplyEndpoint") {
        toast.error(
          message ??
            "Cambios al monto/intervalo/día de pago en empresas vinculadas se hacen desde el panel de suscripción."
        );
      } else if (reason === "already_linked") {
        toast.error(message ?? "Esa cuenta de Eva ya está vinculada a otra empresa.");
      } else if (reason === "MissingIfMatchHeader") {
        toast.error("Error interno: falta el encabezado de versión. Recarga la página.");
      } else if (typeof detail === "string") {
        toast.error(detail);
      } else if (message) {
        toast.error(message);
      } else {
        toast.error("Error al guardar empresa");
      }
    }
  };

  const createEvaAccountFromEmpresa = async () => {
    if (!editingEmpresaId) return;
    const ownerEmail =
      empresaForm.billing_recipient_emails?.[0] ??
      empresaForm.contact_email ??
      empresaForm.email ??
      "";
    if (!ownerEmail) {
      toast.error("Agrega un correo principal antes de crear la cuenta de Eva");
      return;
    }
    setCreatingEvaAccount(true);
    try {
      await empresasApi.createEvaAccount(editingEmpresaId, {
        owner_email: ownerEmail,
        owner_name: empresaForm.contact_name ?? empresaForm.name,
        account_type: "COMMERCE",
        plan_tier: "STANDARD",
        billing_cycle: (empresaForm.billing_interval ?? "monthly").toUpperCase(),
        send_setup_email: true,
      });
      toast.success("Cuenta de Eva creada y vinculada");
      setEmpresaModalOpen(false);
      loadEmpresas();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message ?? "Error al crear cuenta de Eva");
    } finally {
      setCreatingEvaAccount(false);
    }
  };

  const approveDraftAccount = async (draftId: string) => {
    if (approvingDrafts.has(draftId)) return;
    setApprovingDrafts((prev) => new Set(prev).add(draftId));
    try {
      await evaPlatformApi.approveDraft(draftId);
      toast.success("Cuenta aprobada");
      await loadAccountAdmin();
      loadEmpresas();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message ?? "Error al aprobar cuenta");
    } finally {
      setApprovingDrafts((prev) => {
        const next = new Set(prev);
        next.delete(draftId);
        return next;
      });
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
      await empresasApi.createItem(empresaId, {
        title: newItemTitle.trim(),
        kind: newItemDueAt ? "event" : "todo",
        due_at: newItemDueAt ? new Date(`${newItemDueAt}T09:00:00`).toISOString() : null,
      });
      setNewItemTitle("");
      setNewItemDueAt("");
      setAddingItemFor(null);
      loadEmpresas();
    } catch {
      toast.error("Error al agregar pendiente");
    }
  };

  const startAddingItem = (empresaId: string) => {
    setAddingItemFor(empresaId);
    setNewItemTitle("");
    setNewItemDueAt("");
    setTimeout(() => addItemInputRef.current?.focus(), 50);
  };

  // ── History ─────────────────────────────────────────────────────

  const openHistory = async (empresaId: string, empresaName: string) => {
    setHistoryEmpresaName(empresaName);
    setHistoryEntries([]);
    setInteractionEntries([]);
    setHistoryLoading(true);
    setHistoryModalOpen(true);
    try {
      const [history, interactions] = await Promise.all([
        empresasApi.getHistory(empresaId),
        empresasApi.getInteractions(empresaId),
      ]);
      setHistoryEntries(history);
      setInteractionEntries(interactions);
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
            <button
              type="button"
              className={`px-3 py-1.5 text-sm ${view === "calendar" ? "bg-accent text-accent-foreground" : "text-muted-foreground"}`}
              onClick={() => {
                setView("calendar");
                if (typeof window !== "undefined") {
                  const url = new URL(window.location.href);
                  url.searchParams.set("view", "calendar");
                  window.history.replaceState({}, "", url);
                }
              }}
            >
              Calendario
            </button>
            <button
              type="button"
              className={`px-3 py-1.5 text-sm ${view === "accounts" ? "bg-accent text-accent-foreground" : "text-muted-foreground"}`}
              onClick={() => {
                setView("accounts");
                if (typeof window !== "undefined") {
                  const url = new URL(window.location.href);
                  url.searchParams.set("view", "accounts");
                  window.history.replaceState({}, "", url);
                }
              }}
            >
              Cuentas
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
      {loading && view !== "accounts" ? (
        <div className="py-12 text-center text-muted-foreground">Cargando...</div>
      ) : view === "accounts" ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={createAccountFromAccountsTab} disabled={accountActionLoading === "create-account"}>
              <Plus className="mr-2 h-4 w-4" />
              Cuenta Eva
            </Button>
            <Button size="sm" variant="outline" onClick={createDraftFromAccountsTab} disabled={accountActionLoading === "create-draft"}>
              <Plus className="mr-2 h-4 w-4" />
              Borrador
            </Button>
            <Button size="sm" variant="ghost" onClick={loadAccountAdmin} disabled={accountsLoading}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Actualizar
            </Button>
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(360px,460px)]">
            <div className="rounded-xl border bg-card">
              <div className="border-b px-4 py-3">
                <p className="text-sm font-semibold">Cuentas Eva</p>
                <p className="text-xs text-muted-foreground">Crear, administrar, facturar e impersonar cuentas desde Empresas.</p>
              </div>
              {accountsLoading ? (
                <div className="py-10 text-center text-sm text-muted-foreground">Cargando cuentas...</div>
              ) : accounts.length === 0 ? (
                <div className="py-10 text-center text-sm text-muted-foreground">No hay cuentas Eva.</div>
              ) : (
                <div className="max-h-[640px] divide-y overflow-y-auto">
                  {accounts.map((account) => {
                    const pricing = accountPricing.find((item) => item.account_id === account.id);
                    const billing = billingByAccount[account.id];
                    const onboarding = accountOnboarding[account.id];
                    const checkout = checkoutLinkByAccount[account.id];
                    return (
                      <div key={account.id} className="space-y-3 px-4 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium">{account.name}</p>
                            <p className="truncate text-xs text-muted-foreground">
                              {account.plan_tier ?? "sin plan"} · {account.billing_interval ?? "sin ciclo"} · {account.subscription_status ?? "sin suscripción"}
                            </p>
                          </div>
                          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] ${
                            account.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"
                          }`}>
                            {account.is_active ? "Activa" : "Inactiva"}
                          </span>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" variant="outline" onClick={() => updatePricingFromAccountsTab(account.id)}>
                            <CreditCard className="mr-2 h-4 w-4" />
                            Pricing
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => openImpersonation(account)}>
                            <ExternalLink className="mr-2 h-4 w-4" />
                            Impersonar
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => resendOnboarding(account)}>
                            <Mail className="mr-2 h-4 w-4" />
                            Onboarding
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => createCheckoutLink(account)}>
                            <CreditCard className="mr-2 h-4 w-4" />
                            Checkout
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => loadBillingStatus(account)}>
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Facturas
                          </Button>
                          {account.is_active ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                if (window.confirm(`Desactivar ${account.name}?`)) {
                                  void runAccountAction(`delete-${account.id}`, async () => {
                                    await evaPlatformApi.deleteAccount(account.id);
                                    toast.success("Cuenta desactivada");
                                  });
                                }
                              }}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Desactivar
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => runAccountAction(`reactivate-${account.id}`, async () => {
                                await evaPlatformApi.reactivateAccount(account.id);
                                toast.success("Cuenta reactivada");
                              })}
                            >
                              <Check className="mr-2 h-4 w-4" />
                              Reactivar
                            </Button>
                          )}
                        </div>

                        <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                          <div className="rounded-md bg-muted/40 px-3 py-2">
                            <span className="font-medium text-foreground">Pricing: </span>
                            {pricing?.billing_amount ?? "Sin monto"} {pricing?.billing_currency ?? ""} {pricing?.billing_interval ?? ""}
                          </div>
                          {checkout && (
                            <a href={checkout} target="_blank" rel="noreferrer" className="rounded-md bg-muted/40 px-3 py-2 text-primary hover:underline">
                              Abrir checkout
                            </a>
                          )}
                          {onboarding && (
                            <button
                              type="button"
                              className="rounded-md bg-muted/40 px-3 py-2 text-left text-primary hover:underline"
                              onClick={() => navigator.clipboard.writeText(onboarding.onboarding_link)}
                            >
                              <Copy className="mr-1 inline h-3 w-3" />
                              Copiar onboarding
                            </button>
                          )}
                        </div>

                        {billing && (
                          <div className="rounded-md border bg-background">
                            <div className="border-b px-3 py-2 text-xs font-medium">
                              Facturación: {billing.status.subscription_status ?? "sin suscripción"}
                            </div>
                            <div className="divide-y">
                              {billing.documents.length === 0 ? (
                                <div className="px-3 py-2 text-xs text-muted-foreground">Sin documentos.</div>
                              ) : (
                                billing.documents.slice(0, 4).map((document) => (
                                  <div key={document.id} className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
                                    <span className="min-w-0 truncate">{document.document_type} · {document.status}</span>
                                    <div className="flex shrink-0 gap-1">
                                      <Button size="sm" variant="ghost" onClick={() => retryBillingDocument(account, document)}>
                                        <RefreshCw className="h-3 w-3" />
                                      </Button>
                                      <Button size="sm" variant="ghost" onClick={() => resendBillingEmail(account, document)}>
                                        <Mail className="h-3 w-3" />
                                      </Button>
                                    </div>
                                  </div>
                                ))
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="rounded-xl border bg-card">
              <div className="border-b px-4 py-3">
                <p className="text-sm font-semibold">Borradores de cuenta</p>
                <p className="text-xs text-muted-foreground">Aprobar un borrador crea la cuenta de Eva y vincula la empresa si tiene empresa_id.</p>
              </div>
              {accountsLoading ? (
                <div className="py-10 text-center text-sm text-muted-foreground">Cargando borradores...</div>
              ) : accountDrafts.length === 0 ? (
                <div className="py-10 text-center text-sm text-muted-foreground">No hay borradores.</div>
              ) : (
                <div className="max-h-[640px] divide-y overflow-y-auto">
                  {accountDrafts.map((draft) => (
                    <div key={draft.id} className="space-y-2 px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{draft.name}</p>
                          <p className="truncate text-xs text-muted-foreground">
                            {draft.owner_email} · {draft.plan_tier} · {draft.billing_cycle} · {draft.status}
                          </p>
                        </div>
                        <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                          {draft.empresa_id ? "Vinculado" : "Sin empresa"}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {draft.status === "draft" && (
                          <Button
                            size="sm"
                            disabled={approvingDrafts.has(draft.id)}
                            onClick={() => approveDraftAccount(draft.id)}
                          >
                            <Check className="mr-2 h-4 w-4" />
                            {approvingDrafts.has(draft.id) ? "Aprobando..." : "Aprobar"}
                          </Button>
                        )}
                        <Button size="sm" variant="outline" onClick={() => updateDraftFromAccountsTab(draft)}>
                          Editar
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => deleteDraftFromAccountsTab(draft)}>
                          <Trash2 className="mr-2 h-4 w-4" />
                          Eliminar
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : empresas.length === 0 ? (
        <div className="py-12 text-center text-muted-foreground">
          {search ? "No se encontraron empresas" : "No hay empresas aún. Crea la primera."}
        </div>
      ) : view === "calendar" ? (
        <div className="rounded-xl border bg-card">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() - 1, 1))}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div className="flex items-center gap-2 text-sm font-semibold">
              <CalendarDays className="h-4 w-4 text-muted-foreground" />
              {calendarMonth.toLocaleDateString("es-MX", { month: "long", year: "numeric" })}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setCalendarMonth(new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 1))}
            >
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
          {calendarLoading ? (
            <div className="py-10 text-center text-sm text-muted-foreground">Cargando calendario...</div>
          ) : calendarItems.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">No hay pendientes con fecha este mes.</div>
          ) : (
            <div className="divide-y">
              {calendarItems.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  onClick={() => {
                    const emp = empresas.find((candidate) => candidate.id === item.empresa_id);
                    if (emp) void openEditEmpresa(emp);
                  }}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/50"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{item.empresa_name}</p>
                  </div>
                  <span className="shrink-0 rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                    {formatDueLabel(item.start_at ?? item.due_at) ?? "Sin fecha"}
                  </span>
                </button>
              ))}
            </div>
          )}
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
                          {formatDueLabel(item.due_at ?? item.start_at) && (
                            <span className="ml-auto shrink-0 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                              {formatDueLabel(item.due_at ?? item.start_at)}
                            </span>
                          )}
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
                    <div className="flex flex-col gap-1.5">
                      <Input
                        ref={addItemInputRef}
                        value={newItemTitle}
                        onChange={(e) => setNewItemTitle(e.target.value)}
                        placeholder="Pendiente, visita o seguimiento..."
                        className="h-7 text-xs"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") addItem(emp.id);
                          if (e.key === "Escape") setAddingItemFor(null);
                        }}
                      />
                      <div className="flex gap-1.5">
                        <Input
                          type="date"
                          value={newItemDueAt}
                          onChange={(e) => setNewItemDueAt(e.target.value)}
                          className="h-7 text-xs"
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
              {editingEmpresaId && !empresaForm.eva_account_id && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  disabled={creatingEvaAccount}
                  onClick={createEvaAccountFromEmpresa}
                >
                  <Building2 className="mr-2 h-4 w-4" />
                  {creatingEvaAccount ? "Creando..." : "Crear cuenta Eva"}
                </Button>
              )}
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
                  <label className="text-sm font-medium">Correos para facturas</label>
                  <BillingRecipientsInput
                    emails={empresaForm.billing_recipient_emails ?? []}
                    onChange={(next) =>
                      setEmpresaForm({ ...empresaForm, billing_recipient_emails: next })
                    }
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    El primer correo es el principal (se usa para Stripe y como remitente del CFDI).
                    Todos reciben el PDF y XML de cada factura. Máximo {MAX_BILLING_RECIPIENTS}.
                  </p>
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
          ) : historyEntries.length === 0 && interactionEntries.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">Sin actividad registrada</p>
          ) : (
            <div className="space-y-3">
              {interactionEntries.map((entry) => (
                <div key={entry.id} className="border-l-2 border-primary/40 pl-3 py-1">
                  <p className="text-sm">
                    <span className="font-medium capitalize">{entry.type.replace(/_/g, " ")}</span>
                    {" · "}
                    <span className="text-foreground">{entry.summary}</span>
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {new Date(`${entry.date}T00:00:00`).toLocaleDateString("es-MX")}
                  </p>
                </div>
              ))}
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

  useEffect(() => {
    if (prevUrl.current === url) return;
    prevUrl.current = url;
    setFailed(false);
  }, [url]);

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
