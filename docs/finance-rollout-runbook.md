# Finance Lifecycle Rollout Runbook

## Scope

This runbook covers the production rollout for the unified finance lifecycle KPIs:

1. Projected Revenue
2. Invoiced (SAT)
3. Payments Received
4. Bank Deposits
5. Gap To Collect
6. Gap To Deposit

## 1) Feature Flag

Set `FINANCE_KPI_SOURCE`:

- `lifecycle` (default): enables new lifecycle KPI cards/panels.
- `legacy`: hides lifecycle cards and keeps legacy dashboard behavior.

## 2) Stripe Realtime Prerequisites

Required env vars:

- `EVA_STRIPE_SECRET_KEY`
- `EVA_STRIPE_WEBHOOK_SECRET`
- `STRIPE_RECONCILIATION_ENABLED=true`

Webhook endpoint:

- `POST /api/v1/finances/stripe/webhook`

## 3) Historical Backfill (Run Once)

Execute once after deploy:

- `POST /api/v1/finances/stripe/reconcile`
- payload: `{ "backfill": true, "max_events": 5000 }`

Expected: `processed_events` > 0 and `failed_events` == 0.

## 4) Parity Check (Admin)

Compare lifecycle vs legacy monthly totals before enabling lifecycle in production dashboards:

- `GET /api/v1/finances/rollout/parity-check?period=YYYY-MM&threshold_mxn=1.00`

Acceptable:

- `within_threshold = true`

## 5) Resolve Unlinked Revenue

Inspect unresolved events:

- `GET /api/v1/finances/stripe/unlinked?period=YYYY-MM&limit=100`

Link payment events:

- `POST /api/v1/finances/stripe/unlinked/payment/{stripe_event_id}/link`
- payload: `{ "account_id": "<uuid>", "customer_id": "<uuid|null>" }`

Link payout events:

- `POST /api/v1/finances/stripe/unlinked/payout/{stripe_event_id}/link`
- payload: `{ "account_id": "<uuid>" }`

Target before final rollout:

- unlinked payment events and unlinked payout events at acceptable threshold for the month.

## 6) Legacy Invoice Policy

`/finances/invoices` is read-only by design.

- New/patch/delete invoice routes return `410 Gone`.
- SAT Facturas module is the source of truth for invoiced KPI.

## 7) Go-Live

1. Confirm backfill finished.
2. Confirm parity check within threshold.
3. Confirm unlinked counts accepted.
4. Set `FINANCE_KPI_SOURCE=lifecycle`.
5. Verify dashboard + finances cards and reconciliation panel.
