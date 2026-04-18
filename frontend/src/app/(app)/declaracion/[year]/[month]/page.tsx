"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clipboard,
  ClipboardCheck,
  Info,
} from "lucide-react";
import { toast } from "sonner";
import {
  declaracionApi,
  type DeclaracionResponse,
} from "@/lib/api/declaracion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const MONTH_NAMES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

function fmtMoney(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  return n.toLocaleString("es-MX", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtRate(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  return (n * 100).toFixed(2) + "%";
}

function severityClass(severity: string): string {
  switch (severity) {
    case "blocker":
      return "border-red-300 bg-red-50 text-red-900";
    case "warning":
      return "border-amber-300 bg-amber-50 text-amber-900";
    default:
      return "border-blue-300 bg-blue-50 text-blue-900";
  }
}

interface SatFieldRow {
  label: string;
  value: string;
  highlight?: boolean;
}

function SatField({ label, value, highlight }: SatFieldRow) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    toast.success(`Copiado: ${value}`);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div
      className={cn(
        "flex items-center justify-between rounded-md border px-4 py-2.5",
        highlight
          ? "border-primary/40 bg-primary/5"
          : "border-border bg-background",
      )}
    >
      <span className="text-sm text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className={cn("font-mono text-sm", highlight && "font-semibold")}>
          ${value}
        </span>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2"
          onClick={copy}
          aria-label={`Copiar ${label}`}
        >
          {copied ? (
            <ClipboardCheck className="h-3.5 w-3.5 text-green-600" />
          ) : (
            <Clipboard className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>
    </div>
  );
}

export default function DeclaracionDetailPage({
  params,
}: {
  params: Promise<{ year: string; month: string }>;
}) {
  const resolved = use(params);
  const year = parseInt(resolved.year, 10);
  const month = parseInt(resolved.month, 10);

  const [data, setData] = useState<DeclaracionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    declaracionApi
      .get(year, month)
      .then(setData)
      .catch((e: any) =>
        setError(e?.response?.data?.detail || e.message || "Failed to load"),
      )
      .finally(() => setLoading(false));
  }, [year, month]);

  if (loading) {
    return <div className="p-6 text-sm text-muted-foreground">Cargando…</div>;
  }

  if (error || !data) {
    return (
      <div className="p-6">
        <Link
          href="/declaracion"
          className="text-sm text-muted-foreground flex items-center gap-1 mb-4"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Volver
        </Link>
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-900">
          {error || "No se pudo cargar la declaración."}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div>
        <Link
          href="/declaracion"
          className="text-sm text-muted-foreground flex items-center gap-1 mb-2"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Volver
        </Link>
        <h1 className="text-2xl font-semibold">
          Declaración {MONTH_NAMES[month - 1]} {year}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          RFC {data.rfc} · Régimen 626 (RESICO PF)
        </p>
      </div>

      {data.warnings.length > 0 && (
        <section className="space-y-2">
          {data.warnings.map((w, idx) => (
            <div
              key={`${w.code}-${idx}`}
              className={cn(
                "flex items-start gap-3 rounded-md border px-4 py-3 text-sm",
                severityClass(w.severity),
              )}
            >
              {w.severity === "info" ? (
                <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              )}
              <div className="flex-1">{w.message}</div>
            </div>
          ))}
        </section>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            ISR simplificado de confianza · Personas físicas
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <SatField
            label="Total de ingresos efectivamente cobrados"
            value={fmtMoney(data.isr.ingresos)}
            highlight
          />
          <div className="flex items-center justify-between rounded-md border border-border bg-background px-4 py-2.5">
            <span className="text-sm text-muted-foreground">Tasa aplicable</span>
            <span className="font-mono text-sm">{fmtRate(data.isr.tasa)}</span>
          </div>
          <SatField
            label="Impuesto mensual"
            value={fmtMoney(data.isr.impuesto_mensual)}
          />
          <SatField
            label="ISR retenido por personas morales"
            value={fmtMoney(data.isr.isr_retenido_por_pms)}
          />
          {parseFloat(data.isr.impuesto_a_pagar) > 0 ? (
            <SatField
              label="Impuesto a cargo"
              value={fmtMoney(data.isr.impuesto_a_pagar)}
              highlight
            />
          ) : (
            <div className="rounded-md border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-green-900 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" />
                A favor este mes
              </span>
              <span className="font-mono font-semibold">
                ${fmtMoney(data.isr.saldo_a_favor)}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            IVA simplificado de confianza
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <SatField
            label="Actividades gravadas a la tasa del 16%"
            value={fmtMoney(data.iva.actividades_gravadas_16)}
            highlight
          />
          <SatField
            label="IVA a cargo a la tasa del 16%"
            value={fmtMoney(data.iva.iva_trasladado)}
          />
          <SatField
            label="IVA retenido"
            value={fmtMoney(data.iva.iva_retenido_por_pms)}
          />
          <SatField
            label="IVA acreditable del periodo"
            value={fmtMoney(data.iva.iva_acreditable)}
          />
          {parseFloat(data.iva.impuesto_a_pagar) > 0 ? (
            <SatField
              label="Cantidad a pagar"
              value={fmtMoney(data.iva.impuesto_a_pagar)}
              highlight
            />
          ) : (
            <div className="rounded-md border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-green-900 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" />
                IVA a favor
              </span>
              <span className="font-mono font-semibold">
                ${fmtMoney(data.iva.saldo_a_favor)}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="rounded-md border border-border bg-muted/30 p-4 text-xs text-muted-foreground">
        <strong className="text-foreground">Recordatorios:</strong>
        <ul className="list-disc list-inside mt-1 space-y-0.5">
          <li>Fecha límite SAT: día 17 del mes siguiente.</li>
          <li>
            Si usas facturas PPD, emite el Complemento de Pago a más tardar el
            día 5 del mes siguiente al cobro.
          </li>
          <li>
            Sube los XMLs de gastos en <Link href="/gastos" className="underline">/gastos</Link>{" "}
            para sumar IVA acreditable.
          </li>
        </ul>
      </div>
    </div>
  );
}
