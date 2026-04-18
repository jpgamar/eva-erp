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

### Plan to close

Separate PR:

1. Extend models with `exchange_rate_at_issue` (the FX rate snapshotted
   at emission time — SAT needs this for the declaración, not the
   live rate at aggregation time).
2. Add `to_mxn(value, currency, rate)` helper in `src/common/money.py`.
3. Rewrite the three aggregators in `declaracion/service.py` to
   project everything to MXN before summing.
4. Backfill `exchange_rate_at_issue` for non-MXN historical rows via
   a one-off script using DOF FIX rates.
5. Regression test: a mixed USD + MXN period matches hand-computed
   totals.

Estimated effort: 1-2 days.

### Related

- `frontend/src/app/(app)/facturas/page.tsx` already exposes `USD`
  on the currency selector — the backend serialization fix in the
  2026-04-18 PR is what made that selector actually stamp correctly.
- SAT Anexo 20 requires `TipoCambio` on non-MXN CFDIs.
