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
    lifecycle_stage: "negociacion",
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
  it("renders name + stage label + monthly amount", () => {
    render(<EmpresaCard empresa={makeEmpresa()} />);
    expect(screen.getByText("Acabados Premier")).toBeInTheDocument();
    expect(screen.getByText("Negociación")).toBeInTheDocument();
    expect(screen.getByText(/\$1,500/)).toBeInTheDocument();
  });

  it("shows 'Sin vincular' when eva_account_id is null", () => {
    render(<EmpresaCard empresa={makeEmpresa({ eva_account_id: null })} />);
    expect(screen.getByText("Sin vincular")).toBeInTheDocument();
  });

  it("shows 'Vinculada' when eva_account_id is set", () => {
    render(
      <EmpresaCard empresa={makeEmpresa({ eva_account_id: "22222222-2222-2222-2222-222222222222" })} />
    );
    expect(screen.getByText("Vinculada")).toBeInTheDocument();
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

  it("shows 'Próxima factura: …' when only current_period_end is set", () => {
    render(
      <EmpresaCard
        empresa={makeEmpresa({
          cancellation_scheduled_at: null,
          current_period_end: "2026-05-15T00:00:00Z",
        })}
      />
    );
    expect(screen.getByText(/Próxima factura:/)).toBeInTheDocument();
  });

  it("shows 'Anual' chip when billing_interval is annual", () => {
    render(<EmpresaCard empresa={makeEmpresa({ billing_interval: "annual" })} />);
    expect(screen.getByText("Anual")).toBeInTheDocument();
  });
});
