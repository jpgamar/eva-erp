import { NextRequest, NextResponse } from "next/server";
import {
  EvaHttpError,
  buildEvaManualUrl,
  createEvaSsoUrl,
  evaGet,
  getEvaConfig,
  loginEvaSharedAccount,
} from "@/lib/eva";

export const dynamic = "force-dynamic";

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function noStoreJson(body: unknown, init?: ResponseInit) {
  const response = NextResponse.json(body, init);
  response.headers.set("Cache-Control", "no-store");
  return response;
}

function normalizePhone(value: string): string {
  return value.replace(/\D/g, "");
}

function collectValues(input: unknown): { strings: string[]; numbers: number[] } {
  const strings: string[] = [];
  const numbers: number[] = [];
  const queue: unknown[] = [input];
  const visited = new Set<unknown>();
  let inspected = 0;

  while (queue.length > 0 && inspected < 500) {
    const current = queue.shift();
    inspected += 1;

    if (typeof current === "string") {
      strings.push(current);
      continue;
    }

    if (typeof current === "number" && Number.isFinite(current)) {
      numbers.push(current);
      continue;
    }

    if (!current || typeof current !== "object") {
      continue;
    }

    if (visited.has(current)) {
      continue;
    }
    visited.add(current);

    if (Array.isArray(current)) {
      for (const entry of current) {
        queue.push(entry);
      }
      continue;
    }

    for (const value of Object.values(current)) {
      queue.push(value);
    }
  }

  return { strings, numbers };
}

function extractAgentId(agent: JsonRecord): string {
  const candidates = [
    agent.id,
    agent.agent_id,
    agent.openclaw_agent_id,
    isRecord(agent.agent) ? agent.agent.id : undefined,
    isRecord(agent.employee) ? agent.employee.id : undefined,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }

  return "";
}

function toAgentList(payload: unknown): JsonRecord[] {
  if (Array.isArray(payload)) {
    return payload.filter(isRecord);
  }

  if (!isRecord(payload)) {
    return [];
  }

  const containers = [payload.data, payload.items, payload.results, payload.agents];
  for (const container of containers) {
    if (Array.isArray(container)) {
      return container.filter(isRecord);
    }
  }

  return [];
}

function matchByPhone(agents: JsonRecord[], targetPhone: string): JsonRecord | null {
  const normalizedTarget = normalizePhone(targetPhone);
  if (!normalizedTarget) {
    return null;
  }

  for (const agent of agents) {
    const { strings } = collectValues(agent);
    const found = strings.some((value) => normalizePhone(value) === normalizedTarget);
    if (found) {
      return agent;
    }
  }

  return null;
}

function matchByText(agents: JsonRecord[], token: string): JsonRecord | null {
  const normalizedToken = token.trim().toLowerCase();
  if (!normalizedToken) {
    return null;
  }

  for (const agent of agents) {
    const { strings } = collectValues(agent);
    const found = strings.some((value) => value.toLowerCase().includes(normalizedToken));
    if (found) {
      return agent;
    }
  }

  return null;
}

function matchByPort(agents: JsonRecord[], port: number): JsonRecord | null {
  if (!Number.isFinite(port) || port <= 0) {
    return null;
  }

  for (const agent of agents) {
    const { strings, numbers } = collectValues(agent);
    if (numbers.some((value) => value === port)) {
      return agent;
    }
    if (strings.some((value) => Number(value) === port)) {
      return agent;
    }
  }

  return null;
}

function findFixedTargetAgent(
  agents: JsonRecord[],
  criteria: {
    targetAgentId: string;
    targetPhone: string;
    targetGateway: string;
    targetPort: number;
  },
): JsonRecord | null {
  if (criteria.targetAgentId) {
    const byId = agents.find((agent) => extractAgentId(agent) === criteria.targetAgentId);
    if (byId) {
      return byId;
    }
  }

  const byPhone = matchByPhone(agents, criteria.targetPhone);
  if (byPhone) {
    return byPhone;
  }

  const byGateway = matchByText(agents, criteria.targetGateway);
  if (byGateway) {
    return byGateway;
  }

  const byPort = matchByPort(agents, criteria.targetPort);
  if (byPort) {
    return byPort;
  }

  return null;
}

async function checkErpSession(
  request: NextRequest,
): Promise<{ authenticated: boolean; status: number }> {
  const backendBase = process.env.API_URL || "http://127.0.0.1:4010";
  const authResponse = await fetch(`${backendBase}/api/v1/auth/me`, {
    method: "GET",
    cache: "no-store",
    headers: {
      cookie: request.headers.get("cookie") || "",
    },
  });
  return {
    authenticated: authResponse.ok,
    status: authResponse.status,
  };
}

function extractErrorDetail(body: unknown): string | null {
  if (typeof body === "string" && body.trim()) {
    return body.trim();
  }
  if (isRecord(body) && typeof body.detail === "string" && body.detail.trim()) {
    return body.detail.trim();
  }
  return null;
}

function inferFailureStatus(error: unknown): number {
  if (!(error instanceof Error)) return 500;
  const message = error.message.toLowerCase();
  if (
    message.includes("fetch") ||
    message.includes("network") ||
    message.includes("econnrefused") ||
    message.includes("enotfound") ||
    message.includes("timed out")
  ) {
    return 502;
  }
  return 500;
}

export async function GET(request: NextRequest) {
  const config = getEvaConfig();

  try {
    const sessionCheck = await checkErpSession(request);
    if (!sessionCheck.authenticated && sessionCheck.status === 401) {
      return noStoreJson({ detail: "Not authenticated" }, { status: 401 });
    }
    if (!sessionCheck.authenticated) {
      return noStoreJson({ detail: "Failed to validate ERP session" }, { status: 502 });
    }

    if (!config.hasCredentials) {
      return noStoreJson({
        embedUrl: null,
        bootstrapUrl: null,
        manualUrl: config.manualUrl,
        warning: "not configured",
        agentId: null,
      });
    }

    const login = await loginEvaSharedAccount(config);
    const rawAgents = await evaGet<unknown>("/agents", {
      accessToken: login.accessToken,
      apiBase: config.apiBase,
    });
    const agents = toAgentList(rawAgents);

    const matchedAgent = findFixedTargetAgent(agents, {
      targetAgentId: config.targetAgentId,
      targetPhone: config.targetPhone,
      targetGateway: config.targetGateway,
      targetPort: config.targetPort,
    });

    if (!matchedAgent) {
      return noStoreJson(
        {
          embedUrl: null,
          bootstrapUrl: null,
          manualUrl: config.manualUrl,
          agentId: null,
          detail: "Fixed target agent was not found in EVA /agents response",
          target: {
            targetAgentId: config.targetAgentId || null,
            targetPhone: config.targetPhone || null,
            targetGateway: config.targetGateway || null,
            targetPort: config.targetPort || null,
          },
        },
        { status: 404 },
      );
    }

    const agentId = extractAgentId(matchedAgent);
    if (!agentId) {
      return noStoreJson(
        {
          embedUrl: null,
          bootstrapUrl: null,
          manualUrl: config.manualUrl,
          agentId: null,
          detail: "Matched EVA agent has no id field",
        },
        { status: 502 },
      );
    }

    const bootstrapManualUrl = buildEvaManualUrl(config.appBase, "/inbox");
    const employeeManualUrl = buildEvaManualUrl(config.appBase, `/employees/${agentId}`);
    const bootstrapUrl = createEvaSsoUrl(
      bootstrapManualUrl,
      login.accessToken,
      login.refreshToken,
    );
    const embedUrl = createEvaSsoUrl(
      employeeManualUrl,
      login.accessToken,
      login.refreshToken,
    );

    return noStoreJson({
      embedUrl,
      bootstrapUrl,
      manualUrl: employeeManualUrl,
      agentId,
    });
  } catch (error) {
    if (error instanceof EvaHttpError) {
      const status = error.status >= 400 && error.status < 600 ? error.status : 502;
      return noStoreJson(
        {
          embedUrl: null,
          bootstrapUrl: null,
          manualUrl: config.manualUrl,
          agentId: null,
          error: error.message,
          detail: extractErrorDetail(error.body),
        },
        { status },
      );
    }

    return noStoreJson(
      {
        embedUrl: null,
        bootstrapUrl: null,
        manualUrl: config.manualUrl,
        agentId: null,
        error: "Failed to build EVA embed URLs",
        detail: error instanceof Error ? error.message : null,
      },
      { status: inferFailureStatus(error) },
    );
  }
}
