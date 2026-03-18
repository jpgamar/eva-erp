"use client";

import { useEffect, useState } from "react";
import { Plus, ArrowRightLeft, TrendingUp, TrendingDown, Wallet } from "lucide-react";
import { toast } from "sonner";
import { pagosApi, facturasProveedorApi } from "@/lib/api/pagos";
import { proveedoresApi } from "@/lib/api/proveedores";
import { exchangeRateApi } from "@/lib/api/finances";
import { useAuth } from "@/lib/auth/context";
import type { PagoProveedor, PagoProveedorSummary, Proveedor, FacturaProveedor } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

function fmt(amount: number | null | undefined, currency = "USD") {
  if (amount == null) return "-";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

const STATUS_STYLES: Record<string, string> = {
  pendiente: "bg-yellow-50 text-yellow-700",
  parcial: "bg-blue-50 text-blue-700",
  aplicado: "bg-green-50 text-green-700",
  cancelado: "bg-gray-100 text-gray-500",
};

const TIPO_STYLES: Record<string, string> = {
  anticipo: "bg-purple-50 text-purple-700",
  pago: "bg-emerald-50 text-emerald-700",
};

const EMPTY_FORM = {
  proveedor_id: "", tipo: "anticipo", description: "", amount: "", currency: "USD",
  exchange_rate: "", payment_date: new Date().toISOString().split("T")[0],
  payment_method: "transferencia", reference: "", notes: "",
};

export default function PagosPage() {
  const { user } = useAuth();
  const [pagos, setPagos] = useState<PagoProveedor[]>([]);
  const [summary, setSummary] = useState<PagoProveedorSummary | null>(null);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [loading, setLoading] = useState(true);

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const [applyOpen, setApplyOpen] = useState(false);
  const [applyPagoId, setApplyPagoId] = useState<string | null>(null);
  const [applyForm, setApplyForm] = useState({ factura_proveedor_id: "", amount: "" });
  const [facturasProv, setFacturasProv] = useState<FacturaProveedor[]>([]);

  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterTipo, setFilterTipo] = useState<string>("all");
  const [currentRate, setCurrentRate] = useState<number | null>(null);

  const fetchAll = async () => {
    try {
      const params: Record<string, string> = {};
      if (filterStatus !== "all") params.status = filterStatus;
      if (filterTipo !== "all") params.tipo = filterTipo;
      const [list, sum, provs, rate] = await Promise.all([
        pagosApi.list(Object.keys(params).length ? params : undefined),
        pagosApi.summary(filterTipo !== "all" ? { tipo: filterTipo } : undefined),
        proveedoresApi.list(),
        exchangeRateApi.current().catch(() => null),
      ]);
      setPagos(list);
      setSummary(sum);
      setProveedores(provs);
      if (rate) setCurrentRate(rate.rate);
    } catch { toast.error("Error loading data"); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchAll(); }, [filterStatus, filterTipo]);

  const handleCreate = async () => {
    try {
      const payload = {
        ...form,
        amount: parseFloat(form.amount),
        exchange_rate: form.exchange_rate ? parseFloat(form.exchange_rate) : undefined,
        description: form.description || null,
        reference: form.reference || null,
        notes: form.notes || null,
      };
      await pagosApi.create(payload);
      toast.success(form.tipo === "anticipo" ? "Anticipo registrado" : "Pago registrado");
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      await fetchAll();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Error"); }
  };

  const openApply = async (pago: PagoProveedor) => {
    setApplyPagoId(pago.id);
    setApplyForm({ factura_proveedor_id: "", amount: "" });
    try {
      const facturas = await facturasProveedorApi.list({ proveedor_id: pago.proveedor_id, status: "pendiente" });
      const facturasParcial = await facturasProveedorApi.list({ proveedor_id: pago.proveedor_id, status: "parcial" });
      setFacturasProv([...facturas, ...facturasParcial]);
    } catch { setFacturasProv([]); }
    setApplyOpen(true);
  };

  const handleApply = async () => {
    if (!applyPagoId) return;
    try {
      await pagosApi.apply(applyPagoId, {
        factura_proveedor_id: applyForm.factura_proveedor_id,
        amount: parseFloat(applyForm.amount),
      });
      toast.success("Pago aplicado a factura");
      setApplyOpen(false);
      await fetchAll();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Error"); }
  };

  const handleCancel = async (p: PagoProveedor) => {
    const label = p.tipo === "anticipo" ? "anticipo" : "pago";
    if (!window.confirm(`Cancelar ${label} de ${fmt(p.amount, p.currency)}?`)) return;
    try {
      await pagosApi.cancel(p.id);
      toast.success(`${label.charAt(0).toUpperCase() + label.slice(1)} cancelado`);
      await fetchAll();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Error"); }
  };

  if (loading) return <div className="p-6 text-muted-foreground">Cargando...</div>;

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="rounded-lg border p-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1"><Wallet className="h-4 w-4" /> Pendiente</div>
            <div className="text-xl font-semibold">{fmt(summary.total_pendiente_usd, "USD")}</div>
            <div className="text-sm text-muted-foreground">{fmt(summary.total_pendiente_mxn, "MXN")}</div>
          </div>
          <div className="rounded-lg border p-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1"><ArrowRightLeft className="h-4 w-4" /> Aplicado</div>
            <div className="text-xl font-semibold">{fmt(summary.total_aplicado_usd, "USD")}</div>
            <div className="text-sm text-muted-foreground">{fmt(summary.total_aplicado_mxn, "MXN")}</div>
          </div>
          <div className="rounded-lg border p-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
              {summary.total_diferencia_cambiaria_mxn >= 0 ? <TrendingUp className="h-4 w-4 text-green-600" /> : <TrendingDown className="h-4 w-4 text-red-600" />}
              Dif. Cambiaria
            </div>
            <div className={cn("text-xl font-semibold", summary.total_diferencia_cambiaria_mxn >= 0 ? "text-green-600" : "text-red-600")}>
              {fmt(summary.total_diferencia_cambiaria_mxn, "MXN")}
            </div>
          </div>
          <div className="rounded-lg border p-4">
            <div className="text-sm text-muted-foreground mb-1">Conteo</div>
            <div className="text-xl font-semibold">{summary.count_pendientes} pendientes</div>
            <div className="text-sm text-muted-foreground">{summary.count_aplicados} aplicados</div>
          </div>
        </div>
      )}

      {/* Header + filters */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Select value={filterTipo} onValueChange={setFilterTipo}>
            <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="anticipo">Anticipos</SelectItem>
              <SelectItem value="pago">Pagos</SelectItem>
            </SelectContent>
          </Select>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="pendiente">Pendiente</SelectItem>
              <SelectItem value="parcial">Parcial</SelectItem>
              <SelectItem value="aplicado">Aplicado</SelectItem>
              <SelectItem value="cancelado">Cancelado</SelectItem>
            </SelectContent>
          </Select>
          {currentRate && <span className="text-xs text-muted-foreground">T/C actual: {currentRate}</span>}
        </div>
        <Button size="sm" onClick={() => { setForm(EMPTY_FORM); setCreateOpen(true); }}>
          <Plus className="h-4 w-4 mr-1" /> Nuevo Pago
        </Button>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Proveedor</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead>Monto</TableHead>
            <TableHead>T/C</TableHead>
            <TableHead>Equiv. MXN</TableHead>
            <TableHead>Fecha</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Aplicado</TableHead>
            <TableHead className="w-28"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {pagos.map(p => (
            <TableRow key={p.id}>
              <TableCell className="font-medium">{p.proveedor_name || "-"}</TableCell>
              <TableCell><Badge className={TIPO_STYLES[p.tipo] || ""}>{p.tipo}</Badge></TableCell>
              <TableCell>{fmt(p.amount, p.currency)}</TableCell>
              <TableCell className="text-muted-foreground">{Number(p.exchange_rate).toFixed(4)}</TableCell>
              <TableCell>{fmt(p.base_amount_mxn, "MXN")}</TableCell>
              <TableCell>{p.payment_date}</TableCell>
              <TableCell><Badge className={STATUS_STYLES[p.status] || ""}>{p.status}</Badge></TableCell>
              <TableCell>
                {p.applied_amount > 0 ? (
                  <span className="text-sm">{fmt(p.applied_amount, p.currency)} / {fmt(p.amount, p.currency)}</span>
                ) : "-"}
              </TableCell>
              <TableCell>
                <div className="flex gap-1">
                  {p.status !== "aplicado" && p.status !== "cancelado" && (
                    <>
                      <Button variant="outline" size="sm" onClick={() => openApply(p)}>Aplicar</Button>
                      <Button variant="ghost" size="sm" onClick={() => handleCancel(p)} className="text-destructive">X</Button>
                    </>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
          {pagos.length === 0 && (
            <TableRow><TableCell colSpan={9} className="text-center text-muted-foreground py-8">No hay pagos</TableCell></TableRow>
          )}
        </TableBody>
      </Table>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Nuevo Pago</DialogTitle></DialogHeader>
          <div className="grid gap-4 py-2">
            <div>
              <Label>Tipo *</Label>
              <Select value={form.tipo} onValueChange={v => setForm({ ...form, tipo: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="anticipo">Anticipo (pago anticipado)</SelectItem>
                  <SelectItem value="pago">Pago directo</SelectItem>
                </SelectContent>
              </Select>
            </div>
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
              <div><Label>Monto *</Label><Input type="number" step="0.01" value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })} /></div>
              <div>
                <Label>Moneda</Label>
                <Select value={form.currency} onValueChange={v => setForm({ ...form, currency: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="USD">USD</SelectItem><SelectItem value="MXN">MXN</SelectItem></SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Tipo de cambio</Label>
                <Input type="number" step="0.0001" placeholder={currentRate ? `Auto: ${currentRate}` : "Auto"} value={form.exchange_rate} onChange={e => setForm({ ...form, exchange_rate: e.target.value })} />
              </div>
              <div><Label>Fecha de pago *</Label><Input type="date" value={form.payment_date} onChange={e => setForm({ ...form, payment_date: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Metodo de pago</Label>
                <Select value={form.payment_method} onValueChange={v => setForm({ ...form, payment_method: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="transferencia">Transferencia</SelectItem>
                    <SelectItem value="cheque">Cheque</SelectItem>
                    <SelectItem value="efectivo">Efectivo</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Referencia</Label><Input value={form.reference} onChange={e => setForm({ ...form, reference: e.target.value })} placeholder="# transferencia, cheque..." /></div>
            </div>
            <div><Label>Descripcion</Label><Input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></div>
            <div><Label>Notas</Label><Textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={2} /></div>
            <Button onClick={handleCreate} disabled={!form.proveedor_id || !form.amount}>
              {form.tipo === "anticipo" ? "Registrar Anticipo" : "Registrar Pago"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Apply Dialog */}
      <Dialog open={applyOpen} onOpenChange={setApplyOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Aplicar Pago a Factura</DialogTitle></DialogHeader>
          <div className="grid gap-4 py-2">
            <div>
              <Label>Factura del proveedor *</Label>
              <Select value={applyForm.factura_proveedor_id} onValueChange={v => setApplyForm({ ...applyForm, factura_proveedor_id: v })}>
                <SelectTrigger><SelectValue placeholder="Seleccionar factura..." /></SelectTrigger>
                <SelectContent>
                  {facturasProv.map(f => (
                    <SelectItem key={f.id} value={f.id}>
                      #{f.invoice_number} — {fmt(f.remaining_amount, f.currency)} pendiente (T/C {Number(f.exchange_rate).toFixed(4)})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {facturasProv.length === 0 && <p className="text-xs text-muted-foreground mt-1">No hay facturas pendientes de este proveedor</p>}
            </div>
            <div><Label>Monto a aplicar *</Label><Input type="number" step="0.01" value={applyForm.amount} onChange={e => setApplyForm({ ...applyForm, amount: e.target.value })} /></div>

            {/* Preview exchange difference */}
            {applyForm.factura_proveedor_id && applyForm.amount && applyPagoId && (() => {
              const pago = pagos.find(p => p.id === applyPagoId);
              const factura = facturasProv.find(f => f.id === applyForm.factura_proveedor_id);
              if (!pago || !factura) return null;
              const amount = parseFloat(applyForm.amount);
              const basePago = amount * pago.exchange_rate;
              const baseDoc = amount * factura.exchange_rate;
              const diff = baseDoc - basePago;
              return (
                <div className="rounded-lg border p-3 bg-muted/30 text-sm space-y-1">
                  <div>T/C pago: <strong>{Number(pago.exchange_rate).toFixed(4)}</strong> → {fmt(basePago, "MXN")}</div>
                  <div>T/C factura: <strong>{Number(factura.exchange_rate).toFixed(4)}</strong> → {fmt(baseDoc, "MXN")}</div>
                  <div className={cn("font-semibold", diff >= 0 ? "text-green-600" : "text-red-600")}>
                    Diferencia cambiaria: {diff >= 0 ? "+" : ""}{fmt(diff, "MXN")}
                    {diff > 0 ? " (ganancia)" : diff < 0 ? " (perdida)" : ""}
                  </div>
                </div>
              );
            })()}

            <Button onClick={handleApply} disabled={!applyForm.factura_proveedor_id || !applyForm.amount}>Aplicar</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
