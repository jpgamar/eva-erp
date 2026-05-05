"use client";

import { useState, useEffect } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider, useAuth } from "@/lib/auth/context";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { CommandPalette } from "@/components/command-palette";
import { WelcomeOverlay } from "@/components/welcome-overlay";
import { cn } from "@/lib/utils";

const PAGE_TITLES: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": { title: "Dashboard", subtitle: "Overview of EVA operations" },
  "/finances": { title: "Finances", subtitle: "Revenue, expenses, and cash flow" },
  "/facturas": { title: "Facturas", subtitle: "CFDI electronic invoicing" },
  "/gastos": { title: "Gastos", subtitle: "Facturas recibidas e IVA acreditable" },
  "/declaracion": { title: "Declaración", subtitle: "Cálculo mensual RESICO" },
  "/empresas": { title: "Empresas", subtitle: "CRM, follow-ups, and Eva accounts" },
  "/tasks": { title: "Tasks", subtitle: "Track and manage work" },
  // /prospects redirects to /empresas?stage=prospecto; metadata entry kept so
  // the brief moment before redirect shows a sensible heading.
  "/prospects": { title: "Pipeline", subtitle: "Redirigiendo a /empresas…" },
  // /eva-customers redirects to /empresas?view=accounts; metadata for redirect flash.
  "/eva-customers": { title: "Empresas", subtitle: "Redirigiendo a /empresas…" },
  "/monitoring": { title: "Monitoring", subtitle: "Platform health and issues" },
  "/infrastructure": { title: "Infrastructure", subtitle: "OpenClaw runtime hosts and employees" },
  "/partners": { title: "Partners", subtitle: "Partner management and deals" },
  "/team": { title: "Team", subtitle: "Manage team members" },
  "/settings": { title: "Settings", subtitle: "Account preferences" },
};

const PERIOD_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/;

function isValidPeriod(value: string | null): value is string {
  return value != null && PERIOD_PATTERN.test(value);
}

function toPeriodKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

function shiftPeriod(period: string, deltaMonths: number): string {
  const [year, month] = period.split("-").map(Number);
  const shifted = new Date(Date.UTC(year, month - 1 + deltaMonths, 1));
  return `${shifted.getUTCFullYear()}-${String(shifted.getUTCMonth() + 1).padStart(2, "0")}`;
}

function periodLabel(period: string): string {
  const [year, month] = period.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function DashboardPeriodNav() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentPeriod = toPeriodKey(new Date());
  const requestedPeriod = searchParams.get("period");
  const period = isValidPeriod(requestedPeriod) ? requestedPeriod : currentPeriod;
  const previousPeriod = shiftPeriod(period, -1);
  const nextPeriod = shiftPeriod(period, 1);
  const canGoNext = nextPeriod <= currentPeriod;

  const setPeriod = (nextValue: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (nextValue === currentPeriod) {
      params.delete("period");
    } else {
      params.set("period", nextValue);
    }
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  };

  return (
    <div className="inline-flex items-center gap-1">
      <button
        type="button"
        onClick={() => setPeriod(previousPeriod)}
        className="inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition hover:bg-muted/70 hover:text-foreground"
        aria-label="Previous month"
        title="Previous month"
      >
        <ChevronLeft className="h-3.5 w-3.5" />
      </button>
      <span className="min-w-[122px] px-1 text-center text-xs font-semibold text-foreground">
        {periodLabel(period)}
      </span>
      <button
        type="button"
        onClick={() => setPeriod(nextPeriod)}
        disabled={!canGoNext}
        className="inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition hover:bg-muted/70 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-35"
        aria-label="Next month"
        title="Next month"
      >
        <ChevronRight className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function getPageInfo(pathname: string) {
  const match = Object.keys(PAGE_TITLES).find((key) => pathname.startsWith(key));
  return match ? PAGE_TITLES[match] : { title: "", subtitle: "" };
}

function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { title, subtitle } = getPageInfo(pathname);
  const isDashboard = pathname.startsWith("/dashboard");
  const isAssistant = false; // /assistant page removed in CRM consolidation

  // Close mobile sidebar on route change
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="min-h-screen bg-background">
      <WelcomeOverlay userName={user.name} />
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        mobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
      />
      <div className={cn("transition-all duration-200", sidebarCollapsed ? "md:ml-16" : "md:ml-60")}>
        <Header
          title={title}
          subtitle={isDashboard ? undefined : subtitle}
          subtitleNode={isDashboard ? <DashboardPeriodNav /> : undefined}
          onMenuClick={() => setSidebarOpen(true)}
        />
        <main
          className={cn(
            "animate-erp-entrance",
            isAssistant ? "h-[calc(100vh-4rem)] overflow-hidden p-0" : "p-4 md:p-6",
          )}
        >
          {children}
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <TooltipProvider>
        <AppShell>{children}</AppShell>
      </TooltipProvider>
    </AuthProvider>
  );
}
