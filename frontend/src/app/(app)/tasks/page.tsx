"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Plus, Search, Send, MessageSquare, X, CalendarDays, Trash2,
  FolderOpen, LayoutList, Columns3,
} from "lucide-react";
import { toast } from "sonner";
import { tasksApi, boardsApi } from "@/lib/api/tasks";
import { usersApi } from "@/lib/api/users";
import type { Task, TaskDetail, Board, User } from "@/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { KanbanBoard } from "@/components/kanban/kanban-board";

const STATUSES = ["todo", "in_progress", "done"] as const;

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  todo: { label: "To Do", color: "bg-gray-100 text-gray-600" },
  in_progress: { label: "In Progress", color: "bg-blue-50 text-blue-700" },
  done: { label: "Done", color: "bg-green-50 text-green-700" },
};

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: "Low", color: "bg-green-50 text-green-700" },
  medium: { label: "Medium", color: "bg-amber-50 text-amber-700" },
  high: { label: "High", color: "bg-red-50 text-red-700" },
  urgent: { label: "Urgent", color: "bg-red-100 text-red-800" },
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [boards, setBoards] = useState<Board[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [boardFilter, setBoardFilter] = useState<string | null>(null);
  const [assigneeFilter, setAssigneeFilter] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<"table" | "board">("board");

  // Dialogs
  const [addOpen, setAddOpen] = useState(false);
  const [addBoardOpen, setAddBoardOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [taskDetail, setTaskDetail] = useState<TaskDetail | null>(null);

  // New task form
  const [form, setForm] = useState({ title: "", description: "", priority: "medium", due_date: "", status: "todo", board_id: "", assignee_id: "" });

  // New board form
  const [boardForm, setBoardForm] = useState({ name: "", description: "" });

  // Comment
  const [newComment, setNewComment] = useState("");

  const fetchBoards = async () => {
    try { setBoards(await boardsApi.list()); } catch { /* optional */ }
  };

  const fetchUsers = async () => {
    try { setUsers(await usersApi.list()); } catch { /* optional */ }
  };

  const getUserName = (id: string | null) => {
    if (!id) return null;
    const user = users.find((u) => u.id === id);
    return user?.name ?? null;
  };

  const fetchTasks = useCallback(async () => {
    try {
      const params: Record<string, string> = {};
      if (statusFilter !== "all") params.status = statusFilter;
      if (boardFilter) params.board_id = boardFilter;
      setTasks(await tasksApi.list(params));
    } catch {
      toast.error("Failed to load tasks");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, boardFilter]);

  useEffect(() => { fetchBoards(); fetchUsers(); }, []);
  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  const filtered = tasks.filter((t) => {
    if (search && !t.title.toLowerCase().includes(search.toLowerCase())) return false;
    if (assigneeFilter && t.assignee_id !== assigneeFilter) return false;
    return true;
  });

  const handleCreate = async () => {
    try {
      await tasksApi.create({
        title: form.title,
        description: form.description || undefined,
        priority: form.priority,
        due_date: form.due_date || undefined,
        status: form.status,
        board_id: form.board_id || undefined,
        assignee_id: form.assignee_id || undefined,
      });
      setAddOpen(false);
      setForm({ title: "", description: "", priority: "medium", due_date: "", status: "todo", board_id: boardFilter ?? "", assignee_id: "" });
      toast.success("Task created");
      await fetchTasks();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to create task");
    }
  };

  const handleCreateBoard = async () => {
    try {
      await boardsApi.create({ name: boardForm.name, description: boardForm.description || undefined });
      setAddBoardOpen(false);
      setBoardForm({ name: "", description: "" });
      toast.success("Board created");
      await fetchBoards();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to create board");
    }
  };

  const handleDeleteBoard = async (id: string) => {
    try {
      await boardsApi.delete(id);
      if (boardFilter === id) setBoardFilter(null);
      toast.success("Board deleted");
      await Promise.all([fetchBoards(), fetchTasks()]);
    } catch { toast.error("Failed to delete board"); }
  };

  const openDetail = async (id: string) => {
    try {
      setTaskDetail(await tasksApi.get(id));
      setDetailOpen(true);
    } catch { toast.error("Failed to load task"); }
  };

  const handleUpdate = async (field: string, value: any) => {
    if (!taskDetail) return;
    try {
      const updated = await tasksApi.update(taskDetail.id, { [field]: value });
      setTaskDetail((p) => (p ? { ...p, ...updated } : p));
      await fetchTasks();
    } catch { toast.error("Failed to update task"); }
  };

  const handleDelete = async () => {
    if (!taskDetail) return;
    try {
      await tasksApi.delete(taskDetail.id);
      setDetailOpen(false);
      setTaskDetail(null);
      toast.success("Task deleted");
      await fetchTasks();
    } catch { toast.error("Failed to delete task"); }
  };

  const handleAddComment = async () => {
    if (!taskDetail || !newComment.trim()) return;
    try {
      const comment = await tasksApi.addComment(taskDetail.id, newComment);
      setTaskDetail((p) => (p ? { ...p, comments: [...p.comments, comment] } : p));
      setNewComment("");
    } catch { toast.error("Failed to add comment"); }
  };

  const isOverdue = (d: string | null) => d ? new Date(d) < new Date(new Date().toISOString().split("T")[0]) : false;

  const handleKanbanStatusChange = async (taskId: string, newStatus: string) => {
    setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t)));
    try {
      await tasksApi.update(taskId, { status: newStatus });
    } catch {
      await fetchTasks();
      toast.error("Failed to update status");
    }
  };

  const kanbanColumns = STATUSES
    .filter((s) => statusFilter === "all" || s === statusFilter)
    .map((s) => ({ id: s, label: STATUS_CONFIG[s].label, color: STATUS_CONFIG[s].color }));

  const renderTaskCard = (task: Task) => {
    const pCfg = PRIORITY_CONFIG[task.priority];
    const overdue = isOverdue(task.due_date) && task.status !== "done";
    return (
      <div className="space-y-2">
        <p className="text-sm font-medium text-foreground leading-snug">{task.title}</p>
        <div className="flex items-center gap-2 flex-wrap">
          <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", pCfg?.color)}>
            {pCfg?.label}
          </span>
          {task.due_date && (
            <span className={cn("flex items-center gap-1 text-[10px]", overdue ? "font-medium text-red-600" : "text-muted-foreground")}>
              <CalendarDays className="h-2.5 w-2.5" />
              {new Date(task.due_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
            </span>
          )}
        </div>
        {getUserName(task.assignee_id) && (
          <p className="text-[10px] text-muted-foreground">{getUserName(task.assignee_id)}</p>
        )}
      </div>
    );
  };

  const showBoardCol = !boardFilter && boards.length > 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <div className="animate-spin h-8 w-8 border-4 border-accent border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-5 animate-erp-entrance">
      {/* Board chips */}
      {boards.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setBoardFilter(null)}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium transition-all",
              !boardFilter
                ? "bg-accent text-white shadow-sm"
                : "border border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
            )}
          >
            All
          </button>
          {boards.map((board) => (
            <div key={board.id} className="group relative">
              <button
                onClick={() => setBoardFilter(boardFilter === board.id ? null : board.id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium transition-all",
                  boardFilter === board.id
                    ? "bg-accent text-white shadow-sm"
                    : "border border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
                )}
              >
                <FolderOpen className="h-3 w-3" />
                {board.name}
              </button>
              <button
                onClick={() => handleDeleteBoard(board.id)}
                className="absolute -right-1.5 -top-1.5 hidden h-4 w-4 items-center justify-center rounded-full bg-red-500 text-white group-hover:flex"
              >
                <X className="h-2.5 w-2.5" />
              </button>
            </div>
          ))}
          <button
            onClick={() => setAddBoardOpen(true)}
            className="flex items-center gap-1 rounded-full border border-dashed border-gray-300 px-3 py-1.5 text-xs text-gray-400 transition-colors hover:border-gray-400 hover:text-gray-600"
          >
            <Plus className="h-3 w-3" />
            Board
          </button>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tasks..."
              className="h-9 w-56 rounded-lg bg-gray-100 pl-9 pr-3 text-sm outline-none transition-colors placeholder:text-muted focus:bg-white focus:ring-2 focus:ring-accent/20"
            />
          </div>
          <div className="flex gap-1">
            <button
              onClick={() => setStatusFilter("all")}
              className={cn(
                "rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
                statusFilter === "all" ? "bg-gray-200 text-foreground" : "text-gray-400 hover:text-gray-600"
              )}
            >
              All
            </button>
            {STATUSES.map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(statusFilter === s ? "all" : s)}
                className={cn(
                  "rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
                  statusFilter === s ? STATUS_CONFIG[s].color : "text-gray-400 hover:text-gray-600"
                )}
              >
                {STATUS_CONFIG[s].label}
              </button>
            ))}
          </div>
          {users.length > 0 && (
            <select
              value={assigneeFilter ?? ""}
              onChange={(e) => setAssigneeFilter(e.target.value || null)}
              className="h-8 rounded-lg border border-gray-200 bg-gray-50/80 px-2.5 text-xs outline-none transition-all focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20"
            >
              <option value="">All members</option>
              {users.filter((u) => u.is_active).map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-0.5 rounded-lg border border-gray-200 p-0.5">
            <button
              onClick={() => setViewMode("board")}
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-md transition-colors",
                viewMode === "board" ? "bg-gray-200 text-foreground" : "text-gray-400 hover:text-gray-600"
              )}
              title="Board view"
            >
              <Columns3 className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-md transition-colors",
                viewMode === "table" ? "bg-gray-200 text-foreground" : "text-gray-400 hover:text-gray-600"
              )}
              title="Table view"
            >
              <LayoutList className="h-3.5 w-3.5" />
            </button>
          </div>
          <button
            onClick={() => { setForm((f) => ({ ...f, board_id: boardFilter ?? "" })); setAddOpen(true); }}
            className="flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98]"
          >
            <Plus className="h-4 w-4" />
            New Task
          </button>
        </div>
      </div>

      {/* Task Table / Kanban Board */}
      {viewMode === "board" ? (
        <KanbanBoard
          columns={kanbanColumns}
          items={filtered}
          renderCard={renderTaskCard}
          onStatusChange={handleKanbanStatusChange}
          onCardClick={(task) => openDetail(task.id)}
        />
      ) : (
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50/80">
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[100px]">Status</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Task</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[120px]">Assignee</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[90px]">Priority</TableHead>
              {showBoardCol && (
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[120px]">Board</TableHead>
              )}
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted w-[100px]">Due</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={showBoardCol ? 6 : 5} className="text-center text-muted py-12">
                  No tasks yet.
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((task) => {
                const sCfg = STATUS_CONFIG[task.status];
                const pCfg = PRIORITY_CONFIG[task.priority];
                const overdue = isOverdue(task.due_date) && task.status !== "done";
                const board = boards.find((b) => b.id === task.board_id);
                return (
                  <TableRow
                    key={task.id}
                    className="cursor-pointer transition-colors hover:bg-gray-50/60"
                    onClick={() => openDetail(task.id)}
                  >
                    <TableCell>
                      <span className={cn("rounded-full px-2.5 py-0.5 text-[11px] font-medium", sCfg?.color)}>
                        {sCfg?.label}
                      </span>
                    </TableCell>
                    <TableCell className="font-medium text-foreground">{task.title}</TableCell>
                    <TableCell>
                      {getUserName(task.assignee_id) ? (
                        <span className="text-xs text-muted-foreground">{getUserName(task.assignee_id)}</span>
                      ) : (
                        <span className="text-xs text-gray-300">&mdash;</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className={cn("rounded-full px-2.5 py-0.5 text-[11px] font-medium", pCfg?.color)}>
                        {pCfg?.label}
                      </span>
                    </TableCell>
                    {showBoardCol && (
                      <TableCell>
                        {board ? (
                          <span className="text-xs text-muted-foreground">{board.name}</span>
                        ) : (
                          <span className="text-xs text-gray-300">&mdash;</span>
                        )}
                      </TableCell>
                    )}
                    <TableCell>
                      {task.due_date ? (
                        <span className={cn("flex items-center gap-1 text-xs", overdue ? "font-medium text-red-600" : "text-muted-foreground")}>
                          <CalendarDays className="h-3 w-3" />
                          {new Date(task.due_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-300">&mdash;</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
      )}

      {/* ── New Task Dialog ── */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-md overflow-hidden rounded-xl p-0">
          <DialogHeader className="sr-only"><DialogTitle>New Task</DialogTitle></DialogHeader>
          <div className="border-b border-border bg-gray-50/80 px-6 py-4">
            <h2 className="text-sm font-bold text-foreground">New Task</h2>
            <p className="text-xs text-muted mt-0.5">What needs to be done?</p>
          </div>
          <form onSubmit={(e) => { e.preventDefault(); handleCreate(); }} className="space-y-4 px-6 pb-6 pt-5">
            <div>
              <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Title *</label>
              <input
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="e.g. Review pull request"
                autoFocus
                required
                className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all placeholder:text-gray-300 focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Description</label>
              <Textarea
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Add details..."
                rows={2}
                className="rounded-lg border-gray-200 bg-gray-50/80 text-sm placeholder:text-gray-300"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Status</label>
                <div className="flex flex-wrap gap-1.5">
                  {STATUSES.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, status: s }))}
                      className={cn(
                        "rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
                        form.status === s ? STATUS_CONFIG[s].color : "border border-gray-200 text-gray-400 hover:border-gray-300"
                      )}
                    >
                      {STATUS_CONFIG[s].label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Priority</label>
                <div className="flex flex-wrap gap-1.5">
                  {(["low", "medium", "high", "urgent"] as const).map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, priority: p }))}
                      className={cn(
                        "rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
                        form.priority === p ? PRIORITY_CONFIG[p].color : "border border-gray-200 text-gray-400 hover:border-gray-300"
                      )}
                    >
                      {PRIORITY_CONFIG[p].label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Assign To</label>
              <select
                value={form.assignee_id}
                onChange={(e) => setForm((f) => ({ ...f, assignee_id: e.target.value }))}
                className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20"
              >
                <option value="">Unassigned</option>
                {users.filter((u) => u.is_active).map((u) => (
                  <option key={u.id} value={u.id}>{u.name}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Due Date</label>
                <input
                  type="date"
                  value={form.due_date}
                  onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                  className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20"
                />
              </div>
              {boards.length > 0 && (
                <div>
                  <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Board</label>
                  <select
                    value={form.board_id}
                    onChange={(e) => setForm((f) => ({ ...f, board_id: e.target.value }))}
                    className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20"
                  >
                    <option value="">No board</option>
                    {boards.map((b) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={() => setAddOpen(false)} className="h-9 rounded-lg border border-gray-200 px-4 text-sm font-medium text-muted transition-colors hover:bg-gray-50 hover:text-foreground">
                Cancel
              </button>
              <button
                type="submit"
                disabled={!form.title.trim()}
                className="flex h-9 items-center gap-1.5 rounded-lg bg-accent px-5 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-40"
              >
                Create
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* ── New Board Dialog ── */}
      <Dialog open={addBoardOpen} onOpenChange={setAddBoardOpen}>
        <DialogContent className="max-w-sm overflow-hidden rounded-xl p-0">
          <DialogHeader className="sr-only"><DialogTitle>New Board</DialogTitle></DialogHeader>
          <div className="border-b border-border bg-gray-50/80 px-6 py-4">
            <h2 className="text-sm font-bold text-foreground">New Board</h2>
          </div>
          <form onSubmit={(e) => { e.preventDefault(); handleCreateBoard(); }} className="space-y-4 px-6 pb-6 pt-5">
            <div>
              <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Name *</label>
              <input
                value={boardForm.name}
                onChange={(e) => setBoardForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="e.g. Product Development"
                autoFocus
                required
                className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all placeholder:text-gray-300 focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Description</label>
              <input
                value={boardForm.description}
                onChange={(e) => setBoardForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="Optional..."
                className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all placeholder:text-gray-300 focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setAddBoardOpen(false)} className="h-9 rounded-lg border border-gray-200 px-4 text-sm font-medium text-muted transition-colors hover:bg-gray-50 hover:text-foreground">
                Cancel
              </button>
              <button type="submit" disabled={!boardForm.name.trim()} className="flex h-9 items-center gap-1.5 rounded-lg bg-accent px-5 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-40">
                Create
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* ── Task Detail Sheet ── */}
      <Sheet open={detailOpen} onOpenChange={setDetailOpen}>
        <SheetContent className="w-[480px] sm:w-[520px] overflow-y-auto border-l border-border p-0">
          <SheetTitle className="sr-only">Task Details</SheetTitle>
          {taskDetail && (
            <div className="flex h-full flex-col">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-border bg-gray-50/80 px-6 py-4">
                <div className="flex-1 min-w-0 mr-3">
                  <input
                    value={taskDetail.title}
                    onChange={(e) => setTaskDetail((p) => p ? { ...p, title: e.target.value } : p)}
                    onBlur={(e) => handleUpdate("title", e.target.value)}
                    className="w-full bg-transparent text-base font-bold text-foreground outline-none"
                  />
                </div>
                <button
                  onClick={() => setDetailOpen(false)}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted transition-colors hover:bg-gray-200 hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="flex-1 px-6 py-5 space-y-5">
                {/* Status */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Status</label>
                  <div className="flex gap-1.5">
                    {STATUSES.map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => { setTaskDetail((p) => p ? { ...p, status: s } : p); handleUpdate("status", s); }}
                        className={cn(
                          "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                          taskDetail.status === s ? STATUS_CONFIG[s].color : "border border-gray-200 text-gray-400 hover:border-gray-300"
                        )}
                      >
                        {STATUS_CONFIG[s].label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Priority */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Priority</label>
                  <div className="flex gap-1.5">
                    {(["low", "medium", "high", "urgent"] as const).map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => handleUpdate("priority", p)}
                        className={cn(
                          "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                          taskDetail.priority === p ? PRIORITY_CONFIG[p].color : "border border-gray-200 text-gray-400 hover:border-gray-300"
                        )}
                      >
                        {PRIORITY_CONFIG[p].label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Assignee */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Assignee</label>
                  <select
                    value={taskDetail.assignee_id ?? ""}
                    onChange={(e) => handleUpdate("assignee_id", e.target.value || null)}
                    className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20"
                  >
                    <option value="">Unassigned</option>
                    {users.filter((u) => u.is_active).map((u) => (
                      <option key={u.id} value={u.id}>{u.name}</option>
                    ))}
                  </select>
                </div>

                {/* Due date + Board */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Due Date</label>
                    <input
                      type="date"
                      value={taskDetail.due_date ?? ""}
                      onChange={(e) => handleUpdate("due_date", e.target.value || null)}
                      className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20"
                    />
                  </div>
                  {boards.length > 0 && (
                    <div>
                      <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Board</label>
                      <select
                        value={taskDetail.board_id ?? ""}
                        onChange={(e) => handleUpdate("board_id", e.target.value || null)}
                        className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20"
                      >
                        <option value="">No board</option>
                        {boards.map((b) => (
                          <option key={b.id} value={b.id}>{b.name}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>

                {/* Description */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Description</label>
                  <Textarea
                    value={taskDetail.description ?? ""}
                    onChange={(e) => setTaskDetail((p) => p ? { ...p, description: e.target.value } : p)}
                    onBlur={(e) => handleUpdate("description", e.target.value || null)}
                    rows={3}
                    placeholder="Add a description..."
                    className="rounded-lg border-gray-200 bg-gray-50/80 text-sm placeholder:text-gray-300"
                  />
                </div>

                {/* Labels */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted">Labels</label>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {taskDetail.labels?.map((label) => (
                      <span
                        key={label}
                        onClick={() => handleUpdate("labels", taskDetail.labels?.filter((l) => l !== label) ?? [])}
                        className="flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600 cursor-pointer hover:bg-red-50 hover:text-red-600 transition-colors"
                      >
                        {label} <X className="h-2.5 w-2.5" />
                      </span>
                    ))}
                    <input
                      placeholder="Add label..."
                      className="h-6 w-20 rounded bg-transparent text-xs outline-none placeholder:text-gray-300"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && (e.target as HTMLInputElement).value.trim()) {
                          handleUpdate("labels", [...(taskDetail.labels ?? []), (e.target as HTMLInputElement).value.trim()]);
                          (e.target as HTMLInputElement).value = "";
                        }
                      }}
                    />
                  </div>
                </div>

                {/* Comments */}
                <div className="border-t border-border pt-5">
                  <h4 className="mb-3 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">
                    <MessageSquare className="h-3.5 w-3.5" /> Comments ({taskDetail.comments.length})
                  </h4>
                  <div className="space-y-2.5 mb-3">
                    {taskDetail.comments.map((c) => (
                      <div key={c.id} className="rounded-lg bg-gray-50 p-3">
                        <p className="text-sm text-foreground">{c.content}</p>
                        <p className="mt-1 text-[10px] text-muted">
                          {new Date(c.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                        </p>
                      </div>
                    ))}
                  </div>
                  <form onSubmit={(e) => { e.preventDefault(); handleAddComment(); }} className="flex gap-2">
                    <input
                      placeholder="Add a comment..."
                      value={newComment}
                      onChange={(e) => setNewComment(e.target.value)}
                      className="h-9 flex-1 rounded-lg border border-gray-200 bg-gray-50/80 px-3 text-sm outline-none transition-all placeholder:text-gray-300 focus:border-accent focus:bg-white focus:ring-2 focus:ring-accent/20"
                    />
                    <button
                      type="submit"
                      disabled={!newComment.trim()}
                      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition-all hover:opacity-90 disabled:opacity-40"
                    >
                      <Send className="h-3.5 w-3.5" />
                    </button>
                  </form>
                </div>
              </div>

              {/* Footer */}
              <div className="border-t border-border px-6 py-4">
                <button
                  onClick={handleDelete}
                  className="flex h-9 w-full items-center justify-center gap-1.5 rounded-lg border border-red-200 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 active:scale-[0.98]"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete Task
                </button>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* Empty state — show when no boards exist */}
      {boards.length === 0 && (
        <div className="text-center py-2">
          <button
            onClick={() => setAddBoardOpen(true)}
            className="text-xs text-gray-400 hover:text-accent transition-colors"
          >
            + Create your first board to organize tasks
          </button>
        </div>
      )}
    </div>
  );
}
