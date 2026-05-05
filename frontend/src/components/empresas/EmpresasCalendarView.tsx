"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { CalendarClock, ChevronLeft, ChevronRight, Building2 } from "lucide-react";
import { empresasApi, type EmpresaCalendarItem } from "@/lib/api/empresas";

interface Props {
  empresaId?: string;
  onSelectEmpresa?: (empresaId: string) => void;
}

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function endOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59, 999);
}

function isoDate(d: Date): string {
  return d.toISOString();
}

function dayKey(iso: string): string {
  // Group by LOCAL calendar day, not UTC. Without this, an event at
  // 21:00 Mexico time renders under tomorrow's row because the ISO
  // string carries the UTC date.
  const d = new Date(iso);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function localDayKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const SOURCE_LABEL: Record<string, string> = {
  item: "Follow-up",
  meeting: "Reunión",
  interaction: "Outreach",
};

export function EmpresasCalendarView({ empresaId, onSelectEmpresa }: Props) {
  const [anchor, setAnchor] = useState<Date>(() => startOfMonth(new Date()));
  const [items, setItems] = useState<EmpresaCalendarItem[]>([]);
  const [loading, setLoading] = useState(false);

  const monthStart = useMemo(() => startOfMonth(anchor), [anchor]);
  const monthEnd = useMemo(() => endOfMonth(anchor), [anchor]);
  const monthLabel = useMemo(
    () => anchor.toLocaleDateString("es-MX", { month: "long", year: "numeric" }),
    [anchor]
  );

  useEffect(() => {
    setLoading(true);
    empresasApi
      .calendar({ from: isoDate(monthStart), to: isoDate(monthEnd), empresaId })
      .then(setItems)
      .catch(() => toast.error("No se pudo cargar el calendario"))
      .finally(() => setLoading(false));
  }, [monthStart, monthEnd, empresaId]);

  const grouped = useMemo(() => {
    const map = new Map<string, EmpresaCalendarItem[]>();
    for (const item of items) {
      const ts = item.start_at ?? item.due_at ?? item.reminder_at ?? null;
      if (!ts) continue;
      const key = dayKey(ts);
      const bucket = map.get(key) ?? [];
      bucket.push(item);
      map.set(key, bucket);
    }
    return map;
  }, [items]);

  const days = useMemo(() => {
    const result: Date[] = [];
    const cursor = new Date(monthStart);
    while (cursor <= monthEnd) {
      result.push(new Date(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    return result;
  }, [monthStart, monthEnd]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setAnchor(startOfMonth(new Date(anchor.getFullYear(), anchor.getMonth() - 1, 1)))}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border bg-background hover:bg-muted/40"
            aria-label="Mes anterior"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <p className="text-sm font-semibold capitalize text-foreground">{monthLabel}</p>
          <button
            type="button"
            onClick={() => setAnchor(startOfMonth(new Date(anchor.getFullYear(), anchor.getMonth() + 1, 1)))}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border bg-background hover:bg-muted/40"
            aria-label="Mes siguiente"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setAnchor(startOfMonth(new Date()))}
            className="ml-2 rounded-md border border-border bg-background px-2 py-1 text-xs hover:bg-muted/40"
          >
            Hoy
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          {loading ? "Cargando…" : `${items.length} eventos`}
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card">
        {days.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">No hay días en este rango.</p>
        ) : (
          <ul className="divide-y divide-border" data-testid="empresas-calendar-days">
            {days.map((day) => {
              const key = localDayKey(day);
              const bucket = grouped.get(key) ?? [];
              if (bucket.length === 0) return null;
              const label = day.toLocaleDateString("es-MX", {
                weekday: "short",
                day: "numeric",
                month: "short",
              });
              return (
                <li key={key} className="grid grid-cols-[120px_1fr] gap-3 p-4">
                  <div className="text-sm font-medium capitalize text-muted-foreground">{label}</div>
                  <ul className="space-y-2">
                    {bucket.map((item) => {
                      const time = item.start_at
                        ? new Date(item.start_at).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" })
                        : null;
                      return (
                        <li
                          key={`${item.source}-${item.id}`}
                          className="flex items-start gap-3 rounded-lg border border-border/60 bg-background p-3"
                        >
                          <CalendarClock className="mt-0.5 h-4 w-4 text-sky-600" />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-semibold text-foreground">
                              {item.title}
                            </p>
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              {time ? `${time} · ` : ""}
                              {SOURCE_LABEL[item.source] ?? item.source}
                              {item.contact_method ? ` · ${item.contact_method}` : ""}
                            </p>
                            {!empresaId ? (
                              <button
                                type="button"
                                onClick={() => onSelectEmpresa?.(item.empresa_id)}
                                className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-sky-600 hover:underline"
                              >
                                <Building2 className="h-3 w-3" />
                                {item.empresa_name}
                              </button>
                            ) : null}
                            {item.description ? (
                              <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                                {item.description}
                              </p>
                            ) : null}
                          </div>
                          {item.completed_at ? (
                            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                              Hecho
                            </span>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
