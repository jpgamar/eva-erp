# Follow-up: Factura authorization + multi-currency completeness

This doc tracks two items that reviewers flagged but that are out of
scope for the 2026-04-18 CFDI atomicity + RESICO tax module PR.

## 1. Factura object-level authorization (BOLA)

**Status:** tracked, not exploitable in current single-operator production.
**Severity:** P1 when we onboard a second non-admin user.
**Discovered:** Codex review round 4 on the 2026-04-18 CFDI atomicity PR.

## The gap

`get_current_user` (`backend/src/auth/dependencies.py:76`) authenticates
the caller but performs no tenant/account/ownership scoping. Every
factura endpoint then reads or mutates rows by bare `factura_id` — no
`account_id` filter, no ownership check — so an authenticated user
who knows or guesses a UUID can reach a factura created by someone
else on the same deployment.

Affected endpoints (all in `backend/src/facturas/router.py`):

- `GET /api/v1/facturas` — lists every row in the DB globally
- `GET /api/v1/facturas/{id}` — fetches by UUID
- `GET /api/v1/facturas/{id}/pdf` / `xml` — serves SAT-signed files
- `POST /api/v1/facturas/{id}/stamp` — mutates state
- `POST /api/v1/facturas/{id}/payments` — registers payment
- `GET /api/v1/facturas/{id}/payments` — lists payments
- `DELETE /api/v1/facturas/{id}` — cancels in SAT
- `POST /api/v1/facturas` — accepts caller-supplied `account_id` with no verification

## Why it's not exploitable *today*

In 2026-04 production the ERP has effectively one operator (Gustavo,
admin). The partner account (`jpgamar`) is also admin-equivalent for
our current use. There is no non-admin user who would be fenced off
by tenant scoping. The BOLA is a design gap waiting to become a real
exploit the moment we grant a third-party user access to the ERP.

## Why it wasn't fixed in the 2026-04-18 CFDI atomicity PR

Scoping every factura endpoint requires a prior decision:

1. **Ownership model** — is the owner the `created_by` user, the
   `account_id`, or a new per-user "company membership" table?
2. **Admin role** — Gustavo expects to see every factura; scoping
   must exempt him without weakening the check.
3. **Historical data** — facturas adopted by reconciliation have
   `account_id=NULL` and `created_by=NULL`. Strict scoping would
   hide them from Gustavo until we backfill ownership.

Each is a judgment call, not a mechanical patch. Fixing them in the
same PR that ran the CFDI atomicity + RESICO tax module rollout would
have ballooned the PR and delayed the F-4 remediation.

## Plan to close

Separate PR. Outline:

1. Extend `User` with `is_admin` (default false) + `default_account_id`.
2. New `account_members` table: `(user_id, account_id, role)`.
3. Add `enforce_factura_access(factura, user)` helper. Admins pass
   through; non-admins must have an `account_members` row matching
   `factura.account_id`.
4. Apply to all endpoints listed above. `list_facturas` filters by
   `account_id IN user's accounts`. `create_factura` verifies the
   caller-supplied `account_id` is theirs (admins can impersonate).
5. Backfill ownership for NULL rows: assign to Gustavo's account via
   a migration.
6. Regression tests: non-admin user cannot touch a factura in an
   account they don't belong to, even by UUID.

Estimated effort: 2-3 days.

## Related

- Codex round-4 review transcript: local path
  `/private/tmp/claude-501/-Users-gustavozermeno-Code-eva/...`
- CLAUDE.md multi-industry / multi-tenant notes
- The `empresas` module already has account-scoping patterns to
  mirror (see `backend/src/empresas/router.py`)

---

## 2. Multi-currency declaración math

**Status:** tracked, not exploitable today (100% of Gustavo's invoicing is MXN).
**Severity:** P2 the first time a non-MXN factura is emitted/received.
**Discovered:** Codex review round 5 on the 2026-04-18 PR.

### The gap

The 2026-04-18 PR closed the serialization gap on the FacturAPI
payload (invoice `currency` + complement `currency`/`exchange`), so
the stamped CFDI will be fiscally correct in any currency. But the
ERP's declaración aggregator still sums raw `Decimal` values from
`facturas.subtotal`, `cfdi_payments.payment_amount`, and
`facturas_recibidas.tax_iva` without any currency conversion
(`backend/src/declaracion/service.py` `_sum_pue_ingresos`,
`_sum_ppd_payments`, `_sum_iva_acreditable`).

If the operator stamps one MXN factura of $10,000 and one USD
factura of $500, the declaración will report "$10,500 ingresos"
instead of "$10,000 MXN + $9,875 MXN conversion = $19,875". SAT
filings accept a single MXN total, so the declaración would
under-report ingresos and under-pay ISR.

### Why it's not exploitable today

Every factura, gasto, and payment currently in `facturas.currency` /
`cfdi_payments.currency` / `facturas_recibidas.currency` is `MXN`.
The UI exposes a USD selector but Gustavo has never used it. The
bug activates only on the first non-MXN row.

### Plan to close — full multi-currency e2e

This is actually a bigger plan than declaración math alone. End-to-end
multi-currency requires every layer to carry the rate:

1. **Migration** — add `exchange_rate` to `facturas`, `cfdi_payments`,
   and `facturas_recibidas`. Numeric(12, 6), nullable (NULL = MXN).
2. **Model** — mirror the new column on ORM classes.
3. **Router** (`backend/src/facturas/router.py`) — `create_factura`
   reads `data.exchange_rate` and persists to the row.
4. **Outbox rebuild** (`backend/src/facturas/outbox.py`
   `_rebuild_factura_create`) — include `exchange_rate=factura.exchange_rate`
   so async stamping of stored USD rows doesn't trip the new
   `FacturaCreate` validator.
5. **Frontend** (`frontend/src/app/(app)/facturas/page.tsx`) — add
   an `exchange_rate` input that becomes visible when currency != MXN.
   Pull a default from DOF FIX for the invoice date (Banxico API).
6. **Declaración aggregators** (`backend/src/declaracion/service.py`)
   — project every non-MXN row to MXN using its stored rate before
   summing ingresos / IVA / retenciones.
7. **Backfill** — existing NULL rows are MXN by construction; no
   backfill needed since production is 100% MXN today.
8. **Regression test** — a mixed USD + MXN period matches hand-computed
   totals; outbox can stamp a stored USD invoice without tripping
   the schema validator.

Estimated effort: 2-3 days.

### Current state — what the 2026-04-18 PR did and did not do

**Did:**
- Close the FacturAPI serialization gap on tipo-I CFDI (currency +
  exchange on the stamp payload).
- Close the FacturAPI serialization gap on tipo-P complement
  (currency + exchange on the pago data block).
- Add schema-layer validator that REJECTS USD `FacturaCreate` without
  an explicit `exchange_rate`. This turns a silent "stamp at rate
  1.0" footgun into an explicit 422 at the POST /facturas boundary
  — safer than the pre-PR behavior.

**Did not:**
- Add `exchange_rate` as a persisted column on `Factura`.
- Expose `exchange_rate` in the frontend USD flow.
- Teach the outbox rebuild to carry the stored rate.
- Project non-MXN rows to MXN in declaración math.

**Safe to defer because:** 100% of production CFDIs are MXN today.
The UI currency selector exists but no operator has ever clicked
USD. The failure mode for the USD path is now "explicit 422" (safe
rejection), not "silent wrong CFDI stamped at SAT" (the pre-PR bug).

### Related

- `frontend/src/app/(app)/facturas/page.tsx` exposes `USD` on the
  currency selector — the 2026-04-18 PR tightened the validator so
  that path now fails fast instead of stamping a broken CFDI.
- SAT Anexo 20 requires `TipoCambio` on non-MXN CFDIs.
