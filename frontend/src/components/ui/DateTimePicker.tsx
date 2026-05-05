"use client";

import { CalendarIcon, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { TimePicker } from "@/components/ui/TimePicker";
import { cn } from "@/lib/utils";

interface DateTimePickerProps {
  /** ISO 8601 string in UTC, or null. */
  value: string | null;
  onChange: (iso: string | null) => void;
  disabled?: boolean;
  placeholder?: string;
  /** Defaults to 09:00 when picking a date for the first time. */
  defaultTime?: string;
  /** When true, the trigger button shows in a destructive color. */
  invalid?: boolean;
  className?: string;
}

const SHORT_MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

function localFromIso(iso: string | null): { date: Date | null; time: string } {
  if (!iso) return { date: null, time: "09:00" };
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { date: null, time: "09:00" };
  const time = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  return { date: d, time };
}

function combine(date: Date, time: string): string {
  const [h, m] = time.split(":").map((s) => Number.parseInt(s, 10));
  const merged = new Date(date);
  merged.setHours(h, m, 0, 0);
  return merged.toISOString();
}

function formatTrigger(iso: string | null, placeholder: string): string {
  if (!iso) return placeholder;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return placeholder;
  const day = d.getDate();
  const mo = SHORT_MONTHS[d.getMonth()];
  const yr = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${day} ${mo} ${yr}, ${hh}:${mm}`;
}

/**
 * Date+time picker. Trigger button shows the current value or
 * placeholder. Popover contains a `<Calendar>` and a `<TimePicker>`,
 * with a Clear / Hoy footer. Replaces the native `<input type="datetime-local">`
 * across empresa flows.
 */
export function DateTimePicker({
  value,
  onChange,
  disabled,
  placeholder = "Selecciona fecha",
  defaultTime = "09:00",
  invalid,
  className,
}: DateTimePickerProps) {
  const [open, setOpen] = useState(false);
  const initial = useMemo(() => localFromIso(value), [value]);
  const [pendingDate, setPendingDate] = useState<Date | null>(initial.date);
  const [pendingTime, setPendingTime] = useState<string>(initial.time || defaultTime);

  // Sync local pending state when an external `value` change happens
  // (e.g., parent reset).
  useEffect(() => {
    const fresh = localFromIso(value);
    setPendingDate(fresh.date);
    setPendingTime(fresh.time || defaultTime);
  }, [value, defaultTime]);

  const triggerLabel = formatTrigger(value, placeholder);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          className={cn(
            "w-full justify-start gap-2 font-normal",
            !value && "text-muted-foreground",
            invalid && "border-destructive text-destructive",
            className,
          )}
          aria-label={value ? `Cambiar fecha (${triggerLabel})` : "Seleccionar fecha"}
        >
          <CalendarIcon className="h-4 w-4" />
          {triggerLabel}
          {value ? (
            <span
              role="button"
              aria-label="Borrar fecha"
              tabIndex={0}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onChange(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  onChange(null);
                }
              }}
              className="ml-auto inline-flex h-5 w-5 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <div className="flex flex-col gap-3 p-3">
          <Calendar
            mode="single"
            selected={pendingDate ?? undefined}
            onSelect={(d) => setPendingDate(d ?? null)}
            initialFocus
          />
          <div className="flex items-center justify-between gap-3 border-t border-border pt-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>Hora</span>
              <TimePicker value={pendingTime} onChange={setPendingTime} />
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  onChange(null);
                  setOpen(false);
                }}
              >
                Borrar
              </Button>
              <Button
                type="button"
                variant="default"
                size="sm"
                disabled={!pendingDate}
                onClick={() => {
                  if (!pendingDate) return;
                  onChange(combine(pendingDate, pendingTime));
                  setOpen(false);
                }}
              >
                Aceptar
              </Button>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
