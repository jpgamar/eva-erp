"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Building2, ExternalLink, Search } from "lucide-react";

import { evaPlatformApi } from "@/lib/api/eva-platform";
import type { EmpresaListItem } from "@/lib/api/empresas";
import type { EvaAccount, AccountDraft } from "@/types";
import { Input } from "@/components/ui/input";

interface Props {
  empresas: EmpresaListItem[];
  onJumpToEmpresa: (empresa: EmpresaListItem) => void;
}

/**
 * Accounts view inside `/empresas`. Displays:
 *   - Linked empresas (Empresa → Eva account → subscription status)
 *   - Pending drafts (operator must approve them)
 *   - Unlinked active Eva accounts (so the operator can create the
 *     missing empresa or link it to an existing one)
 *
 * Replaces the old standalone `/eva-customers` page; the old page now
 * redirects here.
 */
export function EmpresasAccountsView({ empresas, onJumpToEmpresa }: Props) {
  const [accounts, setAccounts] = useState<EvaAccount[]>([]);
  const [drafts, setDrafts] = useState<AccountDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    setLoading(true);
    Promise.all([
      evaPlatformApi.listAccounts().catch(() => [] as EvaAccount[]),
      evaPlatformApi.listDrafts().catch(() => [] as AccountDraft[]),
    ])
      .then(([a, d]) => {
        setAccounts(a);
        setDrafts(d);
      })
      .catch(() => toast.error("No se pudo cargar la vista de cuentas"))
      .finally(() => setLoading(false));
  }, []);

  const empresaByAccountId = useMemo(() => {
    const map = new Map<string, EmpresaListItem>();
    for (const emp of empresas) {
      if (emp.eva_account_id) map.set(emp.eva_account_id, emp);
    }
    return map;
  }, [empresas]);

  const linkedEmpresas = useMemo(
    () =>
      empresas
        .filter((e) => e.eva_account_id !== null)
        .filter((e) => e.name.toLowerCase().includes(search.toLowerCase())),
    [empresas, search]
  );

  const unlinkedAccounts = useMemo(
    () =>
      accounts.filter((a) => a.is_active && !empresaByAccountId.has(a.id)),
    [accounts, empresaByAccountId]
  );

  const pendingDrafts = useMemo(
    () => drafts.filter((d) => d.status === "draft"),
    [drafts]
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar empresa vinculada"
            className="pl-9"
          />
        </div>
        <p className="text-xs text-muted-foreground">
          {loading
            ? "Cargando…"
            : `${linkedEmpresas.length} vinculadas · ${unlinkedAccounts.length} cuentas sin empresa · ${pendingDrafts.length} borradores`}
        </p>
      </div>

      <section data-testid="empresas-accounts-linked">
        <header className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Empresas vinculadas a Eva</h2>
        </header>
        {linkedEmpresas.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
            Ninguna empresa está vinculada todavía. Crea o vincula una cuenta de Eva desde la tarjeta de la empresa.
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border bg-card">
            {linkedEmpresas.map((empresa) => (
              <li key={empresa.id} className="flex items-center justify-between gap-3 p-3">
                <button
                  type="button"
                  onClick={() => onJumpToEmpresa(empresa)}
                  className="flex min-w-0 flex-1 items-center gap-3 text-left"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-sm font-semibold text-accent-foreground">
                    {empresa.logo_url ? (
                      <img src={empresa.logo_url} alt={empresa.name} className="h-10 w-10 rounded-lg object-contain" />
                    ) : (
                      <Building2 className="h-5 w-5" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-foreground">{empresa.name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {empresa.health.linked_account_name ?? "Cuenta de Eva"}
                      {empresa.subscription_status ? ` · ${empresa.subscription_status.replace(/_/g, " ")}` : ""}
                    </p>
                  </div>
                </button>
                <span className="text-[11px] text-muted-foreground">{empresa.lifecycle_stage}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section data-testid="empresas-accounts-drafts">
        <header className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Borradores pendientes</h2>
        </header>
        {pendingDrafts.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
            No hay borradores pendientes de aprobación.
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border bg-card">
            {pendingDrafts.map((draft) => (
              <li key={draft.id} className="flex items-center justify-between gap-3 p-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-foreground">{draft.name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {draft.owner_email} · {draft.account_type} · {draft.plan_tier}
                  </p>
                </div>
                <Link
                  href="/empresas?view=accounts"
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted/40"
                >
                  <ExternalLink className="h-3 w-3" />
                  Aprobar
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section data-testid="empresas-accounts-unlinked">
        <header className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Cuentas Eva sin empresa</h2>
        </header>
        {unlinkedAccounts.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
            Todas las cuentas activas tienen una empresa vinculada.
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border bg-card">
            {unlinkedAccounts.map((account) => (
              <li key={account.id} className="flex items-center justify-between gap-3 p-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-foreground">{account.name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {account.account_type} · {account.plan_tier}
                  </p>
                </div>
                <span className="text-[11px] text-amber-700">Sin empresa</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
