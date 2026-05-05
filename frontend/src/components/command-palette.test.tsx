import { render, screen, act } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { CommandPalette } from "./command-palette";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// jsdom does not implement scrollIntoView; cmdk calls it after render.
beforeAll(() => {
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = vi.fn();
  }
});

describe("CommandPalette (post company-CRM consolidation)", () => {
  function openPalette() {
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
    });
  }

  it("does not include removed module routes", () => {
    render(<CommandPalette />);
    openPalette();
    for (const removed of ["Vault", "Meetings", "Documents", "OKRs", "Eva AI", "Customers"]) {
      const matches = screen.queryAllByText(new RegExp(`^${removed}$`));
      expect(matches.length).toBe(0);
    }
  });

  it("exposes Empresas entry points (cards / calendar / accounts)", () => {
    render(<CommandPalette />);
    openPalette();
    expect(screen.getByText("Empresas")).toBeInTheDocument();
    expect(screen.getByText("Calendario de Empresas")).toBeInTheDocument();
    expect(screen.getByText("Cuentas Eva")).toBeInTheDocument();
  });
});
