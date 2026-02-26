import api from "./client";
import type {
  EvaAccount,
  AccountDraft,
  MonitoringOverview,
  MonitoringIssue,
  MonitoringCheck,
  ServiceStatusResponse,
  EvaPartner,
  EvaPartnerDetail,
  PartnerDeal,
  PlatformDashboard,
  AccountPricing,
  AccountPricingCoverage,
  RuntimeHost,
  RuntimeEmployee,
  RuntimeEmployeeDetail,
  DockerContainer,
  DockerLogs,
  FileEntry,
  FileContent,
} from "@/types";

export const evaPlatformApi = {
  // Accounts
  listAccounts: (params?: { search?: string; partner_id?: string }): Promise<EvaAccount[]> =>
    api.get("/eva-platform/accounts", { params }).then((r) => r.data),
  getAccount: (id: string): Promise<EvaAccount> =>
    api.get(`/eva-platform/accounts/${id}`).then((r) => r.data),
  createAccount: (data: Record<string, unknown>): Promise<EvaAccount> =>
    api.post("/eva-platform/accounts", data).then((r) => r.data),
  listAccountPricing: (params?: { search?: string }): Promise<AccountPricing[]> =>
    api.get("/eva-platform/account-pricing", { params }).then((r) => r.data),
  updateAccountPricing: (accountId: string, data: Record<string, unknown>): Promise<AccountPricing> =>
    api.patch(`/eva-platform/account-pricing/${accountId}`, data).then((r) => r.data),
  pricingCoverage: (): Promise<AccountPricingCoverage> =>
    api.get("/eva-platform/account-pricing/coverage").then((r) => r.data),
  deleteAccount: (id: string): Promise<{ message: string }> =>
    api.delete(`/eva-platform/accounts/${id}`).then((r) => r.data),
  permanentlyDeleteAccount: (id: string): Promise<{ message: string }> =>
    api.delete(`/eva-platform/accounts/${id}/permanent`).then((r) => r.data),

  // Drafts
  listDrafts: (params?: { status?: string }): Promise<AccountDraft[]> =>
    api.get("/eva-platform/drafts", { params }).then((r) => r.data),
  createDraft: (data: Record<string, unknown>): Promise<AccountDraft> =>
    api.post("/eva-platform/drafts", data).then((r) => r.data),
  updateDraft: (id: string, data: Record<string, unknown>): Promise<AccountDraft> =>
    api.patch(`/eva-platform/drafts/${id}`, data).then((r) => r.data),
  approveDraft: (id: string): Promise<AccountDraft> =>
    api.post(`/eva-platform/drafts/${id}/approve`).then((r) => r.data),
  deleteDraft: (id: string): Promise<void> =>
    api.delete(`/eva-platform/drafts/${id}`).then((r) => r.data),

  // Monitoring
  serviceStatus: (): Promise<ServiceStatusResponse> =>
    api.get("/eva-platform/monitoring/services").then((r) => r.data),
  monitoringOverview: (): Promise<MonitoringOverview> =>
    api.get("/eva-platform/monitoring/overview").then((r) => r.data),
  listIssues: (params?: { status?: string; severity?: string }): Promise<MonitoringIssue[]> =>
    api.get("/eva-platform/monitoring/issues", { params }).then((r) => r.data),
  listChecks: (params?: { service?: string; limit?: number }): Promise<MonitoringCheck[]> =>
    api.get("/eva-platform/monitoring/checks", { params }).then((r) => r.data),
  acknowledgeIssue: (id: string): Promise<MonitoringIssue> =>
    api.post(`/eva-platform/monitoring/issues/${id}/acknowledge`).then((r) => r.data),
  resolveIssue: (id: string): Promise<MonitoringIssue> =>
    api.post(`/eva-platform/monitoring/issues/${id}/resolve`).then((r) => r.data),

  // Partners
  listPartners: (params?: { search?: string; type?: string }): Promise<EvaPartner[]> =>
    api.get("/eva-platform/partners", { params }).then((r) => r.data),
  createPartner: (data: Record<string, unknown>): Promise<EvaPartnerDetail> =>
    api.post("/eva-platform/partners", data).then((r) => r.data),
  getPartner: (id: string): Promise<EvaPartnerDetail> =>
    api.get(`/eva-platform/partners/${id}`).then((r) => r.data),
  updatePartner: (id: string, data: Record<string, unknown>): Promise<EvaPartner> =>
    api.patch(`/eva-platform/partners/${id}`, data).then((r) => r.data),
  deactivatePartner: (id: string): Promise<void> =>
    api.delete(`/eva-platform/partners/${id}`).then((r) => r.data),

  // Deals
  listDeals: (params?: { partner_id?: string; stage?: string }): Promise<PartnerDeal[]> =>
    api.get("/eva-platform/deals", { params }).then((r) => r.data),
  createDeal: (data: Record<string, unknown>): Promise<PartnerDeal> =>
    api.post("/eva-platform/deals", data).then((r) => r.data),
  updateDeal: (id: string, data: Record<string, unknown>): Promise<PartnerDeal> =>
    api.patch(`/eva-platform/deals/${id}`, data).then((r) => r.data),
  deleteDeal: (id: string): Promise<void> =>
    api.delete(`/eva-platform/deals/${id}`).then((r) => r.data),
  markDealWon: (id: string): Promise<PartnerDeal> =>
    api.post(`/eva-platform/deals/${id}/won`).then((r) => r.data),
  markDealLost: (id: string, reason?: string): Promise<PartnerDeal> =>
    api.post(`/eva-platform/deals/${id}/lost`, { reason }).then((r) => r.data),
  createAccountFromDeal: (id: string, data: Record<string, unknown>): Promise<PartnerDeal> =>
    api.post(`/eva-platform/deals/${id}/create-account`, data).then((r) => r.data),

  // Impersonation
  impersonateAccount: (id: string): Promise<{ magic_link_url: string; account_id: string; account_name: string }> =>
    api.post(`/eva-platform/impersonate/account/${id}`).then((r) => r.data),

  // Dashboard
  dashboard: (): Promise<PlatformDashboard> =>
    api.get("/eva-platform/dashboard").then((r) => r.data),

  // Health
  health: (): Promise<{ status: string; detail?: string }> =>
    api.get("/eva-platform/health").then((r) => r.data),

  // Infrastructure
  listHosts: (): Promise<RuntimeHost[]> =>
    api.get("/eva-platform/infrastructure/hosts").then((r) => r.data),
  listHostEmployees: (hostId: string): Promise<RuntimeEmployee[]> =>
    api.get(`/eva-platform/infrastructure/hosts/${hostId}/employees`).then((r) => r.data),
  getEmployeeDetail: (agentId: string): Promise<RuntimeEmployeeDetail> =>
    api.get(`/eva-platform/infrastructure/employees/${agentId}`).then((r) => r.data),
  getDockerStatus: (hostIp: string): Promise<DockerContainer[]> =>
    api.get(`/eva-platform/infrastructure/hosts/${hostIp}/docker/status`).then((r) => r.data),
  getDockerLogs: (hostIp: string, containerName: string, tail?: number): Promise<DockerLogs> =>
    api.get(`/eva-platform/infrastructure/hosts/${hostIp}/docker/logs/${containerName}`, { params: { tail } }).then((r) => r.data),
  listFiles: (hostIp: string, path?: string): Promise<FileEntry[]> =>
    api.get(`/eva-platform/infrastructure/hosts/${hostIp}/files`, { params: { path } }).then((r) => r.data),
  getFileContent: (hostIp: string, path: string): Promise<FileContent> =>
    api.get(`/eva-platform/infrastructure/hosts/${hostIp}/files/content`, { params: { path } }).then((r) => r.data),
};
