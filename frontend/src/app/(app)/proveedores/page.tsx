"use client";

import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { proveedoresApi } from "@/lib/api/proveedores";
import { useAuth } from "@/lib/auth/context";
import type { Proveedor } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const EMPTY_FORM = {
  name: "", rfc: "", contact_name: "", contact_email: "", contact_phone: "",
  bank_name: "", bank_account: "", default_currency: "USD", payment_terms_days: "",
  notes: "",
};

export default function ProveedoresPage() {
  const { user } = useAuth();
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [search, setSearch] = useState("");

  const fetchAll = async () => {
    try {
      const data = await proveedoresApi.list(search ? { search } : undefined);
      setProveedores(data);
    } catch { toast.error("Error loading proveedores"); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchAll(); }, [search]);

  const openCreate = () => { setEditingId(null); setForm(EMPTY_FORM); setDialogOpen(true); };

  const openEdit = (p: Proveedor) => {
    setEditingId(p.id);
    setForm({
      name: p.name, rfc: p.rfc || "", contact_name: p.contact_name || "",
      contact_email: p.contact_email || "", contact_phone: p.contact_phone || "",
      bank_name: p.bank_name || "", bank_account: p.bank_account || "",
      default_currency: p.default_currency, payment_terms_days: p.payment_terms_days?.toString() || "",
      notes: p.notes || "",
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    try {
      const payload = {
        ...form,
        payment_terms_days: form.payment_terms_days ? parseInt(form.payment_terms_days) : null,
        rfc: form.rfc || null, contact_name: form.contact_name || null,
        contact_email: form.contact_email || null, contact_phone: form.contact_phone || null,
        bank_name: form.bank_name || null, bank_account: form.bank_account || null,
        notes: form.notes || null,
      };
      if (editingId) {
        await proveedoresApi.update(editingId, payload);
        toast.success("Proveedor actualizado");
      } else {
        await proveedoresApi.create(payload);
        toast.success("Proveedor creado");
      }
      setDialogOpen(false);
      await fetchAll();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Error"); }
  };

  const handleDelete = async (p: Proveedor) => {
    if (!window.confirm(`Eliminar proveedor "${p.name}"?`)) return;
    try {
      await proveedoresApi.delete(p.id);
      toast.success("Proveedor eliminado");
      await fetchAll();
    } catch (e: any) { toast.error(e?.response?.data?.detail || "Error"); }
  };

  if (loading) return <div className="p-6 text-muted-foreground">Cargando...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Proveedores</h2>
          <p className="text-sm text-muted-foreground">{proveedores.length} proveedores registrados</p>
        </div>
        <div className="flex items-center gap-3">
          <Input placeholder="Buscar..." value={search} onChange={e => setSearch(e.target.value)} className="w-48" />
          <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4 mr-1" /> Nuevo</Button>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nombre</TableHead>
            <TableHead>RFC</TableHead>
            <TableHead>Contacto</TableHead>
            <TableHead>Moneda</TableHead>
            <TableHead>Dias pago</TableHead>
            <TableHead className="w-20"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {proveedores.map(p => (
            <TableRow key={p.id}>
              <TableCell className="font-medium">{p.name}</TableCell>
              <TableCell className="text-muted-foreground">{p.rfc || "-"}</TableCell>
              <TableCell>
                <div className="text-sm">{p.contact_name || "-"}</div>
                {p.contact_email && <div className="text-xs text-muted-foreground">{p.contact_email}</div>}
              </TableCell>
              <TableCell><Badge variant="outline">{p.default_currency}</Badge></TableCell>
              <TableCell>{p.payment_terms_days ?? "-"}</TableCell>
              <TableCell>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" onClick={() => openEdit(p)}><Pencil className="h-4 w-4" /></Button>
                  <Button variant="ghost" size="icon" onClick={() => handleDelete(p)}><Trash2 className="h-4 w-4 text-destructive" /></Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
          {proveedores.length === 0 && (
            <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-8">No hay proveedores</TableCell></TableRow>
          )}
        </TableBody>
      </Table>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingId ? "Editar Proveedor" : "Nuevo Proveedor"}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div><Label>Nombre *</Label><Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>RFC</Label><Input value={form.rfc} onChange={e => setForm({ ...form, rfc: e.target.value })} /></div>
              <div>
                <Label>Moneda default</Label>
                <Select value={form.default_currency} onValueChange={v => setForm({ ...form, default_currency: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="USD">USD</SelectItem><SelectItem value="MXN">MXN</SelectItem><SelectItem value="EUR">EUR</SelectItem></SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Contacto</Label><Input value={form.contact_name} onChange={e => setForm({ ...form, contact_name: e.target.value })} /></div>
              <div><Label>Email</Label><Input value={form.contact_email} onChange={e => setForm({ ...form, contact_email: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Telefono</Label><Input value={form.contact_phone} onChange={e => setForm({ ...form, contact_phone: e.target.value })} /></div>
              <div><Label>Dias de pago</Label><Input type="number" value={form.payment_terms_days} onChange={e => setForm({ ...form, payment_terms_days: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Banco</Label><Input value={form.bank_name} onChange={e => setForm({ ...form, bank_name: e.target.value })} /></div>
              <div><Label>CLABE</Label><Input value={form.bank_account} onChange={e => setForm({ ...form, bank_account: e.target.value })} /></div>
            </div>
            <div><Label>Notas</Label><Textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={2} /></div>
            <Button onClick={handleSave} disabled={!form.name}>{editingId ? "Guardar" : "Crear"}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
