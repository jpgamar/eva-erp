"use client";

import { useEffect, useState } from "react";
import {
  TrendingUp, TrendingDown, Users, DollarSign,
  Flame, Clock, AlertTriangle, CheckCircle2, ArrowUpRight,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ResponsiveContainer, Legend,
} from "recharts";
import { kpisApi } from "@/lib/api/kpis";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface KPICurrent {
  mrr: number;
  arr: number;
  mrr_growth_pct: number | null;
  total_revenue: number;
  total_expenses_mxn: number;
  net_profit: number;
  burn_rate: number;
  runway_months: number | null;
  total_customers: number;
  new_customers: number;
  churned_customers: number;
  arpu: number;
  open_tasks: number;
  overdue_tasks: number;
  prospects_in_pipeline: number;
  cash_balance_mxn: number | null;
}

interface KPIHistory {
  period: string;
  mrr: number;
  arr: number;
  total_revenue: number;
  total_expenses_mxn: number;
  net_profit: number;
  total_customers: number;
  new_customers: number;
  churned_customers: number;
}

function fmt(amount: number | null | undefined, currency = "MXN") {
  if (amount == null) return "—";
  return `$${Number(amount).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })} ${currency}`;
}

function KPICard({
  title, value, subtitle, icon: Icon, trend, color,
}: {
  title: string;
  value: string;
  subtitle?: string;
  icon: any;
  trend?: "up" | "down" | null;
  color?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">{title}</p>
            <p className={`text-2xl font-bold ${color || ""}`}>{value}</p>
            {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
          </div>
          <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
            <Icon className="h-5 w-5 text-primary" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const [current, setCurrent] = useState<KPICurrent | null>(null);
  const [history, setHistory] = useState<KPIHistory[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [c, h] = await Promise.all([kpisApi.current(), kpisApi.history()]);
        setCurrent(c);
        setHistory(h.reverse());
      } catch {
        toast.error("Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center h-[calc(100vh-8rem)]"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>;
  }

  if (!current) return null;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          {new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" })}
        </p>
      </div>

      {/* Top KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard
          title="MRR"
          value={fmt(current.mrr)}
          subtitle={current.mrr_growth_pct != null ? `${current.mrr_growth_pct > 0 ? "+" : ""}${current.mrr_growth_pct}% MoM` : undefined}
          icon={DollarSign}
        />
        <KPICard
          title="Active Customers"
          value={current.total_customers.toString()}
          subtitle={`+${current.new_customers} new, -${current.churned_customers} churned`}
          icon={Users}
        />
        <KPICard
          title="Burn Rate/mo"
          value={fmt(current.burn_rate)}
          icon={Flame}
        />
        <KPICard
          title="Runway"
          value={current.runway_months != null ? `${Number(current.runway_months).toFixed(1)} months` : "—"}
          subtitle={current.cash_balance_mxn != null ? `Cash: ${fmt(current.cash_balance_mxn)}` : undefined}
          icon={Clock}
        />
        <KPICard
          title="Net P/L"
          value={fmt(current.net_profit)}
          icon={current.net_profit >= 0 ? TrendingUp : TrendingDown}
          color={current.net_profit >= 0 ? "text-green-600" : "text-red-600"}
        />
      </div>

      {/* Charts Row */}
      {history.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Revenue vs Expenses */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Revenue vs Expenses</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="period" className="text-xs" />
                  <YAxis className="text-xs" />
                  <RechartsTooltip />
                  <Legend />
                  <Line type="monotone" dataKey="total_revenue" stroke="#22c55e" name="Revenue" strokeWidth={2} />
                  <Line type="monotone" dataKey="total_expenses_mxn" stroke="#ef4444" name="Expenses" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Customer Growth */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Customer Growth</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={history}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="period" className="text-xs" />
                  <YAxis className="text-xs" />
                  <RechartsTooltip />
                  <Legend />
                  <Bar dataKey="new_customers" fill="#3b82f6" name="New" />
                  <Bar dataKey="churned_customers" fill="#ef4444" name="Churned" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Quick Links */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Link href="/tasks">
          <Card className="hover:border-primary/50 transition-colors cursor-pointer">
            <CardContent className="pt-6 flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Open Tasks</p>
                <p className="text-2xl font-bold">{current.open_tasks}</p>
              </div>
              {current.overdue_tasks > 0 && (
                <Badge variant="destructive">{current.overdue_tasks} overdue</Badge>
              )}
            </CardContent>
          </Card>
        </Link>
        <Link href="/finances">
          <Card className="hover:border-primary/50 transition-colors cursor-pointer">
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">ARPU</p>
              <p className="text-2xl font-bold">{fmt(current.arpu)}</p>
            </CardContent>
          </Card>
        </Link>
        <Link href="/customers">
          <Card className="hover:border-primary/50 transition-colors cursor-pointer">
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">ARR</p>
              <p className="text-2xl font-bold">{fmt(current.arr)}</p>
            </CardContent>
          </Card>
        </Link>
        <Link href="/prospects">
          <Card className="hover:border-primary/50 transition-colors cursor-pointer">
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">Prospects</p>
              <p className="text-2xl font-bold">{current.prospects_in_pipeline}</p>
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  );
}
