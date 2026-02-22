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
  type DragOverEvent,
  closestCorners,
} from "@dnd-kit/core";
import { KanbanColumn, type ColumnDef } from "./kanban-column";

export type { ColumnDef };

interface KanbanBoardProps<T extends { id: string; status: string }> {
  columns: ColumnDef[];
  items: T[];
  renderCard: (item: T) => React.ReactNode;
  onStatusChange: (itemId: string, newStatus: string) => void;
  onCardClick?: (item: T) => void;
  columnWidth?: string;
}

export function KanbanBoard<T extends { id: string; status: string }>({
  columns,
  items,
  renderCard,
  onStatusChange,
  onCardClick,
  columnWidth,
}: KanbanBoardProps<T>) {
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    })
  );

  const activeItem = activeId ? items.find((i) => i.id === activeId) : null;

  // Find which column an item belongs to
  const findContainer = useCallback(
    (id: string): string | undefined => {
      // Is it a column ID?
      if (columns.some((c) => c.id === id)) return id;
      // Otherwise it's an item ID — find its status
      const item = items.find((i) => i.id === id);
      return item?.status;
    },
    [columns, items]
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    if (!over) return;

    const activeContainer = findContainer(active.id as string);
    const overContainer = findContainer(over.id as string);

    if (!activeContainer || !overContainer || activeContainer === overContainer) return;

    // Optimistically update — the parent's onStatusChange will handle persistence
    onStatusChange(active.id as string, overContainer);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveId(null);

    const { active, over } = event;
    if (!over) return;

    const overContainer = findContainer(over.id as string);
    if (!overContainer) return;

    const item = items.find((i) => i.id === active.id);
    if (item && item.status !== overContainer) {
      onStatusChange(active.id as string, overContainer);
    }
  };

  const handleDragCancel = () => {
    setActiveId(null);
  };

  // Render DragOverlay via portal to document.body so it escapes any
  // ancestor CSS transforms that break position:fixed positioning.
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
      onDragOver={handleDragOver}
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
