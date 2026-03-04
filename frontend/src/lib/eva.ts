const DEFAULT_EVA_APP_URL = "https://app.goeva.ai";
const DEFAULT_EVA_API_BASE_URL = "https://api.goeva.ai/api/v1";
const DEFAULT_EVA_TARGET_PHONE = "+525629151938";
const DEFAULT_EVA_TARGET_GATEWAY = "openclaw-gateway-e2aac289a6";
const DEFAULT_EVA_TARGET_PORT = 19070;

export interface EvaConfig {
  appBase: string;
  apiBase: string;
  email: string;
  password: string;
  manualUrl: string;
  hasCredentials: boolean;
  targetAgentId: string;
  targetPhone: string;
  targetGateway: string;
  targetPort: number;
}

export class EvaHttpError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown = null) {
    super(message);
    this.name = "EvaHttpError";
    this.status = status;
    this.body = body;
  }
}

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function normalizePath(path: string): string {
  if (!path) return "/";
  return path.startsWith("/") ? path : `/${path}`;
}

function toNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  const textBody = await response.text();
  return textBody || null;
}

export function buildEvaManualUrl(appBase: string, redirectPath: string): string {
  const redirect = encodeURIComponent(normalizePath(redirectPath));
  return `${normalizeBaseUrl(appBase)}/auth/login?redirect=${redirect}`;
}

export function createEvaSsoUrl(
  manualUrl: string,
  accessToken: string,
  refreshToken: string,
): string {
  const hash = new URLSearchParams({
    access_token: accessToken,
    refresh_token: refreshToken,
  }).toString();
  return `${manualUrl}#${hash}`;
}

export function getEvaConfig(): EvaConfig {
  const appBase = normalizeBaseUrl(process.env.EVA_APP_URL || DEFAULT_EVA_APP_URL);
  const apiBase = normalizeBaseUrl(process.env.EVA_API_BASE_URL || DEFAULT_EVA_API_BASE_URL);
  const email = asString(process.env.EVA_SHARED_EMAIL);
  const password = asString(process.env.EVA_SHARED_PASSWORD);
  const targetAgentId = asString(process.env.EVA_TARGET_AGENT_ID);
  const targetPhone = asString(process.env.EVA_TARGET_PHONE) || DEFAULT_EVA_TARGET_PHONE;
  const targetGateway = asString(process.env.EVA_TARGET_GATEWAY) || DEFAULT_EVA_TARGET_GATEWAY;
  const targetPort = toNumber(process.env.EVA_TARGET_PORT, DEFAULT_EVA_TARGET_PORT);
  return {
    appBase,
    apiBase,
    email,
    password,
    manualUrl: buildEvaManualUrl(appBase, "/inbox"),
    hasCredentials: Boolean(email && password),
    targetAgentId,
    targetPhone,
    targetGateway,
    targetPort,
  };
}

export async function loginEvaSharedAccount(config?: EvaConfig): Promise<{
  accessToken: string;
  refreshToken: string;
  ssoUrl: string;
}> {
  const cfg = config ?? getEvaConfig();
  if (!cfg.hasCredentials) {
    throw new EvaHttpError("EVA shared credentials are not configured", 400);
  }

  const response = await fetch(`${cfg.apiBase}/auth/login`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      email: cfg.email,
      password: cfg.password,
    }),
  });

  const body = await parseResponseBody(response);
  if (!response.ok) {
    throw new EvaHttpError("Failed to authenticate EVA shared account", response.status, body);
  }

  const accessToken =
    asString((body as { token?: { access_token?: string } })?.token?.access_token) ||
    asString((body as { access_token?: string })?.access_token);
  const refreshToken =
    asString((body as { token?: { refresh_token?: string } })?.token?.refresh_token) ||
    asString((body as { refresh_token?: string })?.refresh_token);

  if (!accessToken || !refreshToken) {
    throw new EvaHttpError("EVA login response is missing access or refresh token", 502, body);
  }

  const manualUrl = buildEvaManualUrl(cfg.appBase, "/inbox");
  return {
    accessToken,
    refreshToken,
    ssoUrl: createEvaSsoUrl(manualUrl, accessToken, refreshToken),
  };
}

export async function evaRequest<T>(
  path: string,
  options: {
    accessToken: string;
    apiBase?: string;
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
  },
): Promise<T> {
  const apiBase = normalizeBaseUrl(options.apiBase || getEvaConfig().apiBase);
  const method = options.method || "GET";
  const normalizedPath = normalizePath(path);
  const response = await fetch(`${apiBase}${normalizedPath}`, {
    method,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${options.accessToken}`,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  const body = await parseResponseBody(response);
  if (!response.ok) {
    throw new EvaHttpError(`EVA request failed for ${normalizedPath}`, response.status, body);
  }

  return body as T;
}

export async function evaGet<T>(
  path: string,
  options: { accessToken: string; apiBase?: string },
): Promise<T> {
  return evaRequest<T>(path, {
    ...options,
    method: "GET",
  });
}
