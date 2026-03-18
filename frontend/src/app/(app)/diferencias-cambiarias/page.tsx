"use client";

import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, ArrowUpDown } from "lucide-react";
import { toast } from "sonner";
import { diferenciasCambiariasApi } from "@/lib/api/pagos";
import { useAuth } from "@/lib/auth/context";
import type { DiferenciaCambiaria, DiferenciaCambiariaSummary } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

function fmt(amount: number | null | undefined, currency = "MXN") {
  if (amount == null) return "-";
  const prefix = Number(amount) >= 0 ? "+" : "";
  return `${prefix}$${Math.abs(Number(amount)).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currency}`;
}

const currentYear = new Date().getFullYear();
const YEARS = Array.from({ length: 3 }, (_, i) => currentYear - i);

export default function DiferenciasCambiariasPage() {
  const { user } = useAuth();
  const [diffs, setDiffs] = useState<DiferenciaCambiaria[]>([]);
  const [summary, setSummary] = useState<DiferenciaCambiariaSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState<string>(String(currentYear));

  const fetchAll = async () => {
    try {
      const [list, sum] = await Promise.all([
        diferenciasCambiariasApi.list(),
        diferenciasCambiariasApi.summary({ year: parseInt(year) }),
      ]);
      setDiffs(list);
      setSummary(sum);
    } catch { toast.error("Error loading data"); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchAll(); }, [year]);

  if (loading) return <div className="p-6 text-muted-foreground">Cargando...</div>;

  return (
    <div className="space-y-6">
      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-lg border p-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1"><TrendingUp className="h-4 w-4 text-green-600" /> Ganancias</div>
            <div className="text-xl font-semibold text-green-600">{fmt(summary.total_gain_mxn)}</div>
          </div>
          <div className="rounded-lg border p-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1"><TrendingDown className="h-4 w-4 text-red-600" /> Perdidas</div>
            <div className="text-xl font-semibold text-red-600">{fmt(summary.total_loss_mxn)}</div>
          </div>
          <div className="rounded-lg border p-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1"><ArrowUpDown className="h-4 w-4" /> Neto</div>
            <div className={cn("text-xl font-semibold", summary.net_mxn >= 0 ? "text-green-600" : "text-red-600")}>
              {fmt(summary.net_mxn)}
            </div>
            <div className="text-sm text-muted-foreground">{summary.count} movimientos</div>
          </div>
        </div>
      )}

      {/* By period chart (simple table) */}
      {summary && Object.keys(summary.by_period).length > 0 && (
        <div className="rounded-lg border p-4">
          <h3 className="text-sm font-medium mb-3">Por periodo</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(summary.by_period).sort(([a], [b]) => a.localeCompare(b)).map(([period, amount]) => (
              <div key={period} className="text-sm flex justify-between border-b pb-1">
                <span className="text-muted-foreground">{period}</span>
                <span className={cn("font-medium", Number(amount) >= 0 ? "text-green-600" : "text-red-600")}>
                  {fmt(Number(amount))}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-3">
        <Select value={year} onValueChange={setYear}>
          <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
          <SelectContent>
            {YEARS.map(y => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Periodo</TableHead>
            <TableHead>Proveedor</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead>Monto</TableHead>
            <TableHead>T/C Original</TableHead>
            <TableHead>T/C Liquidacion</TableHead>
            <TableHead>Diferencia MXN</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {diffs.map(d => (
            <TableRow key={d.id}>
              <TableCell><Badge variant="outline">{d.period}</Badge></TableCell>
              <TableCell>{d.proveedor_name || "-"}</TableCell>
              <TableCell className="text-muted-foreground">{d.source_type.replace("_", " ")}</TableCell>
              <TableCell>${Number(d.foreign_amount).toLocaleString("en-US", { minimumFractionDigits: 2 })} {d.currency}</TableCell>
              <TableCell>{Number(d.original_rate).toFixed(4)}</TableCell>
              <TableCell>{Number(d.settlement_rate).toFixed(4)}</TableCell>
              <TableCell className={cn("font-medium", d.gain_loss_mxn >= 0 ? "text-green-600" : "text-red-600")}>
                {fmt(d.gain_loss_mxn)}
              </TableCell>
            </TableRow>
          ))}
          {diffs.length === 0 && (
            <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground py-8">No hay diferencias cambiarias</TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
