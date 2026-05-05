/**
 * Contract tests for the dedicated empresa <-> Eva-account link endpoints.
 *
 * The empresa edit modal must NOT save `eva_account_id` through the
 * generic PATCH — that bypasses the backend's billing-cache sync,
 * active-account check, and history row. Instead it routes through
 * `linkEvaAccount` / `unlinkEvaAccount`. These tests fix the API
 * contract and the version-header behavior so a regression in the
 * call shape (or removing `If-Match`) trips a test.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

const apiClientMock = {
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
};

vi.mock("./client", () => ({ default: apiClientMock }));

afterEach(() => vi.clearAllMocks());

describe("empresasApi link/unlink contract", () => {

  it("linkEvaAccount POSTs to /empresas/:id/link-eva-account with If-Match", async () => {
    const { empresasApi } = await import("./empresas");
    apiClientMock.post.mockResolvedValueOnce({ data: { id: "e1", version: 6 } });

    await empresasApi.linkEvaAccount("e1", "a1", 5);

    expect(apiClientMock.post).toHaveBeenCalledWith(
      "/empresas/e1/link-eva-account",
      { eva_account_id: "a1" },
      { headers: { "If-Match": "5" } }
    );
  });

  it("unlinkEvaAccount DELETEs the link endpoint and forwards version", async () => {
    const { empresasApi } = await import("./empresas");
    apiClientMock.delete.mockResolvedValueOnce({ data: { id: "e1", version: 7 } });

    await empresasApi.unlinkEvaAccount("e1", 6);

    expect(apiClientMock.delete).toHaveBeenCalledWith(
      "/empresas/e1/link-eva-account",
      { headers: { "If-Match": "6" } }
    );
  });

  it("createEvaAccount POSTs to /empresas/:id/eva-account", async () => {
    const { empresasApi } = await import("./empresas");
    apiClientMock.post.mockResolvedValueOnce({ data: { account: { id: "a1" } } });

    await empresasApi.createEvaAccount("e1", {
      owner_email: "owner@example.com",
      owner_name: "Owner",
    });

    expect(apiClientMock.post).toHaveBeenCalledWith(
      "/empresas/e1/eva-account",
      expect.objectContaining({ owner_email: "owner@example.com", owner_name: "Owner" })
    );
  });

  it("calendar GET passes range + empresa filters", async () => {
    const { empresasApi } = await import("./empresas");
    apiClientMock.get.mockResolvedValueOnce({ data: [] });

    await empresasApi.calendar({ from: "2026-05-01", to: "2026-05-31", empresaId: "e1" });

    expect(apiClientMock.get).toHaveBeenCalledWith(
      "/empresas/calendar",
      { params: { from: "2026-05-01", to: "2026-05-31", empresa_id: "e1" } }
    );
  });

  it("listInteractions GETs the empresa's outreach timeline", async () => {
    const { empresasApi } = await import("./empresas");
    apiClientMock.get.mockResolvedValueOnce({ data: [] });

    await empresasApi.listInteractions("e1");

    expect(apiClientMock.get).toHaveBeenCalledWith("/empresas/e1/interactions");
  });
});
