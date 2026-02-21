"use client";

import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
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
  "/customers": { title: "Customers", subtitle: "Manage your customer base" },
  "/vault": { title: "Vault", subtitle: "Secure document storage" },
  "/tasks": { title: "Tasks", subtitle: "Track and manage work" },
  "/prospects": { title: "Prospects", subtitle: "Sales pipeline" },
  "/meetings": { title: "Meetings", subtitle: "Schedule and notes" },
  "/documents": { title: "Documents", subtitle: "File management" },
  "/okrs": { title: "OKRs", subtitle: "Objectives and key results" },
  "/assistant": { title: "Eva", subtitle: "Coming soon" },
  "/team": { title: "Team", subtitle: "Manage team members" },
  "/settings": { title: "Settings", subtitle: "Account preferences" },
};

function getPageInfo(pathname: string) {
  const match = Object.keys(PAGE_TITLES).find((key) => pathname.startsWith(key));
  return match ? PAGE_TITLES[match] : { title: "", subtitle: "" };
}

function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const { title, subtitle } = getPageInfo(pathname);

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
      <WelcomeOverlay />
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />
      <div className={cn("transition-all duration-200", sidebarCollapsed ? "ml-16" : "ml-60")}>
        <Header title={title} subtitle={subtitle} />
        <main className="p-6 animate-erp-entrance">{children}</main>
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
