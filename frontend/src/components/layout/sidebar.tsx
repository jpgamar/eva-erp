"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  DollarSign,
  Lock,
  CheckSquare,
  Target,
  Calendar,
  FolderOpen,
  Trophy,
  Settings,
  ChevronsLeft,
  ChevronsRight,
  UsersRound,
  FileText,
  Activity,
  Building2,
  Handshake,
  Server,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { OwlIcon } from "@/components/owl-icon";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
  phase: number;
}

interface NavGroup {
  group?: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    items: [
      { label: "Dashboard", icon: LayoutDashboard, href: "/dashboard", phase: 4 },
    ],
  },
  {
    group: "Core",
    items: [
      { label: "Finances", icon: DollarSign, href: "/finances", phase: 3 },
      { label: "Facturas", icon: FileText, href: "/facturas", phase: 7 },
    ],
  },
  {
    group: "Manage",
    items: [
      { label: "Vault", icon: Lock, href: "/vault", phase: 2 },
      { label: "Tasks", icon: CheckSquare, href: "/tasks", phase: 2 },
    ],
  },
  {
    group: "Growth",
    items: [
      { label: "Prospects", icon: Target, href: "/prospects", phase: 5 },
      { label: "Meetings", icon: Calendar, href: "/meetings", phase: 5 },
      { label: "Documents", icon: FolderOpen, href: "/documents", phase: 5 },
    ],
  },
  {
    group: "Strategy",
    items: [
      { label: "OKRs", icon: Trophy, href: "/okrs", phase: 6 },
      { label: "Eva AI", icon: OwlIcon, href: "/assistant", phase: 7 },
    ],
  },
  {
    group: "Eva Platform",
    items: [
      { label: "Eva Customers", icon: Building2, href: "/eva-customers", phase: 8 },
      { label: "Monitoring", icon: Activity, href: "/monitoring", phase: 8 },
      { label: "Infrastructure", icon: Server, href: "/infrastructure", phase: 8 },
    ],
  },
  {
    group: "Partners",
    items: [
      { label: "Partners", icon: Handshake, href: "/partners", phase: 8 },
    ],
  },
  {
    group: "Admin",
    items: [
      { label: "Team", icon: UsersRound, href: "/team", phase: 1 },
      { label: "Settings", icon: Settings, href: "/settings", phase: 1 },
    ],
  },
];

const CURRENT_PHASE = 8;

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();

  const renderNavItem = (item: NavItem) => {
    const isActive = pathname.startsWith(item.href);
    const isBuilt = item.phase <= CURRENT_PHASE;
    const Icon = item.icon;

    const content = (
      <Link
        href={isBuilt ? item.href : "#"}
        className={cn(
          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-white/10 text-white font-medium"
            : "text-sidebar-foreground hover:text-white hover:bg-white/5",
          !isBuilt && "opacity-50 cursor-not-allowed",
          collapsed && "justify-center px-0"
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
        "fixed left-0 top-0 z-40 flex h-full flex-col bg-sidebar transition-all duration-200",
        collapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b border-gray-800 px-4">
        <Link href="/dashboard" className="flex items-center gap-2 min-w-0">
          <OwlIcon className="h-7 w-7 shrink-0" />
          {!collapsed && <span className="font-semibold text-lg text-white truncate">EVA ERP</span>}
        </Link>
      </div>

      {/* Main nav */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {navGroups.map((group, groupIdx) => (
          <div key={group.group || "top"} className={groupIdx > 0 ? "mt-4" : ""}>
            {group.group && !collapsed && (
              <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-sidebar-accent">
                {group.group}
              </p>
            )}
            {group.group && collapsed && groupIdx > 0 && (
              <div className="mx-2 mb-2 border-t border-gray-700/50" />
            )}
            <div className="space-y-0.5">
              {group.items.map(renderNavItem)}
            </div>
          </div>
        ))}
      </nav>

      {/* Powered by Eva footer */}
      <div className="border-t border-gray-800 px-3 py-3">
        {!collapsed ? (
          <a
            href="https://goeva.ai"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-xs text-sidebar-foreground hover:text-white transition-colors"
          >
            <OwlIcon className="h-4 w-auto shrink-0 opacity-60" />
            <span>Powered by Eva</span>
          </a>
        ) : (
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <a
                href="https://goeva.ai"
                target="_blank"
                rel="noopener noreferrer"
                className="flex justify-center"
              >
                <OwlIcon className="h-4 w-auto opacity-60 hover:opacity-100 transition-opacity" />
              </a>
            </TooltipTrigger>
            <TooltipContent side="right">Powered by Eva</TooltipContent>
          </Tooltip>
        )}
      </div>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        className="flex h-12 items-center justify-center border-t border-gray-800 text-sidebar-foreground hover:text-white transition-colors"
      >
        {collapsed ? (
          <ChevronsRight className="h-4 w-4" />
        ) : (
          <ChevronsLeft className="h-4 w-4" />
        )}
      </button>
    </aside>
  );
}
