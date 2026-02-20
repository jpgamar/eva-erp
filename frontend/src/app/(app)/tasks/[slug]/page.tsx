"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
  type DragOverEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  ArrowLeft,
  Plus,
  GripVertical,
  MessageSquare,
  Calendar,
  User,
  MoreHorizontal,
  X,
  Send,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import { boardsApi, tasksApi } from "@/lib/api/tasks";
import type { BoardDetail, Column, Task, TaskDetail, TaskComment } from "@/types";
import { useAuth } from "@/lib/auth/context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const PRIORITY_COLORS: Record<string, string> = {
  low: "#6b7280",
  medium: "#3b82f6",
  high: "#f59e0b",
  urgent: "#ef4444",
};

function isOverdue(dueDate: string | null) {
  if (!dueDate) return false;
  return new Date(dueDate) < new Date(new Date().toDateString());
}

// Sortable Task Card
function SortableTaskCard({
  task,
  onClick,
}: {
  task: Task;
  onClick: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: task.id,
    data: { type: "task", task },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes}>
      <Card
        className={`p-3 cursor-pointer hover:border-primary/50 transition-colors ${
          isOverdue(task.due_date) ? "border-red-500 border-2" : ""
        }`}
        onClick={onClick}
      >
        <div className="flex items-start gap-2">
          <div {...listeners} className="mt-1 cursor-grab text-muted-foreground hover:text-foreground">
            <GripVertical className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium leading-tight">{task.title}</p>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {/* Priority dot */}
              <div
                className="h-2.5 w-2.5 rounded-full shrink-0"
                style={{ backgroundColor: PRIORITY_COLORS[task.priority] }}
                title={task.priority}
              />
              {/* Due date */}
              {task.due_date && (
                <span className={`text-xs flex items-center gap-0.5 ${isOverdue(task.due_date) ? "text-red-500 font-medium" : "text-muted-foreground"}`}>
                  <Calendar className="h-3 w-3" />
                  {new Date(task.due_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                </span>
              )}
              {/* Labels */}
              {task.labels?.map((label) => (
                <Badge key={label} variant="secondary" className="text-xs px-1.5 py-0">
                  {label}
                </Badge>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

// Droppable Column
function KanbanColumn({
  column,
  onTaskClick,
  onAddTask,
}: {
  column: Column;
  onTaskClick: (task: Task) => void;
  onAddTask: (columnId: string) => void;
}) {
  const sortedTasks = [...column.tasks].sort((a, b) => a.position - b.position);
  const taskIds = sortedTasks.map((t) => t.id);

  return (
    <div className="flex flex-col w-[300px] shrink-0">
      {/* Column header */}
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-full" style={{ backgroundColor: column.color }} />
          <h3 className="font-semibold text-sm">{column.name}</h3>
          <span className="text-xs text-muted-foreground bg-muted rounded-full px-2 py-0.5">
            {column.tasks.length}
          </span>
        </div>
      </div>

      {/* Tasks */}
      <SortableContext items={taskIds} strategy={verticalListSortingStrategy}>
        <div
          className="flex-1 space-y-2 min-h-[100px] p-1 rounded-lg bg-muted/30"
          data-column-id={column.id}
        >
          {sortedTasks.map((task) => (
            <SortableTaskCard key={task.id} task={task} onClick={() => onTaskClick(task)} />
          ))}
        </div>
      </SortableContext>

      {/* Add task button */}
      <Button
        variant="ghost"
        size="sm"
        className="mt-2 justify-start text-muted-foreground"
        onClick={() => onAddTask(column.id)}
      >
        <Plus className="h-4 w-4 mr-1" /> Add task
      </Button>
    </div>
  );
}

export default function KanbanBoardPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const slug = params.slug as string;

  const [board, setBoard] = useState<BoardDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTask, setActiveTask] = useState<Task | null>(null);

  // Task detail panel
  const [detailOpen, setDetailOpen] = useState(false);
  const [taskDetail, setTaskDetail] = useState<TaskDetail | null>(null);
  const [newComment, setNewComment] = useState("");

  // Add task dialog
  const [addColumnId, setAddColumnId] = useState<string | null>(null);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskPriority, setNewTaskPriority] = useState("medium");

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor)
  );

  const fetchBoard = useCallback(async () => {
    try {
      // We need board ID from slug — list boards then find by slug
      const boards = await boardsApi.list();
      const found = boards.find((b: any) => b.slug === slug);
      if (!found) {
        toast.error("Board not found");
        router.push("/tasks");
        return;
      }
      const detail = await boardsApi.get(found.id);
      setBoard(detail);
    } catch {
      toast.error("Failed to load board");
    } finally {
      setLoading(false);
    }
  }, [slug, router]);

  useEffect(() => { fetchBoard(); }, [fetchBoard]);

  const handleDragStart = (event: DragStartEvent) => {
    const task = event.active.data.current?.task;
    if (task) setActiveTask(task);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    setActiveTask(null);
    const { active, over } = event;
    if (!over || !board) return;

    const taskId = active.id as string;
    const task = board.columns.flatMap((c) => c.tasks).find((t) => t.id === taskId);
    if (!task) return;

    // Find target column — either from over.data or from the column containing the over element
    let targetColumnId: string;
    let targetPosition: number;

    const overTask = board.columns.flatMap((c) => c.tasks).find((t) => t.id === over.id);
    if (overTask) {
      targetColumnId = overTask.column_id;
      targetPosition = overTask.position;
    } else {
      // Dropped on a column directly
      const col = board.columns.find((c) => c.id === over.id);
      if (col) {
        targetColumnId = col.id;
        targetPosition = col.tasks.length;
      } else {
        return;
      }
    }

    if (task.column_id === targetColumnId && task.position === targetPosition) return;

    // Optimistic update
    setBoard((prev) => {
      if (!prev) return prev;
      const cols = prev.columns.map((col) => ({
        ...col,
        tasks: col.tasks.filter((t) => t.id !== taskId),
      }));
      const targetCol = cols.find((c) => c.id === targetColumnId);
      if (targetCol) {
        const updatedTask = { ...task, column_id: targetColumnId, position: targetPosition };
        targetCol.tasks.push(updatedTask);
        targetCol.tasks.sort((a, b) => a.position - b.position);
      }
      return { ...prev, columns: cols };
    });

    try {
      await tasksApi.move(taskId, { column_id: targetColumnId, position: targetPosition });
    } catch {
      toast.error("Failed to move task");
      await fetchBoard();
    }
  };

  const openTaskDetail = async (task: Task) => {
    try {
      const detail = await tasksApi.get(task.id);
      setTaskDetail(detail);
      setDetailOpen(true);
    } catch {
      toast.error("Failed to load task");
    }
  };

  const handleAddTask = async () => {
    if (!addColumnId || !newTaskTitle.trim() || !board) return;
    try {
      await tasksApi.create({
        board_id: board.id,
        column_id: addColumnId,
        title: newTaskTitle.trim(),
        priority: newTaskPriority,
      });
      setAddColumnId(null);
      setNewTaskTitle("");
      setNewTaskPriority("medium");
      toast.success("Task created");
      await fetchBoard();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to create task");
    }
  };

  const handleUpdateTask = async (field: string, value: any) => {
    if (!taskDetail) return;
    try {
      await tasksApi.update(taskDetail.id, { [field]: value });
      setTaskDetail((prev) => prev ? { ...prev, [field]: value } : prev);
      await fetchBoard();
    } catch {
      toast.error("Failed to update task");
    }
  };

  const handleAddComment = async () => {
    if (!taskDetail || !newComment.trim()) return;
    try {
      const comment = await tasksApi.addComment(taskDetail.id, newComment.trim());
      setTaskDetail((prev) => prev ? { ...prev, comments: [...prev.comments, comment] } : prev);
      setNewComment("");
    } catch {
      toast.error("Failed to add comment");
    }
  };

  const handleDeleteTask = async () => {
    if (!taskDetail) return;
    try {
      await tasksApi.delete(taskDetail.id);
      setDetailOpen(false);
      setTaskDetail(null);
      toast.success("Task deleted");
      await fetchBoard();
    } catch {
      toast.error("Failed to delete task");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!board) return null;

  const sortedColumns = [...board.columns].sort((a, b) => a.position - b.position);

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Board Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b shrink-0">
        <Link href="/tasks">
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-xl font-bold">{board.name}</h1>
          {board.description && (
            <p className="text-sm text-muted-foreground">{board.description}</p>
          )}
        </div>
      </div>

      {/* Kanban Board */}
      <div className="flex-1 overflow-x-auto p-6">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="flex gap-4 h-full">
            {sortedColumns.map((column) => (
              <KanbanColumn
                key={column.id}
                column={column}
                onTaskClick={openTaskDetail}
                onAddTask={(colId) => setAddColumnId(colId)}
              />
            ))}
          </div>

          <DragOverlay>
            {activeTask && (
              <Card className="p-3 w-[280px] shadow-lg rotate-2">
                <p className="text-sm font-medium">{activeTask.title}</p>
              </Card>
            )}
          </DragOverlay>
        </DndContext>
      </div>

      {/* Task Detail Sheet */}
      <Sheet open={detailOpen} onOpenChange={setDetailOpen}>
        <SheetContent className="w-[400px] sm:w-[500px] overflow-y-auto">
          {taskDetail && (
            <div className="space-y-5 pt-4">
              <SheetHeader>
                <SheetTitle className="text-left">{taskDetail.title}</SheetTitle>
              </SheetHeader>

              {/* Editable fields */}
              <div className="space-y-4">
                <div>
                  <Label className="text-xs text-muted-foreground">Title</Label>
                  <Input
                    value={taskDetail.title}
                    onChange={(e) => setTaskDetail((p) => p ? { ...p, title: e.target.value } : p)}
                    onBlur={(e) => handleUpdateTask("title", e.target.value)}
                  />
                </div>

                <div>
                  <Label className="text-xs text-muted-foreground">Description</Label>
                  <Textarea
                    value={taskDetail.description ?? ""}
                    onChange={(e) => setTaskDetail((p) => p ? { ...p, description: e.target.value } : p)}
                    onBlur={(e) => handleUpdateTask("description", e.target.value || null)}
                    rows={4}
                    placeholder="Add a description..."
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs text-muted-foreground">Priority</Label>
                    <Select
                      value={taskDetail.priority}
                      onValueChange={(v) => handleUpdateTask("priority", v)}
                    >
                      <SelectTrigger>
                        <div className="flex items-center gap-2">
                          <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: PRIORITY_COLORS[taskDetail.priority] }} />
                          <SelectValue />
                        </div>
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(PRIORITY_COLORS).map(([p, c]) => (
                          <SelectItem key={p} value={p}>
                            <div className="flex items-center gap-2">
                              <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: c }} />
                              <span className="capitalize">{p}</span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label className="text-xs text-muted-foreground">Due Date</Label>
                    <Input
                      type="date"
                      value={taskDetail.due_date ?? ""}
                      onChange={(e) => handleUpdateTask("due_date", e.target.value || null)}
                    />
                  </div>
                </div>

                {/* Labels */}
                <div>
                  <Label className="text-xs text-muted-foreground">Labels</Label>
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {taskDetail.labels?.map((label) => (
                      <Badge
                        key={label}
                        variant="secondary"
                        className="cursor-pointer"
                        onClick={() => handleUpdateTask("labels", taskDetail.labels?.filter((l) => l !== label) ?? [])}
                      >
                        {label} <X className="h-3 w-3 ml-1" />
                      </Badge>
                    ))}
                    <Input
                      placeholder="Add label..."
                      className="w-24 h-6 text-xs"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && (e.target as HTMLInputElement).value.trim()) {
                          const newLabel = (e.target as HTMLInputElement).value.trim();
                          handleUpdateTask("labels", [...(taskDetail.labels ?? []), newLabel]);
                          (e.target as HTMLInputElement).value = "";
                        }
                      }}
                    />
                  </div>
                </div>
              </div>

              <Separator />

              {/* Comments */}
              <div>
                <h4 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
                  <MessageSquare className="h-4 w-4" /> Comments ({taskDetail.comments.length})
                </h4>
                <div className="space-y-3 mb-3">
                  {taskDetail.comments.map((comment) => (
                    <div key={comment.id} className="bg-muted rounded-lg p-3">
                      <p className="text-sm">{comment.content}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {new Date(comment.created_at).toLocaleDateString("en-US", {
                          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                        })}
                      </p>
                    </div>
                  ))}
                </div>
                <form
                  onSubmit={(e) => { e.preventDefault(); handleAddComment(); }}
                  className="flex gap-2"
                >
                  <Input
                    placeholder="Add a comment..."
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    className="flex-1"
                  />
                  <Button type="submit" size="icon" disabled={!newComment.trim()}>
                    <Send className="h-4 w-4" />
                  </Button>
                </form>
              </div>

              <Separator />

              {/* Delete */}
              <Button variant="destructive" size="sm" onClick={handleDeleteTask} className="w-full">
                Delete Task
              </Button>
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* Add Task Dialog */}
      <Dialog open={!!addColumnId} onOpenChange={(open) => !open && setAddColumnId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Task</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleAddTask(); }} className="space-y-4">
            <div>
              <Label>Title *</Label>
              <Input
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
                placeholder="What needs to be done?"
                autoFocus
                required
              />
            </div>
            <div>
              <Label>Priority</Label>
              <Select value={newTaskPriority} onValueChange={setNewTaskPriority}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(PRIORITY_COLORS).map(([p, c]) => (
                    <SelectItem key={p} value={p}>
                      <div className="flex items-center gap-2">
                        <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: c }} />
                        <span className="capitalize">{p}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setAddColumnId(null)}>Cancel</Button>
              <Button type="submit" disabled={!newTaskTitle.trim()}>Create</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
