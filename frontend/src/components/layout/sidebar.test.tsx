import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Sidebar } from "./sidebar";

vi.mock("next/navigation", () => ({
  usePathname: () => "/empresas",
}));

describe("Sidebar (post company-CRM consolidation)", () => {
  it("does not render entries for removed surfaces", () => {
    render(<Sidebar collapsed={false} onToggle={() => {}} mobileOpen={true} onMobileClose={() => {}} />);
    for (const removed of ["Vault", "Meetings", "Documents", "OKRs", "Eva AI", "Eva Customers"]) {
      expect(screen.queryByText(removed)).toBeNull();
    }
  });

  it("still renders Empresas + core ERP entries", () => {
    render(<Sidebar collapsed={false} onToggle={() => {}} mobileOpen={true} onMobileClose={() => {}} />);
    expect(screen.getByText("Empresas")).toBeInTheDocument();
    // "Tasks" sidebar entry was removed in the empresas-ux-pass —
    // tasks live under /empresas?view=tasks now.
    expect(screen.queryByText("Tasks")).toBeNull();
    expect(screen.getByText("Finances")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });
});
