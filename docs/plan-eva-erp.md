# EVA Internal ERP — Implementation Plan

**Status:** Final
**Created:** 2026-02-19
**Authors:** Jose Pedro Gama, Claude
**Stack:** Next.js 15 + FastAPI + PostgreSQL (Supabase) — Standalone repo

---

## Company Context

**EVA (goeva.ai)** is an AI-powered customer engagement platform — SaaS B2B. AI agents that handle conversations across WhatsApp, Instagram, Messenger, and web, with a built-in CRM.

**Partners:**
- Jose Pedro Gama (co-founder)
- Gustavo Cermeno (co-founder)
- Both wear all hats — no fixed role split (product, sales, ops, everything)

**Current state:**
- 6-20 paying customers, acquired through personal network
- Pricing: Starter ($999 MXN/mo), Standard ($3,999), Pro ($9,999)
- Pre-salary — both bootstrapping without pay
- No formal tools — no spreadsheets, no Notion, no task tracker
- Currencies: MXN (customers) + USD (many vendor costs like OpenAI, Stripe, etc.)

**#1 pain point:** "We don't know what EVA costs to run each month."

**Known infrastructure costs:** ~$47 USD/mo (Koyeb $32, Supabase $15, Upstash $0.18)
**Other cost categories:** LLM APIs, domains, email, marketing, legal/accounting

---

## What We're Building

10 modules in a standalone ERP for EVA's internal operations:

| # | Module | Purpose |
|---|--------|---------|
| 1 | KPI Dashboard | At-a-glance company health — landing page |
| 2 | Finances | Income (Stripe sync) + expenses + P&L + invoices |
| 3 | Customer Registry | Stripe-synced customer records with LTV, churn |
| 4 | Credential Vault | Encrypted service/credential store with cost tracking |
| 5 | Kanban Tasks | Boards, columns, drag-and-drop task cards |
| 6 | Prospect CRM | Warm leads, referrals, follow-ups |
| 7 | Meeting Notes | Logs with action items that convert to tasks |
| 8 | Document Storage | Contracts, legal, brand assets |
| 9 | OKRs | Quarterly goals with auto-tracking from real metrics |
| 10 | AI Assistant | Natural language queries across all ERP data |

**Design:** Same branding as app.goeva.ai — colors, Tailwind + shadcn/ui, dark/light theme.
**Access:** Public with authentication — accessible from anywhere.
**Notifications:** In-app only (sidebar badge counters) — no email or WhatsApp notifications.
**API prefix:** All backend endpoints are under `/api/v1/` (e.g., `/api/v1/vault/credentials`).

---

## Architecture

```
eva-erp/
├── frontend/                   # Next.js 15 (App Router)
│   ├── src/
│   │   ├── app/
│   │   │   ├── (app)/          # Authenticated routes
│   │   │   │   ├── dashboard/  # KPI dashboard (landing page)
│   │   │   │   ├── finances/   # Income, expenses, P&L, invoices
│   │   │   │   ├── customers/  # Customer registry
│   │   │   │   ├── vault/      # Credential vault
│   │   │   │   ├── tasks/      # Kanban boards
│   │   │   │   ├── prospects/  # Prospect CRM
│   │   │   │   ├── meetings/   # Meeting notes
│   │   │   │   ├── documents/  # File storage
│   │   │   │   ├── okrs/       # Quarterly OKRs
│   │   │   │   ├── assistant/  # AI chat
│   │   │   │   └── settings/   # User profile, team, preferences
│   │   │   ├── (public)/       # Login page
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── ui/             # shadcn/ui base components
│   │   │   ├── layout/         # Sidebar, header, notification bell
│   │   │   └── [module]/       # Per-module components
│   │   ├── lib/
│   │   │   ├── api/            # Axios HTTP client + SWR hooks per module
│   │   │   ├── auth/           # JWT helpers, auth context
│   │   │   └── utils/          # Formatters, currency helpers
│   │   ├── types/              # TypeScript type definitions
│   │   └── styles/             # EVA brand tokens (copied from app.goeva.ai)
│   ├── package.json
│   └── tailwind.config.ts
├── backend/
│   ├── src/
│   │   ├── main.py             # FastAPI app + lifespan + /api/v1 router
│   │   ├── auth/               # JWT auth, login, middleware
│   │   ├── users/              # User CRUD, invites, team management
│   │   ├── notifications/      # In-app notification system (cross-cutting)
│   │   ├── finances/           # Income + expenses + invoices + P&L
│   │   ├── customers/          # Customer registry
│   │   ├── vault/              # Encrypted credential storage
│   │   ├── tasks/              # Kanban boards, columns, tasks
│   │   ├── prospects/          # Prospect CRM + interactions
│   │   ├── meetings/           # Meeting notes + action items
│   │   ├── documents/          # File storage + folders
│   │   ├── okrs/               # Objectives + key results
│   │   ├── kpis/               # KPI calculations + snapshots
│   │   ├── assistant/          # AI chat with tool calling
│   │   ├── integrations/
│   │   │   ├── stripe_sync.py  # Stripe data sync service
│   │   │   └── eva_db.py       # Read-only EVA DB connection
│   │   ├── common/
│   │   │   ├── database.py     # SQLAlchemy async setup (asyncpg driver)
│   │   │   ├── config.py       # Pydantic settings
│   │   │   ├── encryption.py   # AES-256-GCM vault encryption
│   │   │   ├── currency.py     # MXN/USD conversion utilities
│   │   │   ├── scheduler.py    # APScheduler for periodic tasks
│   │   │   └── middleware/     # CORS, logging, auth
│   │   └── models/             # SQLAlchemy ORM models
│   ├── alembic/                # Database migrations
│   ├── seeds/
│   │   ├── 01_users.py         # Jose Pedro + Gustavo (run first)
│   │   ├── 02_boards.py        # Default Kanban boards + columns
│   │   ├── 03_vault.py         # EVA's known services
│   │   ├── 04_exchange_rates.py # USD/MXN rate
│   │   ├── 05_folders.py       # Default document folders
│   │   ├── 06_okrs.py          # Example Q1 objectives
│   │   └── 07_dev_fixtures.py  # Dev-only: sample customers, prospects, expenses, meetings, KPI snapshots
│   ├── requirements.txt
│   └── .env.example
└── docs/
    └── plan-eva-erp.md         # This file
```

**Data fetching pattern:** Axios as the HTTP client, SWR for cache/revalidation (same pattern as EVA). SWR hooks call Axios service methods under the hood.

**Background tasks:** APScheduler (lightweight, no Redis required) for periodic jobs:
- Stripe sync every 6 hours
- KPI snapshot on 1st of each month
- OKR auto-metric refresh every hour

**Cache:** In-memory dict with TTL (simple, fine for 2-5 users). No Redis needed for the ERP — it resets on server restart which is acceptable.

---

## Phase 1: Foundation + Auth + Layout

**Goal:** Get the app running with auth, navigation, notifications infrastructure, and the shell for all modules.
**Duration:** ~2 sessions

### 1.1 Project Scaffold

- [ ] Initialize Next.js 15 with TypeScript, Tailwind, shadcn/ui
- [ ] Initialize FastAPI backend with SQLAlchemy 2.0 (async, asyncpg driver), Alembic, Pydantic v2
- [ ] Set up PostgreSQL (new Supabase project or local Docker)
- [ ] Dev scripts: `make dev` (runs frontend + backend), `make migrate`, `make seed`
- [ ] Configure `.env.example` with all required variables
- [ ] Copy EVA brand tokens (colors, fonts) from app.goeva.ai frontend

### 1.2 Authentication & Users

**Models:**
- [ ] `User`:
  ```
  id (UUID PK), email (unique), name, password_hash,
  role (admin/member), avatar_url (nullable), is_active (bool),
  created_at, updated_at
  ```

**Endpoints (all under `/api/v1/auth/` and `/api/v1/users/`):**
- [ ] `POST /api/v1/auth/login` — Email/password login → set JWT cookies
- [ ] `POST /api/v1/auth/refresh` — Refresh access token
- [ ] `POST /api/v1/auth/logout` — Clear cookies
- [ ] `GET /api/v1/auth/me` — Current user profile
- [ ] `PATCH /api/v1/auth/me` — Update profile (name, avatar)
- [ ] `POST /api/v1/auth/change-password` — Change own password
- [ ] `GET /api/v1/users` — List team members (admin only)
- [ ] `POST /api/v1/users/invite` — Invite user by email (admin only, creates user with temp password)
- [ ] `PATCH /api/v1/users/{id}` — Update user role or deactivate (admin only)
- [ ] `DELETE /api/v1/users/{id}` — Deactivate user (soft delete, admin only)

**JWT:** Access token (15 min) + refresh token (7 days), HTTP-only cookies, custom implementation (no Supabase Auth).

**Auth middleware:** Verify JWT on all `/api/v1/*` routes except `/api/v1/auth/login` and `/api/v1/auth/refresh`.

**Frontend:**
- [ ] Login page: email + password form, EVA logo
- [ ] Settings page (`/settings`): profile editing, password change
- [ ] Settings > Team (`/settings/team`): list members, invite new (admin only)

**Seed:** Jose Pedro (admin) + Gustavo (admin)

### 1.3 Notification System (Cross-Cutting)

Defined here in Phase 1 because it's used by every module that follows.

**Model:**
- [ ] `Notification`:
  ```
  id (UUID PK), user_id (FK → User), type (varchar),
  title, body, link (URL to navigate to),
  read (bool, default false),
  created_at
  ```

**Notification types and triggers (implemented per phase as modules are built):**

| Module | Trigger | Type | When |
|--------|---------|------|------|
| Tasks | Task assigned to you | `task_assigned` | Phase 2 |
| Tasks | Task due tomorrow | `task_due_soon` | Phase 2 |
| Tasks | Task overdue | `task_overdue` | Phase 2 |
| Tasks | Comment on your task | `task_comment` | Phase 2 |
| Vault | Credential accessed by someone else | `vault_access` | Phase 2 |
| Finances | Stripe sync completed | `stripe_sync_done` | Phase 3 |
| Finances | New payment received | `payment_received` | Phase 3 |
| Customers | New customer signed up | `customer_new` | Phase 3 |
| Customers | Customer churned | `customer_churned` | Phase 3 |
| Prospects | Follow-up due today | `prospect_followup_due` | Phase 5 |
| Prospects | Follow-up overdue | `prospect_followup_overdue` | Phase 5 |
| Meetings | Meeting in 1 hour | `meeting_upcoming` | Phase 5 |
| Meetings | Action item due | `meeting_action_due` | Phase 5 |
| OKRs | Key result at risk | `okr_at_risk` | Phase 6 |

**Endpoints:**
- [ ] `GET /api/v1/notifications` — List notifications (paginated, filter: read/unread)
- [ ] `GET /api/v1/notifications/unread-count` — Badge counter number
- [ ] `PATCH /api/v1/notifications/{id}/read` — Mark one as read
- [ ] `POST /api/v1/notifications/mark-all-read` — Mark all as read
- [ ] `DELETE /api/v1/notifications/{id}` — Delete notification

**Frontend:**
- [ ] Bell icon in header with unread count badge (red dot with number)
- [ ] Click bell → dropdown with recent notifications
- [ ] Each notification: icon, title, body, time ago, click → navigate to link
- [ ] "Mark all as read" button
- [ ] Polling: fetch unread count every 30 seconds

### 1.4 Layout & Navigation

- [ ] App layout with collapsible sidebar (same style as app.goeva.ai)
- [ ] Sidebar sections with icons:

  | Section | Icon | Route | Built In |
  |---------|------|-------|----------|
  | Dashboard | LayoutDashboard | `/dashboard` | Phase 4 |
  | Finances | DollarSign | `/finances` | Phase 3 |
  | Customers | Users | `/customers` | Phase 3 |
  | Vault | Lock | `/vault` | Phase 2 |
  | Tasks | CheckSquare | `/tasks` | Phase 2 |
  | Prospects | Target | `/prospects` | Phase 5 |
  | Meetings | Calendar | `/meetings` | Phase 5 |
  | Documents | FolderOpen | `/documents` | Phase 5 |
  | OKRs | Trophy | `/okrs` | Phase 6 |
  | AI Assistant | Sparkles | `/assistant` | Phase 7 |
  | Settings | Settings | `/settings` | Phase 1 |

- [ ] Unbuilt modules show "Coming Soon" placeholder
- [ ] Top header: user avatar dropdown (profile, logout), notification bell
- [ ] Dark/light theme toggle (persisted in localStorage)
- [ ] Responsive: desktop-first, usable on tablet

**Deliverable:** A running app with login, navigation, notifications infrastructure, team management, and the skeleton for every module.

---

## Phase 2: Credential Vault + Kanban Tasks

**Goal:** Answer the #1 pain ("what does EVA cost?") with the vault, plus task coordination.
**Duration:** ~3 sessions

### 2.1 Credential Vault

**Why first:** Every service has a cost. Cataloging credentials = cataloging costs = instant visibility.

**Encryption Architecture:**
- Master password → PBKDF2 (100k iterations, random salt) → 256-bit derived key
- Each credential's sensitive fields encrypted individually with AES-256-GCM
- Each encrypted field stores its ciphertext + nonce together as a single blob (nonce prepended to ciphertext — standard AES-GCM pattern, no separate nonce column needed)
- Master password verified via bcrypt hash (stored in VaultConfig)
- Derived key held in server-side in-memory session (dict keyed by user_id with TTL)
- Auto-lock after 30 minutes of inactivity (TTL expiry)
- On server restart, all vaults auto-lock (users re-enter master password)

**Backend Models:**
- [ ] `VaultConfig`:
  ```
  id (UUID PK), user_id (FK → User, unique),
  master_password_hash (bcrypt), salt (bytes),
  created_at
  ```
- [ ] `Credential`:
  ```
  id (UUID PK), name, category (CredentialCategory enum),
  url (nullable), login_url (nullable),
  username_encrypted (bytes, nullable — ciphertext includes nonce),
  password_encrypted (bytes, nullable),
  api_keys_encrypted (bytes, nullable — JSON string encrypted),
  notes_encrypted (bytes, nullable),
  monthly_cost (decimal, nullable),
  cost_currency (varchar: 'MXN' or 'USD'),
  monthly_cost_mxn (decimal, auto-calculated from cost + exchange rate),
  billing_cycle (monthly/annual/one-time/usage-based),
  who_has_access (UUID[] — PostgreSQL array of user IDs),
  is_deleted (bool, default false — soft delete),
  created_by (FK → User), created_at, updated_at
  ```
- [ ] `CredentialCategory` enum:
  ```
  infrastructure    — Koyeb, Supabase, Upstash, Vercel, Redis
  ai_llm           — OpenAI, Anthropic, Groq, Tavily, Langsmith
  communication    — Meta (WhatsApp/Messenger/Instagram), SendGrid
  payment          — Stripe, Facturapi
  dev_tools        — GitHub, Context7, domain registrar
  marketing        — Ads, analytics, social media tools
  legal_accounting — Accountant, SAT tools, incorporation
  other
  ```
- [ ] `VaultAuditLog`:
  ```
  id (UUID PK), user_id (FK → User),
  credential_id (FK → Credential),
  action (view/edit/create/delete),
  ip_address (varchar), created_at
  ```

**Notification triggers:** `vault_access` — when a user other than the creator views a credential.

**Backend Endpoints:**
- [ ] `POST /api/v1/vault/setup` — Create master password (first time)
- [ ] `POST /api/v1/vault/unlock` — Verify master password, start session
- [ ] `POST /api/v1/vault/lock` — End vault session
- [ ] `GET /api/v1/vault/status` — Setup status + lock state
- [ ] `GET /api/v1/vault/credentials` — List all (metadata + cost, NO secrets)
- [ ] `POST /api/v1/vault/credentials` — Create (encrypts sensitive fields)
- [ ] `GET /api/v1/vault/credentials/{id}` — Full detail with decrypted secrets (requires unlocked)
- [ ] `PATCH /api/v1/vault/credentials/{id}` — Update
- [ ] `DELETE /api/v1/vault/credentials/{id}` — Soft delete
- [ ] `GET /api/v1/vault/cost-summary` — Totals by category, split by currency (USD total, MXN total, combined MXN-equivalent total)
- [ ] `GET /api/v1/vault/audit-log` — Access history (paginated)

**Frontend:**
- [ ] Vault unlock screen — master password input, "Set up vault" flow on first visit
- [ ] Credential list (`/vault`):
  - Summary cards at top: Total monthly (MXN-equivalent), USD services total, MXN services total, Service count
  - Cost by category breakdown (horizontal bar chart)
  - Table: name, category badge, URL link, monthly cost (original currency), billing cycle, who has access (avatars)
  - Search bar + category filter
  - Sort by: name, cost (high→low), date added
- [ ] Credential detail modal:
  - View/edit all fields
  - Show/hide toggle for password and API keys (eye icon)
  - Copy-to-clipboard buttons on username, password, API keys, URL
  - Cost fields: amount, currency, billing cycle
  - Access list: checkboxes per team member
  - Audit log tab: who viewed/edited and when
- [ ] Add credential form (slide-out panel)
- [ ] Auto-lock indicator in sidebar (lock icon turns red when locked)

**Seed Data (EVA's known services):**
- [ ] Infrastructure: Koyeb API ($21.43 USD/mo), Koyeb Worker ($10.71 USD/mo), Supabase ($15 USD/mo), Upstash Redis ($0.18 USD/mo), Vercel (free)
- [ ] AI/LLM: OpenAI (usage-based USD), Anthropic (usage-based USD), Groq (usage-based USD), Tavily, Langsmith
- [ ] Communication: Meta WhatsApp Business, SendGrid
- [ ] Payment: Stripe (% per transaction), Facturapi
- [ ] Dev Tools: GitHub, Context7, goeva.ai domain

### 2.2 Kanban Tasks

**Backend Models:**
- [ ] `Board`:
  ```
  id (UUID PK), name, slug (unique), description (nullable),
  position (int), created_by (FK → User), created_at, updated_at
  ```
- [ ] `Column`:
  ```
  id (UUID PK), board_id (FK → Board),
  name, position (int), color (hex string),
  created_at
  ```
- [ ] `Task`:
  ```
  id (UUID PK), column_id (FK → Column), board_id (FK → Board),
  title, description (markdown text, nullable),
  assignee_id (FK → User, nullable),
  priority (low/medium/high/urgent),
  due_date (date, nullable), labels (text[] — PostgreSQL array),
  position (float — for ordering within column),
  source_meeting_id (FK → Meeting, nullable — set when created from meeting action item),
  created_by (FK → User), created_at, updated_at
  ```
- [ ] `TaskComment`:
  ```
  id (UUID PK), task_id (FK → Task),
  user_id (FK → User), content (text),
  created_at
  ```
- [ ] `TaskActivity`:
  ```
  id (UUID PK), task_id (FK → Task),
  user_id (FK → User), action (varchar),
  old_value (text, nullable), new_value (text, nullable),
  created_at
  ```

**Notification triggers:**
- `task_assigned` — when assignee_id changes to a different user
- `task_due_soon` — checked daily, fires for tasks due tomorrow
- `task_overdue` — checked daily, fires for tasks past due_date
- `task_comment` — when someone comments on a task assigned to you

**Backend Endpoints:**
- [ ] `GET /api/v1/boards` — List boards
- [ ] `POST /api/v1/boards` — Create board (with default columns)
- [ ] `GET /api/v1/boards/{id}` — Board with columns + tasks (full board state)
- [ ] `PATCH /api/v1/boards/{id}` — Update board (name, description)
- [ ] `DELETE /api/v1/boards/{id}` — Delete board (cascades columns + tasks)
- [ ] `POST /api/v1/boards/{id}/columns` — Add column
- [ ] `PATCH /api/v1/columns/{id}` — Update column (name, position, color)
- [ ] `DELETE /api/v1/columns/{id}` — Delete column (must move/delete tasks first)
- [ ] `POST /api/v1/tasks` — Create task (requires board_id, column_id)
- [ ] `GET /api/v1/tasks/{id}` — Task detail with comments + activity
- [ ] `PATCH /api/v1/tasks/{id}` — Update task fields
- [ ] `DELETE /api/v1/tasks/{id}` — Delete task
- [ ] `POST /api/v1/tasks/{id}/move` — Move to column + position (drag-and-drop)
- [ ] `POST /api/v1/tasks/{id}/comments` — Add comment
- [ ] `GET /api/v1/tasks/my-tasks` — Tasks assigned to current user (cross-board)
- [ ] `GET /api/v1/tasks/overdue` — All overdue tasks

**Frontend:**
- [ ] Board list page (`/tasks`) — cards showing board name, task count, last activity
- [ ] Kanban board (`/tasks/[slug]`):
  - Columns rendered horizontally with scroll
  - Drag-and-drop via `@dnd-kit/core` + `@dnd-kit/sortable` (tasks between columns, column reordering)
  - Task cards: title, assignee avatar, priority dot (Low=gray, Medium=blue, High=orange, Urgent=red), due date, label chips
  - Overdue tasks highlighted with red border
  - Click "+" at bottom of column to add task inline
  - Click card → opens detail slide-out panel
- [ ] Task detail panel:
  - Editable title (click-to-edit)
  - Description with Tiptap rich text editor
  - Assignee dropdown
  - Priority selector
  - Due date picker
  - Labels: type to add, click to remove
  - If `source_meeting_id` exists: "Created from meeting: [Meeting Title]" link
  - Comments thread
  - Activity log
- [ ] Board settings: rename, manage columns
- [ ] "My Tasks" view: cross-board list of tasks assigned to me, sorted by due date

**Seed Data:**
- [ ] Board "Product Development" — columns: Backlog, To Do, In Progress, Review, Done
- [ ] Board "Sales & Growth" — columns: Ideas, Planning, Executing, Done
- [ ] Board "Operations" — columns: To Do, In Progress, Done

**Deliverable:** Full cost visibility via vault + working Kanban for daily coordination.

---

## Phase 3: Finances + Customer Registry

**Goal:** Real revenue data from Stripe, full expense tracking with partner contributions, invoices, and customer records.
**Duration:** ~3-4 sessions

### 3.1 Currency System

- [ ] `ExchangeRate` model:
  ```
  id (UUID PK), from_currency (varchar), to_currency (varchar),
  rate (decimal), effective_date (date), source (manual/api),
  created_at
  ```
- [ ] Convention: every monetary field has three columns:
  - `amount` — value in original currency
  - `currency` — 'MXN' or 'USD'
  - `amount_mxn` — auto-calculated MXN equivalent (if currency is MXN, same as amount; if USD, amount × rate)
- [ ] Endpoint: `GET /api/v1/exchange-rates/current` — current rate
- [ ] Endpoint: `PATCH /api/v1/exchange-rates` — update rate (admin only)
- [ ] Frontend formatter: `$21.43 USD (~$429 MXN)` or `$3,999 MXN`
- [ ] Seed: 1 USD = 20 MXN (updated manually each month or on-demand)

### 3.2 Income Tracking (Stripe Sync)

**Backend Models:**
- [ ] `IncomeEntry`:
  ```
  id (UUID PK), source (stripe/manual),
  stripe_payment_id (varchar, nullable, unique),
  stripe_invoice_id (varchar, nullable),
  customer_id (FK → Customer, nullable),
  description (text), amount (decimal), currency (varchar),
  amount_mxn (decimal, auto-calculated),
  category (IncomeCategory enum), date (date),
  is_recurring (bool),
  metadata_json (jsonb, nullable — extra Stripe data),
  created_by (FK → User, nullable — null for Stripe-synced),
  created_at
  ```
- [ ] `IncomeCategory` enum: `subscription, addon, consulting, custom_deal, refund, other`

**Stripe Sync Service:**
- [ ] Connect to EVA's Stripe account using `EVA_STRIPE_SECRET_KEY` (read-only operations only)
- [ ] Sync logic:
  - Pull `PaymentIntent` (status=succeeded) → create IncomeEntry per payment
  - Pull `Subscription` → map to customer plan tier and MRR
  - Pull `Refund` → create IncomeEntry with negative amount, category=refund
  - Deduplication via `stripe_payment_id` unique constraint
- [ ] Sync modes:
  - Manual: `POST /api/v1/income/sync-stripe` (last 30 days)
  - Full historical: `POST /api/v1/income/sync-stripe?full=true`
  - Scheduled: APScheduler runs sync every 6 hours
- [ ] MRR calculation: sum of active monthly subscription amounts (annuals ÷ 12)

**Notification triggers:** `stripe_sync_done` — after sync completes (to all admins), `payment_received` — for each new payment > $500 MXN

**Backend Endpoints:**
- [ ] `GET /api/v1/income` — List (paginated, filter: date range, source, category, customer_id)
- [ ] `POST /api/v1/income` — Manual entry
- [ ] `PATCH /api/v1/income/{id}` — Edit manual entry only (Stripe entries read-only)
- [ ] `DELETE /api/v1/income/{id}` — Delete manual entry only
- [ ] `POST /api/v1/income/sync-stripe` — Trigger sync
- [ ] `GET /api/v1/income/summary` — MRR, ARR, totals by period, MoM growth %
- [ ] `GET /api/v1/income/stripe-status` — Connection OK, last sync time, synced record count

### 3.3 Expense Tracking (with Partner Contributions)

**Backend Models:**
- [ ] `Expense`:
  ```
  id (UUID PK), name, description (text, nullable),
  amount (decimal), currency (varchar),
  amount_mxn (decimal, auto-calculated),
  category (ExpenseCategory enum), vendor (varchar, nullable),
  paid_by (FK → User — which partner fronted the money),
  is_recurring (bool), recurrence (monthly/annual/quarterly/one-time),
  date (date), receipt_url (varchar, nullable),
  vault_credential_id (FK → Credential, nullable — link to vault entry),
  created_by (FK → User), created_at, updated_at
  ```
- [ ] `ExpenseCategory` enum:
  ```
  infrastructure, ai_apis, communication, payment_fees,
  domains_hosting, marketing, legal_accounting, contractors,
  office, software_tools, other
  ```

**Backend Endpoints:**
- [ ] `GET /api/v1/expenses` — List (paginated, filter: date, category, paid_by, recurring)
- [ ] `POST /api/v1/expenses` — Create
- [ ] `PATCH /api/v1/expenses/{id}` — Update
- [ ] `DELETE /api/v1/expenses/{id}` — Delete
- [ ] `GET /api/v1/expenses/summary` — By category, by person, monthly trend, recurring total
- [ ] `POST /api/v1/expenses/import-from-vault` — Auto-create recurring expenses from vault service costs
- [ ] `GET /api/v1/expenses/partner-summary` — Total paid by each partner (Jose Pedro: $X, Gustavo: $Y)

### 3.4 Invoices

**Backend Models:**
- [ ] `Invoice`:
  ```
  id (UUID PK), invoice_number (varchar, auto-generated: EVA-2026-001),
  customer_id (FK → Customer, nullable),
  customer_name (varchar — denormalized for non-registered customers),
  customer_email (varchar, nullable),
  description (text), line_items_json (jsonb — [{description, quantity, unit_price, total}]),
  subtotal (decimal), tax (decimal, nullable), total (decimal),
  currency (varchar), total_mxn (decimal, auto-calculated),
  status (draft/sent/paid/overdue/cancelled),
  issue_date (date), due_date (date), paid_date (date, nullable),
  notes (text, nullable),
  created_by (FK → User), created_at, updated_at
  ```

**Backend Endpoints:**
- [ ] `GET /api/v1/invoices` — List (filter: status, customer, date range)
- [ ] `POST /api/v1/invoices` — Create invoice
- [ ] `GET /api/v1/invoices/{id}` — Detail
- [ ] `PATCH /api/v1/invoices/{id}` — Update (status, fields)
- [ ] `DELETE /api/v1/invoices/{id}` — Delete (draft only)
- [ ] `GET /api/v1/invoices/{id}/pdf` — Generate PDF for download/email

### 3.5 Cash Balance (for Runway Calculation)

- [ ] `CashBalance` model:
  ```
  id (UUID PK), amount (decimal), currency (varchar),
  amount_mxn (decimal), date (date), notes (text, nullable),
  updated_by (FK → User), created_at
  ```
- [ ] Endpoint: `GET /api/v1/cash-balance/current` — Latest entry
- [ ] Endpoint: `POST /api/v1/cash-balance` — Update cash balance (manual entry)
- [ ] Runway = current cash balance / monthly burn rate

### 3.6 P&L Dashboard (Frontend)

**`/finances` with sub-navigation tabs: Overview | Income | Expenses | Invoices**

- [ ] **Overview tab:**
  - KPI cards: MRR, Total Revenue (period), Total Expenses (period), Net Profit/Loss, Burn Rate, Runway (months)
  - P&L table: monthly rows, Revenue - Expenses = Profit/Loss
  - Revenue trend line chart (12 months)
  - Expense breakdown stacked bar chart (by category)
  - Partner contribution summary: Jose Pedro total, Gustavo total
  - Cash balance card with "Update" button
- [ ] **Income tab:**
  - Table: date, description, amount (original + MXN), source badge (Stripe/Manual), category, customer
  - "Sync from Stripe" button with last sync timestamp and status
  - "Add Manual Entry" form
  - Filters: date range, category, source
- [ ] **Expenses tab:**
  - Table: date, name, amount (original + MXN), category, vendor, paid by (avatar), recurring badge
  - "Add Expense" button
  - "Import from Vault" button
  - Filters: date range, category, paid by, recurring only
- [ ] **Invoices tab:**
  - Table: invoice #, customer, total, status badge, issue date, due date
  - "New Invoice" button
  - Invoice editor: line items, customer selector, dates, notes
  - Status workflow: draft → sent → paid (or overdue/cancelled)
  - Download PDF button

### 3.7 Customer Registry

**Backend Models:**
- [ ] `Customer`:
  ```
  id (UUID PK), company_name, contact_name, contact_email (nullable),
  contact_phone (nullable), industry (nullable), website (nullable),
  plan_tier (starter/standard/pro/custom, nullable),
  mrr (decimal, nullable), mrr_currency (varchar, default 'MXN'),
  mrr_mxn (decimal, nullable — auto-calculated),
  arr (decimal, nullable — derived: mrr × 12, same currency as mrr),
  billing_interval (monthly/annual, nullable),
  signup_date (date, nullable),
  status (active/churned/paused/trial),
  churn_date (date, nullable), churn_reason (text, nullable),
  stripe_customer_id (varchar, nullable, unique),
  lifetime_value (decimal, nullable),
  lifetime_value_currency (varchar, default 'MXN'),
  lifetime_value_mxn (decimal, nullable),
  referral_source (text, nullable — who referred them, personal network context),
  prospect_id (FK → Prospect, nullable — if converted from prospect),
  notes (text, nullable), tags (text[] — PostgreSQL array),
  created_by (FK → User, nullable), created_at, updated_at
  ```

**Note on payments:** `GET /api/v1/customers/{id}/payments` returns IncomeEntry records filtered by `customer_id`. No separate payment model needed — IncomeEntry serves this purpose.

**Stripe Sync:**
- [ ] Pull Stripe customers → match/create local Customer by `stripe_customer_id`
- [ ] Map subscription → plan_tier, mrr, billing_interval, status
- [ ] Detect churn: canceled subscription → status=churned, set churn_date
- [ ] Calculate LTV: sum of all IncomeEntry amounts for this customer

**Notification triggers:** `customer_new` (new customer from Stripe sync), `customer_churned` (subscription canceled)

**Backend Endpoints:**
- [ ] `GET /api/v1/customers` — List (filter: status, plan, search)
- [ ] `POST /api/v1/customers` — Manual create
- [ ] `GET /api/v1/customers/{id}` — Detail
- [ ] `PATCH /api/v1/customers/{id}` — Update (notes, tags, churn reason, etc.)
- [ ] `GET /api/v1/customers/summary` — Count, MRR, churn rate, ARPU
- [ ] `GET /api/v1/customers/{id}/payments` — IncomeEntries for this customer
- [ ] `POST /api/v1/customers/sync-stripe` — Sync from Stripe

**Note:** No `DELETE /customers` — customer records are never deleted, only marked as churned.

**Frontend (`/customers`):**
- [ ] Summary cards: Total Customers, MRR (MXN), ARPU, Churn Rate (quarterly)
- [ ] Customer table: company, contact, plan badge, MRR, status badge, signup date, referral source
- [ ] Customer detail page (`/customers/[id]`):
  - Company info, contact details
  - Subscription details (plan, interval, MRR with currency)
  - Payment history timeline (from IncomeEntry)
  - Referral source (who introduced them)
  - If converted from prospect: link to original prospect
  - Notes + tags
  - LTV display
  - "Mark as Churned" button with reason field

**Deliverable:** Complete financial picture + customer database synced with Stripe.

---

## Phase 4: KPI Dashboard

**Goal:** Executive dashboard as the landing page.
**Duration:** ~2 sessions

### 4.1 KPI Engine

**Backend Models:**
- [ ] `KPISnapshot`:
  ```
  id (UUID PK), period (varchar: 'YYYY-MM', unique),
  mrr (decimal), mrr_currency (varchar, default 'MXN'),
  arr (decimal),
  mrr_growth_pct (decimal — month-over-month),
  total_revenue (decimal), total_revenue_currency (varchar, default 'MXN'),
  total_expenses (decimal), total_expenses_mxn (decimal),
  net_profit (decimal),
  burn_rate (decimal — monthly recurring expenses in MXN),
  runway_months (decimal — cash / burn_rate),
  total_customers (int), new_customers (int), churned_customers (int),
  arpu (decimal — MRR / total_customers),
  ltv (decimal), cac (decimal),
  open_tasks (int), overdue_tasks (int),
  prospects_in_pipeline (int), prospects_won (int),
  data_json (jsonb — extensible for future metrics),
  created_at
  ```
- [ ] All financial KPIs are stored in MXN (converted at snapshot time).

**KPI Calculation Service:**
- [ ] **Revenue:** MRR (from Customer.mrr_mxn sum), ARR (MRR×12), MoM growth %
- [ ] **Customers:** total active, new this month (signup_date), churned (churn_date), ARPU (MRR / count)
- [ ] **Financial:** total expenses (Expense.amount_mxn sum), burn rate (recurring expenses/mo), runway (CashBalance / burn), gross margin ((revenue - COGS) / revenue)
- [ ] **Unit economics:** CAC (marketing expenses / new customers), LTV (avg revenue/customer × avg lifespan), LTV/CAC
- [ ] **Operational:** open tasks (not in "Done" column), overdue tasks (past due_date), prospects in pipeline (status not won/lost), follow-ups due today
- [ ] **Product** (from EVA DB): active workspaces, monthly messages sent, active agents

**Cache:** In-memory with 1-hour TTL.
**Monthly cron:** APScheduler saves KPISnapshot on 1st of each month.

### 4.2 EVA DB Connection (Read-Only)

- [ ] Separate SQLAlchemy connection via `EVA_DATABASE_URL` (read-only credentials)
- [ ] Queries: active accounts count, monthly messages, active agents, monthly conversations
- [ ] Fail gracefully: if EVA DB is unreachable, show "N/A" for product metrics

**Endpoints:**
- [ ] `GET /api/v1/kpis/current` — All current KPI values (live calculation)
- [ ] `GET /api/v1/kpis/history?months=12` — Monthly snapshots for charts
- [ ] `GET /api/v1/kpis/product` — Product metrics from EVA DB
- [ ] `POST /api/v1/kpis/snapshot` — Force a snapshot now

### 4.3 Dashboard Frontend (`/dashboard`)

This is the landing page after login.

- [ ] **Top row — Key number cards:** MRR (with MoM % arrow), Active Customers, Burn Rate/mo, Runway (months), Net Profit/Loss (this month)
- [ ] **Charts row:** Revenue vs Expenses (dual line, 12 months), Customer growth (bar: new vs churned)
- [ ] **Middle row:** Expense donut chart (by category), Partner contributions (Jose Pedro vs Gustavo)
- [ ] **Bottom row — Quick links:** Overdue tasks (count + link), Follow-ups due today, Recent customer events, Upcoming meetings
- [ ] Period selector: 30d | 90d | 6mo | 1yr | Custom
- [ ] Charts: **Recharts** library

**Seed Data:** `07_dev_fixtures.py` includes 6-12 months of historical KPISnapshot records for chart testing.

**Deliverable:** One page to see EVA's financial, customer, and operational health.

---

## Phase 5: Prospect CRM + Meetings + Documents

**Goal:** Sales pipeline (focused on warm network), meeting logs, and document storage.
**Duration:** ~3 sessions

### 5.1 Prospect CRM

**Context:** EVA's customers come from personal network. The CRM emphasizes warm introductions, who referred whom, and follow-up discipline.

**Backend Models:**
- [ ] `Prospect`:
  ```
  id (UUID PK), company_name, website (nullable), industry (nullable),
  contact_name, contact_email (nullable),
  contact_phone (nullable), contact_role (nullable),
  status (ProspectStatus enum), source (ProspectSource enum),
  referred_by (text, nullable — who made the introduction),
  estimated_plan (starter/standard/pro, nullable),
  estimated_mrr (decimal, nullable),
  estimated_mrr_currency (varchar, default 'MXN'),
  estimated_mrr_mxn (decimal, nullable — auto-calculated),
  notes (text, nullable),
  next_follow_up (date, nullable),
  assigned_to (FK → User, nullable),
  tags (text[], nullable), lost_reason (text, nullable),
  converted_to_customer_id (FK → Customer, nullable — set on conversion),
  created_by (FK → User), created_at, updated_at
  ```
- [ ] `ProspectStatus` enum: `identified, contacted, interested, demo_scheduled, demo_done, proposal_sent, negotiating, won, lost`
- [ ] `ProspectSource` enum: `personal_network, referral, linkedin, inbound_website, event, partner, cold_outreach, other`
- [ ] `ProspectInteraction`:
  ```
  id (UUID PK), prospect_id (FK → Prospect),
  type (call/email/whatsapp/meeting/demo/note),
  summary (text), date (date),
  created_by (FK → User), created_at
  ```

**Notification triggers:** `prospect_followup_due` (daily check for today's follow-ups), `prospect_followup_overdue` (daily check for past follow-ups)

**Backend Endpoints:**
- [ ] CRUD: `GET/POST /api/v1/prospects`, `GET/PATCH/DELETE /api/v1/prospects/{id}`
- [ ] `GET /api/v1/prospects/pipeline` — Grouped by status (for pipeline view)
- [ ] `POST /api/v1/prospects/{id}/interactions` — Log interaction
- [ ] `GET /api/v1/prospects/{id}/interactions` — History
- [ ] `GET /api/v1/prospects/due-followups` — Due today or overdue
- [ ] `PATCH /api/v1/prospects/{id}/status` — Change status
- [ ] `POST /api/v1/prospects/{id}/convert` — Won → creates Customer (copies fields, sets `converted_to_customer_id` on prospect, sets `prospect_id` on customer)
- [ ] `GET /api/v1/prospects/summary` — Count by status, total estimated pipeline value

**Frontend (`/prospects`):**
- [ ] Toggle between table view and pipeline (Kanban by status)
- [ ] Pipeline view: columns by status, cards with company name, estimated MRR, next follow-up
- [ ] Table view: company, contact, status badge, source, referred by, next follow-up, assigned to
- [ ] Sidebar badge: count of follow-ups due today
- [ ] Prospect detail page:
  - Company + contact info
  - Status selector
  - Source + "Referred by" field
  - Estimated plan + MRR (with currency)
  - Interaction timeline (quick-add form: type dropdown + summary)
  - Next follow-up date
  - "Convert to Customer" button (when status=won)
  - "Mark as Lost" button (with reason)
  - If converted: "Converted to: [Customer Name]" link

### 5.2 Meeting Notes

**Backend Models:**
- [ ] `Meeting`:
  ```
  id (UUID PK), title, date (datetime), duration_minutes (int, nullable),
  type (internal/prospect/customer/partner),
  attendees (text[] — names, not just user IDs, for external attendees),
  notes_markdown (text, nullable),
  action_items_json (jsonb — array of ActionItem objects),
  prospect_id (FK → Prospect, nullable),
  customer_id (FK → Customer, nullable),
  created_by (FK → User), created_at, updated_at
  ```
- [ ] `action_items_json` structure:
  ```json
  [
    {
      "description": "Send proposal to Acme Corp",
      "assignee_id": "uuid-or-null",
      "due_date": "2026-03-01",
      "completed": false,
      "linked_task_id": "uuid-or-null"
    }
  ]
  ```

**Notification triggers:** `meeting_upcoming` (1 hour before meeting.date), `meeting_action_due` (daily check for action items due today)

**Backend Endpoints:**
- [ ] CRUD: `GET/POST /api/v1/meetings`, `GET/PATCH/DELETE /api/v1/meetings/{id}`
- [ ] `GET /api/v1/meetings/upcoming` — Future meetings
- [ ] `GET /api/v1/meetings/recent` — Last 30 days
- [ ] `PATCH /api/v1/meetings/{id}/action-items/{index}` — Toggle complete, update
- [ ] `POST /api/v1/meetings/{id}/action-items/{index}/create-task` — Creates Kanban task with `source_meeting_id` set, updates `linked_task_id` in action item
- [ ] `GET /api/v1/meetings/search?q=` — Full-text search (PostgreSQL tsvector on notes_markdown)

**Frontend (`/meetings`):**
- [ ] Meeting list: date, title, type badge, attendees, action items (done/total)
- [ ] Search bar (full-text)
- [ ] Filter by type, date range
- [ ] Meeting editor:
  - Title, date+time, duration, type selector
  - Attendees (tag input — free text for external names)
  - Link to prospect or customer (optional selectors)
  - Notes: Tiptap rich text editor
  - Action items: checklist with assignee + due date per item + "Create Task" button
- [ ] Quick "New Meeting" button in header

### 5.3 Document Storage

**Backend Models:**
- [ ] `Folder`:
  ```
  id (UUID PK), name, parent_id (FK → Folder, nullable — self-referencing for nesting),
  position (int), created_by (FK → User), created_at
  ```
- [ ] `Document`:
  ```
  id (UUID PK), name, folder_id (FK → Folder),
  file_url (varchar), file_size (bigint), mime_type (varchar),
  description (text, nullable), tags (text[], nullable),
  uploaded_by (FK → User), created_at, updated_at
  ```

**File Storage:** Supabase Storage bucket `erp-documents`

**Backend Endpoints:**
- [ ] CRUD for folders (nested)
- [ ] `POST /api/v1/documents/upload` — Upload file (multipart)
- [ ] `GET /api/v1/documents` — List (filter by folder, search by name/tags)
- [ ] `GET /api/v1/documents/{id}/download` — Signed download URL
- [ ] `DELETE /api/v1/documents/{id}` — Delete file + storage cleanup

**Frontend (`/documents`):**
- [ ] File explorer: folder tree on left, file grid/list on right
- [ ] Drag-and-drop upload
- [ ] File preview for images and PDFs
- [ ] Download, delete, tag management

**Seed Folders:** Contracts, Legal, Brand Assets, Finance, Proposals

**Deliverable:** Sales pipeline with referral tracking, meeting notes with task conversion, and document storage.

---

## Phase 6: OKRs

**Goal:** Quarterly objectives with auto-tracking from real ERP data.
**Duration:** ~1-2 sessions

### 6.1 Backend

**Models:**
- [ ] `OKRPeriod`:
  ```
  id (UUID PK), name (e.g. "Q1 2026"),
  start_date (date), end_date (date),
  status (upcoming/active/completed),
  created_at
  ```
- [ ] `Objective`:
  ```
  id (UUID PK), period_id (FK → OKRPeriod),
  title, description (text, nullable),
  owner_id (FK → User), position (int),
  status (on_track/at_risk/behind/completed),
  created_at, updated_at
  ```
- [ ] `KeyResult`:
  ```
  id (UUID PK), objective_id (FK → Objective),
  title, target_value (decimal), current_value (decimal),
  unit (varchar — "%", "MXN", "customers", "tasks", etc.),
  tracking_mode (manual/auto),
  auto_metric (AutoMetric enum, nullable),
  start_value (decimal, default 0),
  progress_pct (decimal — calculated: (current - start) / (target - start) × 100),
  created_at, updated_at
  ```
- [ ] `AutoMetric` enum with calculation source:
  ```
  mrr                    → SUM(Customer.mrr_mxn) WHERE status='active'
  arr                    → mrr × 12
  total_customers        → COUNT(Customer) WHERE status='active'
  new_customers_quarter  → COUNT(Customer) WHERE signup_date in quarter range
  churn_rate             → churned / (total at start of quarter) × 100
  total_expenses_month   → SUM(Expense.amount_mxn) for current month
  burn_rate              → SUM(Expense.amount_mxn) WHERE is_recurring=true per month
  prospects_won          → COUNT(Prospect) WHERE status='won' AND updated_at in quarter
  tasks_completed        → COUNT(Task) WHERE column.name='Done' AND updated_at in quarter
  monthly_messages       → EVA DB: COUNT(messages) WHERE created_at in last 30 days
  ```

**Notification triggers:** `okr_at_risk` — when auto-calculated progress < 25% and period is > 50% elapsed

**Endpoints:**
- [ ] `GET /api/v1/okrs/active` — Current quarter with objectives + key results (auto-metrics refreshed)
- [ ] `GET /api/v1/okrs/periods` — All quarters
- [ ] `GET /api/v1/okrs/periods/{id}` — Full detail
- [ ] `POST /api/v1/okrs/periods` — Create new quarter
- [ ] `POST /api/v1/okrs/objectives` — Create objective
- [ ] `PATCH /api/v1/okrs/objectives/{id}` — Update objective
- [ ] `POST /api/v1/okrs/key-results` — Create key result
- [ ] `PATCH /api/v1/okrs/key-results/{id}` — Update (manual value or config)
- [ ] `POST /api/v1/okrs/refresh-auto` — Recalculate all auto-tracked KRs now

**Frontend (`/okrs`):**
- [ ] Quarter selector tabs
- [ ] Objectives as expandable cards: title, owner avatar, overall progress bar, status badge
- [ ] Key results inside: title, progress bar (current/target with unit), auto-tracked badge (lightning), manual update button
- [ ] "New Quarter" setup flow
- [ ] Seed:
  - **Q1 2026 Objective:** "Grow revenue to sustainable level"
    - KR: Reach $30,000 MXN MRR (auto: mrr, target: 30000)
    - KR: Acquire 10 new customers (auto: new_customers_quarter, target: 10)
    - KR: Reduce churn below 5% (auto: churn_rate, target: 5)
  - **Q1 2026 Objective:** "Build operational foundation"
    - KR: Catalog all services in vault (manual, target: 20)
    - KR: Complete 50 tasks (auto: tasks_completed, target: 50)

**Deliverable:** Quarterly goal-setting with live progress from real data.

---

## Phase 7: AI Assistant + Polish

**Goal:** Natural language queries + production polish.
**Duration:** ~2-3 sessions

### 7.1 AI Assistant

**Backend:**
- [ ] LLM: OpenAI GPT-4o with function/tool calling
- [ ] System prompt:
  ```
  You are the internal operations assistant for EVA (goeva.ai), an AI SaaS company
  run by Jose Pedro Gama and Gustavo Cermeno. You have access to financial data,
  customer records, tasks, prospects, meetings, OKRs, service costs (never secrets),
  and KPIs. Answer concisely. Use tables for lists. Show currency as original + MXN.
  ```
- [ ] Tool functions (each maps to existing backend queries):
  ```
  query_kpis(metrics[])                          → /kpis/current filtered
  query_income(period, category)                 → /income with filters
  query_expenses(period, category, paid_by, min) → /expenses with filters
  query_customers(status, plan, search)          → /customers with filters
  query_prospects(status, assigned_to)           → /prospects with filters
  query_tasks(board, assignee, overdue_only)     → /tasks with filters
  query_meetings(date_range, type, search)       → /meetings with filters
  query_vault_costs(category)                    → /vault/cost-summary (NO secrets)
  query_okrs(period)                             → /okrs/active or period
  query_invoices(status, customer)               → /invoices with filters
  ```
- [ ] `AssistantConversation`:
  ```
  id (UUID PK), user_id (FK → User),
  title (varchar, nullable — auto-generated from first message),
  messages_json (jsonb — full message array),
  created_at, updated_at
  ```
- [ ] Context window: send last 20 messages to LLM. Full history stored in DB (no truncation).

**Endpoints:**
- [ ] `POST /api/v1/assistant/chat` — Send message (streaming SSE response)
- [ ] `GET /api/v1/assistant/conversations` — List past conversations
- [ ] `POST /api/v1/assistant/conversations` — Start new conversation
- [ ] `DELETE /api/v1/assistant/conversations/{id}` — Delete conversation

**Frontend (`/assistant`):**
- [ ] Chat: message bubbles, streaming display, markdown + table rendering
- [ ] Suggested queries (chips): "What's our MRR?", "Expenses over $500", "Overdue tasks", "Q1 OKR progress"
- [ ] Conversation history sidebar
- [ ] "New Chat" button

### 7.2 Polish & Production

- [ ] Loading skeletons on every page (shimmer, not spinners)
- [ ] Toast notifications for all create/update/delete (sonner library)
- [ ] Error boundaries with friendly error pages
- [ ] Empty states with illustrations + CTAs
- [ ] Keyboard shortcut: `Cmd+K` → command palette (search across modules)
- [ ] Mobile responsiveness audit
- [ ] Deploy:
  - Frontend: Vercel
  - Backend: Koyeb or Railway
  - Database: New Supabase project (separate from EVA production)
  - Domain: `ops.goeva.ai` or `erp.goeva.ai`
- [ ] README with setup instructions
- [ ] Supabase automatic daily backups

**Deliverable:** Complete, polished ERP with AI querying and production deployment.

---

## Database Schema Summary

All models with full field listings. FKs shown as `→ Table`.

```
── Auth & Users ──────────────────────────────────────────────────
User
  id (UUID PK), email (unique), name, password_hash, role (admin/member),
  avatar_url, is_active, created_at, updated_at

── Notifications (cross-cutting) ─────────────────────────────────
Notification
  id (UUID PK), user_id → User, type, title, body, link, read (bool),
  created_at

── Credential Vault ──────────────────────────────────────────────
VaultConfig
  id (UUID PK), user_id → User (unique), master_password_hash, salt,
  created_at

Credential
  id (UUID PK), name, category (enum), url, login_url,
  username_encrypted (bytes), password_encrypted (bytes),
  api_keys_encrypted (bytes), notes_encrypted (bytes),
  monthly_cost, cost_currency, monthly_cost_mxn,
  billing_cycle, who_has_access (UUID[]), is_deleted,
  created_by → User, created_at, updated_at

VaultAuditLog
  id (UUID PK), user_id → User, credential_id → Credential,
  action, ip_address, created_at

── Kanban Tasks ──────────────────────────────────────────────────
Board
  id (UUID PK), name, slug (unique), description, position,
  created_by → User, created_at, updated_at

Column
  id (UUID PK), board_id → Board, name, position, color,
  created_at

Task
  id (UUID PK), column_id → Column, board_id → Board,
  title, description, assignee_id → User, priority (enum),
  due_date, labels (text[]), position (float),
  source_meeting_id → Meeting (nullable),
  created_by → User, created_at, updated_at

TaskComment
  id (UUID PK), task_id → Task, user_id → User, content,
  created_at

TaskActivity
  id (UUID PK), task_id → Task, user_id → User, action,
  old_value, new_value, created_at

── Finances ──────────────────────────────────────────────────────
ExchangeRate
  id (UUID PK), from_currency, to_currency, rate, effective_date,
  source, created_at

IncomeEntry
  id (UUID PK), source (stripe/manual), stripe_payment_id (unique),
  stripe_invoice_id, customer_id → Customer, description,
  amount, currency, amount_mxn, category (enum), date,
  is_recurring, metadata_json, created_by → User, created_at

Expense
  id (UUID PK), name, description, amount, currency, amount_mxn,
  category (enum), vendor, paid_by → User, is_recurring,
  recurrence, date, receipt_url,
  vault_credential_id → Credential (nullable),
  created_by → User, created_at, updated_at

Invoice
  id (UUID PK), invoice_number, customer_id → Customer (nullable),
  customer_name, customer_email, description, line_items_json,
  subtotal, tax, total, currency, total_mxn,
  status (draft/sent/paid/overdue/cancelled),
  issue_date, due_date, paid_date, notes,
  created_by → User, created_at, updated_at

CashBalance
  id (UUID PK), amount, currency, amount_mxn, date, notes,
  updated_by → User, created_at

── Customers ─────────────────────────────────────────────────────
Customer
  id (UUID PK), company_name, contact_name, contact_email,
  contact_phone, industry, website, plan_tier,
  mrr, mrr_currency, mrr_mxn, arr, billing_interval,
  signup_date, status (active/churned/paused/trial),
  churn_date, churn_reason, stripe_customer_id (unique),
  lifetime_value, lifetime_value_currency, lifetime_value_mxn,
  referral_source, prospect_id → Prospect (nullable),
  notes, tags (text[]), created_by → User, created_at, updated_at

── Prospects ─────────────────────────────────────────────────────
Prospect
  id (UUID PK), company_name, website, industry,
  contact_name, contact_email, contact_phone, contact_role,
  status (enum), source (enum), referred_by,
  estimated_plan, estimated_mrr, estimated_mrr_currency,
  estimated_mrr_mxn, notes, next_follow_up,
  assigned_to → User, tags (text[]), lost_reason,
  converted_to_customer_id → Customer (nullable),
  created_by → User, created_at, updated_at

ProspectInteraction
  id (UUID PK), prospect_id → Prospect, type, summary, date,
  created_by → User, created_at

── Meetings ──────────────────────────────────────────────────────
Meeting
  id (UUID PK), title, date (datetime), duration_minutes,
  type (internal/prospect/customer/partner),
  attendees (text[]), notes_markdown, action_items_json,
  prospect_id → Prospect (nullable),
  customer_id → Customer (nullable),
  created_by → User, created_at, updated_at

── Documents ─────────────────────────────────────────────────────
Folder
  id (UUID PK), name, parent_id → Folder (nullable), position,
  created_by → User, created_at

Document
  id (UUID PK), name, folder_id → Folder, file_url, file_size,
  mime_type, description, tags (text[]),
  uploaded_by → User, created_at, updated_at

── OKRs ──────────────────────────────────────────────────────────
OKRPeriod
  id (UUID PK), name, start_date, end_date,
  status (upcoming/active/completed), created_at

Objective
  id (UUID PK), period_id → OKRPeriod, title, description,
  owner_id → User, position, status (on_track/at_risk/behind/completed),
  created_at, updated_at

KeyResult
  id (UUID PK), objective_id → Objective, title,
  target_value, current_value, unit, tracking_mode (manual/auto),
  auto_metric (enum, nullable), start_value, progress_pct,
  created_at, updated_at

── KPIs ──────────────────────────────────────────────────────────
KPISnapshot
  id (UUID PK), period (YYYY-MM, unique),
  mrr, mrr_currency, arr, mrr_growth_pct,
  total_revenue, total_revenue_currency,
  total_expenses, total_expenses_mxn, net_profit,
  burn_rate, runway_months,
  total_customers, new_customers, churned_customers,
  arpu, ltv, cac,
  open_tasks, overdue_tasks, prospects_in_pipeline, prospects_won,
  data_json, created_at

── AI Assistant ──────────────────────────────────────────────────
AssistantConversation
  id (UUID PK), user_id → User, title, messages_json,
  created_at, updated_at
```

**Total models: 22** | **Total tables: 22** (no many-to-many join tables needed — arrays used instead)

---

## Cross-Module Relationships

| From | To | How | Direction |
|------|----|-----|-----------|
| Task | Meeting | `task.source_meeting_id → meeting.id` | Task knows its origin meeting |
| Meeting | Task | `action_items_json[].linked_task_id` | Meeting knows which tasks were created |
| Prospect | Customer | `prospect.converted_to_customer_id → customer.id` | Prospect knows the resulting customer |
| Customer | Prospect | `customer.prospect_id → prospect.id` | Customer knows its origin prospect |
| Expense | Credential | `expense.vault_credential_id → credential.id` | Expense linked to vault service |
| IncomeEntry | Customer | `income.customer_id → customer.id` | Payment linked to customer |
| Meeting | Prospect | `meeting.prospect_id → prospect.id` | Meeting linked to prospect |
| Meeting | Customer | `meeting.customer_id → customer.id` | Meeting linked to customer |
| OKR AutoMetric | Various | Queries across Customer, Expense, Prospect, Task, EVA DB | Auto-calculated |

---

## Tech Stack

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend | Next.js 15 (App Router) | Same as EVA |
| Styling | Tailwind + shadcn/ui | Same as EVA |
| Design | EVA brand (app.goeva.ai tokens) | Internal EVA tool |
| Backend | FastAPI (async) | Same as EVA |
| ORM | SQLAlchemy 2.0 async + asyncpg | Same as EVA |
| Database | PostgreSQL (Supabase) | Managed, cheap |
| Migrations | Alembic | Same as EVA |
| Auth | Custom JWT (HTTP-only cookies) | Independent from EVA |
| Data fetching | Axios + SWR | Same as EVA |
| Drag-and-drop | @dnd-kit/core + @dnd-kit/sortable | Best React DnD |
| Rich text | Tiptap | Lightweight |
| Charts | Recharts | React composable |
| Encryption | AES-256-GCM (Python cryptography lib) | Industry standard |
| File storage | Supabase Storage | Already using Supabase |
| LLM | OpenAI GPT-4o (tool calling) | Best function calling |
| Notifications | In-app only (polling) | Simple for small team |
| Background tasks | APScheduler | Lightweight, no Redis needed |
| Cache | In-memory dict with TTL | Fine for 2-5 users |

---

## Estimated Effort

| Phase | Scope | Sessions | Cumulative |
|-------|-------|----------|------------|
| 1 | Foundation + Auth + Layout + Notifications | 2 | 2 |
| 2 | Credential Vault + Kanban Tasks | 3 | 5 |
| 3 | Finances + Customers (Stripe sync + Invoices) | 3-4 | 8-9 |
| 4 | KPI Dashboard | 2 | 10-11 |
| 5 | Prospect CRM + Meetings + Documents | 3 | 13-14 |
| 6 | OKRs (with auto-tracking) | 1-2 | 14-16 |
| 7 | AI Assistant + Polish + Deploy | 2-3 | 16-19 |
| **Total** | **Full ERP** | **~16-19 sessions** | |

---

## Phase Order Rationale

1. **Foundation** — Can't build anything without auth, navigation, and notifications
2. **Vault + Tasks** — Solves #1 pain (cost visibility) + daily coordination
3. **Finances + Customers** — Stripe sync = real revenue data, full cost picture
4. **KPI Dashboard** — Enough data exists to build meaningful metrics
5. **Prospects + Meetings + Documents** — Sales pipeline and operational tools
6. **OKRs** — Set goals once you have data to measure against
7. **AI + Polish** — Assistant becomes powerful once all data exists
