"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  LayoutDashboard,
  DollarSign,
  CheckSquare,
  Calendar,
  Settings,
  UsersRound,
  Briefcase,
} from "lucide-react";

// Removed entries (kept the audit trail rather than the surface area):
//   - /customers had no app page; helper survives only for Facturas reads.
//   - Vault, Meetings, Documents, OKRs, Assistant, Eva Customers
//     consolidated into /empresas per the company CRM consolidation plan.
const pages = [
  { label: "Dashboard", icon: LayoutDashboard, href: "/dashboard", keywords: "home overview kpis metrics" },
  { label: "Finances", icon: DollarSign, href: "/finances", keywords: "income expenses invoices money revenue" },
  { label: "Empresas", icon: Briefcase, href: "/empresas", keywords: "companies crm accounts customers eva linked unlinked" },
  // /tasks merged into /empresas?view=tasks (empresas-ux-pass).
  { label: "Tareas", icon: CheckSquare, href: "/empresas?view=tasks", keywords: "tasks pendientes todo open overdue" },
  { label: "Pipeline de Empresas", icon: Briefcase, href: "/empresas?view=kanban", keywords: "sales pipeline leads crm prospects kanban" },
  { label: "Calendario de Empresas", icon: Calendar, href: "/empresas?view=calendar", keywords: "calendar schedule meetings followups events" },
  { label: "Cuentas Eva", icon: Briefcase, href: "/empresas?view=accounts", keywords: "eva accounts customers platform" },
  { label: "Team", icon: UsersRound, href: "/team", keywords: "users members invite admin people" },
  { label: "Settings", icon: Settings, href: "/settings", keywords: "profile preferences account" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Search modules..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigation">
          {pages.map((page) => {
            const Icon = page.icon;
            return (
              <CommandItem
                key={page.href}
                value={`${page.label} ${page.keywords}`}
                onSelect={() => {
                  router.push(page.href);
                  setOpen(false);
                }}
              >
                <Icon className="mr-2 h-4 w-4" />
                {page.label}
              </CommandItem>
            );
          })}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
