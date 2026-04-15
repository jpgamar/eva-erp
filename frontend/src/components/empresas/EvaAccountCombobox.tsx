"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Plus, Search, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api/client";
import type { EvaAccountForLink } from "@/lib/api/empresas";

interface Props {
  value: string | null;
  onChange: (accountId: string | null, accountName?: string) => void;
  empresaSuggestedName?: string;
}

/**
 * Searchable combobox that links an Empresa to an existing Eva account,
 * or opens a mini-dialog to create one (which requires owner_email +
 * owner_name — eva-erp's accounts route rejects drafts missing them).
 */
export function EvaAccountCombobox({ value, onChange, empresaSuggestedName }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<EvaAccountForLink[]>([]);
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await api.get<EvaAccountForLink[]>("/eva-platform/accounts/list-for-link", {
          params: query ? { q: query } : undefined,
        });
        setResults(data);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const currentName = useMemo(
    () => (value ? results.find((r) => r.id === value)?.name ?? null : null),
    [results, value]
  );

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder={currentName ? `Vinculada a ${currentName}` : "Buscar cuenta de Eva…"}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Buscar cuenta de Eva"
        />
        {loading ? (
          <Loader2 className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
        ) : null}
      </div>

      <div className="max-h-60 overflow-auto rounded-md border border-border bg-card">
        {results.length === 0 && !loading ? (
          <div className="space-y-2 p-4 text-sm text-muted-foreground">
            <p>No hay resultados.</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCreateOpen(true)}
              type="button"
            >
              <Plus className="mr-2 h-4 w-4" />
              Crear nueva cuenta de Eva
            </Button>
          </div>
        ) : (
          <ul role="listbox" aria-label="Resultados">
            {results.map((acc) => {
              const selected = acc.id === value;
              return (
                <li key={acc.id}>
                  <button
                    type="button"
                    onClick={() => onChange(acc.id, acc.name)}
                    className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-accent/10 ${
                      selected ? "bg-accent/20 font-medium" : ""
                    }`}
                  >
                    <span>{acc.name}</span>
                  </button>
                </li>
              );
            })}
            <li className="border-t border-border">
              <button
                type="button"
                onClick={() => setCreateOpen(true)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-accent-foreground hover:bg-accent/10"
              >
                <Plus className="h-4 w-4" />
                Crear nueva cuenta de Eva
              </button>
            </li>
          </ul>
        )}
      </div>

      <CreateEvaAccountDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        suggestedName={empresaSuggestedName}
        onCreated={(id, name) => {
          setCreateOpen(false);
          onChange(id, name);
        }}
      />
    </div>
  );
}

interface CreateProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  suggestedName?: string;
  onCreated: (accountId: string, name: string) => void;
}

function CreateEvaAccountDialog({ open, onOpenChange, suggestedName, onCreated }: CreateProps) {
  const [name, setName] = useState(suggestedName ?? "");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setName(suggestedName ?? "");
      setOwnerEmail("");
      setOwnerName("");
      setError(null);
    }
  }, [open, suggestedName]);

  async function submit() {
    if (!name.trim() || !ownerEmail.trim() || !ownerName.trim()) {
      setError("Nombre, correo del dueño y nombre del dueño son obligatorios.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const { data } = await api.post<{ id: string; name: string }>(
        "/eva-platform/accounts",
        {
          name: name.trim(),
          account_type: "commerce",
          owner_email: ownerEmail.trim(),
          owner_name: ownerName.trim(),
        }
      );
      onCreated(data.id, data.name);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "No se pudo crear la cuenta.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Crear cuenta de Eva</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <label className="text-sm font-medium">Nombre comercial</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">Correo del dueño</label>
            <Input
              type="email"
              value={ownerEmail}
              onChange={(e) => setOwnerEmail(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">Nombre del dueño</label>
            <Input value={ownerName} onChange={(e) => setOwnerName(e.target.value)} />
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} type="button">
              Cancelar
            </Button>
            <Button onClick={submit} disabled={submitting} type="button">
              {submitting ? "Creando…" : "Crear"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
