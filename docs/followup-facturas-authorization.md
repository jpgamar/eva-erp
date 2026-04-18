# Follow-up: Factura object-level authorization (BOLA)

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
