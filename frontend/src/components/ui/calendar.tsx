"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker } from "react-day-picker";
import { es } from "date-fns/locale";

import { cn } from "@/lib/utils";

export type CalendarProps = React.ComponentProps<typeof DayPicker>;

/**
 * Thin Calendar wrapper around react-day-picker styled with Tailwind to
 * match the rest of the empresa-erp UI. Locale defaults to Spanish.
 *
 * Used by `<DateTimePicker>` and any future range/multi pickers.
 */
export function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  ...props
}: CalendarProps) {
  return (
    <DayPicker
      locale={es}
      showOutsideDays={showOutsideDays}
      className={cn("p-3", className)}
      classNames={{
        months: "flex flex-col sm:flex-row gap-3",
        month: "space-y-3",
        caption: "flex justify-center pt-1 relative items-center",
        caption_label: "text-sm font-medium capitalize",
        nav: "flex items-center gap-1",
        nav_button:
          "inline-flex h-7 w-7 items-center justify-center rounded-md border border-border bg-background hover:bg-muted/40",
        nav_button_previous: "absolute left-1",
        nav_button_next: "absolute right-1",
        table: "w-full border-collapse space-y-1",
        head_row: "flex",
        head_cell:
          "text-muted-foreground rounded-md w-8 font-normal text-[10px] uppercase tracking-wider",
        row: "flex w-full mt-1",
        cell: "h-8 w-8 text-center text-sm p-0 relative",
        day: "inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-accent/15 hover:text-foreground aria-selected:opacity-100",
        day_selected:
          "bg-accent text-accent-foreground hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground",
        day_today: "ring-1 ring-accent/40",
        day_outside: "text-muted-foreground/40",
        day_disabled: "text-muted-foreground/40 cursor-not-allowed",
        day_hidden: "invisible",
        ...classNames,
      }}
      components={{
        // react-day-picker v9 renamed nav icons to a single Chevron
        // component that receives an `orientation` prop.
        Chevron: ({ orientation }: { orientation?: string }) =>
          orientation === "left" ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          ),
      }}
      {...props}
    />
  );
}
