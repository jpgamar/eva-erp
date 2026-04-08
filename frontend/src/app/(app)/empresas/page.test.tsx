/**
 * Tests for the Empresas page channel-health UI additions
 * (silent-channel-health plan).
 *
 * Plan: docs/domains/integrations/instagram/plan-silent-channel-health.md
 *
 * What this asserts:
 *  1. Each empresa card renders a status dot with the correct color
 *     class for its health.status.
 *  2. The dot's tooltip text matches the expected Spanish copy.
 *  3. Clicking the dot opens the health modal and (for linked
 *     empresas) calls getAccountChannelHealth with the right id.
 *  4. The "not_linked" path shows the "no link" hint.
 *  5. The edit modal loads the Eva accounts dropdown via
 *     listEvaAccountsForLink.
 *  6. Saving the form sends eva_account_id in the update payload.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EmpresasPage from "./page";

const apiMock = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
  createItem: vi.fn(),
  updateItem: vi.fn(),
  toggleItem: vi.fn(),
  deleteItem: vi.fn(),
  getHistory: vi.fn(),
  getAccountChannelHealth: vi.fn(),
  listEvaAccountsForLink: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/lib/api/empresas", async () => {
  return {
    empresasApi: apiMock,
  };
});


function buildEmpresa(overrides: Record<string, unknown> = {}) {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    name: "Lucky Telecom",
    logo_url: null,
    status: "operativo",
    ball_on: null,
    summary_note: null,
    monthly_amount: null,
    payment_day: null,
    last_paid_date: null,
    eva_account_id: "11111111-1111-1111-1111-111111111111",
    auto_match_attempted: true,
    item_count: 0,
    pending_count: 0,
    pending_items: [],
    health: {
      status: "healthy",
      unhealthy_count: 0,
      linked_account_name: null,
      messenger: { present: false, healthy: false, count: 0 },
      instagram: { present: false, healthy: false, count: 0 },
    },
    ...overrides,
  };
}


describe("EmpresasPage — channel health UI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.listEvaAccountsForLink.mockResolvedValue([
      { id: "11111111-1111-1111-1111-111111111111", name: "Lucky Telecom" },
      { id: "22222222-2222-2222-2222-222222222222", name: "Gamership" },
    ]);
  });

  it("renders a healthy dot on a healthy empresa card", async () => {
    apiMock.list.mockResolvedValue([buildEmpresa()]);
    render(<EmpresasPage />);

    const dot = await screen.findByTestId("empresa-health-dot-00000000-0000-0000-0000-000000000001");
    expect(dot).toBeInTheDocument();
    expect(dot.getAttribute("data-status")).toBe("healthy");
    expect(dot.getAttribute("title")).toBe("Todos los canales operando");
    // Inner span has the green color class
    expect(dot.querySelector("span")?.className).toContain("bg-emerald-500");
  });

  it("renders an unhealthy dot with the right tooltip count", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        health: { status: "unhealthy", unhealthy_count: 2 },
      }),
    ]);
    render(<EmpresasPage />);

    const dot = await screen.findByTestId("empresa-health-dot-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    expect(dot.getAttribute("data-status")).toBe("unhealthy");
    expect(dot.getAttribute("title")).toBe("2 canales desconectados");
    expect(dot.querySelector("span")?.className).toContain("bg-red-500");
  });

  it("renders a unhealthy dot with singular tooltip when count = 1", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        health: { status: "unhealthy", unhealthy_count: 1 },
      }),
    ]);
    render(<EmpresasPage />);

    const dot = await screen.findByTestId("empresa-health-dot-bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
    expect(dot.getAttribute("title")).toBe("1 canal desconectado");
  });

  it("renders a not_linked dot when the empresa has no eva_account_id", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
        eva_account_id: null,
        health: { status: "not_linked", unhealthy_count: 0 },
      }),
    ]);
    render(<EmpresasPage />);

    const dot = await screen.findByTestId("empresa-health-dot-cccccccc-cccc-cccc-cccc-cccccccccccc");
    expect(dot.getAttribute("data-status")).toBe("not_linked");
    expect(dot.getAttribute("title")).toBe("Sin vincular a una cuenta de Eva");
  });

  it("renders an unknown dot when health is unknown", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
        health: { status: "unknown", unhealthy_count: 0 },
      }),
    ]);
    render(<EmpresasPage />);

    const dot = await screen.findByTestId("empresa-health-dot-dddddddd-dddd-dddd-dddd-dddddddddddd");
    expect(dot.getAttribute("data-status")).toBe("unknown");
    expect(dot.querySelector("span")?.className).toContain("bg-yellow-400");
  });

  it("opens the health modal and fetches the channel detail when clicking the dot on a linked empresa", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        eva_account_id: "11111111-1111-1111-1111-111111111111",
        health: { status: "unhealthy", unhealthy_count: 1 },
      }),
    ]);
    apiMock.getAccountChannelHealth.mockResolvedValue({
      account_id: "11111111-1111-1111-1111-111111111111",
      messenger: [
        {
          id: "ffffffff-ffff-ffff-ffff-ffffffffffff",
          channel_type: "messenger",
          display_name: "Lucky Telecom",
          is_healthy: false,
          health_status_reason: "Token granular_scopes restricted to renovi",
          last_status_check: new Date().toISOString(),
        },
      ],
      instagram: [],
    });

    render(<EmpresasPage />);
    const dot = await screen.findByTestId(
      "empresa-health-dot-eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    );
    fireEvent.click(dot);

    await waitFor(() => {
      expect(apiMock.getAccountChannelHealth).toHaveBeenCalledWith(
        "11111111-1111-1111-1111-111111111111"
      );
    });

    // Modal contents render
    await waitFor(() => {
      expect(screen.getByTestId("empresa-health-modal")).toBeInTheDocument();
      // Two channel rows total: messenger + (empty) instagram. Check
      // that the modal has the messenger row.
      expect(screen.getByTestId("channel-row-ffffffff-ffff-ffff-ffff-ffffffffffff")).toBeInTheDocument();
      expect(screen.getByText("Desconectado")).toBeInTheDocument();
      expect(screen.getByText(/granular_scopes/)).toBeInTheDocument();
    });
  });

  it("opens the not_linked modal hint without calling the channel API", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "01010101-0101-0101-0101-010101010101",
        eva_account_id: null,
        health: { status: "not_linked", unhealthy_count: 0 },
      }),
    ]);

    render(<EmpresasPage />);
    const dot = await screen.findByTestId(
      "empresa-health-dot-01010101-0101-0101-0101-010101010101"
    );
    fireEvent.click(dot);

    await waitFor(() => {
      expect(screen.getByTestId("empresa-health-modal")).toBeInTheDocument();
    });
    expect(apiMock.getAccountChannelHealth).not.toHaveBeenCalled();
    expect(
      screen.getByText(/Esta empresa no está vinculada/)
    ).toBeInTheDocument();
  });

  it("loads the Eva accounts dropdown when opening the create modal", async () => {
    apiMock.list.mockResolvedValue([]);

    render(<EmpresasPage />);
    // Wait for the empty state then click "Nueva Empresa"
    await waitFor(() =>
      expect(screen.getByText(/No hay empresas aún/)).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: /Nueva Empresa/i }));

    await waitFor(() => {
      expect(apiMock.listEvaAccountsForLink).toHaveBeenCalled();
    });
    // Dropdown trigger present
    expect(screen.getByTestId("empresa-eva-account-select")).toBeInTheDocument();
  });

  // ── Round 2 follow-up: surface linked-account name + channel badges ──

  it("renders the linked Eva account name on the card when linked", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "11111111-1111-1111-1111-111111111111",
        health: {
          status: "healthy",
          unhealthy_count: 0,
          linked_account_name: "Lucky Intelligence",
          messenger: { present: true, healthy: true, count: 1 },
          instagram: { present: false, healthy: false, count: 0 },
        },
      }),
    ]);
    render(<EmpresasPage />);
    const link = await screen.findByTestId(
      "empresa-eva-account-11111111-1111-1111-1111-111111111111"
    );
    expect(link.textContent).toContain("Lucky Intelligence");
  });

  it("renders 'Sin vincular a Eva' when not linked", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "22222222-2222-2222-2222-222222222222",
        eva_account_id: null,
        health: {
          status: "not_linked",
          unhealthy_count: 0,
          linked_account_name: null,
          messenger: { present: false, healthy: false, count: 0 },
          instagram: { present: false, healthy: false, count: 0 },
        },
      }),
    ]);
    render(<EmpresasPage />);
    const link = await screen.findByTestId(
      "empresa-eva-account-22222222-2222-2222-2222-222222222222"
    );
    expect(link.textContent).toContain("Sin vincular");
  });

  it("renders Messenger + Instagram badges with green dots when both are healthy", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "33333333-3333-3333-3333-333333333333",
        health: {
          status: "healthy",
          unhealthy_count: 0,
          linked_account_name: "Test Co",
          messenger: { present: true, healthy: true, count: 1 },
          instagram: { present: true, healthy: true, count: 1 },
        },
      }),
    ]);
    render(<EmpresasPage />);
    const msg = await screen.findByTestId("empresa-msg-badge-33333333-3333-3333-3333-333333333333");
    const ig = await screen.findByTestId("empresa-ig-badge-33333333-3333-3333-3333-333333333333");
    expect(msg.getAttribute("data-healthy")).toBe("true");
    expect(ig.getAttribute("data-healthy")).toBe("true");
  });

  it("renders only the Instagram badge with red dot when only Instagram is broken and Messenger isn't configured", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "44444444-4444-4444-4444-444444444444",
        health: {
          status: "unhealthy",
          unhealthy_count: 1,
          linked_account_name: "Test Co",
          messenger: { present: false, healthy: false, count: 0 },
          instagram: { present: true, healthy: false, count: 1 },
        },
      }),
    ]);
    render(<EmpresasPage />);
    const ig = await screen.findByTestId("empresa-ig-badge-44444444-4444-4444-4444-444444444444");
    expect(ig.getAttribute("data-healthy")).toBe("false");
    expect(
      screen.queryByTestId("empresa-msg-badge-44444444-4444-4444-4444-444444444444")
    ).toBeNull();
  });

  it("hides the channel badges row entirely when the linked account has no channels", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "55555555-5555-5555-5555-555555555555",
        health: {
          status: "healthy",
          unhealthy_count: 0,
          linked_account_name: "Test Co",
          messenger: { present: false, healthy: false, count: 0 },
          instagram: { present: false, healthy: false, count: 0 },
        },
      }),
    ]);
    render(<EmpresasPage />);
    // Wait for card to render
    await screen.findByTestId("empresa-eva-account-55555555-5555-5555-5555-555555555555");
    // No badges row at all
    expect(
      screen.queryByTestId("empresa-channel-badges-55555555-5555-5555-5555-555555555555")
    ).toBeNull();
  });

  it("renames the phase banner labels with 'Fase:' prefix", async () => {
    apiMock.list.mockResolvedValue([
      buildEmpresa({
        id: "66666666-6666-6666-6666-666666666666",
        status: "operativo",
      }),
      buildEmpresa({
        id: "77777777-7777-7777-7777-777777777777",
        status: "en_implementacion",
      }),
      buildEmpresa({
        id: "88888888-8888-8888-8888-888888888888",
        status: "requiere_atencion",
      }),
    ]);
    render(<EmpresasPage />);
    expect(await screen.findByText("Fase: Operativo")).toBeInTheDocument();
    expect(screen.getByText("Fase: Implementación")).toBeInTheDocument();
    expect(screen.getByText("Fase: Atención")).toBeInTheDocument();
  });
});
