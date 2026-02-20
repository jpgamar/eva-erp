"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, LayoutGrid, CheckSquare, Clock } from "lucide-react";
import { toast } from "sonner";
import { boardsApi } from "@/lib/api/tasks";
import type { Board } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export default function TasksPage() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const fetchBoards = async () => {
    try {
      const data = await boardsApi.list();
      setBoards(data);
    } catch {
      toast.error("Failed to load boards");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchBoards(); }, []);

  const handleCreate = async () => {
    try {
      await boardsApi.create({ name, description: description || undefined });
      setAddOpen(false);
      setName("");
      setDescription("");
      toast.success("Board created");
      await fetchBoards();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to create board");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Task Boards</h1>
          <p className="text-muted-foreground text-sm">Organize work across Kanban boards</p>
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          <Plus className="h-4 w-4 mr-2" /> New Board
        </Button>
      </div>

      {boards.length === 0 ? (
        <Card className="text-center py-12">
          <CardContent>
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 mb-4">
              <LayoutGrid className="h-8 w-8 text-primary" />
            </div>
            <h2 className="text-lg font-semibold mb-1">No boards yet</h2>
            <p className="text-muted-foreground text-sm mb-4">Create your first board to start organizing tasks.</p>
            <Button onClick={() => setAddOpen(true)}>
              <Plus className="h-4 w-4 mr-2" /> Create Board
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {boards.map((board) => (
            <Link key={board.id} href={`/tasks/${board.slug}`}>
              <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg">{board.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
                    {board.description || "No description"}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {new Date(board.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {/* Create Board Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Board</DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleCreate(); }} className="space-y-4">
            <div>
              <Label>Board Name *</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Product Development" autoFocus required />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What is this board for?" rows={3} />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={!name.trim()}>Create Board</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
