"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
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
  Sparkles,
  Settings,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, href: "/dashboard", phase: 4 },
  { label: "Finances", icon: DollarSign, href: "/finances", phase: 3 },
  { label: "Customers", icon: Users, href: "/customers", phase: 3 },
  { label: "Vault", icon: Lock, href: "/vault", phase: 2 },
  { label: "Tasks", icon: CheckSquare, href: "/tasks", phase: 2 },
  { label: "Prospects", icon: Target, href: "/prospects", phase: 5 },
  { label: "Meetings", icon: Calendar, href: "/meetings", phase: 5 },
  { label: "Documents", icon: FolderOpen, href: "/documents", phase: 5 },
  { label: "OKRs", icon: Trophy, href: "/okrs", phase: 6 },
  { label: "AI Assistant", icon: Sparkles, href: "/assistant", phase: 7 },
];

const bottomItems = [
  { label: "Settings", icon: Settings, href: "/settings", phase: 1 },
];

const CURRENT_PHASE = 2;

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();

  const renderNavItem = (item: typeof navItems[0]) => {
    const isActive = pathname.startsWith(item.href);
    const isBuilt = item.phase <= CURRENT_PHASE;
    const Icon = item.icon;

    const content = (
      <Link
        href={isBuilt ? item.href : "#"}
        className={cn(
          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-primary/10 text-primary"
            : "text-muted-foreground hover:bg-accent hover:text-foreground",
          !isBuilt && "opacity-50 cursor-not-allowed"
        )}
        onClick={(e) => !isBuilt && e.preventDefault()}
      >
        <Icon className="h-5 w-5 shrink-0" />
        {!collapsed && (
          <span className="truncate">
            {item.label}
            {!isBuilt && " (Soon)"}
          </span>
        )}
      </Link>
    );

    if (collapsed) {
      return (
        <Tooltip key={item.href} delayDuration={0}>
          <TooltipTrigger asChild>{content}</TooltipTrigger>
          <TooltipContent side="right" className="flex items-center gap-2">
            {item.label}
            {!isBuilt && <span className="text-xs text-muted-foreground">(Soon)</span>}
          </TooltipContent>
        </Tooltip>
      );
    }

    return <div key={item.href}>{content}</div>;
  };

  return (
    <aside
      className={cn(
        "flex h-screen flex-col border-r bg-card transition-all duration-200",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center justify-between border-b px-4">
        {!collapsed && (
          <Link href="/dashboard" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold text-sm">
              E
            </div>
            <span className="font-semibold text-lg">EVA ERP</span>
          </Link>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={onToggle}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      {/* Main nav */}
      <nav className="flex-1 space-y-1 px-2 py-3 overflow-y-auto">
        {navItems.map(renderNavItem)}
      </nav>

      {/* Bottom nav */}
      <div className="border-t px-2 py-3 space-y-1">
        {bottomItems.map(renderNavItem)}
      </div>
    </aside>
  );
}
