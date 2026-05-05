"use client";

import { CalendarClock, Link2, Building2 } from "lucide-react";
import type { EmpresaListItem } from "@/lib/api/empresas";

const STAGE_LABELS: Record<string, string> = {
  prospecto: "Prospecto",
  interesado: "Interesado",
  demo: "Demo",
  negociacion: "Negociación",
  implementacion: "Implementación",
  operativo: "Operativo",
  churn_risk: "Churn Risk",
  inactivo: "Inactivo",
};

const MONTH_SHORT = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

function formatShortDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.getDate()} ${MONTH_SHORT[d.getMonth()]}`;
}

function formatMxn(amount: number | null): string {
  if (amount == null) return "$—";
  return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 }).format(
    amount
  );
}

interface Props {
  empresa: EmpresaListItem;
  onClick?: (empresa: EmpresaListItem) => void;
}

/**
 * Kanban card for one empresa. Shows logo, name, Eva link chip, monthly
 * amount + billing interval, next/close/cancellation date row, and
 * grandfathered/warning chip when applicable. Min 320×240 per UI/UX table.
 */
export function EmpresaCard({ empresa, onClick }: Props) {
  const stageLabel = STAGE_LABELS[empresa.lifecycle_stage] ?? empresa.lifecycle_stage;
  const nextDate =
    formatShortDate(empresa.cancellation_scheduled_at) ||
    formatShortDate(empresa.current_period_end) ||
    formatShortDate(empresa.expected_close_date);
  const linkedLabel = empresa.eva_account_id ? "Vinculada" : "Sin vincular";

  return (
    <div
      className="flex min-h-60 min-w-80 cursor-pointer flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-sm transition-all hover:shadow-md"
      onClick={() => onClick?.(empresa)}
      data-testid={`empresa-card-${empresa.id}`}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-lg font-semibold text-accent-foreground">
          {empresa.logo_url ? (
            <img src={empresa.logo_url} alt={empresa.name} className="h-12 w-12 rounded-lg object-contain" />
          ) : (
            <Building2 className="h-5 w-5" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base font-semibold text-foreground">{empresa.name}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">{stageLabel}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${
            empresa.eva_account_id
              ? "bg-emerald-50 text-emerald-700"
              : "border border-destructive/30 text-destructive"
          }`}
        >
          <Link2 className="h-3 w-3" />
          {linkedLabel}
        </span>
        {empresa.billing_interval === "annual" ? (
          <span className="rounded-full bg-sky-50 px-2 py-0.5 text-sky-700">Anual</span>
        ) : (
          <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">Mensual</span>
        )}
        {empresa.payment_day ? (
          <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">
            Día {empresa.payment_day}
          </span>
        ) : null}
        {empresa.grandfathered ? (
          <span className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-amber-700">
            Revisar
          </span>
        ) : null}
      </div>

      <div className="flex items-baseline justify-between">
        <span className="font-mono text-lg font-bold text-foreground">
          {formatMxn(empresa.monthly_amount)}
        </span>
        {empresa.subscription_status ? (
          <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
            {empresa.subscription_status.replace(/_/g, " ")}
          </span>
        ) : null}
      </div>

      {nextDate ? (
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <CalendarClock className="h-3.5 w-3.5" />
          {empresa.cancellation_scheduled_at
            ? `Cancelación: ${nextDate}`
            : empresa.current_period_end
              ? `Próxima factura: ${nextDate}`
              : `Cierre esperado: ${nextDate}`}
        </div>
      ) : null}
    </div>
  );
}
