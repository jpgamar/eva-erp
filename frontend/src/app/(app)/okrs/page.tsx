"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/lib/auth/context";
import { okrsApi } from "@/lib/api/okrs";
import type { OKRPeriod, Objective, KeyResult } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  Trophy,
  Plus,
  ChevronDown,
  ChevronRight,
  Target,
  TrendingUp,
  Calendar,
} from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  on_track: "bg-green-500/10 text-green-600 border-green-500/20",
  at_risk: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
  behind: "bg-red-500/10 text-red-600 border-red-500/20",
  completed: "bg-blue-500/10 text-blue-600 border-blue-500/20",
};

const STATUS_LABELS: Record<string, string> = {
  on_track: "On Track",
  at_risk: "At Risk",
  behind: "Behind",
  completed: "Completed",
};

const PERIOD_COLORS: Record<string, string> = {
  active: "bg-green-500/10 text-green-600 border-green-500/20",
  upcoming: "bg-blue-500/10 text-blue-600 border-blue-500/20",
  completed: "bg-gray-500/10 text-gray-600 border-gray-500/20",
};

export default function OKRsPage() {
  const { user } = useAuth();
  const [periods, setPeriods] = useState<OKRPeriod[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<OKRPeriod | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedObjectives, setExpandedObjectives] = useState<Set<string>>(new Set());
  const [showNewPeriod, setShowNewPeriod] = useState(false);
  const [showNewObjective, setShowNewObjective] = useState(false);
  const [showNewKR, setShowNewKR] = useState<string | null>(null); // objective_id
  const [editKR, setEditKR] = useState<KeyResult | null>(null);

  const loadPeriods = useCallback(async () => {
    try {
      const data = await okrsApi.listPeriods();
      setPeriods(data);
      // Auto-select active period, or first
      const active = data.find((p: OKRPeriod) => p.status === "active") || data[0] || null;
      if (active) {
        const full = await okrsApi.getPeriod(active.id);
        setSelectedPeriod(full);
        // Expand all objectives by default
        setExpandedObjectives(new Set(full.objectives.map((o: Objective) => o.id)));
      }
    } catch {
      toast.error("Failed to load OKR periods");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadPeriods(); }, [loadPeriods]);

  const selectPeriod = async (periodId: string) => {
    try {
      const full = await okrsApi.getPeriod(periodId);
      setSelectedPeriod(full);
      setExpandedObjectives(new Set(full.objectives.map((o: Objective) => o.id)));
    } catch {
      toast.error("Failed to load period");
    }
  };

  const toggleObjective = (id: string) => {
    setExpandedObjectives(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const objectiveProgress = (obj: Objective) => {
    if (obj.key_results.length === 0) return 0;
    const total = obj.key_results.reduce((sum, kr) => sum + Number(kr.progress_pct), 0);
    return Math.round(total / obj.key_results.length);
  };

  const periodProgress = (period: OKRPeriod) => {
    if (period.objectives.length === 0) return 0;
    const total = period.objectives.reduce((sum, obj) => sum + objectiveProgress(obj), 0);
    return Math.round(total / period.objectives.length);
  };

  const handleCreatePeriod = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      await okrsApi.createPeriod({
        name: fd.get("name"),
        start_date: fd.get("start_date"),
        end_date: fd.get("end_date"),
        status: fd.get("status"),
      });
      toast.success("Period created");
      setShowNewPeriod(false);
      loadPeriods();
    } catch {
      toast.error("Failed to create period");
    }
  };

  const handleCreateObjective = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedPeriod || !user) return;
    const fd = new FormData(e.currentTarget);
    try {
      await okrsApi.createObjective({
        period_id: selectedPeriod.id,
        title: fd.get("title"),
        description: fd.get("description") || null,
        owner_id: user.id,
        position: selectedPeriod.objectives.length,
      });
      toast.success("Objective created");
      setShowNewObjective(false);
      selectPeriod(selectedPeriod.id);
    } catch {
      toast.error("Failed to create objective");
    }
  };

  const handleCreateKR = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!showNewKR || !selectedPeriod) return;
    const fd = new FormData(e.currentTarget);
    try {
      await okrsApi.createKeyResult({
        objective_id: showNewKR,
        title: fd.get("title"),
        target_value: parseFloat(fd.get("target_value") as string),
        unit: fd.get("unit") || "%",
        start_value: parseFloat((fd.get("start_value") as string) || "0"),
        tracking_mode: fd.get("tracking_mode") || "manual",
      });
      toast.success("Key Result created");
      setShowNewKR(null);
      selectPeriod(selectedPeriod.id);
    } catch {
      toast.error("Failed to create key result");
    }
  };

  const handleUpdateKRValue = async (kr: KeyResult, newValue: number) => {
    if (!selectedPeriod) return;
    try {
      await okrsApi.updateKeyResult(kr.id, { current_value: newValue });
      toast.success("Progress updated");
      setEditKR(null);
      selectPeriod(selectedPeriod.id);
    } catch {
      toast.error("Failed to update key result");
    }
  };

  const handleUpdateObjectiveStatus = async (obj: Objective, status: string) => {
    if (!selectedPeriod) return;
    try {
      await okrsApi.updateObjective(obj.id, { status });
      toast.success("Status updated");
      selectPeriod(selectedPeriod.id);
    } catch {
      toast.error("Failed to update status");
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 p-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-8 w-8 rounded-lg" />
          <Skeleton className="h-8 w-48" />
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
        {[1, 2].map(i => <Skeleton key={i} className="h-48 rounded-xl" />)}
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Trophy className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">OKRs</h1>
            <p className="text-sm text-muted-foreground">Objectives & Key Results</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Period Selector */}
          {periods.length > 0 && (
            <Select
              value={selectedPeriod?.id || ""}
              onValueChange={selectPeriod}
            >
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Select period" />
              </SelectTrigger>
              <SelectContent>
                {periods.map(p => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Dialog open={showNewPeriod} onOpenChange={setShowNewPeriod}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Calendar className="h-4 w-4 mr-1" /> New Period
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create OKR Period</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleCreatePeriod} className="space-y-4">
                <div>
                  <Label htmlFor="name">Name</Label>
                  <Input id="name" name="name" placeholder="Q1 2026" required />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="start_date">Start Date</Label>
                    <Input id="start_date" name="start_date" type="date" required />
                  </div>
                  <div>
                    <Label htmlFor="end_date">End Date</Label>
                    <Input id="end_date" name="end_date" type="date" required />
                  </div>
                </div>
                <div>
                  <Label htmlFor="status">Status</Label>
                  <Select name="status" defaultValue="upcoming">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="upcoming">Upcoming</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="completed">Completed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button type="submit" className="w-full">Create Period</Button>
              </form>
            </DialogContent>
          </Dialog>
          {selectedPeriod && (
            <Dialog open={showNewObjective} onOpenChange={setShowNewObjective}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="h-4 w-4 mr-1" /> Objective
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create Objective</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleCreateObjective} className="space-y-4">
                  <div>
                    <Label htmlFor="obj-title">Title</Label>
                    <Input id="obj-title" name="title" placeholder="Increase revenue by 30%" required />
                  </div>
                  <div>
                    <Label htmlFor="obj-desc">Description</Label>
                    <Textarea id="obj-desc" name="description" placeholder="Optional description..." rows={3} />
                  </div>
                  <Button type="submit" className="w-full">Create Objective</Button>
                </form>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Period Summary Cards */}
      {selectedPeriod && (
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Overall Progress</p>
                  <p className="text-3xl font-bold">{periodProgress(selectedPeriod)}%</p>
                </div>
                <TrendingUp className="h-8 w-8 text-muted-foreground/30" />
              </div>
              <Progress value={periodProgress(selectedPeriod)} className="mt-3" />
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Objectives</p>
                  <p className="text-3xl font-bold">{selectedPeriod.objectives.length}</p>
                </div>
                <Target className="h-8 w-8 text-muted-foreground/30" />
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {selectedPeriod.objectives.reduce((sum, o) => sum + o.key_results.length, 0)} Key Results
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Period</p>
                  <p className="text-lg font-semibold">{selectedPeriod.name}</p>
                </div>
                <Badge variant="outline" className={PERIOD_COLORS[selectedPeriod.status] || ""}>
                  {selectedPeriod.status}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {selectedPeriod.start_date} → {selectedPeriod.end_date}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Empty State */}
      {!selectedPeriod && !loading && (
        <Card className="py-16 text-center">
          <CardContent>
            <Trophy className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
            <h3 className="text-lg font-semibold mb-2">No OKR Periods Yet</h3>
            <p className="text-muted-foreground mb-4">Create your first quarter to start tracking objectives.</p>
            <Button onClick={() => setShowNewPeriod(true)}>
              <Plus className="h-4 w-4 mr-1" /> Create Period
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Objectives */}
      {selectedPeriod && selectedPeriod.objectives.length === 0 && (
        <Card className="py-12 text-center">
          <CardContent>
            <Target className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
            <h3 className="text-lg font-semibold mb-2">No Objectives</h3>
            <p className="text-sm text-muted-foreground mb-4">Add your first objective for this period.</p>
            <Button onClick={() => setShowNewObjective(true)} size="sm">
              <Plus className="h-4 w-4 mr-1" /> Add Objective
            </Button>
          </CardContent>
        </Card>
      )}

      {selectedPeriod?.objectives.map(obj => {
        const expanded = expandedObjectives.has(obj.id);
        const progress = objectiveProgress(obj);

        return (
          <Card key={obj.id}>
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 shrink-0 mt-0.5"
                    onClick={() => toggleObjective(obj.id)}
                  >
                    {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </Button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <CardTitle className="text-base">{obj.title}</CardTitle>
                      <Badge
                        variant="outline"
                        className={`text-xs cursor-pointer ${STATUS_COLORS[obj.status] || ""}`}
                      >
                        {STATUS_LABELS[obj.status] || obj.status}
                      </Badge>
                    </div>
                    {obj.description && (
                      <p className="text-sm text-muted-foreground mt-1">{obj.description}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-4">
                  <div className="text-right">
                    <span className="text-lg font-bold">{progress}%</span>
                    <p className="text-xs text-muted-foreground">{obj.key_results.length} KRs</p>
                  </div>
                  <Select
                    value={obj.status}
                    onValueChange={(val) => handleUpdateObjectiveStatus(obj, val)}
                  >
                    <SelectTrigger className="w-28 h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="on_track">On Track</SelectItem>
                      <SelectItem value="at_risk">At Risk</SelectItem>
                      <SelectItem value="behind">Behind</SelectItem>
                      <SelectItem value="completed">Completed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Progress value={progress} className="mt-2" />
            </CardHeader>

            {expanded && (
              <CardContent className="pt-0 space-y-3">
                {obj.key_results.map(kr => (
                  <div
                    key={kr.id}
                    className="flex items-center gap-4 p-3 rounded-lg bg-muted/50 hover:bg-muted/80 transition-colors cursor-pointer"
                    onClick={() => setEditKR(kr)}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{kr.title}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Progress value={Number(kr.progress_pct)} className="flex-1 h-2" />
                        <span className="text-xs text-muted-foreground shrink-0">
                          {Number(kr.current_value)} / {Number(kr.target_value)} {kr.unit}
                        </span>
                      </div>
                    </div>
                    <span className="text-sm font-semibold shrink-0">
                      {Number(kr.progress_pct)}%
                    </span>
                  </div>
                ))}

                <Dialog open={showNewKR === obj.id} onOpenChange={(open) => setShowNewKR(open ? obj.id : null)}>
                  <DialogTrigger asChild>
                    <Button variant="ghost" size="sm" className="w-full border-dashed border">
                      <Plus className="h-4 w-4 mr-1" /> Add Key Result
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Add Key Result</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={handleCreateKR} className="space-y-4">
                      <div>
                        <Label htmlFor="kr-title">Title</Label>
                        <Input id="kr-title" name="title" placeholder="Achieve $10k MRR" required />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label htmlFor="kr-target">Target Value</Label>
                          <Input id="kr-target" name="target_value" type="number" step="0.01" placeholder="100" required />
                        </div>
                        <div>
                          <Label htmlFor="kr-unit">Unit</Label>
                          <Input id="kr-unit" name="unit" placeholder="%" defaultValue="%" />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label htmlFor="kr-start">Start Value</Label>
                          <Input id="kr-start" name="start_value" type="number" step="0.01" defaultValue="0" />
                        </div>
                        <div>
                          <Label htmlFor="kr-mode">Tracking Mode</Label>
                          <Select name="tracking_mode" defaultValue="manual">
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="manual">Manual</SelectItem>
                              <SelectItem value="auto">Auto</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <Button type="submit" className="w-full">Add Key Result</Button>
                    </form>
                  </DialogContent>
                </Dialog>
              </CardContent>
            )}
          </Card>
        );
      })}

      {/* Edit Key Result Sheet */}
      <Sheet open={!!editKR} onOpenChange={(open) => !open && setEditKR(null)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Update Key Result</SheetTitle>
          </SheetHeader>
          {editKR && (
            <div className="mt-6 space-y-6">
              <div>
                <h3 className="font-semibold">{editKR.title}</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {Number(editKR.start_value)} → {Number(editKR.target_value)} {editKR.unit}
                </p>
              </div>

              <div>
                <Label className="text-sm text-muted-foreground">Current Progress</Label>
                <div className="mt-2">
                  <Progress value={Number(editKR.progress_pct)} className="h-3" />
                  <p className="text-center text-2xl font-bold mt-2">{Number(editKR.progress_pct)}%</p>
                </div>
              </div>

              <div>
                <Label htmlFor="kr-current">Current Value</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    id="kr-current"
                    type="number"
                    step="0.01"
                    defaultValue={Number(editKR.current_value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        handleUpdateKRValue(editKR, parseFloat((e.target as HTMLInputElement).value));
                      }
                    }}
                  />
                  <span className="flex items-center text-sm text-muted-foreground">{editKR.unit}</span>
                </div>
              </div>

              <div className="flex gap-2">
                {[25, 50, 75, 100].map(pct => {
                  const value = Number(editKR.start_value) + (Number(editKR.target_value) - Number(editKR.start_value)) * pct / 100;
                  return (
                    <Button
                      key={pct}
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      onClick={() => handleUpdateKRValue(editKR, value)}
                    >
                      {pct}%
                    </Button>
                  );
                })}
              </div>

              <Button
                className="w-full"
                onClick={() => {
                  const input = document.getElementById("kr-current") as HTMLInputElement;
                  if (input) handleUpdateKRValue(editKR, parseFloat(input.value));
                }}
              >
                Save Progress
              </Button>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
