# Empresas Follow-up Redesign

**Overall Progress:** `0%`

> **Implementation:** Use the `/implement-plan` skill to execute this plan.

---

## Execution Context

**Project:** Eva ERP (`~/eva-erp/`)
**Branch:** `feat/empresas-followup` (create from `main`)

**Start-of-work guardrails:**
1. `git checkout -b feat/empresas-followup` from `main`
2. Verify working directory is `~/eva-erp/`
3. No desk system — this project uses simple git branches

---

## Requirements Extraction

### Original Request
> "I would like to change some stuff inside each card of the enterprises. I would like better if there was like status of each enterprise [...] also there should be like always displayed like the things that each company needs [...] like in what side the ball is, is something apart from the status."

### Additional Requirements (from conversation — 10-question interview)
- Enterprise status: 3 options (Operativo, En implementación, Requiere atención)
- "Ball on" indicator: separate from status, shows who needs to act (Nosotros/Cliente/none)
- Ball on uses arrow indicators: `← Nosotros` / `→ Cliente`
- Status + ball visible on card header below company name, always visible without expanding
- Items simplified to flat checklist: title + done/not done (no type, no priority, no status)
- Card also shows a summary note (free text) + top pending items
- Click item on card to toggle done — it disappears from visible list
- Anyone can edit everything (admin + member)
- Full history changelog saved, shown via "Historial" button on demand
- No status filtering — just the existing search bar
- Keep card grid layout
- Fiscal/contact details removed from card, only accessible in edit modal

### Decisions Made During Planning
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Status + ball separation | Two independent fields | Ball can apply to any status (implementing + ball on us, requires attention + ball on client, etc.) |
| Ball indicator style | Arrows (`← Nosotros` / `→ Cliente`) | More intuitive than colored dots, no color confusion with status badges |
| Item simplification | Flat checklist (title + done) | Follow-up dashboard needs speed, not item categorization |
| History storage | Full changelog, hidden behind button | User wants audit trail but doesn't want visual clutter |
| Fiscal details location | Edit modal only | Rarely needed at a glance, declutters card |
| Filtering | Search only | Under 10 companies, filters add clutter |
| Layout | Card grid | User preference over list/table |

### User Preferences
- Status badges: colored with text (🟢 Operativo, 🟡 En implementación, 🔴 Requiere atención)
- Ball indicator: arrows with text, no extra colors
- Cards should show everything important at a glance without expanding
- Simple and fast — this is a follow-up dashboard, not a CRM

---

## Intended Outcome

The `/empresas` page becomes a follow-up dashboard. Each card shows at a glance: company logo + name, status badge (colored), ball-on indicator (arrow), a summary note, and a short checklist of pending items. Users can click items to toggle them done. Expanding is no longer needed for day-to-day use — only the "..." menu gives access to edit empresa details (including fiscal data) and view history. The page lets the team see in 2 seconds: which companies need attention, whose court the ball is in, and what's pending.

---

## Features

1. **Enterprise status field** — New `status` field on Empresa: `operativo`, `en_implementacion`, `requiere_atencion`. Displayed as a colored badge on the card.
2. **Ball-on indicator** — New `ball_on` field on Empresa: `nosotros`, `cliente`, or `null`. Displayed as `← Nosotros` or `→ Cliente` next to status badge. Null = no indicator shown.
3. **Summary note** — New `summary_note` text field on Empresa. Displayed below status/ball on the card as a short italic line. Editable via the edit modal.
4. **Simplified items** — Remove `type`, `priority`, `status`, `description`, `due_date` from EmpresaItem. Replace with single `done` boolean. Items are just: title + done/not done.
5. **Always-visible pending items** — Card shows up to 3 not-done items as a checklist directly on the card (no expand needed). If more than 3, show "+N more" link.
6. **Click-to-toggle items** — Clicking an item checkbox on the card toggles it done via API. Done items disappear from the card's visible list.
7. **Inline add item** — A small "+" button or input on the card to quickly add a new pending item without opening a modal.
8. **History changelog** — New `EmpresaHistory` model. Records changes to `status`, `ball_on`, and `summary_note` with old/new values, user, and timestamp. Accessible via "Historial" button in the "..." dropdown menu, opens a dialog showing timeline of changes.
9. **Edit modal cleanup** — Remove fiscal details section from expanded card view. Fiscal/contact fields remain in the edit empresa modal. Add status, ball_on, and summary_note fields to the edit modal.
10. **Remove expand for details** — Remove the "Ver detalles" collapsible section and the associated fiscal data display from cards.

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Empresa with no items | Card shows "Sin pendientes" in muted text |
| Empresa with all items done | Card shows "Sin pendientes" — done items are hidden |
| Empresa with no status set | Default to `operativo` (migration sets default) |
| Empresa with no ball_on | No arrow indicator shown, just the status badge |
| Empresa with no summary note | No note line shown on card (space collapses) |
| More than 3 pending items | Show first 3 + "+N más" link that expands to show all |
| Very long item title | Truncate with ellipsis on the card |
| Very long summary note | Truncate to 2 lines on the card, full text in edit modal |
| Toggle item done while card is loading | Disable checkbox during API call to prevent double-toggle |
| Existing items with type/priority/status data | Migration drops those columns; data is lost (acceptable — module is brand new, no real data besides test entries) |
| History for a deleted empresa | Cascade delete history records |

---

## Error Handling

| Error Condition | User-Facing Behavior | Technical Response |
|-----------------|---------------------|-------------------|
| Failed to toggle item | Toast "Error al actualizar" and revert checkbox state | PATCH returns 4xx/5xx |
| Failed to add item | Toast "Error al agregar pendiente" | POST returns 4xx/5xx |
| Failed to load history | Toast "Error al cargar historial" | GET returns 4xx/5xx |
| Failed to update status/ball | Toast "Error al guardar empresa" | PATCH returns 4xx/5xx |

---

## UI/UX Details

### Card Layout (top to bottom)
```
┌──────────────────────────────────┐
│         [Logo]                   │
│        Company Name              │
│  🟡 En implementación · ← Nosotros  │
│                                  │
│  "Esperando credenciales de IG"  │  ← summary note (italic, muted)
│                                  │
│  ☐ Instagram no conectado        │  ← pending items checklist
│  ☐ Configurar catálogo           │
│  ☐ Entrenar bot                  │
│  +2 más                          │  ← overflow link
│                                  │
│  [+ Agregar]              [···]  │  ← add item + menu
└──────────────────────────────────┘
```

### Status Badge Styles
- `operativo`: green background/text pill (`bg-emerald-100 text-emerald-700`)
- `en_implementacion`: yellow/amber pill (`bg-amber-100 text-amber-700`)
- `requiere_atencion`: red pill (`bg-red-100 text-red-700`)

### Ball-on Styles
- `← Nosotros` and `→ Cliente`: plain muted text with arrow, no background — keeps it visually distinct from the status badge
- When `ball_on` is null: nothing rendered

### "..." Dropdown Menu
- Editar empresa (opens edit modal with status, ball_on, summary_note, name, logo, fiscal fields)
- Historial (opens history dialog)
- Eliminar empresa (with existing delete behavior)

### History Dialog
- Chronological list (newest first)
- Each entry: `"Status cambiado de Operativo a En implementación" — Juan · hace 2 días`
- Simple list, no complex timeline UI

### Edit Modal Fields (in order)
- Nombre *
- Logo (file picker — existing)
- Status (select: Operativo / En implementación / Requiere atención)
- Responsable (select: Nosotros / Cliente / Sin asignar)
- Nota de seguimiento (textarea)
- — separator —
- Industria, Email, Teléfono, RFC, Razón Social, Régimen Fiscal, Dirección (collapsed or in a "Datos fiscales" accordion)

---

## Business Rules

- Empresa `status` defaults to `operativo` for new empresas
- Empresa `ball_on` defaults to `null` (no indicator) for new empresas
- Empresa `summary_note` defaults to `null`
- Items only have `title` (required) and `done` (boolean, default false)
- Done items are excluded from the card's visible checklist (they still exist in the DB)
- History is recorded when `status`, `ball_on`, or `summary_note` changes on an empresa
- History records are cascade-deleted when an empresa is deleted
- All users (admin + member) can edit status, ball_on, items, and summary_note

---

## Out of Scope (Explicit)

- Status filtering/tabs — not needed with under 10 companies
- Notifications/alerts for stuck statuses — purely visual dashboard for now
- Item due dates or priorities — removed by design for simplicity
- Item descriptions — removed, just titles
- Drag-and-drop item reordering — not requested
- Pagination — not needed with few companies
- History for item changes (add/remove/toggle) — only status/ball/note changes tracked
- File attachments on items — not discussed

---

## Tasks

### Phase 1: Backend — Model & Migration

- [ ] 🟥 **Step 1: Update models**
  - [ ] 🟥 Add `status` field to `Empresa` (String(30), default "operativo")
  - [ ] 🟥 Add `ball_on` field to `Empresa` (String(10), nullable, default null)
  - [ ] 🟥 Add `summary_note` field to `Empresa` (Text, nullable)
  - [ ] 🟥 Simplify `EmpresaItem`: drop `type`, `description`, `status`, `priority`, `due_date` columns; add `done` (Boolean, default false)
  - [ ] 🟥 Create `EmpresaHistory` model: id (UUID PK), empresa_id (FK), field_changed (String), old_value (Text nullable), new_value (Text nullable), changed_by (FK users.id), changed_at (DateTime, server_default now())
  - [ ] 🟥 Register `EmpresaHistory` in models `__init__.py` if needed

- [ ] 🟥 **Step 2: Alembic migration**
  - [ ] 🟥 Single migration file for all schema changes
  - [ ] 🟥 Add `status`, `ball_on`, `summary_note` columns to `empresas`
  - [ ] 🟥 Drop `type`, `description`, `status`, `priority`, `due_date` from `empresa_items`; add `done` boolean
  - [ ] 🟥 Create `empresa_history` table
  - [ ] 🟥 Create index on `empresa_history.empresa_id`

### Phase 2: Backend — Router & Schemas

- [ ] 🟥 **Step 3: Update schemas**
  - [ ] 🟥 Update `EmpresaCreate` — add `status`, `ball_on`, `summary_note`
  - [ ] 🟥 Update `EmpresaUpdate` — add `status`, `ball_on`, `summary_note`
  - [ ] 🟥 Update `EmpresaResponse` — add `status`, `ball_on`, `summary_note`
  - [ ] 🟥 Update `EmpresaListItem` response — add `status`, `ball_on`, `summary_note`, and `pending_items` (list of not-done item titles, max 3) so the list endpoint provides card data
  - [ ] 🟥 Simplify `EmpresaItemCreate` — just `title`
  - [ ] 🟥 Simplify `EmpresaItemUpdate` — `title` optional, `done` optional
  - [ ] 🟥 Simplify `EmpresaItemResponse` — id, empresa_id, title, done, created_at
  - [ ] 🟥 Add `EmpresaHistoryResponse` — id, field_changed, old_value, new_value, changed_by (UUID), changed_by_name (str), changed_at

- [ ] 🟥 **Step 4: Update router**
  - [ ] 🟥 Update `list_empresas` — return status, ball_on, summary_note, and up to 5 pending (not done) item titles + total pending count
  - [ ] 🟥 Update `create_empresa` — accept new fields, default status to "operativo"
  - [ ] 🟥 Update `update_empresa` — detect changes to status/ball_on/summary_note and create `EmpresaHistory` records
  - [ ] 🟥 Simplify `create_item` — accept only title
  - [ ] 🟥 Update `update_item` — accept title and/or done (for toggle)
  - [ ] 🟥 Add `PATCH /empresas/items/{item_id}/toggle` — quick endpoint to toggle `done` boolean
  - [ ] 🟥 Add `GET /empresas/{empresa_id}/history` — returns history records with user names, ordered newest first

### Phase 3: Frontend — API Client

- [ ] 🟥 **Step 5: Update API client**
  - [ ] 🟥 Update types: `EmpresaListItem` (add status, ball_on, summary_note, pending_items, pending_count), `Empresa`, `EmpresaItem` (simplified), `EmpresaHistory`
  - [ ] 🟥 Update `EmpresaCreate` / `EmpresaItemCreate` types
  - [ ] 🟥 Add `toggleItem(itemId)` method
  - [ ] 🟥 Add `getHistory(empresaId)` method

### Phase 4: Frontend — Page Redesign

- [ ] 🟥 **Step 6: Redesign card component**
  - [ ] 🟥 Show status badge (colored pill) below company name
  - [ ] 🟥 Show ball-on arrow text next to status badge (when set)
  - [ ] 🟥 Show summary note (italic, muted, truncated to 2 lines)
  - [ ] 🟥 Show pending items as checkbox list (up to 3, with "+N más" overflow)
  - [ ] 🟥 Click checkbox → call toggle API → optimistically update UI
  - [ ] 🟥 Add inline "Agregar" input/button for quick item add
  - [ ] 🟥 Remove "Ver detalles" section entirely
  - [ ] 🟥 Remove expand/collapse for items — pending items always visible

- [ ] 🟥 **Step 7: Update edit empresa modal**
  - [ ] 🟥 Add Status select (Operativo / En implementación / Requiere atención)
  - [ ] 🟥 Add Ball-on select (Nosotros / Cliente / Sin asignar)
  - [ ] 🟥 Add Summary note textarea
  - [ ] 🟥 Keep fiscal/contact fields (they're now the only place to see/edit them)

- [ ] 🟥 **Step 8: Simplify item modal**
  - [ ] 🟥 Item create: just a title input (no type, priority, status, description, due_date)
  - [ ] 🟥 Item edit: title field + done toggle

- [ ] 🟥 **Step 9: Add history dialog**
  - [ ] 🟥 "Historial" option in "..." dropdown menu
  - [ ] 🟥 Opens Dialog with chronological list of changes
  - [ ] 🟥 Each entry: description of change + user name + relative time

### Phase 5: Verification

- [ ] 🟥 **Step 10: TypeScript & build check**
  - [ ] 🟥 `npx tsc --noEmit` passes with zero errors
  - [ ] 🟥 `npm run build` succeeds

- [ ] 🟥 **Step 11: Manual verification**
  - [ ] 🟥 Create new empresa → status defaults to Operativo, no ball indicator
  - [ ] 🟥 Edit empresa → change status, ball, note → card updates correctly
  - [ ] 🟥 Add items → appear as checklist on card
  - [ ] 🟥 Click item checkbox → item marked done, disappears from card
  - [ ] 🟥 More than 3 items → "+N más" shows correctly
  - [ ] 🟥 Open Historial → shows status/ball/note changes with user + time
  - [ ] 🟥 Edit modal shows fiscal fields, card does not
  - [ ] 🟥 Logo picker still works
  - [ ] 🟥 Search still works

### Phase 6: Deploy

- [ ] 🟥 **Step 12: Deploy**
  - [ ] 🟥 Commit all changes
  - [ ] 🟥 Push to `origin/main` (after user approval)
  - [ ] 🟥 Deploy frontend via `npx vercel --prod`
  - [ ] 🟥 Verify CI/CD deploys backend + runs migration
  - [ ] 🟥 Verify migration actually applied (check table exists — learned from prior incident)
  - [ ] 🟥 Smoke test on production

---

## Technical Details

### Database Schema Changes

```sql
-- Add to empresas table
ALTER TABLE empresas ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'operativo';
ALTER TABLE empresas ADD COLUMN ball_on VARCHAR(10); -- nullable: nosotros | cliente | null
ALTER TABLE empresas ADD COLUMN summary_note TEXT;

-- Simplify empresa_items table
ALTER TABLE empresa_items DROP COLUMN type;
ALTER TABLE empresa_items DROP COLUMN description;
ALTER TABLE empresa_items DROP COLUMN status;
ALTER TABLE empresa_items DROP COLUMN priority;
ALTER TABLE empresa_items DROP COLUMN due_date;
ALTER TABLE empresa_items ADD COLUMN done BOOLEAN NOT NULL DEFAULT false;

-- New history table
CREATE TABLE empresa_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    field_changed VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by UUID REFERENCES users(id),
    changed_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_empresa_history_empresa_id ON empresa_history(empresa_id);
```

### API Changes

| Method | Path | Change |
|--------|------|--------|
| GET | `/api/v1/empresas` | Returns status, ball_on, summary_note, pending items preview |
| POST | `/api/v1/empresas` | Accepts status, ball_on, summary_note |
| PATCH | `/api/v1/empresas/{id}` | Records history for status/ball_on/summary_note changes |
| POST | `/api/v1/empresas/{id}/items` | Simplified: only accepts title |
| PATCH | `/api/v1/empresas/items/{id}/toggle` | **New** — toggles done boolean |
| GET | `/api/v1/empresas/{id}/history` | **New** — returns changelog |

### List Endpoint Response Shape
```json
[
  {
    "id": "uuid",
    "name": "Cuadra",
    "logo_url": "data:image/png;base64,...",
    "status": "en_implementacion",
    "ball_on": "nosotros",
    "summary_note": "Esperando credenciales de Instagram",
    "item_count": 5,
    "pending_count": 3,
    "pending_items": [
      {"id": "uuid", "title": "Instagram no conectado"},
      {"id": "uuid", "title": "Configurar catálogo"},
      {"id": "uuid", "title": "Entrenar bot"}
    ]
  }
]
```

### History Recording Logic (in update_empresa)
```python
tracked_fields = {"status", "ball_on", "summary_note"}
for field, new_value in data.model_dump(exclude_unset=True).items():
    if field in tracked_fields:
        old_value = getattr(empresa, field)
        if old_value != new_value:
            history = EmpresaHistory(
                empresa_id=empresa.id,
                field_changed=field,
                old_value=str(old_value) if old_value else None,
                new_value=str(new_value) if new_value else None,
                changed_by=user.id,
            )
            db.add(history)
```

### Frontend Files to Modify
| File | Changes |
|------|---------|
| `frontend/src/lib/api/empresas.ts` | Update types, add toggleItem + getHistory |
| `frontend/src/app/(app)/empresas/page.tsx` | Full card redesign, new modals, history dialog |

### Backend Files to Modify
| File | Changes |
|------|---------|
| `backend/src/empresas/models.py` | Add fields to Empresa, simplify EmpresaItem, add EmpresaHistory |
| `backend/src/empresas/schemas.py` | Update all schemas |
| `backend/src/empresas/router.py` | Update endpoints, add toggle + history |
| `backend/alembic/versions/` | New migration file |

---

## Generalization Check

- [x] No hardcoded industry-specific terms
- [x] Status values are generic (operational, implementing, needs attention)
- [x] Ball-on concept works for any client relationship
- [x] Items are generic pending tasks
- [x] Would work for any industry tracking client onboarding/follow-up

---

## Comprehensiveness Checklist

- [x] Re-read the entire conversation
- [x] Every feature mentioned is listed in Features section
- [x] Every edge case discussed is in Edge Cases table
- [x] Every error condition has defined behavior
- [x] Every decision is documented with rationale
- [x] Out of Scope lists what we're NOT doing
- [x] A different agent could implement this from the plan alone

---

## Notes

- The empresas module was just built — there's minimal real data. Dropping columns from empresa_items is safe.
- The previous migration incident (tables stamped but not created) means deployment verification is critical. Step 12 explicitly checks that the migration actually applied.
- The existing LogoPicker (base64 file upload) and LogoAvatar (with error fallback) components should be preserved as-is.
- All labels remain in Spanish throughout the UI.
