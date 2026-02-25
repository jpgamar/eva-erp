"use client";

import { useState } from "react";
import { Check, ChevronsUpDown, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import { SAT_PRODUCT_KEYS } from "@/lib/constants/sat-products";

interface SatProductComboboxProps {
  value: string;
  onChange: (value: string) => void;
}

export function SatProductCombobox({ value, onChange }: SatProductComboboxProps) {
  const [open, setOpen] = useState(false);
  const [customMode, setCustomMode] = useState(false);

  const selected = SAT_PRODUCT_KEYS.find((item) => item.value === value);
  const displayLabel = selected ? selected.label : value || "";

  if (customMode) {
    return (
      <div className="flex gap-1">
        <Input
          className="rounded-lg text-sm"
          placeholder="Escribe la clave..."
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required
          autoFocus
        />
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="h-9 w-9 shrink-0 rounded-lg"
          title="Buscar en catalogo"
          onClick={() => setCustomMode(false)}
        >
          <Search className="h-3.5 w-3.5" />
        </Button>
      </div>
    );
  }

  return (
    <div>
      {/* Hidden input for native form validation */}
      <input
        tabIndex={-1}
        className="sr-only"
        value={value}
        required
        onChange={() => {}}
        onFocus={() => setOpen(true)}
      />
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className={cn(
              "w-full justify-between rounded-lg text-sm font-normal h-9 px-3",
              !value && "text-muted-foreground"
            )}
          >
            <span className="truncate">
              {displayLabel || "Buscar clave..."}
            </span>
            <ChevronsUpDown className="ml-1 h-3.5 w-3.5 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[350px] p-0" align="start">
          <Command>
            <CommandInput placeholder="Buscar por clave o descripcion..." />
            <CommandList>
              <CommandEmpty>
                <div className="px-2 py-3 text-sm text-center space-y-2">
                  <p className="text-muted-foreground">No se encontro la clave.</p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="rounded-lg text-xs"
                    onClick={() => {
                      setOpen(false);
                      setCustomMode(true);
                    }}
                  >
                    Escribir clave manualmente
                  </Button>
                </div>
              </CommandEmpty>
              <CommandGroup>
                {SAT_PRODUCT_KEYS.map((item) => (
                  <CommandItem
                    key={item.value}
                    value={item.label}
                    onSelect={() => {
                      onChange(item.value);
                      setOpen(false);
                    }}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-3.5 w-3.5 shrink-0",
                        value === item.value ? "opacity-100" : "opacity-0"
                      )}
                    />
                    <span className="truncate" title={item.label}>
                      {item.label}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
