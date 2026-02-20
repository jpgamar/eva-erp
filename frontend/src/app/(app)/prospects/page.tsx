"use client";

import { useEffect, useState } from "react";
import { Plus, Search, Target, Phone, Mail, MessageSquare, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { prospectsApi } from "@/lib/api/prospects";
import { useAuth } from "@/lib/auth/context";
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

const STATUSES = ["identified", "contacted", "interested", "demo_scheduled", "demo_done", "proposal_sent", "negotiating", "won", "lost"];
const SOURCES = ["personal_network", "referral", "linkedin", "inbound_website", "event", "partner", "cold_outreach", "other"];
const INTERACTION_TYPES = ["call", "email", "whatsapp", "meeting", "demo", "note"];

const STATUS_COLORS: Record<string, string> = {
  identified: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  contacted: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  interested: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300",
  demo_scheduled: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  demo_done: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300",
  proposal_sent: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  negotiating: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  won: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  lost: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

function fmt(amount: number | null | undefined, currency = "MXN") {
  if (amount == null) return "—";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })} ${currency}`;
}

interface Prospect {
  id: string; company_name: string; contact_name: string; contact_email: string | null;
  contact_phone: string | null; contact_role: string | null; website: string | null;
  industry: string | null; status: string; source: string; referred_by: string | null;
  estimated_plan: string | null; estimated_mrr: number | null; estimated_mrr_currency: string;
  estimated_mrr_mxn: number | null; notes: string | null; next_follow_up: string | null;
  assigned_to: string | null; tags: string[] | null; lost_reason: string | null;
  converted_to_customer_id: string | null; created_at: string; updated_at: string;
}

interface Interaction {
  id: string; prospect_id: string; type: string; summary: string; date: string; created_at: string;
}

export default function ProspectsPage() {
  const { user } = useAuth();
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [addOpen, setAddOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detail, setDetail] = useState<Prospect | null>(null);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [interForm, setInterForm] = useState({ type: "call", summary: "", date: new Date().toISOString().split("T")[0] });

  const [form, setForm] = useState({
    company_name: "", contact_name: "", contact_email: "", contact_phone: "", contact_role: "",
    website: "", industry: "", source: "personal_network", referred_by: "",
    estimated_plan: "standard", estimated_mrr: "", estimated_mrr_currency: "MXN",
    notes: "", next_follow_up: "",
  });

  const fetchData = async () => {
    try {
      const [list, sum] = await Promise.all([
        prospectsApi.list({ status: statusFilter !== "all" ? statusFilter : undefined, search: search || undefined }),
        prospectsApi.summary(),
      ]);
      setProspects(list);
      setSummary(sum);
    } catch { toast.error("Failed to load"); } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [statusFilter, search]);

  const handleCreate = async () => {
    try {
      await prospectsApi.create({
        ...form,
        estimated_mrr: form.estimated_mrr ? parseFloat(form.estimated_mrr) : null,
        contact_email: form.contact_email || null,
        contact_phone: form.contact_phone || null,
        contact_role: form.contact_role || null,
        website: form.website || null,
        industry: form.industry || null,
        referred_by: form.referred_by || null,
        notes: form.notes || null,
        next_follow_up: form.next_follow_up || null,
        assigned_to: user?.id,
      });
      toast.success("Prospect added");
      setAddOpen(false);
      await fetchData();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const openDetail = async (p: Prospect) => {
    setDetail(p);
    setDetailOpen(true);
    try {
      const ints = await prospectsApi.listInteractions(p.id);
      setInteractions(ints);
    } catch { setInteractions([]); }
  };

  const handleAddInteraction = async () => {
    if (!detail || !interForm.summary.trim()) return;
    try {
      await prospectsApi.addInteraction(detail.id, interForm);
      toast.success("Interaction logged");
      const ints = await prospectsApi.listInteractions(detail.id);
      setInteractions(ints);
      setInterForm({ type: "call", summary: "", date: new Date().toISOString().split("T")[0] });
    } catch { toast.error("Failed"); }
  };

  const handleConvert = async () => {
    if (!detail) return;
    try {
      await prospectsApi.convert(detail.id);
      toast.success("Converted to customer!");
      setDetailOpen(false);
      await fetchData();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  if (loading) return <div className="flex items-center justify-center h-[calc(100vh-8rem)]"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Prospects</h1><p className="text-muted-foreground text-sm">Sales pipeline and follow-ups</p></div>
        <Button size="sm" onClick={() => setAddOpen(true)}><Plus className="h-4 w-4 mr-2" /> Add Prospect</Button>
      </div>

      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">Total Prospects</div><div className="text-2xl font-bold">{summary.total}</div></CardContent></Card>
          <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">Pipeline Value</div><div className="text-2xl font-bold">{fmt(summary.total_estimated_pipeline_mxn)}</div></CardContent></Card>
          <Card><CardContent className="pt-6"><div className="text-xs text-muted-foreground">Won</div><div className="text-2xl font-bold text-green-600">{summary.by_status?.won || 0}</div></CardContent></Card>
        </div>
      )}

      <div className="flex gap-3 items-center">
        <div className="relative flex-1 max-w-sm"><Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" /><Input placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" /></div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent><SelectItem value="all">All</SelectItem>{STATUSES.map(s => <SelectItem key={s} value={s}>{s.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      <Card>
        <Table>
          <TableHeader><TableRow><TableHead>Company</TableHead><TableHead>Contact</TableHead><TableHead>Status</TableHead><TableHead>Source</TableHead><TableHead>Referred By</TableHead><TableHead>Est. MRR</TableHead><TableHead>Follow-up</TableHead></TableRow></TableHeader>
          <TableBody>
            {prospects.length === 0 ? (
              <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground py-8">No prospects yet.</TableCell></TableRow>
            ) : prospects.map((p) => (
              <TableRow key={p.id} className="cursor-pointer hover:bg-accent/50" onClick={() => openDetail(p)}>
                <TableCell className="font-medium">{p.company_name}</TableCell>
                <TableCell>{p.contact_name}</TableCell>
                <TableCell><Badge className={STATUS_COLORS[p.status] || ""}>{p.status.replace(/_/g, " ")}</Badge></TableCell>
                <TableCell className="text-sm capitalize">{p.source.replace(/_/g, " ")}</TableCell>
                <TableCell className="text-sm">{p.referred_by || "—"}</TableCell>
                <TableCell className="font-medium">{fmt(p.estimated_mrr, p.estimated_mrr_currency)}</TableCell>
                <TableCell className={`text-sm ${p.next_follow_up && new Date(p.next_follow_up) <= new Date() ? "text-red-500 font-medium" : ""}`}>
                  {p.next_follow_up ? new Date(p.next_follow_up).toLocaleDateString() : "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {/* Detail Sheet */}
      <Sheet open={detailOpen} onOpenChange={setDetailOpen}>
        <SheetContent className="w-[450px] sm:w-[550px] overflow-y-auto">
          {detail && (
            <div className="space-y-5 pt-4">
              <SheetHeader><SheetTitle className="text-left">{detail.company_name}</SheetTitle></SheetHeader>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-xs text-muted-foreground">Contact</Label><p className="text-sm font-medium">{detail.contact_name}</p></div>
                  <div><Label className="text-xs text-muted-foreground">Status</Label><Badge className={STATUS_COLORS[detail.status] || ""}>{detail.status.replace(/_/g, " ")}</Badge></div>
                </div>
                {detail.referred_by && <div><Label className="text-xs text-muted-foreground">Referred By</Label><p className="text-sm">{detail.referred_by}</p></div>}
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-xs text-muted-foreground">Est. MRR</Label><p className="text-sm font-medium">{fmt(detail.estimated_mrr, detail.estimated_mrr_currency)}</p></div>
                  <div><Label className="text-xs text-muted-foreground">Plan</Label><p className="text-sm capitalize">{detail.estimated_plan || "—"}</p></div>
                </div>
                {detail.notes && <div><Label className="text-xs text-muted-foreground">Notes</Label><p className="text-sm whitespace-pre-wrap">{detail.notes}</p></div>}
              </div>
              <Separator />
              {/* Interactions */}
              <div>
                <h4 className="text-sm font-semibold mb-3">Interactions</h4>
                <div className="space-y-2 mb-3">
                  {interactions.map((i) => (
                    <div key={i.id} className="bg-muted rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant="secondary" className="text-xs">{i.type}</Badge>
                        <span className="text-xs text-muted-foreground">{new Date(i.date).toLocaleDateString()}</span>
                      </div>
                      <p className="text-sm">{i.summary}</p>
                    </div>
                  ))}
                </div>
                <div className="space-y-2">
                  <Select value={interForm.type} onValueChange={(v) => setInterForm(f => ({ ...f, type: v }))}>
                    <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                    <SelectContent>{INTERACTION_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                  </Select>
                  <Textarea value={interForm.summary} onChange={(e) => setInterForm(f => ({ ...f, summary: e.target.value }))} placeholder="What happened?" rows={2} />
                  <Button size="sm" onClick={handleAddInteraction} disabled={!interForm.summary.trim()}>Log Interaction</Button>
                </div>
              </div>
              <Separator />
              {detail.status === "won" && detail.converted_to_customer_id && <Badge variant="secondary">Converted to customer</Badge>}
              {detail.status !== "won" && detail.status !== "lost" && (
                <Button onClick={handleConvert} className="w-full"><ArrowRight className="h-4 w-4 mr-2" /> Convert to Customer</Button>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>

      {/* Add Prospect Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Add Prospect</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleCreate(); }} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Company *</Label><Input value={form.company_name} onChange={(e) => setForm(f => ({ ...f, company_name: e.target.value }))} required /></div>
              <div><Label>Contact *</Label><Input value={form.contact_name} onChange={(e) => setForm(f => ({ ...f, contact_name: e.target.value }))} required /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Source</Label><Select value={form.source} onValueChange={(v) => setForm(f => ({ ...f, source: v }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{SOURCES.map(s => <SelectItem key={s} value={s}>{s.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select></div>
              <div><Label>Referred By</Label><Input value={form.referred_by} onChange={(e) => setForm(f => ({ ...f, referred_by: e.target.value }))} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Est. MRR</Label><Input type="number" value={form.estimated_mrr} onChange={(e) => setForm(f => ({ ...f, estimated_mrr: e.target.value }))} /></div>
              <div><Label>Follow-up</Label><Input type="date" value={form.next_follow_up} onChange={(e) => setForm(f => ({ ...f, next_follow_up: e.target.value }))} /></div>
            </div>
            <div><Label>Notes</Label><Textarea value={form.notes} onChange={(e) => setForm(f => ({ ...f, notes: e.target.value }))} rows={2} /></div>
            <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button><Button type="submit">Add</Button></div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
