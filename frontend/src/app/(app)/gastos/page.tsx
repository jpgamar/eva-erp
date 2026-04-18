"use client";

import { useCallback, useEffect, useState } from "react";
import { Upload, FileDown, CheckCircle2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import {
  gastosApi,
  type FacturaRecibida,
  type IvaAcreditableSummary,
} from "@/lib/api/gastos";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const MONTHS = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

function thisMonth(): { year: number; month: number } {
  const d = new Date();
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

function fmtMoney(v: string | number | null): string {
  if (v == null) return "—";
  const n = typeof v === "string" ? parseFloat(v) : v;
  return n.toLocaleString("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
  });
}

function fmtDate(s: string | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("es-MX", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export default function GastosPage() {
  const [period, setPeriod] = useState(thisMonth());
  const [rows, setRows] = useState<FacturaRecibida[]>([]);
  const [summary, setSummary] = useState<IvaAcreditableSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, iva] = await Promise.all([
        gastosApi.list({ year: period.year, month: period.month }),
        gastosApi.ivaAcreditable(period.year, period.month),
      ]);
      setRows(list);
      setSummary(iva);
    } catch (e: any) {
      toast.error(
        e?.response?.data?.detail || e.message || "Error al cargar gastos",
      );
    } finally {
      setLoading(false);
    }
  }, [period.year, period.month]);

  useEffect(() => {
    load();
  }, [load]);

  const lastSixPeriods = () => {
    const out: Array<{ year: number; month: number; label: string }> = [];
    const now = new Date();
    for (let i = 0; i < 12; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      out.push({
        year: d.getFullYear(),
        month: d.getMonth() + 1,
        label: `${MONTHS[d.getMonth()]} ${d.getFullYear()}`,
      });
    }
    return out;
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Gastos (facturas recibidas)</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Sube los CFDIs que tus proveedores te emitieron para acreditar IVA
            en tu declaración mensual.
          </p>
        </div>
        <Button onClick={() => setUploadOpen(true)}>
          <Upload className="h-4 w-4 mr-2" />
          Subir XMLs
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <Select
          value={`${period.year}-${period.month}`}
          onValueChange={(v) => {
            const [y, m] = v.split("-").map(Number);
            setPeriod({ year: y, month: m });
          }}
        >
          <SelectTrigger className="w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {lastSixPeriods().map((p) => (
              <SelectItem
                key={`${p.year}-${p.month}`}
                value={`${p.year}-${p.month}`}
              >
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {summary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">IVA acreditable del periodo</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <div>
              <p className="text-2xl font-semibold">{fmtMoney(summary.iva_acreditable)}</p>
              <p className="text-xs text-muted-foreground mt-1">
                {summary.row_count} CFDI(s) acreditables · listos para la declaración
              </p>
            </div>
            <Badge variant="outline" className="gap-1.5 px-3 py-1">
              <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
              Acreditables
            </Badge>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">CFDIs recibidos</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Fecha pago</TableHead>
                <TableHead>Proveedor</TableHead>
                <TableHead>RFC</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead className="text-right">Subtotal</TableHead>
                <TableHead className="text-right">IVA</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead>Acreditable</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-sm text-muted-foreground py-8">
                    Cargando…
                  </TableCell>
                </TableRow>
              ) : rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-sm text-muted-foreground py-8">
                    Sin gastos registrados para este periodo. Dale &ldquo;Subir XMLs&rdquo; para empezar.
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs">
                      {fmtDate(r.payment_date)}
                    </TableCell>
                    <TableCell className="max-w-[220px] truncate">
                      {r.issuer_legal_name}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{r.issuer_rfc}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {r.cfdi_type === "I" ? "Ingreso" : r.cfdi_type === "E" ? "Egreso" : r.cfdi_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {fmtMoney(r.subtotal)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {fmtMoney(r.tax_iva)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {fmtMoney(r.total)}
                    </TableCell>
                    <TableCell>
                      {r.is_acreditable ? (
                        <Badge className="bg-green-100 text-green-800 hover:bg-green-100 text-xs">
                          Sí
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs">No</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} onDone={load} />
    </div>
  );
}

function UploadDialog({
  open,
  onOpenChange,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDone: () => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    try {
      const result = await gastosApi.upload(files);
      toast.success(
        `Subidas ${result.imported} · Duplicadas ${result.duplicates} · Rechazadas ${result.rejected}`,
      );
      if (result.errors.length > 0) {
        result.errors.forEach((e) => toast.error(e, { duration: 8000 }));
      }
      setFiles([]);
      onOpenChange(false);
      onDone();
    } catch (e: any) {
      toast.error(
        e?.response?.data?.detail || e.message || "Error al subir XMLs",
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Subir CFDIs recibidos</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="rounded-md border-2 border-dashed border-border px-4 py-8 text-center">
            <FileDown className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground mb-3">
              Selecciona XMLs desde el visor SAT (filtro: receptor = tu RFC).
            </p>
            <FileInput
              accept=".xml,application/xml,text/xml"
              multiple
              onFiles={(fs) => setFiles(fs)}
            />
            {files.length > 0 && (
              <p className="text-xs text-muted-foreground mt-2">
                {files.length} archivo(s) listo(s) para subir
              </p>
            )}
          </div>

          <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900 flex items-start gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <div>
              Los XMLs se validan: el receptor debe ser <span className="font-mono">tu RFC</span>.
              Archivos mal dirigidos o malformados se rechazan individualmente sin
              abortar el resto.
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setFiles([]);
                onOpenChange(false);
              }}
              disabled={uploading}
            >
              Cancelar
            </Button>
            <Button
              onClick={handleUpload}
              disabled={files.length === 0 || uploading}
            >
              {uploading
                ? "Subiendo…"
                : files.length === 0
                  ? "Elige archivos"
                  : `Subir ${files.length} XML(s)`}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Simple file input that reports back File[] whenever the selection changes. */
function FileInput({
  accept,
  multiple,
  onFiles,
}: {
  accept: string;
  multiple: boolean;
  onFiles: (files: File[]) => void;
}) {
  return (
    <input
      type="file"
      accept={accept}
      multiple={multiple}
      onChange={(e) => {
        const selected = Array.from(e.target.files || []);
        onFiles(selected);
      }}
      className="block mx-auto text-xs text-muted-foreground file:mr-3 file:px-3 file:py-1.5 file:rounded file:border-0 file:text-xs file:bg-primary file:text-primary-foreground hover:file:bg-primary/90 cursor-pointer"
    />
  );
}
