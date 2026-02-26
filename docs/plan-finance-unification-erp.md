# Finance Unification Plan (Full Functional ERP)

## 1) Goal

Unify EVA ERP finance data so the business can trust these core metrics:

1. Projected Revenue
2. Invoiced (SAT)
3. Payments Received
4. Bank Deposits
5. Gap to Collect
6. Gap to Deposit

Without removing existing working dashboard cards.

---

## 2) Decisions Confirmed in Interview

1. ERP metric model approved:
   - Projected Revenue
   - Invoiced (SAT)
   - Payments Received
   - Bank Deposits
2. Projected Revenue source:
   - Primary source: Eva Accounts pricing (not legacy customer MRR)
3. Invoiced source:
   - SAT `facturas` only (`status=valid`)
   - `finances/invoices` no longer needed as source of truth
4. Stripe ingestion model:
   - Webhooks + nightly reconciliation job
5. Definitions:
   - Payments Received = successful captured payments (minus refunds) + allowed manual payment entries
   - Bank Deposits = Stripe paid payouts (net) + explicit manual deposit flow
6. Data anchor:
   - `account_id` becomes primary cross-module key
   - `customer_id` retained as legacy compatibility during migration
7. Dashboard behavior:
   - Keep all existing cards
   - Add 6 new finance cards on top
   - Compact existing cards to fit
8. Rollout:
   - Phased rollout approved
9. Coverage:
   - Show pricing/data coverage badge until account pricing reaches 100%
10. Manual entries policy:
   - Allowed, tagged reason required
11. Backfill policy:
   - Full Stripe historical backfill
   - Unmapped records go to `Unlinked Revenue` bucket
12. KPI naming approved:
   - Projected Revenue
   - Invoiced (SAT)
   - Payments Received
   - Bank Deposits
13. Projected Revenue formula:
   - Monthly non-prorated v1
14. Invoiced (SAT) filter:
   - Only `facturas.status = valid`
15. Alerts:
   - No automatic threshold alerts for now

---

## 3) Current Problems to Solve

1. Finance identity is fragmented across account/customer/factura/income.
2. Stripe fields exist but sync/webhooks are not implemented.
3. Two invoice systems create drift (`finances/invoices` vs SAT facturas).
4. Dashboard cards do not represent the full revenue lifecycle.
5. Existing accounts have no pricing values, so Projected Revenue is incomplete.

---

## 4) Architecture Target

### 4.1 Canonical Entity

- Canonical business entity for finance: `EvaAccount` (`account_id`)
- Legacy `customer_id` remains nullable bridge during migration

### 4.2 Canonical Metric Sources

1. Projected Revenue:
   - From active account pricing snapshot for selected month
2. Invoiced (SAT):
   - From `facturas` where `status='valid'`
3. Payments Received:
   - From Stripe payment events + manual payment entries
4. Bank Deposits:
   - From Stripe payouts (`paid`) + manual deposit entries
5. Gap to Collect:
   - Invoiced (SAT) - Payments Received
6. Gap to Deposit:
   - Payments Received - Bank Deposits

---

## 5) Phased Implementation

## Phase 1: Data Foundation (Required First)

### 5.1 Account Pricing Model

Add pricing fields to account + draft flows:

- `billing_amount` (Decimal)
- `billing_currency` (`MXN`/`USD`, default `MXN`)
- `billing_interval` (existing monthly/annual; normalize if needed)
- Optional `is_billable` (default true) for edge contracts

Backfill UX:

- Bulk-edit pricing for active accounts
- Coverage indicator:
  - numerator: active billable accounts with complete pricing
  - denominator: active billable accounts

### 5.2 Cross-Module Linking

Add `account_id` nullable FK to:

- `income_entries`
- `facturas`
- Stripe ledger tables (new in Phase 2)

Keep existing `customer_id` for migration compatibility.

### 5.3 SAT as Invoice Truth

- Keep SAT facturas module as invoiced truth
- Mark `finances/invoices` as legacy/read-only path
- Remove it from KPI calculations

### 5.4 Migration/Backfill

- Create schema migrations for new columns
- Backfill `account_id` where match can be inferred
- Unresolved mappings flagged explicitly (not silently guessed)

### 5.5 Phase 1 Tests

- Router tests for new pricing/account link fields
- Data consistency tests for Projected Revenue coverage
- Migration chain and backward compatibility checks

---

## Phase 2: Stripe Ingestion + Reconciliation Engine

### 6.1 Stripe Webhooks

Add secure webhook endpoint(s) for:

- `payment_intent.succeeded`
- `charge.refunded`
- `payout.paid`
- `payout.failed`

Requirements:

- Signature verification
- Idempotency keys
- Retry-safe writes

### 6.2 Ledger Tables (Recommended)

Introduce normalized Stripe ledger tables:

- `stripe_payment_events`
- `stripe_payout_events`
- Optional `stripe_balance_transactions` snapshot table

Link each row to:

- `account_id` when resolved
- else `unlinked=true` for cleanup queue

### 6.3 Reconciliation Jobs

- Nightly incremental reconciliation
- Manual full historical backfill endpoint
- Monthly reconciliation materialization (or computed view)

### 6.4 Manual Entries Policy Enforcement

Manual payments/deposits allowed with mandatory reason taxonomy:

- payment reasons: `offline_transfer`, `cash`, `adjustment`, `correction`
- deposit reasons: `manual_bank_deposit`, `adjustment`

Headline KPI logic excludes adjustment/correction buckets unless explicitly configured.

### 6.5 Phase 2 Tests

- Webhook signature + idempotency tests
- Duplicate event reprocessing tests
- Reconciliation parity tests (raw events vs KPI outputs)
- Unlinked bucket accounting tests

---

## Phase 3: Dashboard + Finances UX

### 7.1 Dashboard Top Control Row (New)

Add top-row cards:

1. Projected Revenue
2. Invoiced (SAT)
3. Payments Received
4. Bank Deposits
5. Gap to Collect
6. Gap to Deposit

All primary totals shown in MXN; detailed sections keep currency breakdown.

### 7.2 Keep Existing Cards

- Keep all current cards
- Reduce visual footprint (padding, typography scale, layout compaction)
- Preserve current links/flows

### 7.3 Coverage + Unlinked Visibility

- Coverage badge on Projected Revenue
- `Unlinked Revenue` badge/section until mapping is complete

### 7.4 Reconciliation Panel in Two Places

Add monthly reconciliation panel to:

1. Dashboard
2. Finances page

Panel sections:

- Projected Revenue
- Invoiced (SAT)
- Payments Received
- Bank Deposits
- Unlinked Revenue
- Manual Adjustments

### 7.5 Phase 3 Tests

- Dashboard API contract tests (new fields)
- Frontend rendering tests for new cards/panel
- Snapshot/interaction tests for compact layout

---

## Phase 4: Rollout, Safety, and Cleanup

1. Feature-flag KPI source switch (old vs new) if needed
2. Validate month parity with known finance samples
3. Enable Stripe realtime ingestion in production
4. Run historical backfill once
5. Resolve unlinked records to acceptable threshold
6. Announce new KPI definitions in internal runbook

---

## 8) API/Contract Changes (Planned)

1. Account APIs:
   - Add pricing fields to create/update/draft/approve payloads
2. Dashboard summary API:
   - Add new KPI fields + coverage fields + unlinked totals
3. Finances API:
   - Add reconciliation endpoint(s) by period
4. Stripe webhook endpoint:
   - Add authenticated webhook route with event ingestion status

---

## 9) Data Integrity Rules

1. No guessed account mapping for Stripe rows
2. Every ingestion event must be idempotent
3. KPI formulas are deterministic and period-bound
4. SAT invoiced KPI ignores drafts/cancelled
5. Legacy invoice module excluded from executive KPI totals

---

## 10) Execution Order (Next Actions)

1. Implement Phase 1 schema + APIs for account pricing and `account_id` links
2. Build pricing backfill UI + coverage indicator
3. Wire dashboard to new coverage signals
4. Proceed to Stripe ingestion and reconciliation engine

---

## 11) Out of Scope (Current Iteration)

1. Prorated Projected Revenue (day-level proration)
2. Automatic threshold alerting for gaps
3. Removing current dashboard cards

