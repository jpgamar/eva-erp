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
  Users,
  Lock,
  CheckSquare,
  Target,
  Calendar,
  FolderOpen,
  Trophy,
  Settings,
  UsersRound,
} from "lucide-react";
import { OwlIcon } from "@/components/owl-icon";

const pages = [
  { label: "Dashboard", icon: LayoutDashboard, href: "/dashboard", keywords: "home overview kpis metrics" },
  { label: "Finances", icon: DollarSign, href: "/finances", keywords: "income expenses invoices money revenue" },
  { label: "Customers", icon: Users, href: "/customers", keywords: "clients mrr arr subscriptions" },
  { label: "Vault", icon: Lock, href: "/vault", keywords: "passwords credentials secrets costs" },
  { label: "Tasks", icon: CheckSquare, href: "/tasks", keywords: "kanban boards todo work" },
  { label: "Prospects", icon: Target, href: "/prospects", keywords: "sales pipeline leads crm" },
  { label: "Meetings", icon: Calendar, href: "/meetings", keywords: "calendar schedule calls" },
  { label: "Documents", icon: FolderOpen, href: "/documents", keywords: "files storage uploads" },
  { label: "OKRs", icon: Trophy, href: "/okrs", keywords: "objectives key results goals" },
  { label: "Eva", icon: OwlIcon, href: "/assistant", keywords: "chat ai query ask eva" },
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
