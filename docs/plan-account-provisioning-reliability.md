# ERP Account Provisioning Reliability Plan

**Overall Progress:** `84%`

> **Implementation:** Use this plan to execute a focused reliability fix for account creation/provisioning in ERP.

---

## Requirements Extraction

### Original Request
> "Sometimes they say they are duplicate and it's not even a duplicate. Sometimes it says code 500. Understand task of fixing the greeting account issues."

### Additional Requirements (from conversation)
- Fix account creation reliability in ERP, not only duplicate-email handling.
- Keep EVA app login and ERP login independent.
- Avoid mixing apps or changing DB infrastructure.
- Preserve current UX flow in ERP Eva Customers.
- Do not perform DB migration/sync/destructive DB ops.

### Decisions Made During Planning
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope | Include all Supabase-backed provisioning flows | Same bug surface exists in multiple routes |
| First implementation pass | No schema migrations | Failures are logic/retry/error-handling, not schema shape |
| Error semantics | Return explicit domain errors (409/502/503 style) instead of generic 500 where possible | Improve operator clarity and user trust |
| Duplicate behavior | Reuse existing Supabase user when resolvable | Prevent false blocking for valid account creation |

### User Preferences
- Wants a robust, production-grade fix (no flaky behavior).
- Wants clear behavior separation between ERP and normal app.
- Wants pragmatic resolution, not just cosmetic error handling.

---

## Intended Outcome

Creating accounts from ERP should be deterministic and resilient:
- Duplicate-email cases should either reuse the existing auth user or fail with a precise actionable error.
- Transient upstream Supabase issues should not show ambiguous `500` in UI.
- All account provisioning entrypoints should share the same hardened behavior.
- User-facing errors should be specific and consistent.

---

## Features

1. **Unified Provisioning Guardrails** — One robust auth-user provisioning path reused by all ERP account creation routes.
2. **Deterministic Duplicate Resolution** — Reliable lookup of existing Supabase users by email with fallback strategies.
3. **Explicit Error Taxonomy** — Map transport/upstream failures to predictable API errors, avoid opaque generic failures.
4. **Frontend Error Clarity** — Preserve detailed backend reason in Eva Customers creation toast.

---

## Affected Flows

1. `POST /api/v1/eva-platform/accounts`
2. `POST /api/v1/eva-platform/drafts/{draft_id}/approve`
3. `POST /api/v1/eva-platform/partners`
4. `POST /api/v1/eva-platform/deals/{deal_id}/create-account`

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Email truly exists in Supabase | Reuse existing auth user ID; proceed with ERP account linkage |
| Supabase says duplicate but lookup cannot find user | Return explicit conflict-style error with retriable guidance, not generic 500 |
| Supabase admin endpoint transient timeout/network failure | Return upstream-unavailable style error; no silent fallback |
| Supabase returns unexpected payload without user id | Return structured provisioning error; include traceable context in logs |
| ERP DB write fails after auth user creation | Return explicit provisioning partial-failure error; log recovery action needed |
| Repeated submit clicks | Single in-flight create action in frontend; no duplicate POST burst |

---

## Error Handling

| Error Condition | User-Facing Behavior | Technical Response |
|-----------------|---------------------|-------------------|
| Duplicate email resolved to existing user | Success flow | Continue with existing `sb_user_id` |
| Duplicate signaled but unresolved | “Account owner email is already registered but could not be linked. Please retry or contact support.” | `409` domain error (`owner_duplicate_unresolved`) |
| Supabase transport error (timeout/network) | “Provisioning service temporarily unavailable. Try again.” | `503`/`502` mapped from client error |
| Invalid Supabase credentials/config | “Provisioning is misconfigured. Contact admin.” | `500` config error with safe detail |
| Unexpected upstream response shape | “Could not complete account provisioning.” | `502` domain error (`invalid_upstream_payload`) |

---

## UI/UX Details

- Keep current Eva Customers dialog design unchanged.
- Keep submit button lock (`Creating...`) during request.
- Always show the most specific backend `detail` when present.
- Maintain current language style already used in ERP page; do not redesign.

---

## Business Rules

- ERP and EVA app authentication remain independent.
- Account creation must always produce a valid `owner_user_id` in EVA `accounts`.
- Provisioning logic must be consistent across all four entrypoints.
- No direct DB migration or cross-environment data sync in this fix.

---

## Out of Scope (Explicit)

- Re-architecting identity model between EVA and ERP.
- Bulk reconciliation of historical orphaned users/accounts.
- UI redesign beyond error presentation already in place.
- Any database schema migration.

---

## Tasks

### Phase 1: Backend Reliability Core
- [x] 🟩 **Step 1: Harden Supabase client provisioning path**
  - [x] 🟩 Add structured exception classes for: duplicate unresolved, upstream unavailable, invalid upstream payload, config error
  - [x] 🟩 Catch `httpx` transport/status parsing errors explicitly
  - [x] 🟩 Implement deterministic lookup strategy for duplicate cases:
    - [x] 🟩 primary: query admin users with email filter
    - [x] 🟩 fallback: paginated scan with bounded retries/backoff
  - [x] 🟩 Normalize email input (`trim + lower`) at client boundary

- [x] 🟩 **Step 2: Centralize provisioning behavior**
  - [x] 🟩 Add helper/service function for `create_or_get_auth_user(email, metadata, password)` (implemented inside Supabase client provisioning path)
  - [x] 🟩 Reuse helper in accounts, draft approval, partner creation, and deal create-account routes
  - [x] 🟩 Ensure all routes map exceptions to consistent HTTP status and error code/detail

- [x] 🟩 **Step 3: Partial-failure protection**
  - [x] 🟩 Add explicit log context when auth user created but EVA DB write fails
  - [x] 🟩 Return deterministic error contract for partial failures (no generic message)

### Phase 2: Frontend Behavior (Eva Customers)
- [x] 🟩 **Step 4: Confirm robust create-account UX**
  - [x] 🟩 Keep in-flight submit lock (already present)
  - [x] 🟩 Ensure backend error detail always reaches toast
  - [x] 🟩 Add fallback mapping for known error codes to clear text

### Phase 3: Test Coverage
- [ ] 🟨 **Step 5: Backend regression tests**
  - [x] 🟩 Duplicate response variants resolve to existing user ID (via canonical extraction tests)
  - [x] 🟩 Duplicate unresolved path returns expected error type mapping
  - [ ] 🟥 Transport timeout maps to upstream-unavailable error
  - [x] 🟩 Unexpected payload shape maps to invalid-upstream-payload
  - [ ] 🟥 Route tests for all 4 entrypoints verify consistent status/detail mapping

- [ ] 🟨 **Step 6: Frontend verification tests/checks**
  - [ ] 🟥 Validate toast behavior for structured backend errors (no frontend test harness currently)
  - [x] 🟩 Lint/typecheck touched frontend file

### Phase 4: Verification and Deploy
- [ ] 🟨 **Step 7: Local verification**
  - [x] 🟩 Run backend test suite
  - [x] 🟩 Run targeted frontend lint/typecheck
  - [x] 🟩 Manual API probe for representative error branches

- [ ] 🟨 **Step 8: Production rollout**
  - [x] 🟩 Deploy frontend + backend through existing pipelines
  - [x] 🟩 Verify GitHub `Production Post-Deployment` success
  - [ ] 🟥 Smoke test `Eva Customers -> Create Account`

### Phase 5: Post-Deploy Observability
- [ ] 🟨 **Step 9: Monitoring and feedback loop**
  - [x] 🟩 Add/adjust logs for provisioning failure categories
  - [ ] 🟥 Capture top 3 failure fingerprints for future hardening
  - [ ] 🟥 Document runbook notes if new recurring pattern appears

---

## Technical Details

- Main technical focus is `backend/src/eva_platform/supabase_client.py` and shared usage in:
  - `backend/src/eva_platform/router/accounts.py`
  - `backend/src/eva_platform/router/partners.py`
- Keep route contracts backward-compatible where possible (`detail` string), but improve semantics with consistent status codes and internal error codes.
- Frontend keeps existing page architecture at:
  - `frontend/src/app/(app)/eva-customers/page.tsx`

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| New error mapping breaks expected frontend assumptions | Maintain `detail` string and add compatibility fallback |
| Supabase API behavior differs across environments | Implement primary + fallback lookup strategy and bounded retries |
| Hidden failure branch in partner/deal paths | Force all paths through one helper and add route-level regression tests |

---

## Comprehensiveness Checklist

- [x] Re-read relevant conversation context
- [x] Included all known failing flows
- [x] Defined edge cases and expected behavior
- [x] Defined error handling contract
- [x] Listed out-of-scope items
- [x] Added phased tasks with tests and deploy verification

---

## Open Decisions To Confirm Before Full Closure

1. If email exists in Supabase Auth, should we always reuse it for new ERP account creation?  
   Current implementation assumes: **Yes**.
2. For duplicate unresolved after retries, should API return `409` with explicit code instead of blocking as generic error?  
   Current implementation assumes: **Yes**.
