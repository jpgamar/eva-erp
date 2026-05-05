"use client";

import { ChevronDown, ChevronUp } from "lucide-react";
import { useCallback } from "react";

import { cn } from "@/lib/utils";

interface TimePickerProps {
  /** "HH:mm" 24h string, or null. */
  value: string | null;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
}

function parse(value: string | null): [number, number] {
  if (!value) return [9, 0];
  const [h, m] = value.split(":").map((s) => Number.parseInt(s, 10));
  return [Number.isFinite(h) ? h : 9, Number.isFinite(m) ? m : 0];
}

function fmt(h: number, m: number): string {
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/**
 * Compact 24h HH:mm picker. Two two-digit fields with up/down arrows
 * and a 15-minute step. Avoids the native datetime-local input the
 * operator complained about.
 */
export function TimePicker({ value, onChange, disabled, className }: TimePickerProps) {
  const [hours, minutes] = parse(value);

  const bumpHours = useCallback(
    (delta: number) => {
      const next = (hours + delta + 24) % 24;
      onChange(fmt(next, minutes));
    },
    [hours, minutes, onChange],
  );

  const bumpMinutes = useCallback(
    (delta: number) => {
      const totalMinutes = (hours * 60 + minutes + delta + 24 * 60) % (24 * 60);
      onChange(fmt(Math.floor(totalMinutes / 60), totalMinutes % 60));
    },
    [hours, minutes, onChange],
  );

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-1 text-sm",
        disabled && "opacity-50 pointer-events-none",
        className,
      )}
    >
      <Stepper
        value={String(hours).padStart(2, "0")}
        onUp={() => bumpHours(1)}
        onDown={() => bumpHours(-1)}
        ariaLabel="Hour"
      />
      <span className="font-mono text-muted-foreground">:</span>
      <Stepper
        value={String(minutes).padStart(2, "0")}
        onUp={() => bumpMinutes(15)}
        onDown={() => bumpMinutes(-15)}
        ariaLabel="Minute"
      />
    </div>
  );
}

function Stepper({
  value,
  onUp,
  onDown,
  ariaLabel,
}: {
  value: string;
  onUp: () => void;
  onDown: () => void;
  ariaLabel: string;
}) {
  return (
    <div className="inline-flex flex-col items-center">
      <button
        type="button"
        aria-label={`${ariaLabel} +`}
        onClick={onUp}
        className="text-muted-foreground hover:text-foreground"
      >
        <ChevronUp className="h-3 w-3" />
      </button>
      <span className="font-mono text-sm tabular-nums" aria-label={ariaLabel}>
        {value}
      </span>
      <button
        type="button"
        aria-label={`${ariaLabel} -`}
        onClick={onDown}
        className="text-muted-foreground hover:text-foreground"
      >
        <ChevronDown className="h-3 w-3" />
      </button>
    </div>
  );
}
