"use client";

import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { cn } from "@/lib/utils";
import { KanbanCard } from "./kanban-card";

export interface ColumnDef {
  id: string;
  label: string;
  color: string;
}

interface KanbanColumnProps<T extends { id: string; status: string }> {
  column: ColumnDef;
  items: T[];
  renderCard: (item: T) => React.ReactNode;
  onCardClick?: (item: T) => void;
  columnWidth?: string;
}

export function KanbanColumn<T extends { id: string; status: string }>({
  column,
  items,
  renderCard,
  onCardClick,
  columnWidth = "w-72",
}: KanbanColumnProps<T>) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id });

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex shrink-0 flex-col rounded-xl border border-border bg-gray-50/50 transition-colors",
        columnWidth,
        isOver && "border-accent/40 bg-accent/5"
      )}
    >
      {/* Column header */}
      <div className="flex items-center gap-2 border-b border-border/50 px-4 py-3">
        <span
          className={cn(
            "rounded-full px-2.5 py-0.5 text-[11px] font-medium",
            column.color
          )}
        >
          {column.label}
        </span>
        <span className="text-xs font-medium text-muted">{items.length}</span>
      </div>

      {/* Cards */}
      <SortableContext
        items={items.map((i) => i.id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="flex flex-col gap-2 p-3 min-h-[80px]">
          {items.map((item) => (
            <KanbanCard
              key={item.id}
              id={item.id}
              onClick={() => onCardClick?.(item)}
            >
              {renderCard(item)}
            </KanbanCard>
          ))}
          {items.length === 0 && (
            <div className="flex flex-1 items-center justify-center py-8 text-xs text-gray-300">
              No items
            </div>
          )}
        </div>
      </SortableContext>
    </div>
  );
}
