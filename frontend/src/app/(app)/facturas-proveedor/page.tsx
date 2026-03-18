"use client";

import { useEffect, useState } from "react";
import { Plus, FileText } from "lucide-react";
import { toast } from "sonner";
import { facturasProveedorApi } from "@/lib/api/pagos";
import { proveedoresApi } from "@/lib/api/proveedores";
import { exchangeRateApi } from "@/lib/api/finances";
import { useAuth } from "@/lib/auth/context";
import type { FacturaProveedor, Proveedor } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

function fmt(amount: number | null | undefined, currency = "USD") {
  if (amount == null) return "-";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

const STATUS_STYLES: Record<string, string> = {
  pendiente: "bg-yellow-50 text-yellow-700",
  parcial: "bg-blue-50 text-blue-700",
  pagada: "bg-green-50 text-green-700",
  cancelada: "bg-gray-100 text-gray-500",
};

const EMPTY_FORM = {
  proveedor_id: "", invoice_number: "", description: "", subtotal: "",
  tax: "0", currency: "USD", exchange_rate: "",
  issue_date: new Date().toISOString().split("T")[0], due_date: "", notes: "",
};

export default function FacturasProveedorPage() {
  const { user } = useAuth();
  const [facturas, setFacturas] = useState<FacturaProveedor[]>([]);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [currentRate, setCurrentRate] = useState<number | null>(null);

  const fetchAll = async () => {
    try {
      const params = filterStatus !== "all" ? { status: filterStatus } : undefined;
      const [list, provs, rate] = await Promise.all([
        facturasProveedorApi.list(params),
        proveedoresApi.list(),
        exchangeRateApi.current().catch(() => null),
      ]);
      setFacturas(list);
      setProveedores(provs);
      if (rate) setCurrentRate(rate.rate);
    } catch { toast.error("Error loading data"); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchAll(); }, [filterStatus]);

  const handleCreate = async () => {
    try {
      const payload = {
        ...form,
        subtotal: parseFloat(form.subtotal),
        tax: parseFloat(form.tax || "0"),
        exchange_rate: form.exchange_rate ? parseFloat(form.exchange_rate) : undefined,
        due_date: form.due_date || null,
        description: form.description || null,
        notes: form.notes || null,
      };
      await facturasProveedorApi.create(payload);
      toast.success("Factura registrada");
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      await fetchAll();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Error"); }
  };

  const handleCancel = async (f: FacturaProveedor) => {
    if (!window.confirm(`Cancelar factura #${f.invoice_number}?`)) return;
    try {
      await facturasProveedorApi.cancel(f.id);
      toast.success("Factura cancelada");
      await fetchAll();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Error"); }
  };

  // Totals
  const totals = facturas.reduce((acc, f) => {
    if (f.status === "cancelada") return acc;
    acc.total += f.base_total_mxn;
    acc.pendiente += (f.remaining_amount * f.exchange_rate);
    return acc;
  }, { total: 0, pendiente: 0 });

  if (loading) return <div className="p-6 text-muted-foreground">Cargando...</div>;

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border p-4">
          <div className="text-sm text-muted-foreground mb-1">Total facturado</div>
          <div className="text-xl font-semibold">{fmt(totals.total, "MXN")}</div>
        </div>
        <div className="rounded-lg border p-4">
          <div className="text-sm text-muted-foreground mb-1">Pendiente de pago</div>
          <div className="text-xl font-semibold">{fmt(totals.pendiente, "MXN")}</div>
        </div>
        <div className="rounded-lg border p-4">
          <div className="text-sm text-muted-foreground mb-1">Facturas</div>
          <div className="text-xl font-semibold">{facturas.filter(f => f.status !== "cancelada").length}</div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              <SelectItem value="pendiente">Pendiente</SelectItem>
              <SelectItem value="parcial">Parcial</SelectItem>
              <SelectItem value="pagada">Pagada</SelectItem>
              <SelectItem value="cancelada">Cancelada</SelectItem>
            </SelectContent>
          </Select>
          {currentRate && <span className="text-xs text-muted-foreground">T/C actual: {currentRate}</span>}
        </div>
        <Button size="sm" onClick={() => { setForm(EMPTY_FORM); setDialogOpen(true); }}>
          <Plus className="h-4 w-4 mr-1" /> Nueva Factura
        </Button>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead># Factura</TableHead>
            <TableHead>Proveedor</TableHead>
            <TableHead>Total</TableHead>
            <TableHead>T/C</TableHead>
            <TableHead>Total MXN</TableHead>
            <TableHead>Saldo</TableHead>
            <TableHead>Fecha</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-20"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {facturas.map(f => (
            <TableRow key={f.id}>
              <TableCell className="font-medium">{f.invoice_number}</TableCell>
              <TableCell>{f.proveedor_name || "-"}</TableCell>
              <TableCell>{fmt(f.total, f.currency)}</TableCell>
              <TableCell className="text-muted-foreground">{Number(f.exchange_rate).toFixed(4)}</TableCell>
              <TableCell>{fmt(f.base_total_mxn, "MXN")}</TableCell>
              <TableCell>
                {f.remaining_amount > 0 ? (
                  <span className="text-orange-600">{fmt(f.remaining_amount, f.currency)}</span>
                ) : <span className="text-green-600">Pagada</span>}
              </TableCell>
              <TableCell>{f.issue_date}</TableCell>
              <TableCell><Badge className={STATUS_STYLES[f.status] || ""}>{f.status}</Badge></TableCell>
              <TableCell>
                {f.status !== "cancelada" && f.status !== "pagada" && (
                  <Button variant="ghost" size="sm" onClick={() => handleCancel(f)} className="text-destructive">Cancelar</Button>
                )}
              </TableCell>
            </TableRow>
          ))}
          {facturas.length === 0 && (
            <TableRow><TableCell colSpan={9} className="text-center text-muted-foreground py-8">No hay facturas</TableCell></TableRow>
          )}
        </TableBody>
      </Table>

      {/* Create Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Nueva Factura de Proveedor</DialogTitle></DialogHeader>
          <div className="grid gap-4 py-2">
            <div>
              <Label>Proveedor *</Label>
              <Select value={form.proveedor_id} onValueChange={v => setForm({ ...form, proveedor_id: v })}>
                <SelectTrigger><SelectValue placeholder="Seleccionar..." /></SelectTrigger>
                <SelectContent>
                  {proveedores.map(p => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label># Factura *</Label><Input value={form.invoice_number} onChange={e => setForm({ ...form, invoice_number: e.target.value })} /></div>
              <div>
                <Label>Moneda</Label>
                <Select value={form.currency} onValueChange={v => setForm({ ...form, currency: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="USD">USD</SelectItem><SelectItem value="MXN">MXN</SelectItem></SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label>Subtotal *</Label><Input type="number" step="0.01" value={form.subtotal} onChange={e => setForm({ ...form, subtotal: e.target.value })} /></div>
              <div><Label>IVA</Label><Input type="number" step="0.01" value={form.tax} onChange={e => setForm({ ...form, tax: e.target.value })} /></div>
              <div>
                <Label>T/C</Label>
                <Input type="number" step="0.0001" placeholder={currentRate ? `Auto: ${currentRate}` : "Auto"} value={form.exchange_rate} onChange={e => setForm({ ...form, exchange_rate: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Fecha emision *</Label><Input type="date" value={form.issue_date} onChange={e => setForm({ ...form, issue_date: e.target.value })} /></div>
              <div><Label>Fecha vencimiento</Label><Input type="date" value={form.due_date} onChange={e => setForm({ ...form, due_date: e.target.value })} /></div>
            </div>
            <div><Label>Descripcion</Label><Input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></div>
            <div><Label>Notas</Label><Textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={2} /></div>

            {/* Preview total */}
            {form.subtotal && (
              <div className="rounded-lg border p-3 bg-muted/30 text-sm">
                Total: {fmt(parseFloat(form.subtotal) + parseFloat(form.tax || "0"), form.currency)}
                {form.currency !== "MXN" && (
                  <span className="ml-2 text-muted-foreground">
                    = {fmt((parseFloat(form.subtotal) + parseFloat(form.tax || "0")) * (form.exchange_rate ? parseFloat(form.exchange_rate) : (currentRate || 0)), "MXN")}
                  </span>
                )}
              </div>
            )}

            <Button onClick={handleCreate} disabled={!form.proveedor_id || !form.invoice_number || !form.subtotal}>Registrar Factura</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
