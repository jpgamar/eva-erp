"use client";

import { useEffect, useState } from "react";
import { Plus, FileDown, XCircle, FileText, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { facturasApi } from "@/lib/api/facturas";
import { customersApi } from "@/lib/api/customers";
import { TAX_SYSTEMS, CFDI_USES, PAYMENT_FORMS } from "@/lib/constants/sat";
import type { Customer } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

interface Factura {
  id: string;
  facturapi_id: string;
  cfdi_uuid: string | null;
  customer_name: string;
  customer_rfc: string;
  customer_id: string | null;
  use: string;
  payment_form: string;
  payment_method: string;
  line_items_json: any[] | null;
  subtotal: number;
  tax: number;
  total: number;
  currency: string;
  status: string;
  cancellation_status: string | null;
  series: string | null;
  folio_number: number | null;
  issued_at: string | null;
  cancelled_at: string | null;
  created_at: string;
}

const STATUS_STYLES: Record<string, string> = {
  valid: "bg-green-50 text-green-700",
  cancelled: "bg-red-50 text-red-700",
  draft: "bg-gray-100 text-gray-700",
};

function fmt(amount: number | null | undefined, currency = "MXN") {
  if (amount == null) return "\u2014";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

const emptyLineItem = { product_key: "", description: "", quantity: "1", unit_price: "", tax_rate: "0.16" };

const MANUAL_ENTRY = "__manual__";

export default function FacturasPage() {
  const [facturas, setFacturas] = useState<Factura[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [noApiKey, setNoApiKey] = useState(false);

  // FacturAPI status
  const [apiStatus, setApiStatus] = useState<"loading" | "ok" | "error" | "not_configured">("loading");

  // Customer list for picker
  const [customers, setCustomers] = useState<Customer[]>([]);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>(MANUAL_ENTRY);
  const [customerFieldsReadOnly, setCustomerFieldsReadOnly] = useState(false);
  const [customerWarning, setCustomerWarning] = useState("");
  const [form, setForm] = useState({
    customer_name: "",
    customer_rfc: "",
    customer_tax_system: "601",
    customer_zip: "",
    use: "G03",
    payment_form: "03",
    payment_method: "PUE",
    currency: "MXN",
    notes: "",
  });
  const [lineItems, setLineItems] = useState([{ ...emptyLineItem }]);

  // Cancel dialog
  const [cancelTarget, setCancelTarget] = useState<Factura | null>(null);

  const fetchFacturas = async () => {
    try {
      const params = statusFilter !== "all" ? { status: statusFilter } : undefined;
      const data = await facturasApi.list(params);
      setFacturas(data);
      setNoApiKey(false);
    } catch (e: any) {
      if (e?.response?.status === 503) {
        setNoApiKey(true);
      } else {
        toast.error("Failed to load facturas");
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchApiStatus = async () => {
    try {
      const res = await facturasApi.apiStatus();
      setApiStatus(res.status as "ok" | "error" | "not_configured");
    } catch {
      setApiStatus("error");
    }
  };

  const fetchCustomers = async () => {
    try {
      const custs = await customersApi.list({ status: "active" });
      setCustomers(custs);
    } catch { /* silent */ }
  };

  useEffect(() => {
    fetchFacturas();
    fetchApiStatus();
    fetchCustomers();
  }, []);

  useEffect(() => { fetchFacturas(); }, [statusFilter]);

  const handleCustomerSelect = (customerId: string) => {
    setSelectedCustomerId(customerId);
    setCustomerWarning("");

    if (customerId === MANUAL_ENTRY) {
      setCustomerFieldsReadOnly(false);
      setForm(f => ({
        ...f,
        customer_name: "",
        customer_rfc: "",
        customer_tax_system: "601",
        customer_zip: "",
        use: "G03",
      }));
      return;
    }

    const customer = customers.find(c => c.id === customerId);
    if (!customer) return;

    if (!customer.legal_name || !customer.rfc) {
      setCustomerWarning("This customer has no fiscal info configured. Fill in the fields manually.");
      setCustomerFieldsReadOnly(false);
      setForm(f => ({
        ...f,
        customer_name: customer.legal_name || customer.company_name,
        customer_rfc: customer.rfc || "",
        customer_tax_system: customer.tax_regime || "601",
        customer_zip: customer.fiscal_zip || "",
        use: customer.default_cfdi_use || f.use,
      }));
      return;
    }

    setCustomerFieldsReadOnly(true);
    setForm(f => ({
      ...f,
      customer_name: customer.legal_name!,
      customer_rfc: customer.rfc!,
      customer_tax_system: customer.tax_regime || "601",
      customer_zip: customer.fiscal_zip || "",
      use: customer.default_cfdi_use || f.use,
    }));
  };

  const handleCreate = async () => {
    setSubmitting(true);
    try {
      const items = lineItems.map(li => ({
        product_key: li.product_key,
        description: li.description,
        quantity: parseInt(li.quantity) || 1,
        unit_price: parseFloat(li.unit_price) || 0,
        tax_rate: parseFloat(li.tax_rate) || 0.16,
      }));

      const payload: any = { ...form, line_items: items };
      if (selectedCustomerId !== MANUAL_ENTRY) {
        payload.customer_id = selectedCustomerId;
      }

      await facturasApi.create(payload);
      toast.success("Factura created and stamped");
      setCreateOpen(false);
      resetForm();
      await fetchFacturas();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      if (typeof detail === "object" && detail?.facturapi_error) {
        toast.error(`Facturapi error: ${JSON.stringify(detail.facturapi_error.message || detail.facturapi_error)}`);
      } else {
        toast.error(typeof detail === "string" ? detail : "Failed to create factura");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async () => {
    if (!cancelTarget) return;
    try {
      await facturasApi.delete(cancelTarget.id);
      toast.success("Factura cancelled");
      setCancelTarget(null);
      await fetchFacturas();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to cancel");
    }
  };

  const handleDownloadPdf = async (f: Factura) => {
    try {
      const blob = await facturasApi.downloadPdf(f.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `CFDI_${f.cfdi_uuid || f.facturapi_id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Failed to download PDF"); }
  };

  const handleDownloadXml = async (f: Factura) => {
    try {
      const blob = await facturasApi.downloadXml(f.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `CFDI_${f.cfdi_uuid || f.facturapi_id}.xml`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Failed to download XML"); }
  };

  const resetForm = () => {
    setForm({
      customer_name: "", customer_rfc: "", customer_tax_system: "601",
      customer_zip: "", use: "G03", payment_form: "03",
      payment_method: "PUE", currency: "MXN", notes: "",
    });
    setLineItems([{ ...emptyLineItem }]);
    setSelectedCustomerId(MANUAL_ENTRY);
    setCustomerFieldsReadOnly(false);
    setCustomerWarning("");
  };

  const addLineItem = () => setLineItems(prev => [...prev, { ...emptyLineItem }]);
  const removeLineItem = (idx: number) => setLineItems(prev => prev.filter((_, i) => i !== idx));
  const updateLineItem = (idx: number, field: string, value: string) =>
    setLineItems(prev => prev.map((li, i) => i === idx ? { ...li, [field]: value } : li));

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <div className="animate-spin h-8 w-8 border-4 border-accent border-t-transparent rounded-full" />
      </div>
    );
  }

  if (noApiKey) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-8rem)] gap-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50">
          <AlertTriangle className="h-8 w-8 text-amber-500" />
        </div>
        <h2 className="text-lg font-semibold text-foreground">Facturapi Not Configured</h2>
        <p className="text-sm text-muted max-w-md text-center">
          Add your Facturapi API key to the backend .env file as <code className="px-1.5 py-0.5 rounded bg-gray-100 text-xs font-mono">FACTURAPI_API_KEY=sk_test_...</code> and restart the server.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-erp-entrance">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[140px] rounded-lg">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="valid">Valid</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
            </SelectContent>
          </Select>

          {/* FacturAPI Status Indicator */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className={cn(
              "h-2 w-2 rounded-full",
              apiStatus === "ok" && "bg-green-500",
              apiStatus === "error" && "bg-red-500",
              apiStatus === "not_configured" && "bg-yellow-500",
              apiStatus === "loading" && "bg-gray-300 animate-pulse",
            )} />
            <span className="text-muted-foreground">
              {apiStatus === "ok" && "FacturAPI Connected"}
              {apiStatus === "error" && "FacturAPI Error"}
              {apiStatus === "not_configured" && "Not Configured"}
              {apiStatus === "loading" && "Checking..."}
            </span>
          </div>
        </div>
        <Button size="sm" className="rounded-lg" onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-2" /> New Factura
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50/80">
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Folio</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Customer</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">RFC</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Total</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Status</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted">Date</TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {facturas.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted py-12">
                  <FileText className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  No facturas yet. Create your first CFDI invoice.
                </TableCell>
              </TableRow>
            ) : facturas.map((f) => (
              <TableRow key={f.id} className="hover:bg-gray-50/80">
                <TableCell className="font-mono text-sm font-medium">
                  {f.series ? `${f.series}-` : ""}{f.folio_number ?? "\u2014"}
                </TableCell>
                <TableCell className="font-medium">{f.customer_name}</TableCell>
                <TableCell className="font-mono text-sm text-muted">{f.customer_rfc}</TableCell>
                <TableCell className="font-mono text-sm">{fmt(f.total, f.currency)}</TableCell>
                <TableCell>
                  <Badge className={cn("rounded-full text-xs font-medium", STATUS_STYLES[f.status] || "")}>
                    {f.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-sm text-muted">
                  {f.issued_at ? new Date(f.issued_at).toLocaleDateString() : new Date(f.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      variant="ghost" size="icon" className="h-8 w-8"
                      title="Download PDF"
                      onClick={() => handleDownloadPdf(f)}
                    >
                      <FileDown className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost" size="icon" className="h-8 w-8"
                      title="Download XML"
                      onClick={() => handleDownloadXml(f)}
                    >
                      <FileText className="h-4 w-4" />
                    </Button>
                    {f.status === "valid" && (
                      <Button
                        variant="ghost" size="icon" className="h-8 w-8 text-red-500 hover:text-red-700"
                        title="Cancel"
                        onClick={() => setCancelTarget(f)}
                      >
                        <XCircle className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={(v) => { if (!v) resetForm(); setCreateOpen(v); }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>New CFDI Invoice</DialogTitle></DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); handleCreate(); }} className="space-y-5">
            {/* Customer picker */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">Customer</p>

              <div className="mb-3">
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Select Customer</Label>
                <Select value={selectedCustomerId} onValueChange={handleCustomerSelect}>
                  <SelectTrigger className="mt-1.5 rounded-lg">
                    <SelectValue placeholder="Select a customer..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={MANUAL_ENTRY}>Manual Entry (one-off customer)</SelectItem>
                    {customers.map(c => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.company_name}{c.rfc ? ` \u2014 ${c.rfc}` : ""}
                        {c.rfc && c.legal_name ? "" : " (no fiscal)"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {customerWarning && (
                <div className="flex items-center gap-2 text-amber-600 text-xs mb-3 p-2 rounded-lg bg-amber-50">
                  <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
                  {customerWarning}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Legal Name *</Label>
                  <Input className="mt-1.5 rounded-lg" value={form.customer_name}
                    readOnly={customerFieldsReadOnly}
                    onChange={(e) => setForm(f => ({ ...f, customer_name: e.target.value }))} required />
                </div>
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-muted">RFC *</Label>
                  <Input className="mt-1.5 rounded-lg" value={form.customer_rfc} maxLength={13}
                    readOnly={customerFieldsReadOnly}
                    onChange={(e) => setForm(f => ({ ...f, customer_rfc: e.target.value.toUpperCase() }))} required />
                </div>
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Tax System *</Label>
                  <Select value={form.customer_tax_system} onValueChange={(v) => setForm(f => ({ ...f, customer_tax_system: v }))} disabled={customerFieldsReadOnly}>
                    <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                    <SelectContent>{TAX_SYSTEMS.map(ts => <SelectItem key={ts.value} value={ts.value}>{ts.label}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-muted">ZIP Code *</Label>
                  <Input className="mt-1.5 rounded-lg" value={form.customer_zip} maxLength={5}
                    readOnly={customerFieldsReadOnly}
                    onChange={(e) => setForm(f => ({ ...f, customer_zip: e.target.value }))} required />
                </div>
              </div>
            </div>

            {/* Invoice metadata */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">Invoice Details</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Uso de CFDI</Label>
                  <Select value={form.use} onValueChange={(v) => setForm(f => ({ ...f, use: v }))}>
                    <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                    <SelectContent>{CFDI_USES.map(u => <SelectItem key={u.value} value={u.value}>{u.label}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Forma de Pago</Label>
                  <Select value={form.payment_form} onValueChange={(v) => setForm(f => ({ ...f, payment_form: v }))}>
                    <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                    <SelectContent>{PAYMENT_FORMS.map(pf => <SelectItem key={pf.value} value={pf.value}>{pf.label}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Metodo de Pago</Label>
                  <Select value={form.payment_method} onValueChange={(v) => setForm(f => ({ ...f, payment_method: v }))}>
                    <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="PUE">PUE - Pago en una sola exhibicion</SelectItem>
                      <SelectItem value="PPD">PPD - Pago en parcialidades</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Currency</Label>
                  <Select value={form.currency} onValueChange={(v) => setForm(f => ({ ...f, currency: v }))}>
                    <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="MXN">MXN</SelectItem>
                      <SelectItem value="USD">USD</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {/* Line items */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted">Line Items</p>
                <Button type="button" variant="outline" size="sm" className="rounded-lg h-7 text-xs" onClick={addLineItem}>
                  <Plus className="h-3 w-3 mr-1" /> Add Item
                </Button>
              </div>
              <div className="space-y-3">
                {lineItems.map((li, idx) => (
                  <div key={idx} className="rounded-lg border border-border p-3 space-y-2">
                    <div className="grid grid-cols-5 gap-2">
                      <div>
                        <Label className="text-[10px] font-semibold uppercase tracking-wider text-muted">SAT Key *</Label>
                        <Input className="mt-1 rounded-lg text-sm" placeholder="43232408" value={li.product_key}
                          onChange={(e) => updateLineItem(idx, "product_key", e.target.value)} required />
                      </div>
                      <div className="col-span-2">
                        <Label className="text-[10px] font-semibold uppercase tracking-wider text-muted">Description *</Label>
                        <Input className="mt-1 rounded-lg text-sm" value={li.description}
                          onChange={(e) => updateLineItem(idx, "description", e.target.value)} required />
                      </div>
                      <div>
                        <Label className="text-[10px] font-semibold uppercase tracking-wider text-muted">Qty</Label>
                        <Input className="mt-1 rounded-lg text-sm" type="number" min="1" value={li.quantity}
                          onChange={(e) => updateLineItem(idx, "quantity", e.target.value)} />
                      </div>
                      <div>
                        <Label className="text-[10px] font-semibold uppercase tracking-wider text-muted">Unit Price *</Label>
                        <Input className="mt-1 rounded-lg text-sm" type="number" step="0.01" value={li.unit_price}
                          onChange={(e) => updateLineItem(idx, "unit_price", e.target.value)} required />
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="w-32">
                        <Label className="text-[10px] font-semibold uppercase tracking-wider text-muted">Tax Rate</Label>
                        <Input className="mt-1 rounded-lg text-sm" type="number" step="0.01" value={li.tax_rate}
                          onChange={(e) => updateLineItem(idx, "tax_rate", e.target.value)} />
                      </div>
                      {lineItems.length > 1 && (
                        <Button type="button" variant="ghost" size="sm" className="text-red-500 hover:text-red-700 h-7 text-xs"
                          onClick={() => removeLineItem(idx)}>Remove</Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Notes */}
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted">Notes</Label>
              <Input className="mt-1.5 rounded-lg" value={form.notes}
                onChange={(e) => setForm(f => ({ ...f, notes: e.target.value }))} />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" className="rounded-lg" onClick={() => { resetForm(); setCreateOpen(false); }}>Cancel</Button>
              <Button type="submit" className="rounded-lg" disabled={submitting}>
                {submitting ? "Stamping..." : "Create & Stamp"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Cancel confirmation dialog */}
      <Dialog open={!!cancelTarget} onOpenChange={(v) => !v && setCancelTarget(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Cancel Factura</DialogTitle></DialogHeader>
          <p className="text-sm text-muted">
            Are you sure you want to cancel this CFDI invoice for <strong>{cancelTarget?.customer_name}</strong>?
            This action will send a cancellation request to the SAT.
          </p>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" className="rounded-lg" onClick={() => setCancelTarget(null)}>Keep</Button>
            <Button variant="destructive" className="rounded-lg" onClick={handleCancel}>Cancel Factura</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
