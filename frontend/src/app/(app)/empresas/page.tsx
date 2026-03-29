"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Building2,
  ChevronDown,
  ChevronRight,
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
  type EmpresaItem,
  type EmpresaItemCreate,
  type EmpresaListItem,
} from "@/lib/api/empresas";

// ── Labels ──────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  open: "Abierto",
  in_progress: "En progreso",
  done: "Hecho",
};

const STATUS_DOT: Record<string, string> = {
  open: "bg-neutral-400",
  in_progress: "bg-neutral-600",
  done: "bg-neutral-800",
};

const PRIORITY_LABELS: Record<string, string> = {
  low: "Baja",
  medium: "Media",
  high: "Alta",
};

const TYPE_LABELS: Record<string, string> = {
  need: "Necesidad",
  task: "Tarea",
};

// ── Initial form states ─────────────────────────────────────────────

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
};

const EMPTY_ITEM: EmpresaItemCreate = {
  type: "need",
  title: "",
  description: null,
  status: "open",
  priority: null,
  due_date: null,
};

// ── Page ────────────────────────────────────────────────────────────

export default function EmpresasPage() {
  const [empresas, setEmpresas] = useState<EmpresaListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const [expandedCards, setExpandedCards] = useState<Record<string, Empresa>>({});
  const [detailsOpenIds, setDetailsOpenIds] = useState<Set<string>>(new Set());

  const [empresaModalOpen, setEmpresaModalOpen] = useState(false);
  const [empresaForm, setEmpresaForm] = useState<EmpresaCreate>(EMPTY_EMPRESA);
  const [editingEmpresaId, setEditingEmpresaId] = useState<string | null>(null);

  const [itemModalOpen, setItemModalOpen] = useState(false);
  const [itemForm, setItemForm] = useState<EmpresaItemCreate>(EMPTY_ITEM);
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [itemEmpresaId, setItemEmpresaId] = useState<string | null>(null);

  // ── Data loading ──────────────────────────────────────────────────

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

  const loadCard = async (id: string) => {
    try {
      const data = await empresasApi.get(id);
      setExpandedCards((prev) => ({ ...prev, [id]: data }));
    } catch {
      toast.error("Error al cargar empresa");
    }
  };

  const toggleCard = (id: string) => {
    if (expandedCards[id]) {
      setExpandedCards((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setDetailsOpenIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } else {
      loadCard(id);
    }
  };

  const toggleDetails = (id: string) => {
    setDetailsOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // ── Empresa CRUD ──────────────────────────────────────────────────

  const openCreateEmpresa = () => {
    setEmpresaForm(EMPTY_EMPRESA);
    setEditingEmpresaId(null);
    setEmpresaModalOpen(true);
  };

  const openEditEmpresa = (e: Empresa) => {
    setEmpresaForm({
      name: e.name,
      logo_url: e.logo_url,
      industry: e.industry,
      email: e.email,
      phone: e.phone,
      address: e.address,
      rfc: e.rfc,
      razon_social: e.razon_social,
      regimen_fiscal: e.regimen_fiscal,
    });
    setEditingEmpresaId(e.id);
    setEmpresaModalOpen(true);
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
        if (expandedCards[editingEmpresaId]) loadCard(editingEmpresaId);
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
      setExpandedCards((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      loadEmpresas();
    } catch {
      toast.error("Error al eliminar empresa");
    }
  };

  // ── Item CRUD ─────────────────────────────────────────────────────

  const openCreateItem = (empresaId: string) => {
    setItemForm(EMPTY_ITEM);
    setEditingItemId(null);
    setItemEmpresaId(empresaId);
    setItemModalOpen(true);
  };

  const openEditItem = (item: EmpresaItem) => {
    setItemForm({
      type: item.type,
      title: item.title,
      description: item.description,
      status: item.status,
      priority: item.priority,
      due_date: item.due_date,
    });
    setEditingItemId(item.id);
    setItemEmpresaId(item.empresa_id);
    setItemModalOpen(true);
  };

  const saveItem = async () => {
    if (!itemForm.title.trim()) {
      toast.error("El título es requerido");
      return;
    }
    try {
      if (editingItemId) {
        const { type, ...updateData } = itemForm;
        await empresasApi.updateItem(editingItemId, updateData);
        toast.success("Elemento actualizado");
      } else if (itemEmpresaId) {
        await empresasApi.createItem(itemEmpresaId, itemForm);
        toast.success("Elemento creado");
      }
      setItemModalOpen(false);
      if (itemEmpresaId) loadCard(itemEmpresaId);
      loadEmpresas();
    } catch {
      toast.error("Error al guardar elemento");
    }
  };

  const deleteItem = async (itemId: string, empresaId: string) => {
    try {
      await empresasApi.deleteItem(itemId);
      toast.success("Elemento eliminado");
      loadCard(empresaId);
      loadEmpresas();
    } catch {
      toast.error("Error al eliminar elemento");
    }
  };

  // ── Render ────────────────────────────────────────────────────────

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
            const expanded = expandedCards[emp.id];
            const showDetails = detailsOpenIds.has(emp.id);

            return (
              <div
                key={emp.id}
                className="rounded-xl border bg-card shadow-sm flex flex-col overflow-hidden"
              >
                {/* Logo + Name header */}
                <button
                  onClick={() => toggleCard(emp.id)}
                  className="flex flex-col items-center gap-3 px-5 pt-6 pb-4 hover:bg-muted/40 transition-colors cursor-pointer"
                >
                  <LogoAvatar url={emp.logo_url} name={emp.name} />
                  <div className="text-center">
                    <h3 className="font-semibold text-base truncate max-w-[200px]">
                      {emp.name}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {emp.item_count} {emp.item_count === 1 ? "elemento" : "elementos"}
                    </p>
                  </div>
                  {expanded ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  )}
                </button>

                {/* Expanded content */}
                {expanded && (
                  <div className="border-t px-4 pb-4 pt-3 space-y-3 flex-1">
                    {/* Top bar: + button left, ... menu right */}
                    <div className="flex items-center justify-between">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs text-muted-foreground"
                        onClick={() => openCreateItem(emp.id)}
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
                          <DropdownMenuItem onClick={() => openEditEmpresa(expanded)}>
                            Editar empresa
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

                    {/* Items list */}
                    {expanded.items.length === 0 ? (
                      <p className="text-sm text-muted-foreground py-3 text-center">
                        Sin elementos
                      </p>
                    ) : (
                      <div className="space-y-1">
                        {expanded.items.map((item) => (
                          <div
                            key={item.id}
                            className="group flex items-start justify-between gap-2 rounded-lg px-2.5 py-2 hover:bg-muted/50 transition-colors"
                          >
                            <div className="min-w-0 space-y-0.5">
                              <p className="text-sm font-medium leading-tight">
                                {item.title}
                              </p>
                              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                                <span>{TYPE_LABELS[item.type]}</span>
                                <span className="text-muted-foreground/40">·</span>
                                <span className="flex items-center gap-1">
                                  <span className={`inline-block h-1.5 w-1.5 rounded-full ${STATUS_DOT[item.status]}`} />
                                  {STATUS_LABELS[item.status]}
                                </span>
                                {item.type === "need" && item.priority && (
                                  <>
                                    <span className="text-muted-foreground/40">·</span>
                                    <span>{PRIORITY_LABELS[item.priority]}</span>
                                  </>
                                )}
                                {item.due_date && (
                                  <>
                                    <span className="text-muted-foreground/40">·</span>
                                    <span>{item.due_date}</span>
                                  </>
                                )}
                              </div>
                            </div>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-0.5"
                                >
                                  <MoreHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => openEditItem(item)}>
                                  Editar
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  className="text-destructive focus:text-destructive"
                                  onClick={() => deleteItem(item.id, emp.id)}
                                >
                                  Eliminar
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Details toggle */}
                    <button
                      onClick={() => toggleDetails(emp.id)}
                      className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors w-full pt-1"
                    >
                      {showDetails ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3" />
                      )}
                      {showDetails ? "Ocultar detalles" : "Ver detalles"}
                    </button>

                    {showDetails && (
                      <div className="grid grid-cols-2 gap-2 text-xs rounded-lg border bg-muted/30 p-3">
                        <Detail label="Industria" value={expanded.industry} />
                        <Detail label="Email" value={expanded.email} />
                        <Detail label="Teléfono" value={expanded.phone} />
                        <Detail label="RFC" value={expanded.rfc} />
                        <Detail label="Razón Social" value={expanded.razon_social} />
                        <Detail label="Régimen Fiscal" value={expanded.regimen_fiscal} />
                        {expanded.address && (
                          <div className="col-span-2">
                            <Detail label="Dirección" value={expanded.address} />
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Empresa Modal ──────────────────────────────────────────── */}
      <Dialog open={empresaModalOpen} onOpenChange={setEmpresaModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingEmpresaId ? "Editar Empresa" : "Nueva Empresa"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Nombre *</label>
              <Input
                value={empresaForm.name}
                onChange={(e) => setEmpresaForm({ ...empresaForm, name: e.target.value })}
                placeholder="Nombre de la empresa"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Logo</label>
              <LogoPicker
                value={empresaForm.logo_url ?? null}
                onChange={(url) => setEmpresaForm({ ...empresaForm, logo_url: url })}
              />
            </div>
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
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setEmpresaModalOpen(false)}>
                Cancelar
              </Button>
              <Button onClick={saveEmpresa}>Guardar</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Item Modal ─────────────────────────────────────────────── */}
      <Dialog open={itemModalOpen} onOpenChange={setItemModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editingItemId ? "Editar Elemento" : "Nuevo Elemento"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {!editingItemId && (
              <div>
                <label className="text-sm font-medium">Tipo</label>
                <Select
                  value={itemForm.type}
                  onValueChange={(v) =>
                    setItemForm({ ...itemForm, type: v as "need" | "task", priority: v === "task" ? null : itemForm.priority })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="need">Necesidad</SelectItem>
                    <SelectItem value="task">Tarea</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            <div>
              <label className="text-sm font-medium">Título *</label>
              <Input
                value={itemForm.title}
                onChange={(e) => setItemForm({ ...itemForm, title: e.target.value })}
                placeholder="Título del elemento"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Descripción</label>
              <Textarea
                value={itemForm.description ?? ""}
                onChange={(e) =>
                  setItemForm({ ...itemForm, description: e.target.value || null })
                }
                rows={3}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">Estado</label>
                <Select
                  value={itemForm.status}
                  onValueChange={(v) => setItemForm({ ...itemForm, status: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="open">Abierto</SelectItem>
                    <SelectItem value="in_progress">En progreso</SelectItem>
                    <SelectItem value="done">Hecho</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {itemForm.type === "need" && (
                <div>
                  <label className="text-sm font-medium">Prioridad</label>
                  <Select
                    value={itemForm.priority ?? ""}
                    onValueChange={(v) => setItemForm({ ...itemForm, priority: v || null })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Sin prioridad" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Baja</SelectItem>
                      <SelectItem value="medium">Media</SelectItem>
                      <SelectItem value="high">Alta</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            <div>
              <label className="text-sm font-medium">Fecha límite</label>
              <Input
                type="date"
                value={itemForm.due_date ?? ""}
                onChange={(e) =>
                  setItemForm({ ...itemForm, due_date: e.target.value || null })
                }
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setItemModalOpen(false)}>
                Cancelar
              </Button>
              <Button onClick={saveItem}>Guardar</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function LogoAvatar({ url, name, size = "lg" }: { url: string | null; name: string; size?: "lg" | "sm" }) {
  const [failed, setFailed] = useState(false);
  const dim = size === "lg" ? "h-20 w-20" : "h-10 w-10";
  const iconDim = size === "lg" ? "h-9 w-9" : "h-5 w-5";
  const radius = size === "lg" ? "rounded-2xl" : "rounded-xl";

  if (url && !failed) {
    return (
      <img
        src={url}
        alt={name}
        className={`${dim} ${radius} object-cover shadow-sm`}
        onError={() => setFailed(true)}
      />
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

function Detail({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="min-w-0">
      <p className="text-muted-foreground text-[10px] uppercase tracking-wide">{label}</p>
      <p className="font-medium text-xs truncate">{value || "—"}</p>
    </div>
  );
}
