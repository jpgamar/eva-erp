"use client";

import { useState, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
  closestCorners,
} from "@dnd-kit/core";
import { KanbanColumn, type ColumnDef } from "./kanban-column";

export type { ColumnDef };

interface KanbanBoardWithGuardProps<T extends { id: string; status: string }> {
  columns: ColumnDef[];
  items: T[];
  renderCard: (item: T) => React.ReactNode;
  onStatusChange: (itemId: string, newStatus: string) => void;
  /**
   * Called on drop (not hover) with the from/to stages. Return true to allow
   * the drop; return false to revert. Allows side-effects like confirm dialogs
   * (e.g., drag to Inactivo → show cancel subscription dialog).
   */
  onBeforeStageChange?: (args: {
    itemId: string;
    from: string;
    to: string;
  }) => Promise<boolean>;
  onCardClick?: (item: T) => void;
  columnWidth?: string;
}

/**
 * Fork of ``KanbanBoard`` that defers persistence until the drop. The original
 * component persisted on every ``handleDragOver`` tick, which meant a half-way
 * hover over Inactivo would flip subscription status before the operator
 * confirmed. This board calls ``onBeforeStageChange`` once on drop and only
 * persists if it resolves true.
 */
export function KanbanBoardWithGuard<T extends { id: string; status: string }>({
  columns,
  items,
  renderCard,
  onStatusChange,
  onBeforeStageChange,
  onCardClick,
  columnWidth,
}: KanbanBoardWithGuardProps<T>) {
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  const activeItem = activeId ? items.find((i) => i.id === activeId) : null;

  const findContainer = useCallback(
    (id: string): string | undefined => {
      if (columns.some((c) => c.id === id)) return id;
      const item = items.find((i) => i.id === id);
      return item?.status;
    },
    [columns, items]
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    setActiveId(null);

    const { active, over } = event;
    if (!over) return;

    const itemId = active.id as string;
    const toStage = findContainer(over.id as string);
    if (!toStage) return;

    const item = items.find((i) => i.id === itemId);
    if (!item || item.status === toStage) return;

    if (onBeforeStageChange) {
      const approved = await onBeforeStageChange({
        itemId,
        from: item.status,
        to: toStage,
      });
      if (!approved) return;
    }

    onStatusChange(itemId, toStage);
  };

  const handleDragCancel = () => setActiveId(null);

  const overlay = (
    <DragOverlay>
      {activeItem ? (
        <div className="rounded-lg border border-accent/30 bg-card p-3 shadow-xl ring-2 ring-accent/20 opacity-90 rotate-2">
          {renderCard(activeItem)}
        </div>
      ) : null}
    </DragOverlay>
  );

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div className="flex gap-4 overflow-x-auto pb-4 -mx-1 px-1">
        {columns.map((column) => {
          const columnItems = items.filter((i) => i.status === column.id);
          return (
            <KanbanColumn
              key={column.id}
              column={column}
              items={columnItems}
              renderCard={renderCard}
              onCardClick={onCardClick}
              columnWidth={columnWidth}
            />
          );
        })}
      </div>

      {typeof document !== "undefined"
        ? createPortal(overlay, document.body)
        : overlay}
    </DndContext>
  );
}
