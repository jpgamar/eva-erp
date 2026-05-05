# Empresas UX Pass — Implementation Plan

**Overall Progress:** `100%` ✅ Shipped 2026-05-05

> **Status:** Shipped to production. Backend deployed via Koyeb (run 25391248015 SUCCESS, migrations applied, instance HEALTHY). Frontend deployed via Vercel (`eva-k6z2pvd00-evaai.vercel.app` Ready). Browser-verified on `https://erp.goeva.ai`: sidebar Tasks entry removed, 5 view tabs render, `/empresas?view=tasks` chips work, calendar renders 31 days for May 2026, `/tasks` redirects, ZERO console errors. Database verified at Alembic head `c8d9e0f1g2h3`.

---

## Execution Context

| Field | Value |
|-------|-------|
| Repository | `/Users/gustavozermeno/Code/eva-erp` |
| Branch | `feat/empresas-ux-pass` |
| Production frontend | `https://erp.goeva.ai` |
| Production backend | `https://erp.goeva.ai/api/v1` (Vercel rewrite to Koyeb) |
| Database | Supabase project `eva-erp` (`ispslnlufmlonvdjtkip`) |
| Migrations | `backend/alembic/versions/`, head currently `b8c9d0e1f2g3` |

**Start-of-work guardrails**

1. `git status` — preserve unrelated edits to `backend/.env.example`, `docs/plan-infrastructure-monitoring.md`, `supabase/.temp/`.
2. `git rev-parse --abbrev-ref HEAD` returns `feat/empresas-ux-pass`.
3. Backend tests baseline: `cd backend && python -m pytest tests/ --no-header -q` → 365 passing on `main`.
4. Frontend tests baseline: `cd frontend && npm test` → 41 passing on `main`.
5. The `eva-erp` repo does NOT have the `./eva` desk system — use plain `git`, `npm`, `pytest`, `codex exec` directly.

---

## Requirements Extraction

### Original Request (verbatim)

> "did you make the pipeline ui?? why is it so uglly!! extreamly ugly!! look at it!"
>
> "it can be improved signifidantly!! it can be made much much nicer!! additionally this section when i can add things for a company make it much nicer and the textbox should be bigger and better!! additionally, how can I add that in the pipeline section? I should be able to do it. you can see that there are companies linked to a Neva account, but how can I create its account there? I should be able to create its account there. think about more things that are missing. all should be the nicest and best possible!!"
>
> "Additionally, I was thinking about something different. Like all of those things that I put in a company, they're basically tasks, right? And then I also have a task section. I think that we should delete the manage section and all the code related to the task section and the tasks should be the things that we have to each of the companies. And then there should be like right now the discards pipeline calendar accounts. There should be also like tasks and there should appear the tasks of every company asks or what do you think? How do you think this should work? Do you think this is the best approach?"
>
> "ADDITIONALLY I ALSO WANT SOEMTHING ELSE: FOR THE CALENDAR EVENTS I WANT TO BE REMINDED 1 DAY AND 1 HOUR BEFORE THE EVENT!! EMAIL REMINDERS TO gus@goeva.ai PLZ!!"
>
> "additionally, make the interface for selecting the date and all that way nicer. Just like the one of the Eva repo you can look at it. Like this is super, super ugly!!"

### Decisions Made During Planning (from `/interview`)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Item create/edit UX | **Slide-over panel from right** (single component for create + edit) | Doesn't cover the kanban while logging; same UI handles both flows |
| Item edit pattern | **Click row → slide-over with prefilled data** (trash icon at top deletes; Mark done button completes) | One affordance for everything; fewer code paths |
| Calendar quick-create | **Click day cell → slide-over with date prefilled** (start_at = clicked day at 09:00 local) | Matches Linear/Cron expectations |
| Edit Empresa modal redesign | **Two-column denser layout + 4-row resizable nota textarea** | Fits more on screen, looks intentional, ships in same pass |
| Quick-log outreach | **Channel-shortcut row** on each card (💬 SMS / 🟢 WhatsApp / 📞 Call / ✉ Email / 🚗 Visit) | Two taps per logged interaction vs. six |
| Pipeline kanban add | **Per-card "+" button** (opens slide-over with that empresa prefilled) | Operator never leaves the board to log a follow-up |
| Create Eva account | **Inside edit modal → link picker has "+ Crear nueva cuenta de Eva" option** that expands inline mini-form | Single flow, no extra page jumps; backend `POST /empresas/{id}/eva-account` already exists |
| Other gaps | **All four (kind badges, filter chips, bulk-move, channel health badges everywhere) ship in this pass** | User explicit: "ALL!! IT SHOULD ALL BE PERFECT!!" |
| Internal/non-empresa tasks | **Allow `empresa_items.empresa_id = NULL`** | Unified data model; Tareas tab groups them under "Sin empresa (internas)" |
| Tareas tab default filter | **Mis pendientes abiertos** (`assigned_to=me AND done=false`) | Matches operator's primary "what should I do today" question |
| Tasks data migration | **Auto-migrate in same Alembic revision** (backfill 10 rows → empresa_items, drop tasks table) | Atomic, no manual data wrangling |
| Date/time picker | **shadcn `<Calendar>` + custom `<TimePicker>` pair**, wrapped in `<DateTimePicker>` | Clean, no heavy deps; pattern reusable across slide-over + Editar Empresa |
| Reminder recipient | **Hardcoded `gus@goeva.ai` via `EMPRESA_ITEM_REMINDER_EMAIL` env var** | Single recipient ships fast; per-assignee routing is a follow-up |
| Reminder dispatcher | **Async background loop in API process, every 5 min** (next to `monitoring_runner_loop` etc.) | No new infra, ±5 min slack acceptable for 24h and 1h reminders |
| Reminder storage | **Two new columns on `empresa_items`**: `reminder_24h_sent_at`, `reminder_1h_sent_at` | Idempotent, simpler than a separate reminders table |

---

## Intended Outcome

`/empresas` becomes a dense, high-information CRM hub where the operator can:

1. **Add a follow-up from anywhere** (kanban card, cards grid, calendar day, Tareas list) via a polished slide-over panel with proper title/kind/date/channel/assignee fields.
2. **Edit or complete an existing follow-up** by clicking it; the same slide-over opens prefilled.
3. **Log an outreach interaction in two taps** via channel shortcut buttons (💬🟢📞✉🚗) on each card.
4. **Create a new Eva account directly from the empresa edit modal** without leaving the page or clicking through to the legacy `/eva-customers` workflow.
5. **See all tasks across companies in one place** via a new "Tareas" tab — replacing the standalone `/tasks` section, which is removed.
6. **Pick dates with a nice calendar+time popover**, not the system-styled `<input type="datetime-local">`.
7. **Receive automatic email reminders** 24 hours and 1 hour before any item with a `start_at` (events).
8. **Bulk-move kanban cards** by selecting multiple and dragging them as a group.
9. **See linked-account names + channel-health dots** on every card view (kanban, cards, Cuentas).

---

## Success Bar

- All five views render under `/empresas` without errors: `?view=grid` (default), `?view=kanban`, `?view=calendar`, `?view=tasks`, `?view=accounts`.
- Slide-over panel handles create + edit + delete for items via the same component; works from kanban "+", cards "+", calendar day-click, Tareas row-click.
- `<DateTimePicker>` component is the only date/time control in the empresas surface. No `<input type="datetime-local">` remains in the empresa flows.
- `/tasks` redirects to `/empresas?view=tasks` (kept for bookmark compatibility — operator-friendly); `/api/v1/tasks/...` returns 404; sidebar "Tasks" entry is gone; command palette has no `/tasks` entry.
- The 10 prod tasks rows are migrated into `empresa_items` with `empresa_id=NULL`. The tasks table is dropped.
- A scheduled empresa-item event with `start_at = NOW() + 24h` triggers an email to `gus@goeva.ai` within 5 min of the T-24h boundary; same for T-1h.
- The empresa edit modal "Cuenta de Eva" picker offers "+ Crear nueva cuenta de Eva". Selecting it inline-creates the account and links it to the empresa in one save.
- Pipeline kanban: each card has a "+" button (opens slide-over) and a channel-shortcut row (💬🟢📞✉🚗). Cmd-click selects multiple cards; drag moves them all to the target stage.
- The Tareas tab default view shows items where `assigned_to = current user AND done = false`, grouped by empresa, with "Sin empresa" bucket at the top. Filter chips: Mis / Equipo / Vencidas / By kind work.
- Backend pytest passes (≥ 380 tests, no regressions from the 365 baseline).
- Frontend vitest passes (≥ 50 tests, no regressions from the 41 baseline).
- `npm run lint` returns 0 errors. `npm run build` succeeds.
- `codex exec` review of the diff returns `Summary verdict: PASS` with no P0/P1.
- Browser verification on `https://erp.goeva.ai` confirms every Phase-4 flow works.

---

## Evidence Required Before Completion

1. New Alembic head shipped to Koyeb (`alembic_version.version_num` = the new revision id).
2. Production query `SELECT COUNT(*) FROM tasks` fails with "relation does not exist" (table dropped).
3. Production query `SELECT COUNT(*) FROM empresa_items WHERE empresa_id IS NULL` ≥ 10 (tasks rows migrated).
4. Production query `SELECT column_name FROM information_schema.columns WHERE table_name='empresa_items' AND column_name IN ('reminder_24h_sent_at','reminder_1h_sent_at')` returns 2 rows.
5. SendGrid activity log shows reminder emails sent to `gus@goeva.ai` within 5 min of expected T-24h / T-1h windows for a test event scheduled during verification.
6. Browser verification (Phase 4) artifacts: ZERO console errors on `/empresas?view={grid,kanban,calendar,tasks,accounts}`.
7. Final codex review log shows `Summary verdict: PASS`.

---

## Features

> Every feature listed here MUST ship in this plan. Anything missing here is out of scope.

### Backend

1. **Alembic migration** chained after `b8c9d0e1f2g3`:
   - `ALTER TABLE empresa_items ALTER COLUMN empresa_id DROP NOT NULL` (allow internal tasks).
   - `ADD COLUMN reminder_24h_sent_at TIMESTAMPTZ NULL`.
   - `ADD COLUMN reminder_1h_sent_at TIMESTAMPTZ NULL`.
   - Backfill from `tasks`. Real `tasks` schema: `id, title, description, assignee_id, priority, due_date, labels, source_meeting_id, created_by, created_at, updated_at, status, board_id`. Mapping (idempotent, `ON CONFLICT (id) DO NOTHING`):
     - `id → id` (preserve UUID)
     - `title → title`
     - `description → description`
     - `due_date → due_at` (cast date to `(date::timestamp + interval '23 hours 59 minutes') AT TIME ZONE 'America/Mexico_City'`)
     - `status='done' → done = true`, `completed_at = updated_at` if done
     - `created_by → created_by`, `assignee_id → assigned_to`, timestamps preserved
     - `'todo' → kind` (constant)
     - **Lossy:** `priority`, `labels`, `source_meeting_id`, `board_id` are NOT migrated (no destination columns; documented in migration docstring + run-book).
     - **Comments:** if `task_comments` exists, prepend the latest comment text to `description` (idempotent: skip if already prefixed). Then `DROP TABLE task_comments CASCADE` BEFORE dropping `tasks`.
   - Past-event reminder sentinel: backfilled rows with `due_at < NOW()` get `reminder_24h_sent_at = NOW()` and `reminder_1h_sent_at = NOW()` so the dispatcher never matches them. Same rule applied in API on create/edit (see Feature 2 below).
   - `DROP TABLE task_comments CASCADE` (if exists), then `DROP TABLE tasks CASCADE`, then `DROP TABLE boards CASCADE` (if exists).
   - Idempotent helpers (`_table_exists`, `_column_exists`, `_constraint_exists`) so re-running on partial state is safe.

2. **`empresa_items` API surface extensions**:
   - `GET /empresas/items?assigned_to=me&done=false&kind=todo,event&overdue=true&empresa_id=...` — new list-across-empresas endpoint for the Tareas tab. Returns rows with `empresa` summary embedded (id, name, logo_url) via `LEFT JOIN` so internal items (`empresa_id IS NULL`) are included with `empresa: null`. Registered BEFORE `/empresas/{empresa_id}` to avoid shadowing.
   - `PATCH /empresas/items/{item_id}` — already exists. Augmented: when the PATCH changes `start_at` to a value in the past, automatically stamp `reminder_24h_sent_at` and `reminder_1h_sent_at` to NOW (no email is owed for a past event).
   - `DELETE /empresas/items/{item_id}` — already exists, no change needed.
   - `POST /empresas/items` (NEW) — create an item with explicit `empresa_id` (or NULL for internal). Today only `POST /empresas/{empresa_id}/items` exists, which can't create internal tasks. On create, if `start_at < NOW()` stamp both reminder-sent columns to NOW (same rule as PATCH).
   - `POST /empresas/bulk-stage` (NEW) — `{ moves: [{empresa_id, version}, ...], lifecycle_stage_to: ... }` for bulk kanban move. Atomic: any version conflict OR any close-date-required violation OR any active-subscription empresa with target=`inactivo` rejects the WHOLE batch with 409 / 400 listing the offending ids. Same business rules as the single-card path:
     - Target=`operativo` requires linked Eva account with active subscription (`OperativoRequiresActiveSubscription`).
     - Target ∈ `interesado/demo/negociacion` requires `expected_close_date` on every empresa in the batch.
     - Target=`inactivo` with any empresa in subscription_status `active`/`trialing` → 409 `BulkInactivoNeedsCancel` listing offending ids; UI surfaces them and asks the operator to drag those individually (which triggers the existing cancel-subscription dialog) before retrying the bulk move on the rest.

3. **Reminder dispatcher** (concurrency-safe via atomic claim):
   - New module `backend/src/empresas/reminders.py`:
     - `empresa_item_reminder_runner_loop(stop_event)` — async loop sleeping 300s between ticks (settings-overridable).
     - **Atomic claim pattern** to handle concurrent API instances + crashes:
       ```sql
       UPDATE empresa_items
          SET reminder_24h_sent_at = NOW()
        WHERE id IN (
          SELECT id FROM empresa_items
           WHERE done = false
             AND kind <> 'note'
             AND start_at IS NOT NULL
             AND reminder_24h_sent_at IS NULL
             AND start_at BETWEEN (NOW() + interval '23 hours 55 minutes')
                              AND (NOW() + interval '24 hours 5 minutes')
           FOR UPDATE SKIP LOCKED
           LIMIT 50
        )
       RETURNING id, empresa_id, title, description, start_at, assigned_to;
       ```
       This claims rows BEFORE sending so two API instances never email the same row. Same pattern for the 1h window.
     - For each claimed row, call `_send_item_reminder_email(item, kind="24h"|"1h")`. **If SendGrid send fails**, run a compensating `UPDATE empresa_items SET reminder_*_sent_at = NULL WHERE id = ...` so the next tick retries. (Acceptable trade-off: a process crash between claim and SendGrid call drops a single reminder; the 1h reminder still fires as a backup. Documented behavior.)
     - Recipient: `settings.empresa_item_reminder_email` (env: `EMPRESA_ITEM_REMINDER_EMAIL`, default `gus@goeva.ai`).
     - Subject: `Recordatorio: {item.title} (en {1 hora|24 horas})`.
     - Body: HTML + plaintext, includes empresa name (or "Tarea interna" if `empresa_id IS NULL`), start_at in operator's timezone (`America/Mexico_City`), deeplink to the item (`https://erp.goeva.ai/empresas?view=tasks#item-{id}`).
   - **Failure modes (concrete, matches monitoring-loop convention)**:
     - SendGrid 4xx (auth/permission) → log `ERROR` once per tick, do NOT exit the loop, continue.
     - SendGrid 429/5xx → retry once with 30s backoff inside the same tick. If still failing, run the compensating UPDATE to clear the claim; next tick retries.
     - DB connection lost → catch, log `WARNING`, sleep 60s, continue (same as `monitoring_runner_loop`).
     - Loop never exits on its own — only on `stop_event.set()` from FastAPI lifespan shutdown.
   - Wire the loop into `main.py` lifespan next to `monitoring_runner_loop` etc., gated by `settings.empresa_item_reminders_enabled` (default `True`).

4. **Settings additions** (`backend/src/common/config.py`):
   - `empresa_item_reminders_enabled: bool = True`.
   - `empresa_item_reminder_email: str = "gus@goeva.ai"`.
   - `empresa_item_reminder_loop_interval_seconds: int = 300`.

5. **Unmount `/api/v1/tasks` and `/api/v1/boards`**:
   - Remove `task_router` and `board_router` includes from `main.py`.
   - Delete `backend/src/tasks/` directory entirely (router, models, schemas).
   - Delete `backend/src/boards/` (if present) entirely.
   - Backend test: `tests/test_removed_modules.py` updated to assert `/api/v1/tasks` and `/api/v1/boards` no longer mount.

6. **Dashboard tasks fully migrated to `empresa_items`** (P1 from review #1):
   - `backend/src/dashboard/router.py` currently queries `Task` for THREE counts: `open_tasks`, `overdue_tasks`, `tasks_active` (lines 181-202). All three must move to `empresa_items`. The `from src.tasks.models import Task` import (line 34) must go.
   - **`open_tasks` count:** `SELECT COUNT(*) FROM empresa_items WHERE done = false AND kind <> 'note'` — total open, all assignees.
   - **`overdue_tasks` count:** `SELECT COUNT(*) FROM empresa_items WHERE done = false AND kind <> 'note' AND due_at IS NOT NULL AND due_at < NOW()`.
   - **`recent_tasks` list:** `SELECT * FROM empresa_items WHERE done = false AND kind <> 'note' ORDER BY COALESCE(due_at, start_at, created_at) ASC LIMIT 6`. Each row carries empresa name (LEFT JOIN). Frontend dashboard card renders empresa context inline.
   - Dashboard contract test: `tests/test_removed_modules.py::test_dashboard_response_omits_removed_metrics` extended to assert no `tasks_active` / `recent_tasks` regression after the swap.

### Frontend

7. **`<DateTimePicker>` component** at `frontend/src/components/ui/DateTimePicker.tsx`:
   - Trigger button shows formatted local datetime (e.g., `📅 14 may 2026, 09:00`).
   - Popover contains a `<Calendar>` (shadcn-recipe, `react-day-picker` based) and a `<TimePicker>` (custom: HH:MM in 15-min steps + scroll arrows + AM/PM toggle).
   - "Today" / "Clear" footer actions.
   - Locale = es-MX (`Spanish day labels: D L M M J V S`).
   - Returns ISO string OR `null`.
   - Shadcn install: `npx shadcn@latest add calendar` from the frontend directory adds `react-day-picker` + the Calendar primitive.

8. **`<ItemEditorPanel>` slide-over** at `frontend/src/components/empresas/ItemEditorPanel.tsx`:
   - Right-side fixed panel, 384px wide (max), slides in/out via Tailwind transition.
   - Modes: `create` (no item id), `edit` (item id provided).
   - Fields: `title` (required, autofocus), `kind` (pill row: Pendiente / Evento / Outreach / Nota), `start_at` (DateTimePicker, required when kind=event), `due_at` (DateTimePicker, optional for todo/outreach), `end_at` (DateTimePicker, only for kind=event), `contact_method` (select, only for kind=outreach/event), `assigned_to` (user picker), `description` (textarea, 4 rows resizable), `empresa_id` (autocomplete, optional — for internal tasks).
   - Actions: Save (primary), Cancel, "Marcar como hecho" (only in edit mode), Delete (trash icon top-right, with confirm).
   - Surfaces backend validation errors inline (EventDateRequired, InvalidDateWindow).
   - Used by: kanban "+" button, cards-grid "+", calendar day-click, Tareas row-click, EmpresaCard channel-shortcut row.

9. **Channel-shortcut row** on `EmpresaCard`:
   - Footer chip row: 💬 SMS / 🟢 WhatsApp / 📞 Call / ✉ Email / 🚗 Visit.
   - Click an icon → opens `ItemEditorPanel` in create mode with `kind=outreach`, `contact_method=<that channel>`, `start_at = now`, focus on title input.

10. **Kanban per-card "+" button**:
    - Small `+` icon-button bottom-right of each card.
    - Click → opens `ItemEditorPanel` in create mode with that empresa prefilled.

11. **Kanban bulk-select + bulk-move**:
    - Cmd/Ctrl-click on a card toggles selection (visual ring around card).
    - When ≥1 card selected, dragging any selected card moves the whole group.
    - Persisted via `POST /empresas/bulk-stage`.
    - Selection cleared on mouse-up after drop or Esc.

12. **Visual kind badges on existing items**:
    - Item rows show a small icon + color per `kind`: ☐ Todo (slate), 📅 Event (sky), 🟣 Note (violet), 💬 Outreach (emerald, with channel icon if set).
    - Card pending-items list uses the same badges.

13. **Calendar view click-day quick-create**:
    - In `EmpresasCalendarView`, an empty area of any day cell is clickable.
    - Click → opens `ItemEditorPanel` in create mode with `kind=event`, `start_at = clicked day at 09:00 local`, no empresa preselected (operator picks via empresa autocomplete).
    - Existing calendar items are also clickable → opens `ItemEditorPanel` in edit mode.

14. **Tareas tab** (5th view on `/empresas`):
    - Tab order: Tarjetas / Pipeline / Calendario / Tareas / Cuentas.
    - URL: `/empresas?view=tasks`.
    - Default filter: `assigned_to = current user AND done = false`.
    - Filter chips at top: Mis / Equipo / Vencidas / Todos / + kind chips (Pendiente / Evento / Outreach / Nota).
    - List grouped by empresa, "Sin empresa (internas)" bucket at the top, then empresas alphabetical.
    - Each row: checkbox (toggle done) + kind badge + title + due/start date + empresa name (clickable → open empresa edit modal) + assignee avatar + "⋯" menu (Editar / Eliminar).
    - Click row body → opens `ItemEditorPanel` in edit mode.

15. **Edit Empresa modal redesign**:
    - Two-column body grid (`grid-cols-2 gap-4`).
    - Left column: Logo + Nombre (full-width row), Status + Lifecycle stage (2-col within), Responsable + Cuenta de Eva (2-col within).
    - Right column: Monto base + Día de pago (2-col), Último pago + Próx. factura (2-col), Nota de seguimiento (4-row resizable textarea spans both right cells).
    - "Datos fiscales y contacto" stays as a collapsible section spanning both columns at the bottom.
    - Cancel / Guardar buttons stay bottom-right.

16. **"Crear nueva cuenta de Eva" inline option**:
    - In the EvaAccount picker inside the edit modal, add a top item: `+ Crear nueva cuenta de Eva`.
    - Selecting it switches the picker into a mini-form: owner email (required), owner name, plan_tier (Standard/Pro), billing_cycle (Monthly/Annual), facturapi_org_api_key (optional).
    - On Guardar: calls `POST /empresas/{id}/eva-account` with the inline form values, surfaces SuccessToast, closes the modal, refreshes the list.
    - Surfaces `OperativoRequiresExistingSubscription` and other backend rejection reasons.

17. **Cuentas view: per-empresa "Crear cuenta" CTA**:
    - In `EmpresasAccountsView`, the "Empresas vinculadas" list — for empresas with `eva_account_id = null` (which currently land in "Cuentas Eva sin empresa" or are missing entirely), surface a "+ Crear cuenta" button on the row.
    - Click → opens the same inline-create flow as #16.

18. **Channel health badges everywhere**:
    - `EmpresaCard` already has `health.linked_account_name` text. Add the per-channel dots (Messenger 🟢, Instagram 🟢, WhatsApp 🟢) underneath when `eva_account_id` is set, mirroring the older grid card.

19. **Sidebar removal**:
    - Remove "Tasks" sidebar entry (`frontend/src/components/layout/sidebar.tsx`).

20. **Command palette removal**:
    - Remove "Tasks" command palette entry (`frontend/src/components/command-palette.tsx`).

21. **Dashboard tasks card switch**:
    - The dashboard "Tasks" card reads `data.recent_tasks` (already wired to backend). The card link target switches from `/tasks` to `/empresas?view=tasks`.

22. **Frontend API helpers**:
    - `empresasApi.listAllItems(filters)` → `GET /empresas/items` (Tareas tab feed). Each row shape allows `empresa_id: string | null` and an embedded `empresa: { id, name, logo_url } | null`.
    - `empresasApi.createInternalItem(payload)` → `POST /empresas/items` (top-level create, supports `empresa_id: null`).
    - `empresasApi.bulkStage({ moves, lifecycle_stage_to })` → `POST /empresas/bulk-stage` where `moves` is `[{empresa_id, version}]`. Returns 200 on success or 4xx with `{conflicts: [...], reason: ...}`.
    - `empresasApi.createEvaAccountForEmpresa(empresaId, payload)` already exists — reuse from inline flow.

23. **Type updates (P1 from review #1: nullable `empresa_id` end-to-end)**:
    - `EmpresaItem.empresa_id`: `string | null`.
    - `EmpresaCalendarItem.empresa_id`: `string | null`, `empresa_name: string | null`.
    - `PendingItem` (already nullable-friendly via optional fields).
    - SQLAlchemy `EmpresaItem.empresa_id` typed as `Mapped[uuid.UUID | None]`.
    - All Pydantic response models (`EmpresaItemResponse`, `EmpresaCalendarItemResponse`) accept `empresa_id: uuid.UUID | None = None`.

### Removed (this pass)

- `/tasks` page (`frontend/src/app/(app)/tasks/`).
- `frontend/src/lib/api/tasks.ts` (and `boards.ts` if present).
- Backend `src/tasks/` and `src/boards/` (if present) modules.
- `tasks` and `boards` (if present) production tables.

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Operator creates an event with `start_at` in the past | Allowed (backfill use case). No reminder fires. `reminder_24h_sent_at` and `reminder_1h_sent_at` set to NOW so dispatcher skips. |
| Operator edits an event's `start_at` AFTER the 24h reminder fired but BEFORE the 1h reminder | 24h reminder is NOT re-sent (column already populated). 1h reminder fires at the new T-1h window. |
| Operator edits an event's `start_at` BEFORE either reminder fired | Both windows are recomputed from the new `start_at`. Sent flags stay NULL until the dispatcher matches. |
| Operator marks an event done before the reminder window | `done=true` filter excludes the row from the dispatcher query. No reminder. |
| Reminder dispatcher restarts mid-tick (process crash) | Atomic claim pattern: `UPDATE ... RETURNING` stamps `reminder_*_sent_at = NOW()` BEFORE the SendGrid call. If the process dies after the claim but before SendGrid responds, that single reminder is lost (the 1h reminder still fires as a backup). Documented trade-off; concurrent loops never double-send because of `FOR UPDATE SKIP LOCKED`. |
| SendGrid 429 / 5xx on reminder send | Retry once with 30s backoff. If still failing, run compensating `UPDATE empresa_items SET reminder_*_sent_at = NULL WHERE id = ...` so the next tick retries within the same 10-min window. |
| Item with `start_at = NULL` (todo without date) | Never matched by reminder dispatcher. No emails. |
| Item with `kind = 'note'` and a `start_at` | Never matched (notes don't get reminders by design). |
| Empresa deleted while an item has pending reminders | `ON DELETE CASCADE` removes items; dispatcher misses them naturally. |
| Bulk-move kanban: one of N empresas has stale `version` | Whole bulk fails atomically with 409, response lists conflicting empresa ids. UI re-fetches and the operator retries. |
| Bulk-move kanban: target stage requires `expected_close_date` and one empresa lacks it | Whole bulk fails with 400 listing the offending ids. UI surfaces inline. |
| Tareas tab: operator with no `assigned_to` items | Default "Mis" filter shows empty state. "Equipo" or "Todos" still surface team items. Empty state copy: "No tienes pendientes asignados. Cambia a 'Equipo' para ver todos." |
| `<DateTimePicker>` operator types invalid datetime | Field stays open with inline error. Save button disabled until valid. |
| Internal task creation (`empresa_id=NULL`): operator on the kanban view | Tareas list still surfaces the row under "Sin empresa". The kanban board does NOT show it (kanban is empresa-stage, not item-stage). |
| Migration runs on a schema where `tasks` table doesn't exist | Idempotent: `if not _table_exists("tasks"): pass`. No error. |
| Migration runs on a schema where `tasks` rows have `due_date IS NULL` | Backfill row with `due_at = NULL` (allowed since `due_at` is nullable on `empresa_items`). |
| Migration runs and there's already a row in `empresa_items` with the same `id` as a `tasks` row | `ON CONFLICT (id) DO NOTHING` — old row kept, no duplicate. |
| Operator clicks "Eliminar" on an item with the slide-over panel | Confirmation dialog ("¿Eliminar este pendiente?"). Confirm → `DELETE /empresas/items/{id}`, panel closes, list refreshes. |
| Operator clicks "+ Crear nueva cuenta de Eva" on an empresa that's already `operativo` (no current link) | Backend rejects with `OperativoRequiresExistingSubscription`. UI surfaces the toast and keeps the modal open. |
| `EMPRESA_ITEM_REMINDER_EMAIL` env var unset | Default `gus@goeva.ai` is used. No crash. |
| `empresa_item_reminders_enabled = False` | Loop is not started. No reminders fire. Useful for tests. |

---

## Error Handling

| Error condition | User-facing behavior | Technical response |
|-----------------|---------------------|---------------------|
| `POST /empresas/items` with no `title` | Slide-over shows inline error: "El título es requerido" | 422 with field-level errors |
| `POST /empresas/items` with `kind=event` and no `start_at` | "Eventos requieren start_at o due_at" toast | 400 `{reason: "EventDateRequired"}` |
| `POST /empresas/items` with `end_at < start_at` | "end_at debe ser >= start_at" toast | 400 `{reason: "InvalidDateWindow"}` |
| `POST /empresas/bulk-stage` with stale version on any row | "Otra persona cambió alguna empresa. Recarga e inténtalo de nuevo." toast | 409 `{reason: "OptimisticLockMismatch", conflicts: [...]}` |
| `GET /empresas/items` without auth | Login redirect | 401 |
| `POST /empresas/{id}/eva-account` when empresa already linked | "Esta empresa ya está vinculada a otra cuenta de Eva." toast (existing) | 409 `{reason: "empresa_already_linked"}` |
| Reminder dispatcher: SendGrid 4xx (auth/permission) | Log `ERROR` once per tick. Loop continues (does NOT exit). | Matches Feature 3 spec; same convention as monitoring_runner_loop. |
| Reminder dispatcher: SendGrid 429 / 5xx | Retry once with 30s backoff. On persistent failure, compensating UPDATE clears the claim so next tick retries. | Internal to dispatcher; no caller-facing surface. |
| Reminder dispatcher: DB connection lost | Catch, log `WARNING`, sleep 60 s, continue. Loop NEVER exits on its own — only on `stop_event.set()` from FastAPI shutdown. | Same convention as `monitoring_runner_loop`. |
| Tareas tab: `GET /empresas/items` returns 500 | "No se pudieron cargar las tareas. Intenta recargar." inline alert | Exception surfaced to the toast |

---

## UI/UX Details

- **Slide-over panel:** 384 px wide, full height, fixed right. Tailwind `transition-transform duration-200`. Backdrop `bg-black/20` only on mobile (`< md`).
- **DateTimePicker popover:** 320 px wide. Calendar grid + time strip side-by-side at `md+`, stacked at `< md`.
- **Channel-shortcut icons:** lucide icons (`MessageCircle`, `Phone`, `Mail`, `MapPin`) plus a custom WhatsApp icon (existing in repo).
- **Kanban "+" button:** 24×24 ghost button at card footer, hidden until card hover (touch devices: always visible).
- **Bulk-select ring:** `ring-2 ring-accent ring-offset-2` on selected cards.
- **Kind badges:** `<KindIcon>` component returning a 14×14 svg + text-xs label. Colors picked to match the existing design system tokens.
- **Tareas tab grouping:** sticky empresa header with logo + name + count, items indented by 16 px under it.
- **Reminder email:** subject `Recordatorio: {title} (en {1 hora|24 horas})`. Body has a plain-text fallback and a single-column HTML table styled like the existing onboarding emails.
- **Generic empty states:** every empty list ships with explicit copy (no "No data" placeholders).

---

## Business Rules

- An `empresa_item.kind = 'event'` row REQUIRES `start_at`. Validated at API + slide-over level.
- `end_at` must be `>= start_at` if both are set.
- `reminder_24h_sent_at` is set EXACTLY ONCE per item (NULL → timestamp). Same for `reminder_1h_sent_at`. Editing the item's `start_at` does NOT reset these flags by design — re-sending a reminder for the same event would feel like spam.
- **Past events** (`start_at < NOW()` at create or edit time) auto-stamp BOTH reminder-sent columns to `NOW()` so the dispatcher never matches them. Migration backfill applies the same rule to backfilled rows.
- An item with `done = true` is never matched by the reminder dispatcher.
- An item with `kind = 'note'` is never matched by the reminder dispatcher.
- Internal tasks (`empresa_id IS NULL`) participate fully in the reminder system; the email body shows "Tarea interna" instead of an empresa name.
- The Tareas tab list endpoint enforces auth via `get_current_user`. No public access.
- `POST /empresas/bulk-stage` requires every empresa's `version` in the request body. Atomic — all or nothing. Same business rules as the single-card path: operativo requires linked+active sub, demo/negociacion require expected_close_date, target=inactivo with active/trialing sub → 409 with offending ids (no auto-cancel; operator drags those individually).
- The `+ Crear nueva cuenta de Eva` inline form preflights the empresa link state on the backend (existing `_preflight_empresa_link`). No regression to those rules.
- Reminder dispatch is concurrency-safe: rows are atomically claimed via `UPDATE ... WHERE id IN (SELECT ... FOR UPDATE SKIP LOCKED) RETURNING ...` BEFORE the SendGrid call. If SendGrid fails, the claim is reverted (set back to NULL) so the next tick retries.

---

## Out of Scope (Explicit)

- **Per-assignee reminder routing.** v1 sends to a single hardcoded address. Future plan.
- **Custom `reminder_at` lead-time control.** The `reminder_at` column already exists for operator-set custom reminders; we do not wire it to email in this pass.
- **Push notifications.** Email only.
- **Mobile-native picker.** Mobile uses the same DateTimePicker; no PWA-specific tweaks.
- **Calendar drag-range create.** Only click-day single-event create. Range select is a follow-up.
- **Editing items inline on the kanban without opening the slide-over.** Always opens slide-over.
- **Importing the eva repo's full calendar component (`EventDateTimeFields`).** We reimplement a smaller, eva-erp-specific version using shadcn primitives. The eva component pulls in next-intl + IANA timezone helpers we don't want.
- **Recurring events / recurring reminders.** v1 fires per item once at T-24h and once at T-1h.
- **Multi-language.** UI stays in Spanish; English copy is not added in this pass.

---

## Tasks

### Phase 1: Backend

- [ ] 🟥 **Step 1: Alembic migration**
  - [ ] 🟥 New revision file `c8d9e0f1g2h3_empresas_ux_pass_consolidation.py` chained after `b8c9d0e1f2g3`.
  - [ ] 🟥 Drop NOT NULL on `empresa_items.empresa_id` (idempotent).
  - [ ] 🟥 Add `reminder_24h_sent_at`, `reminder_1h_sent_at` columns (idempotent).
  - [ ] 🟥 Backfill from `tasks` table into `empresa_items` if `tasks` exists.
  - [ ] 🟥 Drop `tasks` table (and `boards` if present) at the end of the same revision.
  - [ ] 🟥 Down-migration restores both tables (best-effort schema only; data loss documented in docstring).

- [ ] 🟥 **Step 2: Models + schemas**
  - [ ] 🟥 `empresa_id: Mapped[uuid.UUID | None]` on `EmpresaItem`.
  - [ ] 🟥 New columns: `reminder_24h_sent_at`, `reminder_1h_sent_at`.
  - [ ] 🟥 New schema `EmpresaItemListFilters` for the GET endpoint.
  - [ ] 🟥 New schema `BulkStageRequest`, `BulkStageConflict`, `BulkStageResponse`.

- [ ] 🟥 **Step 3: New endpoints**
  - [ ] 🟥 `GET /empresas/items?...` — registered BEFORE `/{empresa_id}` and `/calendar` to avoid shadowing.
  - [ ] 🟥 `POST /empresas/items` (top-level create that accepts optional empresa_id).
  - [ ] 🟥 `POST /empresas/bulk-stage`.
  - [ ] 🟥 Route ordering test added to `test_company_crm_items.py`.

- [ ] 🟥 **Step 4: Reminder dispatcher**
  - [ ] 🟥 New module `backend/src/empresas/reminders.py` with `empresa_item_reminder_runner_loop`.
  - [ ] 🟥 SendGrid client reuse (extract shared helper from `eva_platform/onboarding.py` if needed).
  - [ ] 🟥 Settings additions in `common/config.py`.
  - [ ] 🟥 Wire loop into `main.py` lifespan.
  - [ ] 🟥 Unit test: 24h window match + dedup; 1h window match + dedup; done items skipped; notes skipped.

- [ ] 🟥 **Step 5: Unmount tasks + dashboard swap**
  - [ ] 🟥 Remove `task_router`, `board_router` includes from `main.py`.
  - [ ] 🟥 Delete `backend/src/tasks/` and `backend/src/boards/` directories.
  - [ ] 🟥 Remove `Task` import from `backend/src/dashboard/router.py` (line 34).
  - [ ] 🟥 Replace ALL THREE dashboard queries (`open_tasks`, `overdue_tasks`, `tasks_active` at lines 181-202) with `empresa_items` equivalents per Feature 6. `done = false AND kind <> 'note'` is the universal predicate.
  - [ ] 🟥 Update dashboard contract test in `tests/test_removed_modules.py` to assert the new field shapes.
  - [ ] 🟥 Add a backend smoke test that calls `dashboard.summary()` after the migration and asserts no 500.
  - [ ] 🟥 Update `tests/test_removed_modules.py` to assert `/api/v1/tasks`, `/api/v1/boards` 404.

- [ ] 🟥 **Step 6: Backend tests**
  - [ ] 🟥 `tests/test_empresa_item_reminders.py` (new):
    - [ ] 🟥 24h window match + atomic claim sets sent_at.
    - [ ] 🟥 1h window match + atomic claim sets sent_at.
    - [ ] 🟥 Concurrent claim safety: simulate two loops, only one sends per row.
    - [ ] 🟥 Done items skipped; notes skipped; past events skipped.
    - [ ] 🟥 SendGrid failure reverts the claim (sent_at back to NULL) so next tick retries.
    - [ ] 🟥 Internal items (`empresa_id=NULL`) participate; email body says "Tarea interna".
    - [ ] 🟥 Recipient resolution honors `EMPRESA_ITEM_REMINDER_EMAIL` env override.
    - [ ] 🟥 Past-event create/edit auto-stamps both sent columns.
  - [ ] 🟥 `tests/test_company_crm_items.py` extended:
    - [ ] 🟥 `GET /empresas/items` filters: assigned_to=me, done=false, kind=todo,event, overdue=true, empresa_id.
    - [ ] 🟥 `GET /empresas/items` route registered BEFORE `/empresas/{empresa_id}`.
    - [ ] 🟥 `POST /empresas/items` happy path with `empresa_id=null` (internal task).
    - [ ] 🟥 `POST /empresas/items` rejects blank title.
    - [ ] 🟥 `POST /empresas/bulk-stage` happy path moves all empresas.
    - [ ] 🟥 `POST /empresas/bulk-stage` 409 on any version conflict (atomic — no partial moves).
    - [ ] 🟥 `POST /empresas/bulk-stage` 400 on close-date-required violation (atomic).
    - [ ] 🟥 `POST /empresas/bulk-stage` 409 `BulkInactivoNeedsCancel` when target=inactivo and any empresa has active/trialing sub.
    - [ ] 🟥 PATCH item with `start_at` in past auto-stamps both reminder-sent columns.
  - [ ] 🟥 `tests/test_dashboard_router.py` (new): assert dashboard.summary returns 200 with the new empresa_items-backed fields.
  - [ ] 🟥 `tests/test_removed_modules.py` extended: tasks/boards 404, dashboard contract.
  - [ ] 🟥 Migration: dry-run unit test exercises the upgrade against a temporary schema (use the in-process `Base.metadata.create_all` pattern from existing tests).

### Phase 2: Frontend

- [ ] 🟥 **Step 7: shadcn Calendar primitive**
  - [ ] 🟥 `npx shadcn@latest add calendar` — pulls in `react-day-picker`.
  - [ ] 🟥 New file `frontend/src/components/ui/TimePicker.tsx`: HH:MM 15-min step, AM/PM, scroll arrows.
  - [ ] 🟥 New file `frontend/src/components/ui/DateTimePicker.tsx`: Trigger button + Popover wrapping Calendar + TimePicker.
  - [ ] 🟥 Component test: renders, picks a date, picks a time, fires onChange with ISO string.

- [ ] 🟥 **Step 8: ItemEditorPanel slide-over**
  - [ ] 🟥 New file `frontend/src/components/empresas/ItemEditorPanel.tsx`.
  - [ ] 🟥 Modes: create / edit. Fields per spec. Validation surfaces inline.
  - [ ] 🟥 Action buttons: Save / Cancel / Mark done / Delete.
  - [ ] 🟥 Component tests for create + edit + delete + validation error rendering.

- [ ] 🟥 **Step 9: Card surface**
  - [ ] 🟥 Channel-shortcut row on `EmpresaCard` (kanban + grid both use it).
  - [ ] 🟥 Per-card "+" button on kanban variant.
  - [ ] 🟥 Kind badges on item rows.
  - [ ] 🟥 Channel health dots restored under linked-account name.

- [ ] 🟥 **Step 10: Kanban bulk-select**
  - [ ] 🟥 Cmd/Ctrl-click toggles selection, ring on selected cards.
  - [ ] 🟥 Drag of any selected card moves the whole group.
  - [ ] 🟥 Persist via `empresasApi.bulkStage({moves, lifecycle_stage_to})`.
  - [ ] 🟥 Surface `BulkInactivoNeedsCancel`: prompt operator to drag those empresas individually (existing cancel-subscription dialog) before retrying.
  - [ ] 🟥 Surface `OperativoRequiresActiveSubscription` and `ExpectedCloseDateRequired` with offending-id chips.
  - [ ] 🟥 Esc clears selection.

- [ ] 🟥 **Step 11: Calendar quick-create**
  - [ ] 🟥 Day cells in `EmpresasCalendarView` are clickable on empty space.
  - [ ] 🟥 Click → opens `ItemEditorPanel` with date prefilled.
  - [ ] 🟥 Existing item → opens edit mode.

- [ ] 🟥 **Step 12: Tareas tab**
  - [ ] 🟥 Add `view=tasks` to the view switcher.
  - [ ] 🟥 New file `frontend/src/components/empresas/EmpresasTareasView.tsx`.
  - [ ] 🟥 Filter chips: Mis / Equipo / Vencidas / + kind chips.
  - [ ] 🟥 List grouped by empresa (empresa header sticky, "Sin empresa" bucket on top).
  - [ ] 🟥 Each row: checkbox / kind badge / title / date / empresa name link / assignee / "⋯" menu.
  - [ ] 🟥 Click row → opens `ItemEditorPanel`.

- [ ] 🟥 **Step 13: Edit Empresa modal redesign**
  - [ ] 🟥 Two-column body grid (`grid-cols-2 gap-4`).
  - [ ] 🟥 Bigger nota textarea (4 rows resizable).
  - [ ] 🟥 "Datos fiscales y contacto" stays collapsible.
  - [ ] 🟥 "+ Crear nueva cuenta de Eva" picker option that expands inline mini-form.
  - [ ] 🟥 Wires to `empresasApi.createEvaAccount(empresaId, payload)`.

- [ ] 🟥 **Step 14: Cuentas view "Crear cuenta" CTA**
  - [ ] 🟥 Per-row "+ Crear cuenta" button on unlinked empresa rows.
  - [ ] 🟥 Opens the same inline-create flow as #13.

- [ ] 🟥 **Step 15: Sidebar / palette / dashboard cleanup**
  - [ ] 🟥 Remove "Tasks" entry from sidebar.
  - [ ] 🟥 Remove "Tasks" entry from command palette.
  - [ ] 🟥 Remove `/tasks` page directory.
  - [ ] 🟥 Remove `frontend/src/lib/api/tasks.ts` (and `boards.ts` if present).
  - [ ] 🟥 Dashboard tasks card link target → `/empresas?view=tasks`.

- [ ] 🟥 **Step 16: Frontend tests**
  - [ ] 🟥 `DateTimePicker.test.tsx`: picks date+time, formats output.
  - [ ] 🟥 `ItemEditorPanel.test.tsx`: create + edit + delete + validation.
  - [ ] 🟥 `EmpresaCard.test.tsx` updated: channel-shortcut row renders, "+" button opens panel, kind badges visible.
  - [ ] 🟥 `EmpresasKanban.test.tsx` (NEW): cmd-click adds to selection, drag-move calls bulk-stage.
  - [ ] 🟥 `EmpresasCalendarView.test.tsx` (NEW): click-day opens panel with date prefilled.
  - [ ] 🟥 `EmpresasTareasView.test.tsx` (NEW): filter chips toggle, group headers render.
  - [ ] 🟥 `sidebar.test.tsx` updated: Tasks entry gone.
  - [ ] 🟥 `command-palette.test.tsx` updated: Tasks entry gone.

### Phase 3: ⛔ Automated Verification (MANDATORY)

- [ ] 🟥 **Step 17: Run full test suite**
  - [ ] 🟥 Backend: `cd backend && python -m pytest tests/ --no-header -q` → all green.
  - [ ] 🟥 Frontend: `cd frontend && npm test` → all green.
  - [ ] 🟥 Types: `cd frontend && npx tsc --noEmit` → 0 errors.
  - [ ] 🟥 Lint: `cd frontend && npm run lint` → 0 errors.
  - [ ] 🟥 Build: `cd frontend && npm run build` → succeeds.

- [ ] 🟥 **Step 18: ⛔ Code review (codex direct, no `./eva` tooling)**
  - [ ] 🟥 Build prompt: "Review the diff between origin/main and HEAD on /Users/gustavozermeno/Code/eva-erp. Apply scope discipline. Output PASS unless P0/P1."
  - [ ] 🟥 Run: `codex exec -c model=gpt-5.5 -c model_reasoning_effort=high - < /tmp/eva-erp-review-prompt.txt > /tmp/eva-erp-codex-review.log 2>&1`.
  - [ ] 🟥 Read every finding. Fix all P0 / P1.
  - [ ] 🟥 Re-run review until verdict = `PASS`.

### Phase 4: ⛔ Browser Verification (MANDATORY)

> Determine URL: production = `https://erp.goeva.ai`. (eva-erp doesn't have feature desks; we verify against prod after deploy.)

- [ ] 🟥 **Step 19: Browser verification per feature**
  - [ ] 🟥 **Slide-over create from kanban "+":** open `/empresas?view=kanban`, click "+" on a card, fill title + kind=event + DateTimePicker date, save → row appears on the card.
  - [ ] 🟥 **Slide-over edit:** click that same item row → panel opens prefilled. Change title → save → row updates.
  - [ ] 🟥 **Slide-over delete:** open the same item, click 🗑 → confirm → row disappears.
  - [ ] 🟥 **Channel-shortcut log:** click 🟢 WhatsApp on an empresa card → panel opens with kind=outreach, contact_method=whatsapp, start_at=now. Save → outreach row appears.
  - [ ] 🟥 **Calendar quick-create:** open `/empresas?view=calendar`, click an empty day cell → panel opens with start_at = day at 09:00. Save → event appears under that day.
  - [ ] 🟥 **Bulk kanban move:** Cmd-click 2 cards in same column → drag one to another column → both move; toast confirms.
  - [ ] 🟥 **Tareas tab default filter:** open `/empresas?view=tasks` → only my open items show. Switch to "Todos" → all items show. Switch to "Vencidas" → only overdue items.
  - [ ] 🟥 **Internal task creation:** in slide-over, leave empresa picker empty, save → row appears under "Sin empresa (internas)" in Tareas tab.
  - [ ] 🟥 **Edit Empresa modal redesign:** open empresa edit modal → 2-column layout visible, nota textarea is 4 rows tall and resizable.
  - [ ] 🟥 **"+ Crear nueva cuenta de Eva":** in modal, open Cuenta de Eva picker, click "+ Crear nueva cuenta de Eva" → mini-form appears. Fill owner email + name → Guardar → toast confirms account created and empresa linked.
  - [ ] 🟥 **Reminder smoke test:** create an event with `start_at = NOW() + 24h05m`. Wait 5 min. Check SendGrid activity → reminder email sent to gus@goeva.ai. Repeat for `start_at = NOW() + 1h05m`.
  - [ ] 🟥 **DateTimePicker on every datetime field:** open every empresa form path that touches a datetime → confirm shadcn picker (NOT native).
  - [ ] 🟥 **Old /tasks 404:** navigate to `/tasks` → 404 page.
  - [ ] 🟥 **Console:** ZERO JS errors on each view.
  - [ ] 🟥 **Network:** all `/api/v1/empresas/items` and `/api/v1/empresas/bulk-stage` calls return 2xx.

### Phase 5: Documentation

- [ ] 🟥 **Step 20: Update docs**
  - [ ] 🟥 Update `docs/domains/crm/index.md` (or create) to point at the new tab + reminder behavior.
  - [ ] 🟥 New `how-empresa-item-reminders.md` documenting the dispatcher, env vars, and operator expectations.

### Phase 6: Ship

- [ ] 🟥 **Step 21: Merge + deploy**
  - [ ] 🟥 `git checkout main && git merge --ff-only feat/empresas-ux-pass`.
  - [ ] 🟥 `git push origin main` (triggers GitHub Actions: Koyeb deploy + alembic upgrade head).
  - [ ] 🟥 `cd /Users/gustavozermeno/Code/eva-erp && npx vercel --prod --yes` (frontend deploy — Vercel auto-deploy isn't wired).
  - [ ] 🟥 Wait for Koyeb deployment HEALTHY via `gh run watch`.
  - [ ] 🟥 Verify Alembic head: `supabase db query --linked --output table "SELECT version_num FROM alembic_version;"`.
  - [ ] 🟥 Run Phase 4 again on production.

- [ ] 🟥 **Step 22: Cleanup**
  - [ ] 🟥 Move plan to `docs/archive/plans/` after 100%.
  - [ ] 🟥 `git push origin --delete feat/empresas-ux-pass`.
  - [ ] 🟥 `git branch -d feat/empresas-ux-pass`.

---

## Technical Details

### Reminder dispatcher: atomic claim query (T-24h example)

The dispatcher MUST atomically claim rows BEFORE the SendGrid call. Plain
`SELECT` would race under concurrent API instances and double-send.

```sql
UPDATE empresa_items
   SET reminder_24h_sent_at = NOW()
 WHERE id IN (
   SELECT id FROM empresa_items
    WHERE done = false
      AND kind <> 'note'
      AND start_at IS NOT NULL
      AND reminder_24h_sent_at IS NULL
      AND start_at BETWEEN (NOW() + interval '23 hours 55 minutes')
                       AND (NOW() + interval '24 hours 5 minutes')
    FOR UPDATE SKIP LOCKED
    LIMIT 50
 )
RETURNING id, empresa_id, title, description, start_at, assigned_to;
```

After the SendGrid call:
- **Success** → leave the claim in place (`reminder_24h_sent_at` stays = NOW).
- **Failure** → compensating `UPDATE empresa_items SET reminder_24h_sent_at = NULL WHERE id = :id` so the next tick retries inside the 10-min window.

Same pattern for the 1h window — substitute `reminder_1h_sent_at` and `0 hours 55 minutes` / `1 hour 5 minutes`.

### Migration backfill snippet (canonical — matches Feature 1)

```python
def upgrade() -> None:
    # 1. Add new columns and drop NOT NULL on empresa_id (idempotent)
    with op.batch_alter_table("empresa_items") as batch:
        if not _column_exists("empresa_items", "reminder_24h_sent_at"):
            batch.add_column(sa.Column("reminder_24h_sent_at", sa.DateTime(timezone=True), nullable=True))
        if not _column_exists("empresa_items", "reminder_1h_sent_at"):
            batch.add_column(sa.Column("reminder_1h_sent_at", sa.DateTime(timezone=True), nullable=True))
        batch.alter_column("empresa_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)

    conn = op.get_bind()
    has_tasks = conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name='tasks' LIMIT 1")
    ).first() is not None

    if has_tasks:
        # 2a. If task_comments exists, fold latest comment text into description
        #     before backfill (lossy migration: only the most recent comment is
        #     preserved; the rest are deleted along with task_comments).
        has_comments = conn.execute(
            sa.text("SELECT 1 FROM information_schema.tables WHERE table_name='task_comments' LIMIT 1")
        ).first() is not None
        if has_comments:
            op.execute("""
                UPDATE tasks t
                   SET description = COALESCE(t.description, '') ||
                       CASE WHEN t.description IS NOT NULL AND t.description <> '' THEN E'\\n\\n---\\n' ELSE '' END ||
                       'Last comment: ' || c.body
                  FROM (
                    SELECT DISTINCT ON (task_id) task_id, body
                      FROM task_comments
                     ORDER BY task_id, created_at DESC
                  ) c
                 WHERE c.task_id = t.id
                   AND COALESCE(t.description, '') NOT LIKE '%Last comment:%';
            """)
            op.execute("DROP TABLE task_comments CASCADE;")

        # 2b. Backfill into empresa_items. Lossy: priority/labels/source_meeting_id/board_id
        #     are NOT migrated (no destination columns). Documented in run-book.
        op.execute("""
            INSERT INTO empresa_items (
                id, empresa_id, title, description, kind, due_at, done, completed_at,
                created_by, created_at, updated_at, assigned_to,
                reminder_24h_sent_at, reminder_1h_sent_at
            )
            SELECT
                id,
                NULL AS empresa_id,
                title,
                description,
                'todo' AS kind,
                CASE WHEN due_date IS NULL THEN NULL
                     ELSE (due_date::timestamp + interval '23 hours 59 minutes') AT TIME ZONE 'America/Mexico_City'
                END AS due_at,
                (status = 'done') AS done,
                CASE WHEN status = 'done' THEN updated_at END AS completed_at,
                created_by,
                created_at,
                updated_at,
                assignee_id,
                -- Past-event sentinel: if due_date already passed, mark both reminder columns sent
                CASE WHEN due_date IS NOT NULL AND due_date < CURRENT_DATE THEN NOW() END,
                CASE WHEN due_date IS NOT NULL AND due_date < CURRENT_DATE THEN NOW() END
            FROM tasks
            ON CONFLICT (id) DO NOTHING;
        """)

        # 2c. Drop tasks (and boards if present)
        op.execute("DROP TABLE tasks CASCADE;")

    has_boards = conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name='boards' LIMIT 1")
    ).first() is not None
    if has_boards:
        op.execute("DROP TABLE boards CASCADE;")

    # 3. Sentinel pass for any pre-existing empresa_items where start_at is in the past:
    #    stamp both reminder columns so the dispatcher never tries them.
    op.execute("""
        UPDATE empresa_items
           SET reminder_24h_sent_at = COALESCE(reminder_24h_sent_at, NOW()),
               reminder_1h_sent_at  = COALESCE(reminder_1h_sent_at,  NOW())
         WHERE start_at IS NOT NULL
           AND start_at < NOW();
    """)
```

### `<DateTimePicker>` API

```tsx
interface DateTimePickerProps {
  value: string | null;          // ISO 8601 or null
  onChange: (iso: string | null) => void;
  disabled?: boolean;
  placeholder?: string;          // default: "Selecciona fecha"
  minDate?: Date;
  maxDate?: Date;
}
```

### `<ItemEditorPanel>` API

```tsx
type Mode = { type: "create"; empresaId?: string | null; defaults?: Partial<ItemForm> }
          | { type: "edit"; itemId: string };

interface ItemEditorPanelProps {
  mode: Mode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: () => void;          // refresh callback
  empresas: { id: string; name: string }[];  // for the optional empresa picker
}
```

---

## Generalization Check

- [ ] No hardcoded industry-specific terms — `kind` literal is generic (`todo`/`event`/`note`/`outreach`).
- [ ] Channel labels (`SMS`, `WhatsApp`, `Call`, `Email`, `Visit`) are universal CRM verbs, not industry-specific.
- [ ] DateTimePicker uses `Intl.DateTimeFormat` so locale and timezone aren't hardcoded.
- [ ] Reminder copy uses generic Spanish ("Recordatorio: {title}") with the empresa name pulled from data, not hardcoded examples.
- [ ] No customer-specific logic in this pass.

---

## Comprehensiveness Checklist

- [x] Re-read the entire conversation.
- [x] Every feature mentioned is in the Features section.
- [x] Every edge case discussed is in the Edge Cases table.
- [x] Every error condition has defined behavior.
- [x] Every decision is documented in Decisions Made During Planning.
- [x] Out of Scope explicitly lists what we're NOT doing.
- [x] A different agent could implement this from the plan alone.

---

## Notes

- eva-erp does NOT have the `./eva` desk system. All commands use plain `git`, `npm`, `pytest`, `codex exec`. The plan-template wording was adapted accordingly.
- Production frontend deploys via `npx vercel --prod --yes` from the repo root (Vercel project `eva-erp`, not the now-stale `frontend` Vercel project — guard against `frontend/.vercel/project.json` being recreated).
- The Vercel project is NOT auto-deploying on push to main; manual deploys are the current workflow.
- The Koyeb backend auto-deploys on push to main and runs `alembic upgrade head` via `start.sh`.
- Branch `feat/empresas-ux-pass` was created at the start of planning; if you start fresh, run `git checkout -b feat/empresas-ux-pass`.

---

## Output Contract

```text
Repo Context
repo: /Users/gustavozermeno/Code/eva-erp
branch: feat/empresas-ux-pass
production frontend: https://erp.goeva.ai
production backend: https://erp.goeva.ai/api/v1
plan: docs/domains/crm/plan-empresas-ux-pass.md
```
