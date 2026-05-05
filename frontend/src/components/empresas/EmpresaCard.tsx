"use client";

import { CalendarClock, Link2, Building2, AlertCircle, Unplug } from "lucide-react";
import type { EmpresaListItem, PendingItem } from "@/lib/api/empresas";

const MONTH_SHORT = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

function formatShortDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.getDate()} ${MONTH_SHORT[d.getMonth()]}`;
}

function formatMxn(amount: number | null): string | null {
  if (amount == null || amount <= 0) return null;
  return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 }).format(
    amount
  );
}

interface Props {
  empresa: EmpresaListItem;
  onClick?: (empresa: EmpresaListItem) => void;
}

function nextActionLabel(item: PendingItem): string {
  const when = item.start_at ?? item.due_at ?? null;
  const dateLabel = when ? formatShortDate(when) : null;
  return dateLabel ? `${dateLabel} · ${item.title}` : item.title;
}

/**
 * Kanban card for one empresa. The lifecycle stage label is intentionally
 * NOT repeated here — the column header already provides it. The card
 * collapses to its actual content (no fixed min-height) so sparse rows
 * stay short and dense rows stay readable.
 */
export function EmpresaCard({ empresa, onClick }: Props) {
  const monthlyAmount = formatMxn(empresa.monthly_amount);
  const nextDate =
    formatShortDate(empresa.cancellation_scheduled_at) ||
    formatShortDate(empresa.current_period_end) ||
    formatShortDate(empresa.expected_close_date);
  const linked = !!empresa.eva_account_id;
  const linkedAccountName = empresa.health.linked_account_name;
  const overdue = empresa.overdue_count > 0;
  const showLinkedRow = linked || empresa.lifecycle_stage === "operativo";

  // The KanbanCard wrapper already paints the border, background, and
  // padding for this card; we just lay out the inner content. Without
  // this we end up with a double-bordered / double-padded card with
  // a lot of dead vertical space.
  return (
    <div
      className="flex flex-col gap-1.5"
      onClick={() => onClick?.(empresa)}
      data-testid={`empresa-card-${empresa.id}`}
    >
      <div className="flex items-start gap-2.5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted text-muted-foreground">
          {empresa.logo_url ? (
            <img src={empresa.logo_url} alt={empresa.name} className="h-9 w-9 object-contain" />
          ) : (
            <Building2 className="h-4 w-4" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold leading-tight text-foreground">
            {empresa.name}
          </h3>
          {monthlyAmount ? (
            <p className="mt-0.5 truncate font-mono text-xs text-muted-foreground">
              {monthlyAmount}
              <span className="ml-1 text-[10px] uppercase tracking-wide text-muted-foreground/70">
                {empresa.billing_interval === "annual" ? "anual" : "mensual"}
              </span>
            </p>
          ) : empresa.billing_interval === "annual" ? (
            <p className="mt-0.5 text-[10px] uppercase tracking-wide text-muted-foreground/70">anual</p>
          ) : null}
        </div>
        {empresa.grandfathered ? (
          <span className="shrink-0 rounded-full border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
            Revisar
          </span>
        ) : null}
      </div>

      {showLinkedRow ? (
        <div
          className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] ${
            linked
              ? "bg-emerald-50 text-emerald-700"
              : "bg-amber-50 text-amber-700"
          }`}
        >
          {linked ? <Link2 className="h-3 w-3 shrink-0" /> : <Unplug className="h-3 w-3 shrink-0" />}
          <span className="truncate">
            {linked ? (linkedAccountName ?? "Vinculada a Eva") : "Sin cuenta de Eva"}
          </span>
          {empresa.subscription_status ? (
            <span className="ml-auto shrink-0 text-[10px] uppercase tracking-wide opacity-70">
              {empresa.subscription_status.replace(/_/g, " ")}
            </span>
          ) : null}
        </div>
      ) : null}

      {empresa.summary_note ? (
        <p className="line-clamp-2 text-xs text-muted-foreground">{empresa.summary_note}</p>
      ) : null}

      {empresa.next_action ? (
        <div className="flex items-center gap-1 text-xs">
          <CalendarClock className="h-3 w-3 shrink-0 text-sky-600" />
          <span className="truncate text-foreground">{nextActionLabel(empresa.next_action)}</span>
        </div>
      ) : nextDate ? (
        <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
          <CalendarClock className="h-3 w-3 shrink-0" />
          <span className="truncate">
            {empresa.cancellation_scheduled_at
              ? `Cancelación: ${nextDate}`
              : empresa.current_period_end
                ? `Próx. factura: ${nextDate}`
                : `Cierre esperado: ${nextDate}`}
          </span>
        </div>
      ) : null}

      {overdue ? (
        <div className="flex items-center gap-1 text-[11px] font-semibold text-destructive">
          <AlertCircle className="h-3 w-3" />
          {empresa.overdue_count} vencido{empresa.overdue_count === 1 ? "" : "s"}
        </div>
      ) : null}
    </div>
  );
}
