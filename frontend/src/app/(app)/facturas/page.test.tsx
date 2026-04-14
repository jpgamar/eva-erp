/**
 * Tests for the Facturas page: draft-mode UI additions.
 * Plan: docs/plan-facturas-draft-and-modal.md
 */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FacturasPage from "./page";

const facturasMock = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  get: vi.fn(),
  stamp: vi.fn(),
  delete: vi.fn(),
  downloadPdf: vi.fn(),
  downloadXml: vi.fn(),
  apiStatus: vi.fn(),
}));

const customersMock = vi.hoisted(() => ({
  list: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/lib/api/facturas", () => ({ facturasApi: facturasMock }));
vi.mock("@/lib/api/customers", () => ({ customersApi: customersMock }));

vi.mock("@/components/sat-product-combobox", () => ({
  SatProductCombobox: ({ value, onChange }: any) => (
    <input
      data-testid="sat-combobox"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

function buildFactura(overrides: Record<string, unknown> = {}) {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    facturapi_id: null,
    cfdi_uuid: null,
    customer_name: "Cliente Demo",
    customer_rfc: "XAXX010101000",
    customer_id: null,
    use: "G03",
    payment_form: "03",
    payment_method: "PUE",
    line_items_json: [],
    subtotal: 100,
    tax: 16,
    isr_retention: 0,
    iva_retention: 0,
    total: 116,
    currency: "MXN",
    status: "draft",
    cancellation_status: null,
    series: null,
    folio_number: null,
    issued_at: null,
    cancelled_at: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

beforeEach(() => {
  facturasMock.list.mockReset();
  facturasMock.create.mockReset();
  facturasMock.stamp.mockReset();
  facturasMock.delete.mockReset();
  facturasMock.downloadPdf.mockReset();
  facturasMock.apiStatus.mockReset();
  customersMock.list.mockReset();

  facturasMock.apiStatus.mockResolvedValue({ status: "ok" });
  customersMock.list.mockResolvedValue([]);
});

describe("FacturasPage — create modal two-button flow", () => {
  it("renders both 'Guardar borrador (preview)' and 'Crear y timbrar' buttons", async () => {
    facturasMock.list.mockResolvedValue([]);
    render(<FacturasPage />);
    await waitFor(() => expect(facturasMock.list).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /new factura/i }));

    expect(await screen.findByRole("button", { name: /guardar borrador/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /crear y timbrar/i })).toBeInTheDocument();
  });

  it("'Guardar borrador (preview)' posts with draft=true and does NOT call stamp", async () => {
    facturasMock.list.mockResolvedValue([]);
    facturasMock.create.mockResolvedValue(buildFactura({ facturapi_id: "fac_draft_1" }));

    render(<FacturasPage />);
    await waitFor(() => expect(facturasMock.list).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /new factura/i }));

    const modal = await screen.findByRole("dialog");
    const draftBtn = await within(modal).findByRole("button", { name: /guardar borrador/i });
    // type=button — bypasses HTML5 required validation; the test just verifies the API call shape.
    fireEvent.click(draftBtn);

    await waitFor(() => expect(facturasMock.create).toHaveBeenCalledTimes(1));
    const [, opts] = facturasMock.create.mock.calls[0];
    expect(opts).toEqual({ draft: true });
    expect(facturasMock.stamp).not.toHaveBeenCalled();
  });

  it("'Crear y timbrar' path (direct handleCreate) posts without draft flag and then stamps", async () => {
    facturasMock.list.mockResolvedValue([]);
    const created = buildFactura({ id: "00000000-0000-0000-0000-000000000099" });
    facturasMock.create.mockResolvedValue(created);
    facturasMock.stamp.mockResolvedValue({ ...created, status: "valid", cfdi_uuid: "uuid-x" });

    render(<FacturasPage />);
    await waitFor(() => expect(facturasMock.list).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /new factura/i }));

    const modal = await screen.findByRole("dialog");
    // Submit the form directly — HTML5 'required' skipped, which is fine for this assertion.
    const form = modal.querySelector("form")!;
    fireEvent.submit(form);

    await waitFor(() => expect(facturasMock.create).toHaveBeenCalledTimes(1));
    const [, opts] = facturasMock.create.mock.calls[0];
    expect(opts).toEqual({ draft: false });
    await waitFor(() => expect(facturasMock.stamp).toHaveBeenCalledWith(created.id));
  });
});

describe("FacturasPage — 'Descargar preview' row action", () => {
  it("renders the preview-download button only when draft has facturapi_id", async () => {
    const draftLocal = buildFactura({ id: "aaaa", facturapi_id: null });
    const draftPushed = buildFactura({ id: "bbbb", facturapi_id: "fac_draft_xyz" });
    facturasMock.list.mockResolvedValue([draftLocal, draftPushed]);

    render(<FacturasPage />);
    await waitFor(() => expect(facturasMock.list).toHaveBeenCalled());

    const previewButtons = await screen.findAllByTitle(/descargar preview pdf/i);
    expect(previewButtons).toHaveLength(1);
  });

  it("clicking 'Descargar preview' calls downloadPdf with the row id", async () => {
    const draftPushed = buildFactura({ id: "row-xyz", facturapi_id: "fac_draft_xyz" });
    facturasMock.list.mockResolvedValue([draftPushed]);

    const fakeBlob = new Blob(["%PDF-"], { type: "application/pdf" });
    facturasMock.downloadPdf.mockResolvedValue(fakeBlob);

    const urlMock = vi.fn(() => "blob:http://test/xxx");
    const revokeMock = vi.fn();
    (globalThis.URL.createObjectURL as any) = urlMock;
    (globalThis.URL.revokeObjectURL as any) = revokeMock;

    render(<FacturasPage />);
    await waitFor(() => expect(facturasMock.list).toHaveBeenCalled());

    const previewBtn = await screen.findByTitle(/descargar preview pdf/i);
    fireEvent.click(previewBtn);

    await waitFor(() => expect(facturasMock.downloadPdf).toHaveBeenCalledWith("row-xyz"));
  });
});
