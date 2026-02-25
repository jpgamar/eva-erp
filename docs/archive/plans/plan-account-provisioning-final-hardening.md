# ERP Account Provisioning Final Hardening Plan

**Overall Progress:** `100%`

> **Implementation:** Execute this plan to eliminate remaining account-provisioning runtime errors in ERP.

---

## Requirements Extraction

### Original Request
> "please make sure no errors pop up again when creating an account. I don't want to be sending you error by error after you deploy each fix."

### Additional Requirements (from conversation)
- Diagnose all likely account provisioning failure points, not only the latest error.
- Keep ERP and EVA login systems independent (no auth-system merge).
- Validate fixes locally before deploy.
- Deploy only after plan implementation and checks pass.
- No DB migrations or destructive DB changes.

### Decisions Made During Planning
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope of fix | Enum parity + route normalization + error mapping hardening | Targets the current production failure class and adjacent failure paths |
| Data layer approach | Fix SQLAlchemy mirror model types (no schema changes) | Error is app-layer datatype mismatch, not DB schema absence |
| Verification | Backend tests + targeted runtime checks + deploy workflow verification | Minimizes risk of another production surprise |

---

## Intended Outcome

Account creation from ERP succeeds consistently without enum datatype mismatch errors, and related provisioning paths no longer fail due to model/type drift.

---

## Features

1. **Enum Parity for Eva Mirror Models** — align ERP mirror columns with EVA enum types.
2. **Provisioning Error Hardening** — map common enum mismatch DB errors to deterministic API responses.
3. **Deal Flow Consistency** — normalize deal stage values to match EVA enum values.
4. **Regression Coverage** — tests for new normalization/error paths.

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Account provisioning inserts nullable enum fields | Insert succeeds without varchar→enum mismatch |
| DB returns enum mismatch error string | API returns deterministic 400/409 style response, not opaque 500 |
| Deal stage value arrives uppercase/lowercase | Normalized to valid DB enum value |
| Unknown deal stage value | API returns 400 with clear allowed values |

---

## Out of Scope (Explicit)

- Database migrations
- Syncing data between environments
- Login UI redesign changes
- Cross-app auth architecture changes

---

## Tasks

### Phase 1: Model and Backend Hardening
- [x] 🟩 **Step 1: Align mirror model enums with EVA schema**
  - [x] 🟩 Fix `accounts.subscription_status` type
  - [x] 🟩 Fix other enum columns in touched tables (`partner_domains.status`, `partner_deals.stage`)

- [x] 🟩 **Step 2: Harden provisioning/deal normalization**
  - [x] 🟩 Add deal-stage normalization helper and use in partner routes
  - [x] 🟩 Extend provisioning error mapping for enum datatype mismatch signatures

### Phase 2: Tests
- [x] 🟩 **Step 3: Add regression tests**
  - [x] 🟩 Add tests for enum mismatch mapping (`subscription_status`, related enums)
  - [x] 🟩 Add tests for deal stage normalization behavior

### Phase 3: Verification and Release
- [x] 🟩 **Step 4: Execute verification**
  - [x] 🟩 Run backend test suite
  - [x] 🟩 Confirm clean git diff only for intended files
  - [x] 🟩 Deploy with production workflow checks

---

## Notes

- This plan is intentionally limited to reliability fixes in ERP account provisioning and adjacent partner/deal write paths.
- Backend verification snapshot:
  - `cd backend && .venv/bin/python -m pytest tests -q` → `42 passed`
  - GitHub Actions `Production Post-Deployment` run `22377990063` → `success`
