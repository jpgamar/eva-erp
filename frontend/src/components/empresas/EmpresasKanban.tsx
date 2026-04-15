"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";

import { KanbanBoardWithGuard, type ColumnDef } from "@/components/kanban/kanban-board-with-guard";
import { EmpresaCard } from "@/components/empresas/EmpresaCard";
import { CancelSubscriptionDialog } from "@/components/empresas/CancelSubscriptionDialog";
import { api } from "@/lib/api/client";
import type { EmpresaListItem } from "@/lib/api/empresas";

const COLUMNS: ColumnDef[] = [
  { id: "prospecto", title: "Prospecto", color: "bg-slate-400" },
  { id: "interesado", title: "Interesado", color: "bg-blue-400" },
  { id: "demo", title: "Demo", color: "bg-indigo-400" },
  { id: "negociacion", title: "Negociación", color: "bg-violet-400" },
  { id: "implementacion", title: "Implementación", color: "bg-purple-400" },
  { id: "operativo", title: "Operativo", color: "bg-emerald-500" },
  { id: "churn_risk", title: "Churn Risk", color: "bg-amber-500" },
  { id: "inactivo", title: "Inactivo", color: "bg-rose-500" },
];

interface Props {
  empresas: EmpresaListItem[];
  /** Called after a stage change is persisted successfully so the parent can refetch. */
  onChanged: () => Promise<void> | void;
  onCardClick?: (empresa: EmpresaListItem) => void;
  stageFilter?: string | null;
}

type KanbanItem = EmpresaListItem & { status: string };

export function EmpresasKanban({ empresas, onChanged, onCardClick, stageFilter }: Props) {
  const [cancelOpen, setCancelOpen] = useState(false);
  const [pendingCancelEmpresaId, setPendingCancelEmpresaId] = useState<string | null>(null);
  const [cancelResolver, setCancelResolver] = useState<((v: boolean) => void) | null>(null);

  const items: KanbanItem[] = useMemo(
    () =>
      empresas.map((e) => ({
        ...e,
        status: e.lifecycle_stage,
      })),
    [empresas]
  );

  const filteredColumns = stageFilter ? COLUMNS.filter((c) => c.id === stageFilter) : COLUMNS;

  async function persistStageChange(empresaId: string, toStage: string) {
    const empresa = empresas.find((e) => e.id === empresaId);
    if (!empresa) return;
    try {
      await api.patch(
        `/empresas/${empresaId}`,
        { lifecycle_stage: toStage },
        { headers: { "If-Match": String(empresa.version ?? 0) } }
      );
      await onChanged();
      toast.success(`Movida a ${toStage}`);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail?.reason === "OptimisticLockMismatch") {
        toast.error("Otra persona cambió esta empresa. Recarga para ver la versión actual.");
      } else if (detail?.reason === "OperativoRequiresActiveSubscription") {
        toast.error("Operativo requiere cuenta de Eva con suscripción activa.");
      } else if (detail?.reason === "ExpectedCloseDateRequired") {
        toast.error("Define la fecha de cierre esperada para esta etapa.");
      } else {
        toast.error(typeof detail === "string" ? detail : "No se pudo actualizar la etapa.");
      }
      await onChanged(); // refetch to unwind optimistic UI
    }
  }

  async function handleBeforeStageChange(args: {
    itemId: string;
    from: string;
    to: string;
  }): Promise<boolean> {
    // Drag to Inactivo intercepts with a cancel dialog — resolves promise
    // based on operator choice in that dialog.
    if (args.to !== "inactivo") return true;

    const empresa = empresas.find((e) => e.id === args.itemId);
    if (!empresa || !empresa.stripe_subscription_id) {
      // No active subscription — just move the card.
      return true;
    }

    setPendingCancelEmpresaId(empresa.id);
    return new Promise<boolean>((resolve) => {
      setCancelResolver(() => resolve);
      setCancelOpen(true);
    });
  }

  return (
    <div>
      <KanbanBoardWithGuard<KanbanItem>
        columns={filteredColumns}
        items={items}
        renderCard={(item) => <EmpresaCard empresa={item} onClick={onCardClick} />}
        onStatusChange={persistStageChange}
        onBeforeStageChange={handleBeforeStageChange}
        onCardClick={onCardClick as ((item: KanbanItem) => void) | undefined}
      />
      <CancelSubscriptionDialog
        open={cancelOpen}
        onOpenChange={(open) => {
          if (!open && cancelResolver) {
            // User closed without confirming — revert drag.
            cancelResolver(false);
            setCancelResolver(null);
            setPendingCancelEmpresaId(null);
          }
          setCancelOpen(open);
        }}
        empresaId={pendingCancelEmpresaId ?? ""}
        onCanceled={() => {
          if (cancelResolver) {
            cancelResolver(true);
            setCancelResolver(null);
          }
          setPendingCancelEmpresaId(null);
        }}
      />
    </div>
  );
}
