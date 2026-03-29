"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  ChevronDown,
  ImagePlus,
  MoreHorizontal,
  Plus,
  Search,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  empresasApi,
  type Empresa,
  type EmpresaCreate,
  type EmpresaHistory,
  type EmpresaListItem,
} from "@/lib/api/empresas";

// ── Constants ──────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  operativo: { label: "Operativo", className: "bg-emerald-100 text-emerald-700" },
  en_implementacion: { label: "En implementación", className: "bg-amber-100 text-amber-700" },
  requiere_atencion: { label: "Requiere atención", className: "bg-red-100 text-red-700" },
};

const BALL_ON_CONFIG: Record<string, { label: string; icon: typeof ArrowLeft }> = {
  nosotros: { label: "Nosotros", icon: ArrowLeft },
  cliente: { label: "Cliente", icon: ArrowRight },
};

const FIELD_LABELS: Record<string, string> = {
  status: "Status",
  ball_on: "Responsable",
  summary_note: "Nota de seguimiento",
};

const VALUE_LABELS: Record<string, string> = {
  operativo: "Operativo",
  en_implementacion: "En implementación",
  requiere_atencion: "Requiere atención",
  nosotros: "Nosotros",
  cliente: "Cliente",
};

const EMPTY_EMPRESA: EmpresaCreate = {
  name: "",
  logo_url: null,
  industry: null,
  email: null,
  phone: null,
  address: null,
  rfc: null,
  razon_social: null,
  regimen_fiscal: null,
  status: "operativo",
  ball_on: null,
  summary_note: null,
};

// ── Page ───────────────────────────────────────────────────────────

export default function EmpresasPage() {
  const [empresas, setEmpresas] = useState<EmpresaListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  // Empresa modal
  const [empresaModalOpen, setEmpresaModalOpen] = useState(false);
  const [empresaForm, setEmpresaForm] = useState<EmpresaCreate>(EMPTY_EMPRESA);
  const [editingEmpresaId, setEditingEmpresaId] = useState<string | null>(null);

  // History modal
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [historyEmpresaName, setHistoryEmpresaName] = useState("");
  const [historyEntries, setHistoryEntries] = useState<EmpresaHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Inline add item
  const [addingItemFor, setAddingItemFor] = useState<string | null>(null);
  const [newItemTitle, setNewItemTitle] = useState("");
  const addItemInputRef = useRef<HTMLInputElement>(null);

  // Items expanded (show all)
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  // Toggling items (for optimistic UI + disable)
  const [togglingItems, setTogglingItems] = useState<Set<string>>(new Set());

  // ── Data loading ────────────────────────────────────────────────

  const loadEmpresas = async () => {
    try {
      const data = await empresasApi.list(search || undefined);
      setEmpresas(data);
    } catch {
      toast.error("Error al cargar empresas");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEmpresas();
  }, [search]);

  // ── Empresa CRUD ────────────────────────────────────────────────

  const openCreateEmpresa = () => {
    setEmpresaForm(EMPTY_EMPRESA);
    setEditingEmpresaId(null);
    setEmpresaModalOpen(true);
  };

  const openEditEmpresa = async (emp: EmpresaListItem) => {
    try {
      const full = await empresasApi.get(emp.id);
      setEmpresaForm({
        name: full.name,
        logo_url: full.logo_url,
        industry: full.industry,
        email: full.email,
        phone: full.phone,
        address: full.address,
        rfc: full.rfc,
        razon_social: full.razon_social,
        regimen_fiscal: full.regimen_fiscal,
        status: full.status,
        ball_on: full.ball_on,
        summary_note: full.summary_note,
      });
      setEditingEmpresaId(full.id);
      setEmpresaModalOpen(true);
    } catch {
      toast.error("Error al cargar empresa");
    }
  };

  const saveEmpresa = async () => {
    if (!empresaForm.name.trim()) {
      toast.error("El nombre es requerido");
      return;
    }
    try {
      if (editingEmpresaId) {
        await empresasApi.update(editingEmpresaId, empresaForm);
        toast.success("Empresa actualizada");
      } else {
        await empresasApi.create(empresaForm);
        toast.success("Empresa creada");
      }
      setEmpresaModalOpen(false);
      loadEmpresas();
    } catch {
      toast.error("Error al guardar empresa");
    }
  };

  const deleteEmpresa = async (id: string) => {
    try {
      await empresasApi.delete(id);
      toast.success("Empresa eliminada");
      loadEmpresas();
    } catch {
      toast.error("Error al eliminar empresa");
    }
  };

  // ── Items ───────────────────────────────────────────────────────

  const toggleItem = async (itemId: string, empresaId: string) => {
    if (togglingItems.has(itemId)) return;
    setTogglingItems((prev) => new Set(prev).add(itemId));

    // Optimistic: remove from pending list
    setEmpresas((prev) =>
      prev.map((emp) =>
        emp.id === empresaId
          ? {
              ...emp,
              pending_items: emp.pending_items.filter((i) => i.id !== itemId),
              pending_count: emp.pending_count - 1,
            }
          : emp
      )
    );

    try {
      await empresasApi.toggleItem(itemId);
    } catch {
      toast.error("Error al actualizar");
      loadEmpresas(); // revert
    } finally {
      setTogglingItems((prev) => {
        const next = new Set(prev);
        next.delete(itemId);
        return next;
      });
    }
  };

  const addItem = async (empresaId: string) => {
    if (!newItemTitle.trim()) return;
    try {
      await empresasApi.createItem(empresaId, { title: newItemTitle.trim() });
      setNewItemTitle("");
      setAddingItemFor(null);
      loadEmpresas();
    } catch {
      toast.error("Error al agregar pendiente");
    }
  };

  const startAddingItem = (empresaId: string) => {
    setAddingItemFor(empresaId);
    setNewItemTitle("");
    setTimeout(() => addItemInputRef.current?.focus(), 50);
  };

  // ── History ─────────────────────────────────────────────────────

  const openHistory = async (empresaId: string, empresaName: string) => {
    setHistoryEmpresaName(empresaName);
    setHistoryEntries([]);
    setHistoryLoading(true);
    setHistoryModalOpen(true);
    try {
      const data = await empresasApi.getHistory(empresaId);
      setHistoryEntries(data);
    } catch {
      toast.error("Error al cargar historial");
    } finally {
      setHistoryLoading(false);
    }
  };

  // ── Render ──────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Empresas</h1>
        <Button onClick={openCreateEmpresa}>
          <Plus className="mr-2 h-4 w-4" />
          Nueva Empresa
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Buscar empresa..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Cards grid */}
      {loading ? (
        <div className="py-12 text-center text-muted-foreground">Cargando...</div>
      ) : empresas.length === 0 ? (
        <div className="py-12 text-center text-muted-foreground">
          {search ? "No se encontraron empresas" : "No hay empresas aún. Crea la primera."}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {empresas.map((emp) => {
            const statusCfg = STATUS_CONFIG[emp.status] || STATUS_CONFIG.operativo;
            const ballCfg = emp.ball_on ? BALL_ON_CONFIG[emp.ball_on] : null;
            const isExpanded = expandedItems.has(emp.id);
            const visibleItems = isExpanded ? emp.pending_items : emp.pending_items.slice(0, 3);
            const overflowCount = emp.pending_items.length - 3;

            return (
              <div
                key={emp.id}
                className="rounded-xl border bg-card shadow-sm flex flex-col overflow-hidden"
              >
                {/* Status banner at top */}
                <div className={`flex items-center justify-center gap-2 px-4 py-1.5 ${statusCfg.className}`}>
                  <span className="text-[11px] font-semibold">{statusCfg.label}</span>
                  {ballCfg && (
                    <span className="inline-flex items-center gap-0.5 text-[11px] opacity-80">
                      · <ballCfg.icon className="h-3 w-3" /> {ballCfg.label}
                    </span>
                  )}
                </div>

                {/* Logo + name */}
                <div className="flex flex-col items-center gap-3 px-5 pt-5 pb-3">
                  <LogoAvatar url={emp.logo_url} name={emp.name} />
                  <h3 className="font-semibold text-lg truncate max-w-[220px] text-center">
                    {emp.name}
                  </h3>
                </div>

                {/* Summary note */}
                {emp.summary_note && (
                  <p className="px-5 pb-2 text-xs text-muted-foreground italic text-center">
                    {emp.summary_note}
                  </p>
                )}

                {/* Pending items */}
                <div className="px-4 pt-3 pb-2 flex-1 space-y-1">
                  {emp.pending_count === 0 ? (
                    <p className="text-xs text-muted-foreground text-center py-2">Sin pendientes</p>
                  ) : (
                    <>
                      {visibleItems.map((item) => (
                        <label
                          key={item.id}
                          className="flex items-start gap-2 group cursor-pointer rounded px-1.5 py-1 hover:bg-muted/50 transition-colors"
                        >
                          <button
                            type="button"
                            disabled={togglingItems.has(item.id)}
                            onClick={() => toggleItem(item.id, emp.id)}
                            className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border border-muted-foreground/30 transition-colors hover:border-foreground hover:bg-muted disabled:opacity-50"
                          >
                            {togglingItems.has(item.id) && (
                              <Check className="h-3 w-3 text-muted-foreground animate-pulse" />
                            )}
                          </button>
                          <span className="text-xs leading-tight truncate">{item.title}</span>
                        </label>
                      ))}
                      {!isExpanded && overflowCount > 0 && (
                        <button
                          onClick={() => setExpandedItems((prev) => new Set(prev).add(emp.id))}
                          className="text-[11px] text-muted-foreground hover:text-foreground transition-colors pl-1.5 pt-0.5"
                        >
                          +{overflowCount} más
                        </button>
                      )}
                      {isExpanded && overflowCount > 0 && (
                        <button
                          onClick={() => {
                            setExpandedItems((prev) => {
                              const next = new Set(prev);
                              next.delete(emp.id);
                              return next;
                            });
                          }}
                          className="text-[11px] text-muted-foreground hover:text-foreground transition-colors pl-1.5 pt-0.5"
                        >
                          Mostrar menos
                        </button>
                      )}
                    </>
                  )}
                </div>

                {/* Inline add item */}
                {addingItemFor === emp.id ? (
                  <div className="px-4 pb-2">
                    <div className="flex gap-1.5">
                      <Input
                        ref={addItemInputRef}
                        value={newItemTitle}
                        onChange={(e) => setNewItemTitle(e.target.value)}
                        placeholder="Nuevo pendiente..."
                        className="h-7 text-xs"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") addItem(emp.id);
                          if (e.key === "Escape") setAddingItemFor(null);
                        }}
                      />
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 shrink-0"
                        onClick={() => addItem(emp.id)}
                      >
                        <Check className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 shrink-0"
                        onClick={() => setAddingItemFor(null)}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                ) : null}

                {/* Footer: add + menu */}
                <div className="border-t px-3 py-2 flex items-center justify-between">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-xs text-muted-foreground"
                    onClick={() => startAddingItem(emp.id)}
                  >
                    <Plus className="mr-1 h-3 w-3" />
                    Agregar
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-7 w-7">
                        <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEditEmpresa(emp)}>
                        Editar empresa
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => openHistory(emp.id, emp.name)}>
                        Historial
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => deleteEmpresa(emp.id)}
                      >
                        Eliminar empresa
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Empresa Modal ──────────────────────────────────────────── */}
      <Dialog open={empresaModalOpen} onOpenChange={setEmpresaModalOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingEmpresaId ? "Editar Empresa" : "Nueva Empresa"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {/* Name */}
            <div>
              <label className="text-sm font-medium">Nombre *</label>
              <Input
                value={empresaForm.name}
                onChange={(e) => setEmpresaForm({ ...empresaForm, name: e.target.value })}
                placeholder="Nombre de la empresa"
              />
            </div>

            {/* Logo */}
            <div>
              <label className="text-sm font-medium">Logo</label>
              <LogoPicker
                value={empresaForm.logo_url ?? null}
                onChange={(url) => setEmpresaForm({ ...empresaForm, logo_url: url })}
              />
            </div>

            {/* Status + Ball */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">Status</label>
                <Select
                  value={empresaForm.status || "operativo"}
                  onValueChange={(v) => setEmpresaForm({ ...empresaForm, status: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="operativo">Operativo</SelectItem>
                    <SelectItem value="en_implementacion">En implementación</SelectItem>
                    <SelectItem value="requiere_atencion">Requiere atención</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium">Responsable</label>
                <Select
                  value={empresaForm.ball_on || "_none"}
                  onValueChange={(v) => setEmpresaForm({ ...empresaForm, ball_on: v === "_none" ? null : v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_none">Sin asignar</SelectItem>
                    <SelectItem value="nosotros">← Nosotros</SelectItem>
                    <SelectItem value="cliente">→ Cliente</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Summary note */}
            <div>
              <label className="text-sm font-medium">Nota de seguimiento</label>
              <Textarea
                value={empresaForm.summary_note ?? ""}
                onChange={(e) =>
                  setEmpresaForm({ ...empresaForm, summary_note: e.target.value || null })
                }
                placeholder="Resumen del estado actual..."
                rows={2}
              />
            </div>

            {/* Separator */}
            <div className="border-t pt-3">
              <button
                type="button"
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors w-full"
                onClick={(e) => {
                  const target = e.currentTarget.nextElementSibling;
                  if (target) target.classList.toggle("hidden");
                  const chevron = e.currentTarget.querySelector("svg");
                  if (chevron) chevron.classList.toggle("rotate-180");
                }}
              >
                <ChevronDown className="h-3 w-3 transition-transform" />
                Datos fiscales y contacto
              </button>
              <div className="hidden mt-3 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-medium">Industria</label>
                    <Input
                      value={empresaForm.industry ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, industry: e.target.value || null })
                      }
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Email</label>
                    <Input
                      value={empresaForm.email ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, email: e.target.value || null })
                      }
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Teléfono</label>
                    <Input
                      value={empresaForm.phone ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, phone: e.target.value || null })
                      }
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">RFC</label>
                    <Input
                      value={empresaForm.rfc ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, rfc: e.target.value || null })
                      }
                      maxLength={13}
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Razón Social</label>
                    <Input
                      value={empresaForm.razon_social ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, razon_social: e.target.value || null })
                      }
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Régimen Fiscal</label>
                    <Input
                      value={empresaForm.regimen_fiscal ?? ""}
                      onChange={(e) =>
                        setEmpresaForm({ ...empresaForm, regimen_fiscal: e.target.value || null })
                      }
                    />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">Dirección</label>
                  <Textarea
                    value={empresaForm.address ?? ""}
                    onChange={(e) =>
                      setEmpresaForm({ ...empresaForm, address: e.target.value || null })
                    }
                    rows={2}
                  />
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setEmpresaModalOpen(false)}>
                Cancelar
              </Button>
              <Button onClick={saveEmpresa}>Guardar</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── History Modal ──────────────────────────────────────────── */}
      <Dialog open={historyModalOpen} onOpenChange={setHistoryModalOpen}>
        <DialogContent className="max-w-md max-h-[70vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Historial — {historyEmpresaName}</DialogTitle>
          </DialogHeader>
          {historyLoading ? (
            <p className="text-sm text-muted-foreground py-4 text-center">Cargando...</p>
          ) : historyEntries.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">Sin cambios registrados</p>
          ) : (
            <div className="space-y-3">
              {historyEntries.map((entry) => (
                <div key={entry.id} className="border-l-2 border-muted pl-3 py-1">
                  <p className="text-sm">
                    <span className="font-medium">{FIELD_LABELS[entry.field_changed] || entry.field_changed}</span>
                    {" cambiado de "}
                    <span className="text-muted-foreground">
                      {entry.old_value ? (VALUE_LABELS[entry.old_value] || entry.old_value) : "vacío"}
                    </span>
                    {" a "}
                    <span className="font-medium">
                      {entry.new_value ? (VALUE_LABELS[entry.new_value] || entry.new_value) : "vacío"}
                    </span>
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {entry.changed_by_name || "Sistema"} · {formatRelativeTime(entry.changed_at)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Helper Components ──────────────────────────────────────────────

function LogoAvatar({ url, name, size = "lg" }: { url: string | null; name: string; size?: "lg" | "sm" }) {
  const [failed, setFailed] = useState(false);
  const prevUrl = useRef(url);
  if (prevUrl.current !== url) {
    prevUrl.current = url;
    setFailed(false);
  }

  const dim = size === "lg" ? "h-20 w-20" : "h-10 w-10";
  const iconDim = size === "lg" ? "h-9 w-9" : "h-5 w-5";
  const radius = size === "lg" ? "rounded-2xl" : "rounded-xl";

  if (url && !failed) {
    return (
      <div className={`flex ${dim} items-center justify-center ${radius} bg-white shadow-sm p-1.5`}>
        <img
          src={url}
          alt={name}
          className="h-full w-full object-contain"
          onError={() => setFailed(true)}
        />
      </div>
    );
  }

  return (
    <div className={`flex ${dim} items-center justify-center ${radius} bg-muted shadow-sm`}>
      <Building2 className={`${iconDim} text-muted-foreground`} />
    </div>
  );
}

function LogoPicker({ value, onChange }: { value: string | null; onChange: (url: string | null) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 500_000) {
      alert("La imagen debe pesar menos de 500 KB");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      onChange(reader.result as string);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  return (
    <div className="flex items-center gap-3 mt-1">
      <LogoAvatar url={value} name="" size="sm" />
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-8 text-xs"
        onClick={() => inputRef.current?.click()}
      >
        <ImagePlus className="mr-1.5 h-3.5 w-3.5" />
        {value ? "Cambiar" : "Seleccionar imagen"}
      </Button>
      {value && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => onChange(null)}
        >
          <X className="h-3.5 w-3.5 text-muted-foreground" />
        </Button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleFile}
      />
    </div>
  );
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "ahora";
  if (diffMin < 60) return `hace ${diffMin} min`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `hace ${diffHrs}h`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays === 1) return "ayer";
  if (diffDays < 30) return `hace ${diffDays} días`;
  const diffMonths = Math.floor(diffDays / 30);
  return `hace ${diffMonths} ${diffMonths === 1 ? "mes" : "meses"}`;
}
