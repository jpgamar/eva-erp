# Company CRM Consolidation Plan

**Overall Progress:** `0%`

> **Status:** Not implemented. This is a handoff plan for the next agent.

---

## Execution Context

**Repository:** `/Users/gustavozermeno/Code/eva-erp`

**Goal:** Make `Empresas` the single CRM/account hub in the ERP, remove unused ERP sections, and add company follow-up/calendar/account-linking workflows.

**Do not assume any implementation is complete.** The previous implementation was reverted by request.

---

## Scope

### Keep

- `Empresas` as the main company CRM section.
- Existing billing, invoices, finances, tasks, infrastructure, monitoring, partners, team, and settings unless directly affected.
- Existing database tables for removed modules unless the user explicitly approves destructive table drops.

### Remove From Product Surface

- Separate `Eva Customers` section.
- Strategy / OKRs section.
- Eva AI / Assistant section.
- Vault section.
- Meetings section.
- Documents section.

Removal means:

- no sidebar item
- no command palette item
- no dashboard card/link
- no app page
- no frontend API helper
- no backend router mounted
- tests proving removed routes are not active

Historical Alembic migration files should not be rewritten. Existing historical tables can remain unless there is a separate explicit data-drop plan.

---

## Desired Product Behavior

`/empresas` should be the single place to manage companies, outreach, follow-ups, account state, and Eva account operations.

Companies can exist without an Eva account. This supports outbound sales where the team texts or contacts many companies before they become customers.

Each company should support:

- company card
- linked Eva account state
- plan/subscription/billing summary when linked
- unlinked state when no account exists
- create Eva account action
- link existing Eva account action
- company todos/follow-ups
- dated reminders
- office visits or meetings as company events
- outreach notes such as SMS, WhatsApp, call, email, visit, demo, or meeting
- calendar view for company follow-ups/events

---

## Backend Plan

1. Extend `empresa_items` for CRM follow-ups:
   - `kind`: `todo`, `event`, `note`, `outreach`
   - `description`
   - `contact_method`
   - `due_at`
   - `start_at`
   - `end_at`
   - `reminder_at`
   - `assigned_to`
   - `completed_at`

2. Add or update schemas for:
   - company item create/update/response
   - company calendar item response
   - Eva account link request
   - create Eva account from company request
   - company outreach/interaction response if needed

3. Add Empresa APIs:
   - list companies with linked account summary and next action
   - create/update/delete company follow-up item
   - complete/toggle item
   - calendar query by date range
   - link existing Eva account
   - create Eva account for company
   - deterministic auto-match or admin backfill for existing accounts

4. Update Eva account provisioning:
   - account creation with `empresa_id` links the Empresa before success
   - draft approval with `empresa_id` links the Empresa before success
   - duplicate account links return 409
   - deactivation of a linked Eva account must not strand an Empresa link
   - creating a fresh Eva account for an already `operativo` Empresa must not create external side effects before failing business rules

5. Unmount/remove backend routers for removed sections:
   - Vault
   - OKRs
   - Assistant
   - Meetings
   - Documents

6. Remove deleted-module metrics from dashboard contracts where the UI no longer uses them.

---

## Frontend Plan

1. Sidebar:
   - remove `Eva Customers`
   - remove Strategy/OKRs/Eva AI/Vault if present
   - remove `Meetings`
   - remove `Documents`

2. Command palette:
   - remove all deleted sections and routes.

3. Dashboard:
   - remove dashboard cards/links for deleted sections.
   - redirect account/customer cards into `/empresas` or `/empresas?view=accounts`.

4. Empresas page:
   - preserve cards and pipeline
   - add calendar view
   - add accounts view or account panel inside Empresas
   - show linked/unlinked Eva account state
   - show next action and overdue count
   - support adding dated follow-ups/events
   - expose create/link account actions from company detail

5. Delete frontend pages/API helpers for removed modules:
   - `eva-customers` page should either be removed or redirect to `/empresas?view=accounts`
   - `vault`
   - `okrs`
   - `assistant`
   - `meetings`
   - `documents`

---

## Tests Required

Backend:

- removed routers are not mounted
- dashboard contract no longer exposes removed unused metrics
- company item schema validates dates and blank titles
- calendar route is registered before dynamic `/{empresa_id}` route
- account linking syncs Empresa cache/history/version
- stale account cache is cleared when linking a new account
- linked account deactivation is blocked
- new-account provisioning for invalid `operativo` Empresa fails before Supabase side effects

Frontend:

- sidebar no longer renders removed items
- command palette no longer routes to removed items
- Empresas card shows next action / unlinked state
- Empresas accounts view includes old Eva customer workflows
- removed pages are gone or redirect intentionally

---

## Verification Required Before Shipping

- backend tests pass
- frontend tests pass
- frontend lint passes
- frontend build passes
- one plan/code review pass before implementation
- final Codex review has no P0/P1 findings
- final cross-model review has no P0/P1 findings
- production migration reaches Alembic head
- production database check confirms new `empresa_items` fields
- production database check confirms no duplicate non-null `empresas.eva_account_id`
- production browser verification confirms:
  - `/empresas` loads authenticated
  - sidebar no longer shows deleted sections
  - cards show linked/unlinked account states
  - calendar view loads
  - accounts view/workflow lives under Empresas
  - removed routes return 404 or intentional redirect

---

## Important Notes For Next Agent

- Preserve unrelated local edits in:
  - `backend/.env.example`
  - `docs/plan-infrastructure-monitoring.md`
- Do not rewrite old Alembic migration history.
- Do not drop production tables without explicit user confirmation.
- If using a compatibility redirect for `/eva-customers`, keep it out of sidebar and command palette.
- Browser verification may require creating a temporary auth cookie from the live backend or using the user’s authenticated browser session.
