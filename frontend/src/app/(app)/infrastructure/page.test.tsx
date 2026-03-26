import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  OpenclawRuntimeMonitoringAgent,
  OpenclawRuntimeOverview,
  RuntimeEmployee,
  RuntimeEmployeeDetail,
} from "@/types";
import { EmployeeDetailSheet, OpenclawHealthTab } from "./page";

const { toastSuccess, toastError, apiMock } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  apiMock: {
    getEmployeeDetail: vi.fn(),
    getOpenclawEmployeeHealth: vi.fn(),
    runOpenclawEmployeeChecks: vi.fn(),
    reprovisionOpenclawEmployee: vi.fn(),
    repairOpenclawEmployeeToken: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: toastSuccess,
    error: toastError,
  },
}));

vi.mock("@/lib/api/eva-platform", () => ({
  evaPlatformApi: apiMock,
}));

function buildOverview(): OpenclawRuntimeOverview {
  return {
    monitoring: {
      slots_available: 3,
      active_hosts: 2,
      warning_hosts: 0,
      critical_hosts: 0,
      queue_depth: 1,
      locked_tenants: 0,
      release_parity_status: "ok",
      release_parity: {},
      release_drift_count: 1,
      readiness_drift_count: 0,
      manual_interventions_24h: 2,
      hosts: [],
      allocations: [],
      incidents: [
        {
          id: "incident-1",
          source: "eva",
          event_type: "token_drift_detected",
          severity: "warning",
          reason_code: "TOKEN_DRIFT",
          payload: {},
          openclaw_agent_id: "emp-1",
          runtime_host_id: null,
          created_at: "2026-03-26T12:00:00Z",
        },
      ],
    },
    fleet_audit: {
      checked_at: "2026-03-26T12:00:00Z",
      total_employees: 1,
      reprovision_recommended_count: 1,
      release_drift_count: 1,
      readiness_drift_count: 0,
      token_drift_count: 1,
      suspected_untracked_change_count: 1,
      employees: [
        {
          openclaw_agent_id: "emp-1",
          employee_label: "Eva Ops",
          employee_status: "active",
          readiness_state: "ready",
          runtime_bootstrapped: true,
          chat_ready: true,
          runtime_release_drift: true,
          db_runtime_image_digest: "sha256:old",
          db_runtime_template_version: "1",
          actual_runtime_image_ref: "registry/openclaw@sha256:new",
          actual_runtime_openclaw_version: "2026.3.13",
          actual_runtime_release_drift: true,
          token_state: "invalid",
          reprovision_recommended: true,
          recommended_action: "reprovision",
          suspected_untracked_change: true,
          suspected_untracked_change_reason: "runtime_and_token_drift_without_recorded_intervention",
          last_manual_intervention_at: null,
          latest_operation: {
            id: "op-1",
            operation_type: "openclaw.provision_employee",
            status: "retrying",
            updated_at: "2026-03-26T12:01:00Z",
            next_retry_at: "2026-03-26T12:05:00Z",
            last_error_code: "HOST_UNAVAILABLE",
            last_error_message: "Host is unavailable",
          },
        },
      ],
    },
  };
}

function buildEmployee(): RuntimeEmployee {
  return {
    id: "emp-1",
    agent_id: "emp-1",
    account_id: "acct-1",
    account_name: "Acme",
    label: "Eva Ops",
    status: "active",
    phone_number: null,
    allocation_state: "active",
    container_name: "openclaw-gateway-emp1",
    gateway_port: 4501,
    cpu_reservation_mcpu: 500,
    ram_reservation_mb: 1024,
    reconnect_risk: null,
    whatsapp_connected: true,
    telegram_connected: false,
    vps_ip: "10.0.0.10",
  };
}

function buildEmployeeDetail(): RuntimeEmployeeDetail {
  return {
    ...buildEmployee(),
    status_detail: "Ready",
    error: null,
    connections_state: {},
    provisioning_started_at: "2026-03-26T11:55:00Z",
    provisioning_completed_at: "2026-03-26T11:58:00Z",
    host_name: "runtime-1",
    host_ip: "10.0.0.10",
    queued_reason: null,
    placed_at: "2026-03-26T11:55:30Z",
    started_at: "2026-03-26T11:56:00Z",
    recent_events: [],
  };
}

function buildHealth(): OpenclawRuntimeMonitoringAgent {
  return {
    openclaw_agent_id: "emp-1",
    employee_label: "Eva Ops",
    employee_status: "active",
    readiness_state: "ready",
    runtime_bootstrapped: true,
    chat_ready: true,
    user_status_message: "Ready for chat",
    allocation_state: "active",
    tenant_class: "standard",
    runtime_host_id: "host-1",
    runtime_host_name: "runtime-1",
    runtime_host_state: "active",
    restart_lock_until: null,
    reconnect_risk: null,
    queued_reason: null,
    runtime_image_digest: "sha256:new",
    runtime_template_version: "1",
    runtime_release_drift: false,
    provisioning_completed_at: "2026-03-26T11:58:00Z",
    last_manual_intervention_at: null,
    latest_operation: {
      id: "op-2",
      operation_type: "openclaw.run_checks",
      status: "running",
      updated_at: "2026-03-26T12:00:30Z",
      next_retry_at: null,
      last_error_code: null,
      last_error_message: null,
    },
    incidents: [],
  };
}

describe("OpenClaw infrastructure UI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders OpenClaw health cards and highlights untracked changes", () => {
    const onRefresh = vi.fn();
    const onReprovisionAll = vi.fn();
    const onInspectEmployee = vi.fn();

    render(
      <OpenclawHealthTab
        overview={buildOverview()}
        loading={false}
        campaignStatus={null}
        onRefresh={onRefresh}
        onReprovisionAll={onReprovisionAll}
        onInspectEmployee={onInspectEmployee}
      />,
    );

    expect(screen.getByText("OpenClaw health")).toBeInTheDocument();
    expect(screen.getByText("Untracked Changes")).toBeInTheDocument();
    expect(screen.getByText("Untracked runtime and token change suspected")).toBeInTheDocument();
    expect(screen.getByText("Retrying automatically")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Re-run checks/i }));
    fireEvent.click(screen.getByRole("button", { name: /Reprovision all/i }));
    fireEvent.click(screen.getByText("Eva Ops"));

    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(onReprovisionAll).toHaveBeenCalledTimes(1);
    expect(onInspectEmployee).toHaveBeenCalledWith("emp-1");
  });

  it("runs employee checks from the detail sheet and refreshes the health snapshot", async () => {
    apiMock.getEmployeeDetail.mockResolvedValue(buildEmployeeDetail());
    apiMock.getOpenclawEmployeeHealth.mockResolvedValue(buildHealth());
    apiMock.runOpenclawEmployeeChecks.mockResolvedValue({
      accepted: true,
      message: "Checks completed",
    });

    render(
      <EmployeeDetailSheet
        employee={buildEmployee()}
        open
        onClose={vi.fn()}
      />,
    );

    await screen.findByText("Eva Ops");
    expect(screen.getByText(/Running · openclaw.run_checks/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Run checks/i }));

    await waitFor(() => {
      expect(apiMock.runOpenclawEmployeeChecks).toHaveBeenCalledWith("emp-1");
    });
    await waitFor(() => {
      expect(apiMock.getEmployeeDetail).toHaveBeenCalledTimes(2);
      expect(apiMock.getOpenclawEmployeeHealth).toHaveBeenCalledTimes(2);
    });
    expect(toastSuccess).toHaveBeenCalledWith("Checks completed");
  });
});
