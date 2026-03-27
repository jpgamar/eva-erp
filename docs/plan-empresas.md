# Empresas Module Implementation Plan

**Overall Progress:** `100%`

> **Implementation:** Use the `/implement-plan` skill to execute this plan.

---

## Execution Context

**Project:** Eva ERP (`~/eva-erp/`)
**Branch:** `feat/empresas` (create from `main`)

**Start-of-work guardrails:**
1. `git checkout -b feat/empresas` from `main`
2. Verify working directory is `~/eva-erp/`
3. No desk system — this project uses simple git branches

---

## Requirements Extraction

### Original Request
> "Add a new page which is called Empresas... that's going to be like a table where you're going to see the logo of each enterprise and under that you're going to see all of their needs and all of their appointments and all of everything like sort of sorting tasks for each enterprise."

### Additional Requirements (from conversation)
- Standalone module — NO imports from other ERP modules
- New `empresas` table in ERP database only (not imported from anywhere)
- Related entities: **Needs** and **Tasks** only (new tables, not existing ERP tasks)
- Empresa visible fields: logo + name only (fiscal/contact data in expandable dropdown)
- Full fiscal data model: RFC, razón social, régimen fiscal, industry, contact info
- Needs: title, description, status (open/in_progress/done), priority (low/med/high), due date
- Tasks: title, description, status (open/in_progress/done), due date (NO priority)
- Page layout: full-width table with expandable rows
- Expanded view: combined list with type badge (need vs task)
- CRUD via modals
- All users can access (admin + member)

### Decisions Made During Planning
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data source | New standalone table | User explicitly said "not import from anywhere" |
| Needs + Tasks storage | Single `empresa_items` table with `type` column | User chose combined list with type badge — single table simplifies queries |
| Priority field | Nullable, only meaningful for needs | Tasks don't have priority per user spec |
| Module isolation | Zero imports from other src/ modules (except auth + common) | User said "don't relate anything to the ERP" |
| Permissions | No role check beyond login | All users (admin + member) can access |

### User Preferences
- Minimal initial UI — only logo + name visible per row
- Fiscal/contact details hidden behind expandable section
- Combined need/task list (not separate tabs or tables)

---

## Intended Outcome

A new `/empresas` page in the Eva ERP sidebar. Users see a full-width table of enterprises, each row showing a small logo and company name. Clicking a row expands it to reveal a combined list of needs and tasks, each with a colored type badge ("Necesidad" / "Tarea"). Users can create/edit empresas, needs, and tasks via modal dialogs. Empresa detail fields (fiscal, contact) are accessible via a collapsible section within the expanded row, not shown by default.

---

## Features

1. **Empresa CRUD** — Create, read, update, delete enterprises with name, logo_url, industry, email, phone, address, RFC, razón social, régimen fiscal
2. **Empresa Item CRUD** — Create, read, update, delete needs and tasks linked to an empresa
3. **Empresas table page** — Full-width table at `/empresas` with expandable rows
4. **Expandable row content** — Combined list of needs + tasks with type badges, plus collapsible empresa details section
5. **Modal forms** — Dialog modals for creating/editing empresas and items
6. **Sidebar navigation** — "Empresas" link in sidebar under a suitable group
7. **Search/filter** — Search empresas by name

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Empresa with no items | Expanded row shows "No hay necesidades ni tareas" empty state |
| Empresa with no logo | Show a placeholder icon (Building2 or initials) |
| Delete empresa with items | Cascade delete all related items |
| Very long empresa name | Truncate with ellipsis in table row |
| Priority field on tasks | Stored as null, not displayed |

---

## Error Handling

| Error Condition | User-Facing Behavior | Technical Response |
|-----------------|---------------------|-------------------|
| Failed to load empresas | Toast error "Error al cargar empresas" | GET /empresas returns 500 |
| Failed to create empresa | Toast error "Error al crear empresa" | POST /empresas returns 4xx/5xx |
| Failed to create item | Toast error "Error al crear elemento" | POST /empresas/{id}/items returns 4xx/5xx |
| Empresa not found | Toast error, no crash | 404 from API |
| Network error | Toast error with generic message | Axios interceptor handles |

---

## UI/UX Details

- **Table columns:** Logo (small avatar/icon), Name, # Items (count badge), expand chevron
- **Expanded section has two parts:**
  1. **Items list** — combined needs + tasks, sorted by created_at desc, type badge colors: blue for "Necesidad", green for "Tarea"
  2. **Empresa details** — collapsible accordion showing fiscal + contact fields (hidden by default)
- **Modals:**
  - "Nueva Empresa" — name (required), logo URL, industry, contact fields, fiscal fields
  - "Nuevo Elemento" — type selector (need/task), title (required), description, status, priority (only shown if type=need), due date
- **Status badges:** open = yellow, in_progress = blue, done = green
- **All labels in Spanish**

---

## Business Rules

- Empresa `name` is required, all other fields optional
- Item `title` is required, all other fields optional
- Item `type` must be "need" or "task"
- Item `status` defaults to "open"
- Item `priority` is only settable when type = "need"; ignored/null for tasks
- Items belong to exactly one empresa (FK constraint)

---

## Out of Scope (Explicit)

- Import/sync from Eva AI app or any external source
- Relationships to existing ERP modules (customers, prospects, tasks, etc.)
- File upload for logos (just a URL field for now)
- Pagination (can add later if list grows)
- Drag-and-drop reordering
- Assignee field on tasks (user explicitly excluded it)

---

## Tasks

### Phase 1: Backend

- [x] 🟩 **Step 1: Create `empresas` module skeleton**
  - [x] 🟩 Create `backend/src/empresas/` directory
  - [x] 🟩 Create `backend/src/empresas/__init__.py`
  - [x] 🟩 Create `backend/src/empresas/models.py` with `Empresa` and `EmpresaItem` models
  - [x] 🟩 Create `backend/src/empresas/schemas.py` with Pydantic schemas
  - [x] 🟩 Create `backend/src/empresas/router.py` with CRUD endpoints
  - [x] 🟩 Register models in `backend/src/models/__init__.py`
  - [x] 🟩 Register router in `backend/src/main.py`

- [x] 🟩 **Step 2: Alembic migration**
  - [x] 🟩 Manual migration written (DB was stopped, autogenerate skipped)
  - [x] 🟩 Migration file: `m2n3o4p5q6r7_add_empresas_and_items.py`

### Phase 2: Frontend

- [x] 🟩 **Step 3: API client**
  - [x] 🟩 Create `frontend/src/lib/api/empresas.ts` with all CRUD functions

- [x] 🟩 **Step 4: Empresas page**
  - [x] 🟩 Create `frontend/src/app/(app)/empresas/page.tsx`
  - [x] 🟩 Implement full-width table with expandable rows (logo + name)
  - [x] 🟩 Implement expanded row: combined items list with type badges
  - [x] 🟩 Implement expanded row: collapsible empresa details section
  - [x] 🟩 Implement "Nueva Empresa" modal form
  - [x] 🟩 Implement "Nuevo Elemento" modal form (need/task)
  - [x] 🟩 Implement edit modals for empresa and items
  - [x] 🟩 Implement delete with confirmation
  - [x] 🟩 Implement search by empresa name
  - [x] 🟩 Add empty states

- [x] 🟩 **Step 5: Sidebar navigation**
  - [x] 🟩 Add "Empresas" to sidebar navGroups (Briefcase icon, under "Growth" group)

### Phase 3: Verification

- [x] 🟩 **Step 6: Test & verify**
  - [x] 🟩 Start backend and frontend locally
  - [x] 🟩 Test full CRUD flow in browser — ALL PASS
  - [x] 🟩 Verify no TypeScript errors (`npx tsc --noEmit`) — PASS
  - [x] 🟩 Verify no import leaks to other ERP modules — PASS (only auth + common)

---

## Technical Details

### Database Schema

```sql
-- empresas table
CREATE TABLE empresas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    logo_url VARCHAR(512),
    industry VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    rfc VARCHAR(13),
    razon_social VARCHAR(255),
    regimen_fiscal VARCHAR(100),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- empresa_items table (needs + tasks combined)
CREATE TABLE empresa_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    type VARCHAR(10) NOT NULL CHECK (type IN ('need', 'task')),
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'open',  -- open, in_progress, done
    priority VARCHAR(10),  -- low, medium, high (only for needs)
    due_date DATE,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/empresas` | List all empresas (with optional `?search=`) |
| POST | `/api/v1/empresas` | Create empresa |
| GET | `/api/v1/empresas/{id}` | Get empresa with its items |
| PATCH | `/api/v1/empresas/{id}` | Update empresa |
| DELETE | `/api/v1/empresas/{id}` | Delete empresa (cascades items) |
| POST | `/api/v1/empresas/{id}/items` | Create item (need or task) for empresa |
| PATCH | `/api/v1/empresas/items/{item_id}` | Update item |
| DELETE | `/api/v1/empresas/items/{item_id}` | Delete item |

### Backend Files

| File | Purpose |
|------|---------|
| `backend/src/empresas/__init__.py` | Package init |
| `backend/src/empresas/models.py` | `Empresa` + `EmpresaItem` SQLAlchemy models |
| `backend/src/empresas/schemas.py` | Pydantic request/response schemas |
| `backend/src/empresas/router.py` | FastAPI router with all endpoints |

### Frontend Files

| File | Purpose |
|------|---------|
| `frontend/src/lib/api/empresas.ts` | Axios API client |
| `frontend/src/app/(app)/empresas/page.tsx` | Empresas page component |

### Conventions Followed
- UUID primary keys (matches all existing models)
- `Mapped[Type]` with `mapped_column()` (SQLAlchemy 2.0 style)
- Pydantic `BaseModel` with `model_config = {"from_attributes": True}`
- Router uses `APIRouter(prefix="/empresas", tags=["empresas"])`
- Auth via `Depends(get_current_user)` on all endpoints
- Frontend uses `api.get/post/patch/delete` from shared axios client
- Toast notifications via `sonner`
- shadcn/ui components: Table, Dialog, Badge, Button, Input, Textarea, Select

---

## Generalization Check

- [x] No hardcoded industry-specific terms
- [x] "Empresa" is generic (company/enterprise)
- [x] "Need" and "Task" are generic work items
- [x] No industry-specific logic

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

- This module intentionally has zero coupling to other ERP modules. Only imports allowed: `src.common.database.Base`, `src.common.database.get_db`, `src.auth.dependencies.get_current_user`, `src.auth.models.User`
- Logo is a URL string field — no file upload. User can paste a URL to an image hosted elsewhere.
- Spanish labels throughout the UI (Empresas, Necesidades, Tareas, etc.)
