"use client";

import { useEffect, useState } from "react";
import { Plus, Search, Calendar, Clock, Users, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { meetingsApi } from "@/lib/api/meetings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";

const TYPES = ["internal", "prospect", "customer", "partner"];
const TYPE_COLORS: Record<string, string> = {
  internal: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  prospect: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  customer: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  partner: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
};

interface MeetingEntry {
  id: string; title: string; date: string; duration_minutes: number | null;
  type: string; attendees: string[] | null; notes_markdown: string | null;
  action_items_json: any[] | null; prospect_id: string | null;
  customer_id: string | null; created_at: string;
}

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState<MeetingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [addOpen, setAddOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState<MeetingEntry | null>(null);

  const [form, setForm] = useState({
    title: "", date: "", duration_minutes: "60", type: "internal",
    attendees: "", notes_markdown: "",
  });

  const fetchData = async () => {
    try {
      const list = await meetingsApi.list({
        type: typeFilter !== "all" ? typeFilter : undefined,
        search: search || undefined,
      });
      setMeetings(list);
    } catch { toast.error("Failed to load"); } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [typeFilter, search]);

  const handleCreate = async () => {
    try {
      await meetingsApi.create({
        title: form.title,
        date: new Date(form.date).toISOString(),
        duration_minutes: form.duration_minutes ? parseInt(form.duration_minutes) : null,
        type: form.type,
        attendees: form.attendees ? form.attendees.split(",").map(s => s.trim()) : null,
        notes_markdown: form.notes_markdown || null,
      });
      toast.success("Meeting created");
      setAddOpen(false);
      setForm({ title: "", date: "", duration_minutes: "60", type: "internal", attendees: "", notes_markdown: "" });
      await fetchData();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const openDetail = async (m: MeetingEntry) => {
    try {
      const full = await meetingsApi.get(m.id);
      setDetail(full);
      setDetailOpen(true);
    } catch { toast.error("Failed to load meeting"); }
  };

  if (loading) return <div className="flex items-center justify-center h-[calc(100vh-8rem)]"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Meetings</h1><p className="text-muted-foreground text-sm">Meeting notes with action items</p></div>
        <Button size="sm" onClick={() => setAddOpen(true)}><Plus className="h-4 w-4 mr-2" /> New Meeting</Button>
      </div>

      <div className="flex gap-3 items-center">
        <div className="relative flex-1 max-w-sm"><Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" /><Input placeholder="Search meetings..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" /></div>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-[150px]"><SelectValue placeholder="Type" /></SelectTrigger>
          <SelectContent><SelectItem value="all">All</SelectItem>{TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      <Card>
        <Table>
          <TableHeader><TableRow><TableHead>Date</TableHead><TableHead>Title</TableHead><TableHead>Type</TableHead><TableHead>Attendees</TableHead><TableHead>Duration</TableHead><TableHead>Actions</TableHead></TableRow></TableHeader>
          <TableBody>
            {meetings.length === 0 ? (
              <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-8">No meetings yet.</TableCell></TableRow>
            ) : meetings.map((m) => {
              const done = m.action_items_json?.filter((a: any) => a.completed).length || 0;
              const total = m.action_items_json?.length || 0;
              return (
                <TableRow key={m.id} className="cursor-pointer hover:bg-accent/50" onClick={() => openDetail(m)}>
                  <TableCell className="text-sm">{new Date(m.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</TableCell>
                  <TableCell className="font-medium">{m.title}</TableCell>
                  <TableCell><Badge className={TYPE_COLORS[m.type] || ""}>{m.type}</Badge></TableCell>
                  <TableCell className="text-sm">{m.attendees?.join(", ") || "—"}</TableCell>
                  <TableCell className="text-sm">{m.duration_minutes ? `${m.duration_minutes}m` : "—"}</TableCell>
                  <TableCell className="text-sm">{total > 0 ? `${done}/${total}` : "—"}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>

      {/* Detail Sheet */}
      <Sheet open={detailOpen} onOpenChange={setDetailOpen}>
        <SheetContent className="w-[450px] sm:w-[550px] overflow-y-auto">
          {detail && (
            <div className="space-y-5 pt-4">
              <SheetHeader><SheetTitle className="text-left">{detail.title}</SheetTitle></SheetHeader>
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Calendar className="h-4 w-4" />
                {new Date(detail.date).toLocaleString()}
                {detail.duration_minutes && <><Clock className="h-4 w-4 ml-3" />{detail.duration_minutes}m</>}
              </div>
              <Badge className={TYPE_COLORS[detail.type] || ""}>{detail.type}</Badge>
              {detail.attendees && detail.attendees.length > 0 && (
                <div><Label className="text-xs text-muted-foreground">Attendees</Label><p className="text-sm">{detail.attendees.join(", ")}</p></div>
              )}
              {detail.notes_markdown && (
                <div><Label className="text-xs text-muted-foreground">Notes</Label><div className="text-sm whitespace-pre-wrap bg-muted rounded-lg p-3">{detail.notes_markdown}</div></div>
              )}
              {detail.action_items_json && detail.action_items_json.length > 0 && (
                <div>
                  <Label className="text-xs text-muted-foreground">Action Items</Label>
                  <div className="space-y-2 mt-2">
                    {detail.action_items_json.map((item: any, i: number) => (
                      <div key={i} className="flex items-start gap-2 bg-muted rounded-lg p-2">
                        <CheckCircle2 className={`h-4 w-4 mt-0.5 shrink-0 ${item.completed ? "text-green-500" : "text-muted-foreground"}`} />
                        <div>
                          <p className={`text-sm ${item.completed ? "line-through text-muted-foreground" : ""}`}>{item.description}</p>
                          {item.due_date && <p className="text-xs text-muted-foreground">Due: {item.due_date}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* Add Meeting Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent><DialogHeader><DialogTitle>New Meeting</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleCreate(); }} className="space-y-3">
            <div><Label>Title *</Label><Input value={form.title} onChange={(e) => setForm(f => ({ ...f, title: e.target.value }))} required /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Date & Time *</Label><Input type="datetime-local" value={form.date} onChange={(e) => setForm(f => ({ ...f, date: e.target.value }))} required /></div>
              <div><Label>Duration (min)</Label><Input type="number" value={form.duration_minutes} onChange={(e) => setForm(f => ({ ...f, duration_minutes: e.target.value }))} /></div>
            </div>
            <div><Label>Type</Label><Select value={form.type} onValueChange={(v) => setForm(f => ({ ...f, type: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Attendees (comma-separated)</Label><Input value={form.attendees} onChange={(e) => setForm(f => ({ ...f, attendees: e.target.value }))} placeholder="Jose Pedro, Gustavo, ..." /></div>
            <div><Label>Notes</Label><Textarea value={form.notes_markdown} onChange={(e) => setForm(f => ({ ...f, notes_markdown: e.target.value }))} rows={4} placeholder="Meeting notes..." /></div>
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button><Button type="submit">Create</Button></div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
