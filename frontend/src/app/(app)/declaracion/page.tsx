"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CalendarDays, ChevronRight, Info } from "lucide-react";
import { declaracionApi, type DeclaracionAlert } from "@/lib/api/declaracion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const MONTH_NAMES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

function lastNMonths(n: number): Array<{ year: number; month: number }> {
  const now = new Date();
  const out: Array<{ year: number; month: number }> = [];
  for (let i = 0; i < n; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    out.push({ year: d.getFullYear(), month: d.getMonth() + 1 });
  }
  return out;
}

function severityClass(severity: DeclaracionAlert["severity"]): string {
  switch (severity) {
    case "blocker":
      return "border-red-300 bg-red-50 text-red-900";
    case "warning":
      return "border-amber-300 bg-amber-50 text-amber-900";
    case "info":
    default:
      return "border-blue-300 bg-blue-50 text-blue-900";
  }
}

export default function DeclaracionesPage() {
  const [alerts, setAlerts] = useState<DeclaracionAlert[]>([]);
  const [loadingAlerts, setLoadingAlerts] = useState(true);

  useEffect(() => {
    declaracionApi
      .alerts()
      .then(r => setAlerts(r.alerts))
      .catch(() => setAlerts([]))
      .finally(() => setLoadingAlerts(false));
  }, []);

  const months = useMemo(() => lastNMonths(12), []);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Declaraciones mensuales</h1>
        <p className="text-sm text-muted-foreground mt-1">
          RESICO Personas Físicas. Los números aquí corresponden exactamente a lo
          que se captura en el portal del SAT.
        </p>
      </div>

      {!loadingAlerts && alerts.length > 0 && (
        <section className="space-y-2">
          {alerts.map((a, idx) => (
            <div
              key={`${a.code}-${idx}`}
              className={cn(
                "flex items-start gap-3 rounded-md border px-4 py-3 text-sm",
                severityClass(a.severity),
              )}
            >
              {a.severity === "blocker" || a.severity === "warning" ? (
                <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              ) : (
                <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
              )}
              <div className="flex-1">
                <div className="font-medium">{a.message}</div>
              </div>
              {a.deep_link && (
                <Link
                  href={a.deep_link}
                  className="text-xs font-medium underline whitespace-nowrap"
                >
                  Abrir
                </Link>
              )}
            </div>
          ))}
        </section>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <CalendarDays className="h-4 w-4" />
            Últimos 12 meses
          </CardTitle>
        </CardHeader>
        <CardContent className="divide-y divide-border">
          {months.map(({ year, month }) => (
            <Link
              key={`${year}-${month}`}
              href={`/declaracion/${year}/${month}`}
              className="flex items-center justify-between py-3 hover:bg-muted/40 transition -mx-6 px-6"
            >
              <div className="flex items-center gap-3">
                <span className="font-medium">
                  {MONTH_NAMES[month - 1]} {year}
                </span>
                <Badge variant="outline" className="text-xs">
                  {`${year}-${String(month).padStart(2, "0")}`}
                </Badge>
              </div>
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            </Link>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
