# Runbook: CFDI stamping failure

This runbook fires when `billing_monitor` reports a
`billing_cfdi_failure` issue (critical severity) on the monitoring
dashboard. The outbox worker has exhausted retries for a factura or
payment complement.

## Triage (60 seconds)

1. Open the monitoring dashboard at `/monitoring` (route in the ERP).
2. Find the issue with category `billing_cfdi_failure` and grab:
   - `summary` string → has `factura=<id>` or `payment=<id>`
   - `empresa_name` → which customer's CFDI failed
   - `stripe_invoice_id` → if applicable (subscription path)
3. Pull the row directly:
   ```sql
   -- For a factura (ingreso):
   SELECT id, status, customer_name, total, stamp_retry_count,
          last_stamp_error, next_retry_at
   FROM facturas
   WHERE id = '<factura_id>';

   -- For a complemento de pago:
   SELECT p.id, p.status, p.payment_amount, p.payment_date,
          p.stamp_retry_count, p.last_stamp_error,
          f.cfdi_uuid AS parent_uuid
   FROM cfdi_payments p
   JOIN facturas f ON f.id = p.factura_id
   WHERE p.id = '<payment_id>';
   ```

## Diagnose the `last_stamp_error`

### `FacturAPI 400: customer tax data invalid`

The customer's fiscal info is wrong (RFC format, missing postal code,
wrong régimen). Fix the `empresas` / `customers` row, then:

```sql
-- Reset to pending_stamp to let the outbox retry
UPDATE facturas
SET status = 'pending_stamp',
    stamp_retry_count = 0,
    last_stamp_error = NULL,
    next_retry_at = NULL
WHERE id = '<factura_id>';
```

Or hit `POST /api/v1/facturas/reconcile` — the reconciliation loop
heals stamp_failed → valid if FacturAPI already has the CFDI.

### `FacturAPI 401/403`

API key rotated or expired. Fix in Koyeb secrets:

```bash
koyeb secret update FACTURAPI_API_KEY_eva_erp --value sk_live_...
koyeb service redeploy eva-erp/api --git-sha <current HEAD>
```

Then reset the failed rows as above.

### `FacturAPI 502/503/504` or `Connection reset`

Transient FacturAPI outage. The worker already backs off exponentially;
if rows are stuck in `stamp_failed`, reset them with the SQL above —
the worker will retry during the next poll.

If FacturAPI outage is ongoing: reduce the risk of PPD-complemento
deadlines slipping by checking:

```sql
SELECT COUNT(*) FROM cfdi_payments
WHERE status IN ('pending_stamp', 'stamp_failed')
  AND payment_date < date_trunc('month', now()) + interval '5 days';
```

If > 0 and today ≥ day 3 of the month, escalate to the owner
(Gustavo) — may need to emit the complements from the FacturAPI
dashboard manually.

### `Original factura missing or unstamped`

Complemento de Pago tried to stamp but its parent PPD factura has no
`cfdi_uuid` (never stamped, or cancelled). Either:

- Stamp the parent first (reset it to pending_stamp and let the outbox
  pick it up), OR
- Cancel the complemento and re-register the payment after the parent
  is stamped.

## When the CFDI is actually in FacturAPI but the ERP says failed

Check FacturAPI first — the outbox might have stamped successfully but
the commit failed:

```bash
curl -s -H "Authorization: Bearer $FACTURAPI_API_KEY" \
  "https://www.facturapi.io/v2/invoices?limit=5" | jq '.data[] | {id, uuid, status, folio: .folio_number}'
```

If the CFDI is there but the ERP row is stamp_failed: run
reconciliation manually:

```bash
curl -X POST https://erp.goeva.ai/api/v1/facturas/reconcile \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

The reconciliation pass will heal the row (status → valid,
cfdi_uuid populated).

## Prevention checklist

After resolving any `billing_cfdi_failure`, consider:

- [ ] Is the root cause fixed at the source? (fiscal data, config, etc.)
- [ ] Any other rows likely to hit the same failure? Query by customer_rfc.
- [ ] Should `FACTURAPI_OUTBOX_MAX_RETRIES` be bumped if this was
      transient but slow? Default 5 is conservative.
- [ ] File follow-up ticket if this reveals a product gap.

## Related

- Architecture: `docs/facturas-architecture.md`
- Fiscal rules: `docs/fiscal-resico-pf.md`
- Monitoring dashboard: `/monitoring` in the ERP frontend
- Billing monitor code: `backend/src/eva_platform/billing_monitor.py`
