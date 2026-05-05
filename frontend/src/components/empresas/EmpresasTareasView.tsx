"use client";

import {
  AlertCircle,
  Building2,
  CalendarClock,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  ItemEditorPanel,
  kindBadgeStyle,
  type EmpresaPickerOption,
  type ItemEditorMode,
} from "@/components/empresas/ItemEditorPanel";
import { Button } from "@/components/ui/button";
import {
  empresasApi,
  type EmpresaItemKind,
  type EmpresaItemListFilters,
  type EmpresaItemWithEmpresa,
} from "@/lib/api/empresas";
import { cn } from "@/lib/utils";

interface Props {
  empresas: EmpresaPickerOption[];
}

type FilterPreset = "mine" | "team" | "overdue" | "all";

const PRESETS: { key: FilterPreset; label: string }[] = [
  { key: "mine", label: "Mis pendientes" },
  { key: "team", label: "Equipo" },
  { key: "overdue", label: "Vencidas" },
  { key: "all", label: "Todos" },
];

const KIND_FILTERS: { key: EmpresaItemKind; label: string }[] = [
  { key: "todo", label: "Pendientes" },
  { key: "event", label: "Eventos" },
  { key: "outreach", label: "Outreach" },
  { key: "note", label: "Notas" },
];

const SHORT_MONTHS = [
  "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic",
];

function fmtDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.getDate()} ${SHORT_MONTHS[d.getMonth()]}`;
}

/**
 * Tareas tab on /empresas. Cross-empresa items list, grouped by empresa
 * with a "Sin empresa (internas)" bucket on top. Replaces the deleted
 * standalone /tasks section.
 */
export function EmpresasTareasView({ empresas }: Props) {
  const [items, setItems] = useState<EmpresaItemWithEmpresa[]>([]);
  const [loading, setLoading] = useState(true);
  const [preset, setPreset] = useState<FilterPreset>("mine");
  const [kindFilter, setKindFilter] = useState<Set<EmpresaItemKind>>(new Set());
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<ItemEditorMode>({ type: "create" });
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const refresh = async () => {
    const filters: EmpresaItemListFilters = { limit: 200 };
    switch (preset) {
      case "mine":
        filters.assigned_to = "me";
        filters.done = false;
        break;
      case "team":
        filters.done = false;
        break;
      case "overdue":
        filters.overdue = true;
        filters.done = false;
        break;
      case "all":
        // No filters — show everything (including done) so operator can see history.
        break;
    }
    if (kindFilter.size > 0) {
      filters.kind = Array.from(kindFilter);
    }
    setLoading(true);
    try {
      const data = await empresasApi.listAllItems(filters);
      setItems(data);
    } catch {
      toast.error("No se pudieron cargar los pendientes");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset, kindFilter]);

  const grouped = useMemo(() => {
    const map = new Map<string, { empresaId: string | null; empresaName: string; rows: EmpresaItemWithEmpresa[] }>();
    for (const it of items) {
      const key = it.empresa?.id ?? "__internal__";
      const name = it.empresa?.name ?? "Sin empresa (internas)";
      if (!map.has(key)) {
        map.set(key, { empresaId: it.empresa?.id ?? null, empresaName: name, rows: [] });
      }
      map.get(key)!.rows.push(it);
    }
    // Internal first, then alphabetical
    return Array.from(map.values()).sort((a, b) => {
      if (a.empresaId === null) return -1;
      if (b.empresaId === null) return 1;
      return a.empresaName.localeCompare(b.empresaName);
    });
  }, [items]);

  function toggleKind(k: EmpresaItemKind) {
    setKindFilter((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  }

  async function toggleDone(item: EmpresaItemWithEmpresa) {
    setTogglingId(item.id);
    try {
      await empresasApi.toggleItem(item.id);
      setItems((prev) =>
        prev.map((i) => (i.id === item.id ? { ...i, done: !i.done } : i)),
      );
    } catch {
      toast.error("No se pudo actualizar");
    } finally {
      setTogglingId(null);
    }
  }

  function openEdit(item: EmpresaItemWithEmpresa) {
    setEditorMode({ type: "edit", item, empresaId: item.empresa_id });
    setEditorOpen(true);
  }

  function openCreate() {
    setEditorMode({ type: "create" });
    setEditorOpen(true);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => setPreset(p.key)}
              className={cn(
                "rounded-full border border-border px-3 py-1 text-xs font-medium transition-colors",
                preset === p.key
                  ? "bg-accent text-accent-foreground border-transparent"
                  : "text-muted-foreground hover:bg-muted/40",
              )}
              data-testid={`tareas-preset-${p.key}`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="ml-auto">
          <Button size="sm" onClick={openCreate}>
            Nueva tarea
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5 text-[11px]">
        {KIND_FILTERS.map((k) => {
          const active = kindFilter.has(k.key);
          const badge = kindBadgeStyle(k.key);
          return (
            <button
              key={k.key}
              type="button"
              onClick={() => toggleKind(k.key)}
              className={cn(
                "rounded-full px-2.5 py-0.5 transition-colors",
                active ? badge.className : "border border-border text-muted-foreground hover:bg-muted/40",
              )}
              data-testid={`tareas-kind-${k.key}`}
            >
              {k.label}
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Cargando tareas…
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center text-sm text-muted-foreground">
          {preset === "mine"
            ? "No tienes pendientes asignados. Cambia a 'Equipo' para ver todos."
            : "No hay pendientes con estos filtros."}
        </div>
      ) : (
        <div className="space-y-4" data-testid="tareas-groups">
          {grouped.map((group) => (
            <section key={group.empresaId ?? "internal"} className="rounded-xl border border-border bg-card">
              <header className="sticky top-0 flex items-center gap-2 border-b border-border bg-card/95 px-4 py-2 backdrop-blur">
                <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                <p className="text-xs font-semibold text-foreground">
                  {group.empresaName}
                </p>
                <span className="text-[10px] text-muted-foreground">{group.rows.length}</span>
              </header>
              <ul className="divide-y divide-border">
                {group.rows.map((item) => {
                  const target = item.start_at ?? item.due_at ?? null;
                  const overdue =
                    !item.done &&
                    item.due_at != null &&
                    new Date(item.due_at).getTime() < Date.now();
                  const kindBadge = kindBadgeStyle(item.kind);
                  return (
                    <li
                      key={item.id}
                      className={cn(
                        "flex items-center gap-2 px-4 py-2 hover:bg-muted/30",
                        item.done && "opacity-60",
                      )}
                    >
                      <button
                        type="button"
                        aria-label={item.done ? "Reabrir" : "Marcar hecho"}
                        disabled={togglingId === item.id}
                        onClick={() => toggleDone(item)}
                        className={cn(
                          "flex h-4 w-4 shrink-0 items-center justify-center rounded border border-border",
                          item.done && "bg-emerald-500 border-emerald-500 text-white",
                        )}
                      >
                        {item.done ? <CheckCircle2 className="h-3 w-3" /> : null}
                      </button>
                      <span
                        className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${kindBadge.className}`}
                      >
                        {kindBadge.label}
                      </span>
                      <button
                        type="button"
                        onClick={() => openEdit(item)}
                        className={cn(
                          "min-w-0 flex-1 truncate text-left text-sm",
                          item.done && "line-through text-muted-foreground",
                        )}
                      >
                        {item.title}
                      </button>
                      {target ? (
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 text-[11px]",
                            overdue ? "text-destructive" : "text-muted-foreground",
                          )}
                        >
                          {overdue ? (
                            <AlertCircle className="h-3 w-3" />
                          ) : (
                            <CalendarClock className="h-3 w-3" />
                          )}
                          {fmtDate(target)}
                        </span>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      )}

      <ItemEditorPanel
        open={editorOpen}
        onOpenChange={setEditorOpen}
        mode={editorMode}
        empresas={empresas}
        onChanged={() => {
          void refresh();
        }}
      />
    </div>
  );
}
