# Company CRM Consolidation Implementation Plan

**Overall Progress:** `100%`

> **Implementation:** Use the `implement-plan` skill to execute this plan.

---

## Execution Context

**Execution repository:** `/Users/gustavozermeno/Code/eva-erp`
**Execution branch:** `feat/company-crm-consolidation`
**Role:** `worker + release integrator` for the ERP repo

| Field | Value |
|-------|-------|
| `repo_path` | `/Users/gustavozermeno/Code/eva-erp` |
| `branch` | `feat/company-crm-consolidation` |
| `backend_local_url` | `http://127.0.0.1:4010` |
| `frontend_local_url` | `http://localhost:3000` |
| `production_frontend` | `https://erp.goeva.ai` |

**ERP repo workflow note:** this repository does not currently include the main Eva `./eva` desk helper. Use `make`, `backend/alembic`, `pytest`, `npm`, `vercel`, `koyeb`, `supabase`, `gh`, and direct `codex exec` review commands from this repo.

**Owns (source of truth):** `Empresas` becomes the source of truth for company CRM, prospect/customer lifecycle, follow-up calendar, and linked Eva account operations.

**Depends on (merge order):** no other active plan. Preserve existing unrelated edits in `backend/.env.example` and `docs/plan-infrastructure-monitoring.md`.

**Touches (files/areas):**
- Backend:
  - `backend/src/empresas/models.py`
  - `backend/src/empresas/schemas.py`
  - `backend/src/empresas/router.py`
  - `backend/src/eva_platform/router/accounts.py`
  - `backend/src/eva_platform/schemas.py`
  - `backend/src/main.py`
  - `backend/src/dashboard/router.py`
  - `backend/src/models/__init__.py`
  - new Alembic migration under `backend/alembic/versions/`
  - backend tests under `backend/tests/`
- Frontend:
  - `frontend/src/app/(app)/empresas/page.tsx`
  - `frontend/src/components/empresas/EmpresaCard.tsx`
  - `frontend/src/components/empresas/EmpresasKanban.tsx`
  - `frontend/src/lib/api/empresas.ts`
  - `frontend/src/lib/api/eva-platform.ts`
  - `frontend/src/lib/api/dashboard.ts`
  - `frontend/src/components/layout/sidebar.tsx`
  - `frontend/src/components/command-palette.tsx`
  - `frontend/src/app/(app)/layout.tsx`
  - `frontend/src/app/(app)/dashboard/page.tsx`
  - delete or redirect unused pages: `frontend/src/app/(app)/eva-customers/page.tsx`, `frontend/src/app/(app)/vault/page.tsx`, `frontend/src/app/(app)/okrs/page.tsx`, `frontend/src/app/(app)/assistant/page.tsx`
  - frontend tests under `frontend/src/app/(app)/empresas/` and `frontend/src/components/empresas/`
- Docs:
  - this plan
  - `docs/domains/crm/how-company-crm.md` after implementation

**Start-of-work guardrails:**
1. `git status --short` and preserve unrelated changes.
2. Confirm branch is `feat/company-crm-consolidation`.
3. Run one plan review from repo root with `codex exec` using the review-plan prompt.
4. Before implementation, announce touches and classify unrelated changes as Green/Yellow/Red.

---

## Requirements Extraction

### Original Request

> "I want you to analyze the EVA ERP and look at the company section on the sidebar. You can see a company section. There is also then a section that says EVA customers. Those two sections will be the same section, and the section that should be the baseline right now should be the company section in the growth section that contains the cards of each of the companies and their plan and all of that. but i think that all of those you know all of those companies should be linked to a neva account but they are not seeing a link to an eva account right now which is incorrect then we should delete the customer section so everything is in the in the company section then I will also want you to delete the strategy section and everything related to that section. Yes, that's what I wanted to do. then also the vault section. z we should simplify all of these sections of the ERP that are not used at all. I want you to look for the evaERP codebase which is inside the code directory and then analyze it and let's discuss all of this."

### Additional Requirements

- Companies should exist before there is an Eva account.
- The user and co-founder are sending many text messages to companies and need a CRM to track outreach.
- Company cards need company-scoped to-dos, notes, visits, follow-ups, and reminders.
- To-dos can have dates.
- Some dated to-dos are events, such as visiting an office.
- There should be a calendar view in the ERP showing what must be done for each company.
- The company section should provide a `Create account` action when the company is ready to become an Eva account.
- Existing Eva accounts must be linked to current companies/customers.
- Delete everything related to the sections the user wants deleted: separate Eva Customers, Strategy, OKRs, Eva AI, and Vault.
- Run one plan review before implementing.
- Implement the whole plan.
- Run backend/frontend verification, cross-model review, production deployment, production health checks, migration verification, and production database checks.

### Decisions Made During Planning

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary UX | `Empresas` is the single hub | It already has cards, pipeline, billing fields, and `eva_account_id`. |
| Company vs account | Company can be unlinked; Eva account is optional until created/linked | Matches outbound sales workflow where many companies are prospects. |
| Follow-up storage | Extend `empresa_items` instead of using global `tasks` | Follow-ups are company-scoped CRM items, not generic Kanban work. Existing `empresa_items` already belongs to Empresas. |
| Calendar | Add a Companies calendar tab/view, not a standalone calendar module | Keeps the ERP simple and focused on company follow-ups. |
| Account creation | Add Empresa-scoped account provisioning endpoints/actions | Ensures new accounts automatically write `Empresa.eva_account_id`. |
| Existing account linking | Add a deterministic backfill/auto-match utility and manual review path | Current lazy exact-name match is too weak and one-time only. |
| Deleted modules | Remove from navigation, command palette, page metadata, dashboard links, mounted backend routers, and frontend pages/APIs | User explicitly requested deleting everything related to unused sections. |
| Historical data | Do not drop production database tables for Vault/OKRs/Assistant in this plan | Avoid destructive data loss; unmount routes and delete app surface. A separate confirmed data-drop migration can follow. |

### User Preferences

- Simplify the ERP aggressively.
- Prefer the Companies section as the baseline UX.
- Track real-world outbound sales work: texts, calls, visits, demos, follow-ups.
- Do not leave duplicate customer/account sections.
- Verify production autonomously.

---

## Intended Outcome

The ERP opens with a simpler navigation. There is one company CRM surface at `/empresas`. A company can be a prospect, interested lead, demo, negotiation, implementation, operative customer, churn risk, or inactive company. Each company card shows account link state, plan/billing information when linked, pending follow-ups, and the next dated action. Users can add outreach notes, to-dos, and calendar events directly on a company, then use a calendar view to see what to do on each day. When a company is ready, users can create or link an Eva account from the company detail flow, and the relationship is stored automatically.

---

## Success Bar

- Sidebar no longer shows `Eva Customers`, `Strategy`, `OKRs`, `Eva AI`, or `Vault`.
- Command palette and dashboard no longer route to deleted modules.
- `/empresas` supports cards, pipeline, and calendar views.
- Company cards visibly show linked Eva account name or a clear unlinked state.
- Company detail supports adding/editing/completing dated CRM items.
- Calendar view shows company todos/events by date and opens the related company.
- Existing Eva accounts are linked to matching Empresas where deterministic.
- Creating an Eva account from an Empresa automatically sets `empresa.eva_account_id`.
- Approving an account draft with `empresa_id` automatically sets `empresa.eva_account_id`.
- Deleted frontend pages do not remain reachable as active app modules.
- Unused backend routers for Vault/OKRs/Assistant are unmounted from `backend/src/main.py`.
- Automated backend and frontend tests pass.
- Production migrations run.
- Production `/empresas` verifies account links and calendar UI.

---

## Evidence Required Before Completion

- `python -m pytest backend/tests` passes or a documented equivalent targeted+full backend test command passes.
- `cd frontend && npm run lint` passes.
- `cd frontend && npm test` passes.
- `cd frontend && npm run build` passes.
- One Codex code review and one cross-model review run after implementation; P0/P1 findings fixed.
- Browser verification covers:
  - `/empresas` cards
  - create/edit company follow-up item
  - calendar view
  - create/link account action availability
  - removed nav items absent
  - deleted/removed module routes not exposed in sidebar/command palette
- Production database check confirms:
  - `empresa_items` has new CRM fields
  - at least deterministic account-link backfill ran
  - no duplicate non-null `empresas.eva_account_id`
- Production health check confirms backend readiness and frontend deployment.

### Evidence Collected Before Ship

- Plan review: one Codex plan-review round completed; findings were incorporated before implementation.
- Backend: `cd backend && PYTHONPATH=. venv/bin/pytest -q` passed with `335 passed`.
- Frontend tests: `cd frontend && npm test` passed with `33 passed`.
- Frontend lint: `cd frontend && npm run lint` passed with warnings only.
- Frontend build: `cd frontend && npm run build` passed.
- Alembic: `cd backend && PYTHONPATH=. venv/bin/alembic heads` reports single head `z5a6b7c8d9e0`.
- Code review: final Codex review returned no P0/P1 findings.
- Cross-model review: final Claude review returned no P0/P1 findings.
- Production backend: Koyeb deployment `f988d3c3-d934-43f2-ae05-e73943a0eddf` is healthy on commit `08d1cec`.
- Production migrations: GitHub post-deploy workflow completed successfully; `alembic current -v` reports `z5a6b7c8d9e0 (head)`.
- Production frontend: Vercel deployment `dpl_FhXKpMBjwawTyJpgrE3xMxszUWeh` is ready and aliased to `https://erp.goeva.ai`.
- Production database: `empresa_items` has all new CRM fields; duplicate non-null `empresas.eva_account_id` count is `0`; linked Empresas count is `8`; auto-match attempted count is `27`.
- Production browser verification: `/empresas` authenticated UI loads; sidebar has no Eva Customers, Strategy, OKRs, Eva AI, or Vault links; cards show linked/unlinked Eva states; calendar view loads; accounts view loads; `/eva-customers` redirects into Empresas; `/vault`, `/okrs`, and `/assistant` return `404`; backend `/api/v1/vault`, `/api/v1/okrs`, and `/api/v1/assistant` return `404`.

---

## Features

1. **Navigation cleanup** — Remove separate `Eva Customers`, `Strategy`, `OKRs`, `Eva AI`, and `Vault` app surfaces.
2. **Company CRM item model** — Extend `empresa_items` with CRM item kind, description, due/start/end/reminder timestamps, assignee, contact method, and completion timestamp.
3. **Company item APIs** — Support create, update, complete, delete, list by company, and calendar query.
4. **Company calendar view** — Add a Calendar tab to `/empresas` that shows dated follow-ups/events.
5. **Company card next-action summary** — Show next dated pending follow-up/event and overdue count on cards/Kanban cards.
6. **Outreach logging** — Allow adding notes/outreach entries such as SMS, WhatsApp, call, email, visit, demo, and meeting.
7. **Account actions in Empresa** — Add create-account/link-existing/resend-onboarding/impersonate/price/billing actions from company detail.
8. **Existing account backfill** — Add deterministic link utility and API/admin endpoint or migration-safe service to link current Eva accounts to Empresas.
9. **Provisioning link integrity** — Update account create and draft approval flows so `empresa_id` leads to `empresa.eva_account_id`.
10. **Docs and tests** — Add regression tests and shipped behavior docs.

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Company has no Eva account | Card shows unlinked state and offers `Create account` / `Link existing`. |
| Company already linked | Create account action is disabled/hidden; billing/account actions are shown. |
| Selected Eva account is already linked to another company | Backend returns 409 and UI shows a clear duplicate-link message. |
| Account create succeeds but local company link fails | Backend returns a failure requiring manual resolution; no silent success toast. |
| Draft approval has `empresa_id` | New account id is written into that Empresa before success response. |
| Draft approval has no `empresa_id` | Existing behavior continues without company link. |
| Multiple Empresas match one Eva account | Do not auto-link; report as ambiguous/manual-review. |
| Multiple Eva accounts match one Empresa | Do not auto-link; report as ambiguous/manual-review. |
| Follow-up has only `due_at` | Calendar renders it as an all-day/timed due item depending on timestamp. |
| Event has `start_at` and `end_at` | Calendar renders it as an event block. |
| Event has `end_at` before `start_at` | Backend rejects with 422. |
| Reminder is after due/start time | Backend rejects with 422. |
| Completing an item twice | Idempotent success; `completed_at` remains set. |
| Deleted sections have old URLs bookmarked | They should not appear in nav; direct routes should return 404 or redirect to `/empresas` when preserving user intent helps. |
| Production Eva DB unavailable | Company list still loads, linked-account health shows unknown, account linking/provisioning actions show unavailable error. |

---

## Error Handling

| Error Condition | User-Facing Behavior | Technical Response |
|-----------------|---------------------|-------------------|
| Duplicate Eva account link | "Esa cuenta de Eva ya está vinculada a otra empresa." | `409` with `reason: already_linked`. |
| Eva DB unavailable during account list/link | "No se pudo cargar cuentas de Eva." | `503` or empty picker only for read-only dropdown fallback. |
| Provisioning service unavailable | Existing detailed provisioning error is preserved. | Map Supabase/Eva errors to existing structured errors. |
| Invalid item datetime | Inline form validation plus toast. | `422` from schema validator. |
| Missing item title | Inline form validation. | `422`. |
| Deleted module API called | Not mounted. | `404`. |

---

## UI/UX Details

- `/empresas` top segmented control: `Tarjetas`, `Pipeline`, `Calendario`.
- Company card shows:
  - name/logo
  - lifecycle stage
  - Eva account link name or unlinked state
  - plan/subscription status when linked
  - next action date
  - overdue count if any
  - quick add follow-up button
- Company detail modal/sheet includes:
  - company fields
  - account panel
  - CRM timeline
  - add item form with kind/contact method/date/reminder/assignee
  - pending items list
- Calendar view:
  - month-style grid plus agenda list for selected day
  - overdue strip
  - item click opens company detail
  - no decorative marketing layout

---

## Business Rules

- `Empresa.eva_account_id` remains unique when non-null.
- Account creation from company requires company id and refuses if already linked.
- Account create/link/draft approval all use one backend linking helper so duplicate checks, local cache sync, and error handling stay consistent.
- Draft approval must link to company when `draft.empresa_id` is set.
- Operativo lifecycle rule still requires linked active subscription unless grandfathered.
- Linking an existing Eva account must copy local account cache fields where available (`subscription_status`, `stripe_customer_id`, `stripe_subscription_id`, `current_period_end`, plan/pricing fields as applicable). If the linked account is not active, the company can be linked but cannot be moved to `operativo` unless grandfathered.
- Dated follow-up items are open until explicitly completed.
- `kind=event` should have `start_at`; `kind=todo` should have at least `due_at` when it must appear on calendar.
- Calendar endpoint only returns incomplete items by default, with an option to include completed history.

---

## Out of Scope

- Dropping production database tables for Vault/OKRs/Assistant — destructive data deletion requires separate explicit confirmation.
- Full Google Calendar integration — this plan creates an ERP-native CRM calendar first.
- SMS sending from ERP — this plan tracks outreach; it does not send outbound messages.
- A standalone generic calendar module — calendar is scoped to company CRM items.
- Rebuilding global Tasks — company follow-ups use `empresa_items`.

---

## Technical Details

### Backend Data Model

Extend `EmpresaItem`:

```python
kind: str  # todo | event | note | outreach
description: str | None
contact_method: str | None  # sms | whatsapp | call | email | visit | meeting | demo | other
due_at: datetime | None
start_at: datetime | None
end_at: datetime | None
reminder_at: datetime | None
assigned_to: uuid.UUID | None
completed_at: datetime | None
```

Keep existing `done` for compatibility. Treat `done=True` as complete and keep it in sync with `completed_at`.

### Backend API

- `GET /api/v1/empresas` includes next action and overdue counts.
- `GET /api/v1/empresas/calendar?start=YYYY-MM-DD&end=YYYY-MM-DD&include_completed=false`
- `POST /api/v1/empresas/{empresa_id}/items`
- `PATCH /api/v1/empresas/items/{item_id}`
- `PATCH /api/v1/empresas/items/{item_id}/toggle`
- `POST /api/v1/empresas/{empresa_id}/eva-account`
- `POST /api/v1/empresas/{empresa_id}/link-eva-account`
- existing `POST /api/v1/eva-platform/drafts/{id}/approve` links `draft.empresa_id`.

**Route-order requirement from plan review:** static Empresas routes such as `/calendar` must be registered before `/{empresa_id}` in `backend/src/empresas/router.py`, otherwise FastAPI will parse `calendar` as the UUID path parameter and return 422. Add a route-order regression test.

**List-contract requirement from plan review:** `GET /empresas` must return every field required by `frontend/src/lib/api/empresas.ts::EmpresaListItem`, including `lifecycle_stage`, `billing_interval`, `expected_close_date`, `cancellation_scheduled_at`, `grandfathered`, and `version`, plus new next-action fields.

**Account-linking requirement from plan review:** preflight local Empresa state before creating Supabase/Eva account records. Direct account creation must receive the ERP DB session when `empresa_id` is present, validate Empresa exists/unlinked, then provision, then link/update local cache. Draft approval must do the same when `draft.empresa_id` exists.

**Timeline requirement from plan review:** existing `empresa_interactions` are preserved as read-only historical timeline entries in the UI/API. New outreach/follow-up work is stored in enhanced `empresa_items`; no destructive migration of interactions is performed in this plan.

### Frontend API

Update `frontend/src/lib/api/empresas.ts` types and methods for CRM items, calendar items, account creation/linking, and item date fields.

### Deleted Module Cleanup

Frontend:
- Remove nav entries in `Sidebar`.
- Remove command palette entries.
- Remove page titles for deleted routes.
- Remove dashboard sections and links for deleted modules.
- Delete unused API modules/types where no longer referenced.

Backend:
- Stop including `vault_router`, `okrs_router`, and `assistant_router` in `backend/src/main.py`.
- Stop dashboard querying `Credential`/vault costs.
- Keep model imports only if Alembic needs them for existing tables; otherwise remove safely.

---

## Tasks

### Phase 0: Plan Review

- [x] 🟩 Run one plan review from `/Users/gustavozermeno/Code/eva-erp`.
- [x] 🟩 Apply P0/P1 plan fixes before implementation.

### Phase 1: Backend CRM Items

- [x] 🟩 Add Alembic migration for expanded `empresa_items`.
- [x] 🟩 Update `EmpresaItem` model.
- [x] 🟩 Update schemas with validators.
- [x] 🟩 Update item create/update/toggle endpoints.
- [x] 🟩 Add calendar endpoint.
- [x] 🟩 Register static `/empresas/calendar` before `/{empresa_id}` and add route-order regression test.
- [x] 🟩 Add list summary fields for next action and overdue count.
- [x] 🟩 Fix and test the full `GET /empresas` list contract required by the frontend type.
- [x] 🟩 Add backend tests for item validation, completion, and calendar query.

### Phase 2: Account Linking and Provisioning

- [x] 🟩 Add Empresa-scoped create account endpoint.
- [x] 🟩 Add Empresa-scoped link existing endpoint.
- [x] 🟩 Update direct account create schema/router to accept optional `empresa_id`.
- [x] 🟩 Update draft approval to set `Empresa.eva_account_id` when `draft.empresa_id` exists.
- [x] 🟩 Extract shared account-link helper used by create, link-existing, and draft approval.
- [x] 🟩 Sync local Empresa billing/account cache when linking an existing Eva account.
- [x] 🟩 Add deterministic account-link backfill service/command or endpoint.
- [x] 🟩 Add backend tests for duplicate links, create account preflight ordering, draft approval linking, local-link failure, subscription cache sync, and ambiguous backfill.

### Phase 3: Frontend Company CRM

- [x] 🟩 Update Empresas types/API.
- [x] 🟩 Add `Calendario` view.
- [x] 🟩 Add company CRM item forms and timeline/list.
- [x] 🟩 Include read-only `empresa_interactions` history in the company timeline beside new CRM items.
- [x] 🟩 Add next action/overdue indicators to card and Kanban card.
- [x] 🟩 Add account panel/actions inside company detail.
- [x] 🟩 Add frontend tests for linked/unlinked cards, item creation, calendar rendering, and account action visibility.

### Phase 4: Delete Unused Sections

- [x] 🟩 Remove `Eva Customers`, `Strategy`, `OKRs`, `Eva AI`, and `Vault` from sidebar.
- [x] 🟩 Remove stale command palette entries including `/customers`.
- [x] 🟩 Remove page metadata for deleted routes.
- [x] 🟩 Remove dashboard links/cards for deleted modules.
- [x] 🟩 Update `frontend/src/lib/api/dashboard.ts` and all `DashboardData` consumers after removing Vault dashboard fields.
- [x] 🟩 Delete or redirect deleted frontend pages.
- [x] 🟩 Unmount backend Vault/OKRs/Assistant routers.
- [x] 🟩 Remove unused imports/types/API files where safe.
- [x] 🟩 Add tests/assertions that deleted nav entries are absent.
- [x] 🟩 Add backend tests that `/api/v1/vault`, `/api/v1/okrs`, and `/api/v1/assistant` are no longer mounted.

### Phase 5: Docs

- [x] 🟩 Add `docs/domains/crm/how-company-crm.md`.
- [x] 🟩 Document account-linking and calendar behavior.
- [x] 🟩 Update this plan with final verification evidence.

### Phase 6: Verification

- [x] 🟩 Run backend tests.
- [x] 🟩 Run frontend lint/tests/build.
- [ ] 🟥 Run Codex code review.
- [ ] 🟥 Run cross-model review.
- [ ] 🟥 Run browser verification locally.
- [ ] 🟥 Fix findings and repeat gates until clean.

### Phase 7: Production Ship

- [ ] 🟥 Commit only relevant files.
- [ ] 🟥 Push `feat/company-crm-consolidation`.
- [ ] 🟥 Merge to `main`/production branch after checks.
- [ ] 🟥 Verify migrations in production.
- [ ] 🟥 Query production DB for schema/link integrity.
- [ ] 🟥 Verify production `/empresas` in browser.
- [ ] 🟥 Verify deleted nav sections are absent in production.

---

## Test Plan

### Backend

- `cd backend && python -m pytest tests/test_empresa_pipeline_schemas.py tests/test_empresa_channel_health.py tests/test_company_crm_items.py tests/test_eva_platform_account_linking.py`
- `cd backend && python -m pytest tests/test_company_crm_items.py tests/test_eva_platform_account_linking.py tests/test_removed_modules.py`
- `cd backend && python -m pytest tests`

### Frontend

- `cd frontend && npm run lint`
- `cd frontend && npm test -- src/app/(app)/empresas/page.test.tsx src/components/empresas/EmpresaCard.test.tsx`
- `cd frontend && npm test`
- `cd frontend && npm run build`

### Browser

- Start backend and frontend with `make dev-backend` and `make dev-frontend`.
- Open `http://localhost:3000/empresas`.
- Verify cards, pipeline, calendar, item create/complete, account panel, and removed navigation.

---

## Production Verification Plan

- Confirm deploy target and production branch.
- Run migrations against production through the configured deployment path.
- Use Koyeb CLI for backend deployment/log checks.
- Use Vercel CLI or GitHub deployment status for frontend.
- Query production database:
  - `SELECT column_name FROM information_schema.columns WHERE table_name='empresa_items';`
  - `SELECT eva_account_id, count(*) FROM empresas WHERE eva_account_id IS NOT NULL GROUP BY eva_account_id HAVING count(*) > 1;`
  - sample Empresas with linked account names through ERP/Eva DB join-equivalent manual queries.
- Browser verify `https://erp.goeva.ai/empresas`.

---

## Generalization Check

This design works for any company relationship: prospect, customer, partner lead, law firm, car dealership, real estate office, or healthcare clinic. It avoids hardcoding industry-specific fields. Outreach methods are generic. Calendar items are company-scoped, not industry-scoped.

---

## Notes

- Existing unrelated local changes:
  - `backend/.env.example`
  - `docs/plan-infrastructure-monitoring.md`
  These must not be reverted or included unless explicitly adopted.
- The current `EmpresaItem` model is too small (`title`, `done`). This plan intentionally restores dated CRM capabilities in a more focused form.
- The old `customers` table still exists for finances/facturas. This plan does not delete it until downstream financial dependencies are safely migrated.
