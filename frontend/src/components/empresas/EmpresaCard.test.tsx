import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmpresaCard } from "./EmpresaCard";
import type { EmpresaListItem } from "@/lib/api/empresas";

function makeEmpresa(overrides: Partial<EmpresaListItem> = {}): EmpresaListItem {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    name: "Acabados Premier",
    logo_url: null,
    status: "operativo",
    lifecycle_stage: "operativo",
    ball_on: null,
    summary_note: null,
    monthly_amount: 1500,
    billing_interval: "monthly",
    payment_day: 15,
    last_paid_date: null,
    expected_close_date: "2026-05-15",
    cancellation_scheduled_at: null,
    eva_account_id: null,
    auto_match_attempted: false,
    grandfathered: false,
    version: 0,
    subscription_status: null,
    current_period_end: null,
    person_type: "moral",
    rfc: null,
    item_count: 0,
    pending_count: 0,
    pending_items: [],
    next_action: null,
    overdue_count: 0,
    health: {
      status: "not_linked",
      unhealthy_count: 0,
      linked_account_name: null,
      messenger: { present: false, healthy: false, count: 0 },
      instagram: { present: false, healthy: false, count: 0 },
      whatsapp: { present: false, healthy: false, count: 0 },
    },
    ...overrides,
  };
}

describe("EmpresaCard", () => {
  it("renders name and monthly amount; lifecycle stage is owned by the column header", () => {
    render(<EmpresaCard empresa={makeEmpresa()} />);
    expect(screen.getByText("Acabados Premier")).toBeInTheDocument();
    expect(screen.getByText(/\$1,500/)).toBeInTheDocument();
    // Lifecycle stage label intentionally NOT duplicated on the card —
    // the kanban column already shows it.
    expect(screen.queryByText("Operativo")).toBeNull();
  });

  it("hides the linked-account row entirely for unlinked non-operativo prospects", () => {
    render(
      <EmpresaCard empresa={makeEmpresa({ eva_account_id: null, lifecycle_stage: "prospecto" })} />
    );
    // Outbound prospects should NOT loudly advertise "Sin vincular";
    // it's the expected default for that stage.
    expect(screen.queryByText(/Sin cuenta de Eva/)).toBeNull();
  });

  it("shows 'Sin cuenta de Eva' on operativo cards that lack a linked account", () => {
    render(
      <EmpresaCard empresa={makeEmpresa({ eva_account_id: null, lifecycle_stage: "operativo" })} />
    );
    expect(screen.getByText(/Sin cuenta de Eva/)).toBeInTheDocument();
  });

  it("shows the linked Eva account name when linked", () => {
    render(
      <EmpresaCard
        empresa={makeEmpresa({
          eva_account_id: "22222222-2222-2222-2222-222222222222",
          health: {
            status: "healthy",
            unhealthy_count: 0,
            linked_account_name: "Acabados Premier (Eva)",
            messenger: { present: false, healthy: false, count: 0 },
            instagram: { present: false, healthy: false, count: 0 },
            whatsapp: { present: false, healthy: false, count: 0 },
          },
        })}
      />
    );
    expect(screen.getByText("Acabados Premier (Eva)")).toBeInTheDocument();
  });

  it("shows 'Revisar' chip for grandfathered rows", () => {
    render(<EmpresaCard empresa={makeEmpresa({ grandfathered: true })} />);
    expect(screen.getByText("Revisar")).toBeInTheDocument();
  });

  it("shows 'Cancelación: …' when cancellation_scheduled_at is set", () => {
    render(
      <EmpresaCard
        empresa={makeEmpresa({
          cancellation_scheduled_at: "2026-06-15T00:00:00Z",
          current_period_end: "2026-05-01T00:00:00Z",
        })}
      />
    );
    expect(screen.getByText(/Cancelación:/)).toBeInTheDocument();
  });

  it("shows 'Próx. factura: …' when only current_period_end is set", () => {
    render(
      <EmpresaCard
        empresa={makeEmpresa({
          cancellation_scheduled_at: null,
          current_period_end: "2026-05-15T00:00:00Z",
        })}
      />
    );
    expect(screen.getByText(/Próx. factura:/)).toBeInTheDocument();
  });

  it("renders 'anual' lower-case suffix when billing_interval is annual", () => {
    render(<EmpresaCard empresa={makeEmpresa({ billing_interval: "annual" })} />);
    expect(screen.getByText("anual")).toBeInTheDocument();
  });

  it("hides the monthly-amount row entirely when amount is null", () => {
    render(<EmpresaCard empresa={makeEmpresa({ monthly_amount: null })} />);
    expect(screen.queryByText(/\$—/)).toBeNull();
  });
});
