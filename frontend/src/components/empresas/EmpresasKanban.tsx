"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { X } from "lucide-react";

import { KanbanBoardWithGuard, type ColumnDef } from "@/components/kanban/kanban-board-with-guard";
import { EmpresaCard } from "@/components/empresas/EmpresaCard";
import { CancelSubscriptionDialog } from "@/components/empresas/CancelSubscriptionDialog";
import { ItemEditorPanel, type ItemEditorMode } from "@/components/empresas/ItemEditorPanel";
import { Button } from "@/components/ui/button";
import api from "@/lib/api/client";
import { empresasApi } from "@/lib/api/empresas";
import type { EmpresaContactMethod, EmpresaListItem, LifecycleStage } from "@/lib/api/empresas";

const COLUMNS: ColumnDef[] = [
  { id: "prospecto", label: "Prospecto", color: "bg-slate-400" },
  { id: "interesado", label: "Interesado", color: "bg-blue-400" },
  { id: "demo", label: "Demo", color: "bg-indigo-400" },
  { id: "negociacion", label: "Negociación", color: "bg-violet-400" },
  { id: "implementacion", label: "Implementación", color: "bg-purple-400" },
  { id: "operativo", label: "Operativo", color: "bg-emerald-500" },
  { id: "churn_risk", label: "Churn Risk", color: "bg-amber-500" },
  { id: "inactivo", label: "Inactivo", color: "bg-rose-500" },
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

  // Inline item editor opened from the per-card "+" button or
  // channel-shortcut row. The same panel is used for create + edit.
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<ItemEditorMode>({ type: "create" });

  // Cmd/Ctrl-click multi-select on cards. When ≥1 selected, a
  // floating bar lets the operator move all selected empresas to a
  // target stage in one atomic batch via /empresas/bulk-stage.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkSubmitting, setBulkSubmitting] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && selectedIds.size > 0) {
        setSelectedIds(new Set());
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedIds]);

  function toggleSelect(empresa: EmpresaListItem) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(empresa.id)) next.delete(empresa.id);
      else next.add(empresa.id);
      return next;
    });
  }

  async function bulkMoveTo(stage: LifecycleStage) {
    if (selectedIds.size === 0) return;
    const moves = empresas
      .filter((e) => selectedIds.has(e.id))
      .map((e) => ({ empresa_id: e.id, version: e.version ?? 0 }));
    setBulkSubmitting(true);
    try {
      const result = await empresasApi.bulkStage({ moves, lifecycle_stage_to: stage });
      toast.success(`Movidas ${result.moved.length} empresas a ${stage}`);
      setSelectedIds(new Set());
      await onChanged();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const conflicts = detail?.conflicts ?? [];
      const reasons = new Set(conflicts.map((c: { reason: string }) => c.reason));
      if (reasons.has("BulkInactivoNeedsCancel")) {
        toast.error(
          "Una o más empresas tienen suscripción activa. Arrástralas individualmente para cancelar primero.",
        );
      } else if (reasons.has("OperativoRequiresActiveSubscription")) {
        toast.error("Algunas empresas no tienen cuenta de Eva con suscripción activa.");
      } else if (reasons.has("ExpectedCloseDateRequired")) {
        toast.error("Algunas empresas requieren fecha de cierre esperada para esta etapa.");
      } else if (reasons.has("OptimisticLockMismatch")) {
        toast.error("Otra persona cambió alguna empresa. Recarga e inténtalo de nuevo.");
        await onChanged();
      } else {
        toast.error("No se pudo mover el lote.");
      }
    } finally {
      setBulkSubmitting(false);
    }
  }

  const empresaPickerOptions = useMemo(
    () => empresas.map((e) => ({ id: e.id, name: e.name })),
    [empresas],
  );

  function openQuickAdd(emp: EmpresaListItem) {
    setEditorMode({ type: "create", defaults: { empresa_id: emp.id, kind: "todo" } });
    setEditorOpen(true);
  }

  function openLogChannel(emp: EmpresaListItem, method: EmpresaContactMethod) {
    const nowIso = new Date().toISOString();
    setEditorMode({
      type: "create",
      defaults: {
        empresa_id: emp.id,
        kind: "outreach",
        contact_method: method,
        due_at: nowIso,
        title: "",
      },
    });
    setEditorOpen(true);
  }

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
    const hasActiveSub =
      empresa?.subscription_status === "active" || empresa?.subscription_status === "trialing";
    if (!empresa || !hasActiveSub) {
      // No active subscription — just move the card.
      return true;
    }

    setPendingCancelEmpresaId(empresa.id);
    return new Promise<boolean>((resolve) => {
      setCancelResolver(() => resolve);
      setCancelOpen(true);
    });
  }

  const stageOptions: { id: LifecycleStage; label: string }[] = [
    { id: "prospecto", label: "Prospecto" },
    { id: "interesado", label: "Interesado" },
    { id: "demo", label: "Demo" },
    { id: "negociacion", label: "Negociación" },
    { id: "implementacion", label: "Implementación" },
    { id: "operativo", label: "Operativo" },
    { id: "churn_risk", label: "Churn Risk" },
    { id: "inactivo", label: "Inactivo" },
  ];

  return (
    <div>
      {selectedIds.size > 0 ? (
        <div
          className="sticky top-0 z-30 mb-3 flex items-center gap-3 rounded-lg border border-accent/40 bg-accent/10 px-3 py-2 backdrop-blur"
          data-testid="empresas-kanban-bulk-bar"
        >
          <span className="text-xs font-semibold text-foreground">
            {selectedIds.size} seleccionadas
          </span>
          <span className="text-xs text-muted-foreground">Mover a:</span>
          <select
            disabled={bulkSubmitting}
            onChange={(e) => {
              if (e.target.value) {
                void bulkMoveTo(e.target.value as LifecycleStage);
                e.currentTarget.value = "";
              }
            }}
            className="h-7 rounded-md border border-border bg-background px-2 text-xs"
            data-testid="empresas-kanban-bulk-target"
            defaultValue=""
          >
            <option value="" disabled>
              Selecciona etapa…
            </option>
            {stageOptions.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
          <Button
            variant="ghost"
            size="sm"
            disabled={bulkSubmitting}
            onClick={() => setSelectedIds(new Set())}
            className="ml-auto"
          >
            <X className="mr-1 h-3.5 w-3.5" /> Limpiar
          </Button>
        </div>
      ) : null}
      <KanbanBoardWithGuard<KanbanItem>
        columns={filteredColumns}
        items={items}
        renderCard={(item) => (
          <div
            className={
              selectedIds.has(item.id)
                ? "ring-2 ring-accent ring-offset-2 rounded-xl"
                : undefined
            }
          >
            <EmpresaCard
              empresa={item}
              onClick={(emp, event) => {
                // Cmd/Ctrl-click toggles bulk selection. A regular click
                // opens the empresa edit modal as before. Without
                // stopPropagation the click would bubble to the outer
                // KanbanCard wrapper, which also fires onClick and would
                // open the modal in addition to toggling selection.
                if (event && (event.metaKey || event.ctrlKey)) {
                  event.stopPropagation();
                  event.preventDefault();
                  toggleSelect(emp);
                  return;
                }
                onCardClick?.(emp);
              }}
              onQuickAdd={openQuickAdd}
              onLogChannel={openLogChannel}
            />
          </div>
        )}
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
      <ItemEditorPanel
        open={editorOpen}
        onOpenChange={setEditorOpen}
        mode={editorMode}
        empresas={empresaPickerOptions}
        onChanged={() => {
          void onChanged();
        }}
      />
    </div>
  );
}
