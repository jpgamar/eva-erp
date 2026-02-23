# EVA ERP Agent API

This backend now supports agent authentication with a single API key for all existing ERP routes under `/api/v1/*`.

## 1) Required env vars

Set these in backend environment:

```env
AGENT_API_KEY=your-long-random-secret
AGENT_API_ACTOR_EMAIL=admin@your-company.com
```

- `AGENT_API_KEY`: value sent by the agent in `X-Agent-Key`.
- `AGENT_API_ACTOR_EMAIL`: active ERP admin user email used as actor identity.

## 2) Authentication format

Send this header in every request:

```http
X-Agent-Key: <AGENT_API_KEY>
```

When the key is valid, backend authenticates as the configured ERP admin actor and can call all routes that currently depend on `get_current_user` or `require_admin`.

## 3) Route discovery for agents

Use the dedicated endpoints:

- `GET /api/v1/agent/capabilities`
- `GET /api/v1/agent/openapi`

These are agent-key-only and return machine-readable route metadata/spec.

## 4) High-level agent actions

Shortcut endpoints:

- `POST /api/v1/agent/customers`
- `POST /api/v1/agent/facturas`
- `GET /api/v1/agent/facturas`
- `POST /api/v1/agent/workflows/customer-factura`

The workflow endpoint creates a customer first, then creates factura using that customer.

## 5) Canonical ERP routes now mounted

`/api/v1/customers` is mounted in main router and available for normal users and agent-key clients.
