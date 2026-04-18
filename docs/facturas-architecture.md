# Facturas architecture — outbox + reconciliation + complements

This document describes how CFDI emission flows through the Eva ERP
after the 2026-04-18 F-4 incident fix. If you're touching
`backend/src/facturas/`, `backend/src/webhooks/router.py`, or
`backend/src/eva_billing/service.py`, read this first.

## The bug this architecture exists to prevent

Factura F-4 (SERVIACERO COMERCIAL, $4,162.29, 2026-03-23, UUID
`0B7DD523-8189-4131-A584-BEB731A54CA3`) was stamped successfully by
FacturAPI but never committed to the ERP DB. The owner only discovered
this during his 2026-04-18 tax declaration, when the SAT's prefill
showed an ingreso he couldn't find in the ERP.

Root cause: the old code called `facturapi.create_invoice()` inside the
request handler, BEFORE the implicit `await session.commit()` in
`get_db()`. If the commit failed for any reason (Supabase connection
timeout, Koyeb container restart, serialization conflict), the
FacturAPI CFDI was orphaned with no ERP record.

## The outbox pattern

All CFDI emission now flows through three stages:

```
 ┌────────────────────────────────────────────────────────────────┐
 │ Stage 1: Request handler / webhook                             │
 │                                                                │
 │   1. INSERT facturas row                                       │
 │      status = 'pending_stamp'                                  │
 │      facturapi_idempotency_key = str(uuid)                     │
 │   2. COMMIT  ← point of no return                              │
 │   3. Return 202 Accepted (or enqueue notification)             │
 └────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ Stage 2: Outbox worker (30s interval)                          │
 │   backend/src/facturas/outbox.py                               │
 │                                                                │
 │   1. SELECT ... FOR UPDATE SKIP LOCKED                         │
 │        WHERE status='pending_stamp'                            │
 │          AND next_retry_at <= now()                            │
 │   2. POST /v2/invoices                                         │
 │        body.idempotency_key = factura.facturapi_idempotency_key│
 │   3. On success: UPDATE status='valid' + CFDI fields + COMMIT  │
 │   4. On failure: bump retry count, schedule next_retry_at      │
 │                  after 5 failures: status='stamp_failed' +     │
 │                  billing_monitor alert                         │
 └────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ Stage 3: Reconciliation loop (1h interval)                     │
 │   backend/src/facturas/reconciliation.py                       │
 │                                                                │
 │   For every FacturAPI invoice:                                 │
 │     * Not in DB       → INSERT (adopt — e.g. F-4 itself)       │
 │     * pending_stamp   → UPDATE to valid (heal outbox failures) │
 │     * valid→cancelled → UPDATE (sync dashboard cancellations)  │
 │     * matched         → no-op                                  │
 └────────────────────────────────────────────────────────────────┘
```

Why this is robust:

- **Commit before FacturAPI**: the row exists before we hit the network.
  A crash mid-call just means the worker retries later.
- **Idempotency key**: retries send the same key, so FacturAPI returns
  the same CFDI instead of creating duplicates.
- **Reconciliation**: even if *everything* fails, the hourly loop pulls
  the truth from FacturAPI and sync the ERP back.

## Three entry points today

| Entry point | File | Result |
|---|---|---|
| Manual UI `/facturas` | `facturas/router.py::create_factura` + `stamp_factura` | row → `pending_stamp` |
| Stripe webhook (customer pays subscription) | `webhooks/router.py::_enqueue_cfdi_stamp` → `eva_billing/service.py::stamp` | row → `pending_stamp` + `eva_billing_record` → `pending_stamp` |
| Eva platform API (`/internal/eva-billing/stamp`) | `eva_billing/router.py::stamp` → `eva_billing/service.py::stamp` | same as above |

All three now converge on the same outbox state machine. Nothing hits
FacturAPI inside a request handler.

## Complementos de Pago (CFDI tipo P)

When a PPD factura is partially paid, SAT requires a separate tipo P
CFDI. Flow:

1. UI `POST /facturas/{id}/payments` with `{payment_date, amount,
   payment_form}`.
2. `payment_complements.register_payment` validates preconditions
   (factura is valid, is PPD, balance is sufficient) and inserts a
   `cfdi_payments` row in `status='pending_stamp'` with its own
   idempotency key (`pago:{payment_id}`). Bumps `factura.total_paid`
   and `factura.payment_status` optimistically.
3. Same outbox worker processes both `facturas` and `cfdi_payments`.
   Payment rows sort by `payment_date ASC` so the nearest-to-deadline
   row stamps first (SAT's 5-day rule).
4. Payload structure (FacturAPI spec):
   ```json
   {
     "type": "P",
     "customer": {"legal_name": ..., "tax_id": ..., ...},
     "complements": [{
       "type": "pago",
       "data": [{
         "payment_form": "28",
         "related_documents": [{
           "uuid": "<original PPD CFDI UUID>",
           "amount": 5800.00,
           "installment": 1,
           "last_balance": 10000.00,
           "taxes": [{"base": 5000.00, "type": "IVA", "rate": 0.16}]
         }]
       }]
     }]
   }
   ```

## Gastos (received CFDIs)

Separate module `backend/src/facturas_recibidas/`. Parser is pure stdlib
(`xml.etree.ElementTree`), supports CFDI 3.3 and 4.0. Validates the
receiver RFC matches the operator's. Payment date defaults to issue
date for PUE and stays NULL for PPD (operator updates when paid).

Used by the declaración calculator to compute IVA acreditable per
month. See `docs/gastos-cfdi.md`.

## Operator-facing files

| File | Purpose |
|---|---|
| `backend/src/facturas/models.py` | `Factura`, `CfdiPayment` ORM |
| `backend/src/facturas/service.py` | FacturAPI HTTP primitives + payload builders |
| `backend/src/facturas/outbox.py` | Worker loop + `stamp_pending_factura` / `stamp_pending_payment` |
| `backend/src/facturas/reconciliation.py` | Hourly FacturAPI → ERP sync |
| `backend/src/facturas/payment_complements.py` | PPD payment registration logic |
| `backend/src/facturas/router.py` | HTTP endpoints |
| `backend/src/eva_billing/service.py` | Subscription billing bridge that feeds into the outbox |
| `backend/src/webhooks/router.py` | Stripe webhook → enqueue CFDI |

## Config toggles

| Env var | Default | Meaning |
|---|---|---|
| `FACTURAPI_API_KEY` | — | FacturAPI auth (required in prod) |
| `FACTURAPI_OUTBOX_ENABLED` | `true` | Worker loop on/off |
| `FACTURAPI_OUTBOX_INTERVAL_SECONDS` | `30` | Poll cadence |
| `FACTURAPI_OUTBOX_MAX_RETRIES` | `5` | Failures before `stamp_failed` |
| `FACTURAPI_RECONCILIATION_ENABLED` | `true` | Hourly sync on/off |
| `FACTURAPI_RECONCILIATION_INTERVAL_SECONDS` | `3600` | Sync cadence |

## See also

- `docs/runbook-cfdi-stamping-failure.md` — incident response when
  `billing_cfdi_failure` alerts fire.
- `docs/fiscal-resico-pf.md` — tax rules that shape the code.
- `docs/declaracion-mensual.md` — how the monthly tax calculator uses
  facturas + gastos.
