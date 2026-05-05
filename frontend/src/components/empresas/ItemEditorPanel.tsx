"use client";

import {
  Building2,
  CheckCircle,
  ChevronDown,
  Loader2,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
  StickyNote,
  Trash2,
  Users2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DateTimePicker } from "@/components/ui/DateTimePicker";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  empresasApi,
  type EmpresaContactMethod,
  type EmpresaItem,
  type EmpresaItemKind,
  type EmpresaItemTopCreate,
} from "@/lib/api/empresas";

const KIND_OPTIONS: { value: EmpresaItemKind; label: string; icon: typeof MessageCircle }[] = [
  { value: "todo", label: "Pendiente", icon: CheckCircle },
  { value: "event", label: "Evento", icon: ChevronDown }, // calendar icon picked dynamically
  { value: "outreach", label: "Outreach", icon: MessageCircle },
  { value: "note", label: "Nota", icon: StickyNote },
];

const CONTACT_OPTIONS: { value: EmpresaContactMethod; label: string }[] = [
  { value: "sms", label: "SMS" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "call", label: "Llamada" },
  { value: "email", label: "Email" },
  { value: "visit", label: "Visita" },
  { value: "demo", label: "Demo" },
  { value: "meeting", label: "Reunión" },
  { value: "other", label: "Otro" },
];

export interface EmpresaPickerOption {
  id: string;
  name: string;
}

export type ItemEditorMode =
  | { type: "create"; defaults?: Partial<EmpresaItemTopCreate> }
  | { type: "edit"; item: EmpresaItem; empresaId: string | null };

interface ItemEditorPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: ItemEditorMode;
  empresas?: EmpresaPickerOption[];
  /** Called after a successful save / delete so the parent can refetch. */
  onChanged?: () => void;
}

interface ItemForm {
  title: string;
  empresa_id: string | null;
  kind: EmpresaItemKind;
  description: string;
  contact_method: EmpresaContactMethod | "";
  due_at: string | null;
  start_at: string | null;
  end_at: string | null;
  assigned_to: string | null;
}

function emptyForm(defaults: Partial<EmpresaItemTopCreate> = {}): ItemForm {
  return {
    title: defaults.title ?? "",
    empresa_id: defaults.empresa_id ?? null,
    kind: (defaults.kind ?? "todo") as EmpresaItemKind,
    description: defaults.description ?? "",
    contact_method: (defaults.contact_method ?? "") as ItemForm["contact_method"],
    due_at: defaults.due_at ?? null,
    start_at: defaults.start_at ?? null,
    end_at: defaults.end_at ?? null,
    assigned_to: defaults.assigned_to ?? null,
  };
}

function fromItem(item: EmpresaItem, empresaId: string | null): ItemForm {
  return {
    title: item.title,
    empresa_id: item.empresa_id ?? empresaId,
    kind: item.kind,
    description: item.description ?? "",
    contact_method: (item.contact_method ?? "") as ItemForm["contact_method"],
    due_at: item.due_at,
    start_at: item.start_at,
    end_at: item.end_at,
    assigned_to: item.assigned_to,
  };
}

/**
 * Slide-over panel for creating + editing empresa_items. Same component
 * handles every entry point: kanban "+", cards "+", calendar day-click,
 * Tareas row-click, channel-shortcut row.
 *
 * Wide: 384px on desktop. Backdrop is non-blocking on desktop so the
 * operator keeps the board context.
 */
export function ItemEditorPanel({
  open,
  onOpenChange,
  mode,
  empresas = [],
  onChanged,
}: ItemEditorPanelProps) {
  const initial = useMemo(
    () =>
      mode.type === "edit" ? fromItem(mode.item, mode.empresaId) : emptyForm(mode.defaults),
    [mode],
  );
  const [form, setForm] = useState<ItemForm>(initial);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (open) setForm(initial);
  }, [open, initial]);

  const isEdit = mode.type === "edit";
  const requiresDate = form.kind === "event";
  const requiresContact = form.kind === "outreach";
  const showContact = form.kind === "outreach" || form.kind === "event";
  const showDate = form.kind !== "note";

  function patchForm(updates: Partial<ItemForm>) {
    setForm((prev) => ({ ...prev, ...updates }));
  }

  async function handleSave() {
    if (!form.title.trim()) {
      toast.error("El título es requerido");
      return;
    }
    if (requiresDate && !form.start_at && !form.due_at) {
      toast.error("Eventos requieren una fecha");
      return;
    }
    if (form.start_at && form.end_at && form.end_at < form.start_at) {
      toast.error("La fecha de fin debe ser después del inicio");
      return;
    }

    const payload: EmpresaItemTopCreate = {
      title: form.title.trim(),
      empresa_id: form.empresa_id,
      kind: form.kind,
      description: form.description.trim() || null,
      contact_method: form.contact_method ? (form.contact_method as EmpresaContactMethod) : null,
      due_at: form.due_at,
      start_at: form.start_at,
      end_at: form.end_at,
      assigned_to: form.assigned_to,
    };

    setSaving(true);
    try {
      if (isEdit) {
        await empresasApi.updateItem(mode.item.id, {
          title: payload.title,
          kind: payload.kind,
          description: payload.description ?? undefined,
          contact_method: payload.contact_method ?? undefined,
          due_at: payload.due_at,
          start_at: payload.start_at,
          end_at: payload.end_at,
          assigned_to: payload.assigned_to,
        });
        toast.success("Pendiente actualizado");
      } else if (form.empresa_id) {
        await empresasApi.createItem(form.empresa_id, payload as never);
        toast.success("Pendiente creado");
      } else {
        await empresasApi.createInternalItem(payload);
        toast.success("Pendiente interno creado");
      }
      onChanged?.();
      onOpenChange(false);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const reason = detail?.reason;
      const message = detail?.message;
      if (reason === "EventDateRequired") {
        toast.error(message ?? "Eventos requieren una fecha");
      } else if (reason === "InvalidDateWindow") {
        toast.error(message ?? "El rango de fechas es inválido");
      } else {
        toast.error(message ?? "No se pudo guardar el pendiente");
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleMarkDone() {
    if (!isEdit) return;
    setSaving(true);
    try {
      await empresasApi.updateItem(mode.item.id, { done: true });
      toast.success("Marcado como hecho");
      onChanged?.();
      onOpenChange(false);
    } catch {
      toast.error("No se pudo marcar como hecho");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!isEdit) return;
    if (!window.confirm("¿Eliminar este pendiente?")) return;
    setDeleting(true);
    try {
      await empresasApi.deleteItem(mode.item.id);
      toast.success("Pendiente eliminado");
      onChanged?.();
      onOpenChange(false);
    } catch {
      toast.error("No se pudo eliminar");
    } finally {
      setDeleting(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 pointer-events-none">
      {/* Mobile backdrop only */}
      <div
        className="absolute inset-0 bg-black/20 md:hidden pointer-events-auto"
        onClick={() => onOpenChange(false)}
        aria-hidden="true"
      />
      <aside
        role="dialog"
        aria-label={isEdit ? "Editar pendiente" : "Nuevo pendiente"}
        className={cn(
          "absolute right-0 top-0 h-full w-full max-w-md bg-card border-l border-border shadow-2xl",
          "flex flex-col pointer-events-auto",
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="text-sm font-semibold text-foreground">
            {isEdit ? "Editar pendiente" : "Nuevo pendiente"}
          </p>
          <div className="flex items-center gap-1">
            {isEdit ? (
              <Button
                variant="ghost"
                size="icon"
                aria-label="Eliminar pendiente"
                disabled={deleting}
                onClick={handleDelete}
              >
                {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4 text-destructive" />}
              </Button>
            ) : null}
            <Button
              variant="ghost"
              size="icon"
              aria-label="Cerrar"
              onClick={() => onOpenChange(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Título *</label>
            <Input
              autoFocus
              value={form.title}
              onChange={(e) => patchForm({ title: e.target.value })}
              placeholder={
                form.kind === "event"
                  ? "Visita, demo, reunión…"
                  : form.kind === "outreach"
                    ? "Resumen del contacto…"
                    : form.kind === "note"
                      ? "Nota interna…"
                      : "Pendiente…"
              }
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Tipo</label>
            <div className="flex flex-wrap gap-1.5">
              {KIND_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => patchForm({ kind: opt.value })}
                  className={cn(
                    "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                    form.kind === opt.value
                      ? "bg-accent text-accent-foreground"
                      : "border border-border text-muted-foreground hover:bg-muted/40",
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {showDate ? (
            <div className="grid grid-cols-1 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  {form.kind === "event" ? "Inicio *" : "Fecha límite"}
                </label>
                <DateTimePicker
                  value={form.kind === "event" ? form.start_at : form.due_at}
                  onChange={(iso) =>
                    form.kind === "event" ? patchForm({ start_at: iso }) : patchForm({ due_at: iso })
                  }
                  invalid={requiresDate && !form.start_at && !form.due_at}
                />
              </div>
              {form.kind === "event" ? (
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">Fin</label>
                  <DateTimePicker
                    value={form.end_at}
                    onChange={(iso) => patchForm({ end_at: iso })}
                  />
                </div>
              ) : null}
            </div>
          ) : null}

          {showContact ? (
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Canal {requiresContact ? "*" : ""}
              </label>
              <div className="flex flex-wrap gap-1.5">
                {CONTACT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => patchForm({ contact_method: opt.value })}
                    className={cn(
                      "rounded-full px-3 py-1 text-xs",
                      form.contact_method === opt.value
                        ? "bg-accent text-accent-foreground"
                        : "border border-border text-muted-foreground hover:bg-muted/40",
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Empresa</label>
            <select
              value={form.empresa_id ?? ""}
              onChange={(e) => patchForm({ empresa_id: e.target.value || null })}
              className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
              data-testid="item-empresa-picker"
            >
              <option value="">Sin empresa (interna)</option>
              {empresas.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Notas</label>
            <Textarea
              rows={4}
              value={form.description}
              onChange={(e) => patchForm({ description: e.target.value })}
              placeholder="Detalle, contexto, próximos pasos…"
              className="resize-y"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3">
          {isEdit ? (
            <Button
              variant="ghost"
              size="sm"
              disabled={saving || mode.item.done}
              onClick={handleMarkDone}
            >
              {mode.item.done ? "Hecho" : "Marcar hecho"}
            </Button>
          ) : null}
          <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
            Guardar
          </Button>
        </div>
      </aside>
    </div>
  );
}

/** Compact channel shortcut row used on empresa cards. */
export const CHANNEL_SHORTCUTS: { method: EmpresaContactMethod; icon: typeof MessageCircle; label: string; color: string }[] = [
  { method: "sms", icon: MessageCircle, label: "SMS", color: "text-blue-600" },
  { method: "whatsapp", icon: MessageCircle, label: "WhatsApp", color: "text-emerald-600" },
  { method: "call", icon: Phone, label: "Llamada", color: "text-violet-600" },
  { method: "email", icon: Mail, label: "Email", color: "text-amber-600" },
  { method: "visit", icon: MapPin, label: "Visita", color: "text-rose-600" },
];

/** Visual badge for an item's `kind` — one consistent map across the UI. */
export function kindBadgeStyle(kind: EmpresaItemKind | string | undefined): {
  className: string;
  label: string;
} {
  switch (kind) {
    case "event":
      return { className: "bg-sky-100 text-sky-700", label: "Evento" };
    case "outreach":
      return { className: "bg-emerald-100 text-emerald-700", label: "Outreach" };
    case "note":
      return { className: "bg-violet-100 text-violet-700", label: "Nota" };
    case "todo":
    default:
      return { className: "bg-slate-100 text-slate-700", label: "Pendiente" };
  }
}

export const ItemEditorPanelExports = { Users2, Building2 };
