# Facturas Draft Mode + Modal Layout Fix Plan

**Overall Progress:** `100%`

> **Implementation:** Use the `/implement-plan` skill to execute this plan.

---

## Execution Context

**Project:** Eva ERP (`~/eva-erp/`)
**Branch:** `feat/facturas-draft-mode` (create from `main`)

**Start-of-work guardrails:**
1. `cd ~/eva-erp && git status` — must be clean
2. `git checkout main && git pull`
3. `git checkout -b feat/facturas-draft-mode`
4. Confirm services: backend on :4002, frontend on :3001 (per MEMORY ports)
5. No desk system — simple git branch workflow

---

## Requirements Extraction

### Original Request
> "get inside eva.erp there we need to fix two things one is related to facturapi and right now is that when creating a new invoice everything looks like cut like it is not properly adjusted so you can see all the fields so maybe we need to be a bigger a bigger card or something as you may see the unit price the rfc the zip code like everything becomes a mess so that's the first thing that we should check right now and the second one is that a client of mine asked me to like i need to invoice him something but he told me that i should send him a draft like i shouldn't stamp it yet because their accountability people need to validate it so yes he told me to not stamp it so how do i send draft maybe we need to configure something in the ERP related to factor up be maybe yeah so research on both of that and fix them both but before you do anything, tell me what you're gonna fix."

### Additional Requirements (from conversation)
- The **New CFDI Invoice** modal must show all fields without visual truncation (Legal Name, RFC, Tax System, ZIP, Uso, Forma/Metodo de Pago, Currency, and the line-items row with Qty, Unit Price, Tax, Ret. ISR, Ret. IVA, plus the "Add Item" button).
- Need a way to create a **draft invoice** that is sent to Facturapi WITHOUT stamping it, so Pepe can share a **preview PDF** with a client's accountants for validation.
- Once the accountants approve, Pepe must be able to **stamp** the existing draft (not recreate it).
- The flow must live inside the existing `/facturas` page — no separate screen.

### Decisions Made During Planning
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Draft storage location | Push drafts to Facturapi (`status: "draft"`) | Facturapi's draft feature gives a real preview PDF with the org's template — which is exactly what the client's accountants need to review. Current local-only drafts have no PDF to share. |
| Keep local-only drafts too? | Yes — a new `push-draft` action promotes them | Avoid breaking existing callers. Local draft = "not yet fiscal-ready", Facturapi draft = "PDF preview exists, stamp-ready". |
| Stamp endpoint behavior | Branch: if `facturapi_id` exists → stamp the draft via `POST /v2/invoices/{id}/stamp`; else fall back to current create-and-stamp | Preserves the one-click "create and stamp immediately" flow while adding the two-step "draft → stamp" flow. |
| PDF endpoint behavior | Allow download whenever `facturapi_id` exists | Facturapi generates a preview PDF for drafts (no XML). Remove the "must be stamped first" gate. |
| XML endpoint behavior | Still blocked for drafts | Per Facturapi docs: *"you can download the PDF, but not the XML of a draft."* |
| Modal width | `max-w-5xl` (1024px) | `max-w-3xl` (768px) was the source of cramped columns; `5xl` leaves room for all 5 line-item fields plus padding. |
| Line-item layout | Restructure second grid into two rows (numeric fields row, retention dropdowns row) | Even at 1024px the 5-column grid squeezes the "Sin retención" dropdowns. Splitting by field type reads cleaner. |
| UI entry point for draft mode | Two submit buttons at the bottom of the create modal | Clearer than a checkbox: "Guardar borrador (preview)" pushes to Facturapi as draft; "Crear y timbrar" is the current create-and-stamp flow. |
| Preview PDF button on list rows | Show "Descargar preview" only when `status === "draft"` AND `facturapi_id != null` | Local-only drafts have no PDF yet. |

### User Preferences
- Keep UI Spanish-consistent with rest of the page (labels like "Guardar borrador", "Timbrar", "Descargar preview").
- Don't force a schema migration if avoidable — `facturapi_id` column already exists and is nullable.
- Don't break the existing "create and stamp in one click" flow; draft mode is additive.

---

## Intended Outcome

When Pepe opens **New CFDI Invoice** in `/facturas`, the modal is wide enough that every field (RFC, ZIP Code, Unit Price, Ret. ISR dropdown showing "Sin retención" in full, Ret. IVA dropdown, and the "Add Item" button) is visible without horizontal clipping on a standard ~1440px laptop viewport.

Inside the modal, two submit options:
- **"Crear y timbrar"** — current behavior: creates locally, stamps via Facturapi in one shot, marks as `valid`.
- **"Guardar borrador (preview)"** — creates locally AND pushes to Facturapi as `status: "draft"`, storing the returned `facturapi_id`. The row appears in the list with status `draft`.

On a draft row in the list, a new **"Descargar preview"** action downloads the PDF from Facturapi so Pepe can email it to the client's accountants.

Once approved, clicking **"Timbrar"** on that draft row calls Facturapi's `POST /v2/invoices/{id}/stamp`, converting the draft to a valid stamped CFDI with UUID and XML. The row updates accordingly.

---

## Features

1. **Wider invoice modal** — `max-w-5xl` with a restructured line-items grid so all fields render without clipping.
2. **Facturapi draft creation** — new backend service fn + schema flag enabling `status: "draft"` invoices in Facturapi.
3. **Two-step flow UI** — two submit buttons in the modal ("Crear y timbrar" vs "Guardar borrador (preview)").
4. **Preview PDF download** — new row action in the list for drafts that have a `facturapi_id`.
5. **Stamp-a-draft flow** — backend stamp endpoint routes to `/v2/invoices/{id}/stamp` when `facturapi_id` already exists.
6. **PDF endpoint unlocked for drafts** — `GET /facturas/{id}/pdf` works whenever Facturapi has the invoice (draft or valid).

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User clicks "Guardar borrador" with manual-entry customer fields incomplete | Facturapi requires customer fiscal info even for drafts; backend validates same fields as the stamp flow and returns 400 before calling Facturapi. |
| Facturapi rejects the draft payload (e.g. invalid RFC) | 502 surfaced to frontend with `facturapi_error` detail; the local draft is NOT saved (rollback inside the same DB flush), so the user can retry. |
| User stamps a draft that's missing required fields (Facturapi responds `is_ready_to_stamp: false`) | Backend catches 400 from Facturapi and returns 400 with the Facturapi error detail; frontend toasts the message. |
| User deletes a Facturapi-draft (status=draft, facturapi_id set) | Backend calls Facturapi's delete-draft endpoint first, then hard-deletes the local row. If Facturapi delete fails, abort and surface the error. |
| Modal is opened on a narrow window (<1024px) | `max-w-5xl` caps at 1024px but shrinks down via `w-full`; the line-items grid must still render (two rows) without horizontal scroll at ~900px. |
| Existing stamped factura's "Download PDF" action | Unchanged — still works through the same endpoint. |
| Local-only draft (no facturapi_id) clicks "Timbrar" | Fall back to current create-and-stamp path (`create_invoice` with no draft status). |
| Facturapi-draft with facturapi_id clicks "Timbrar" | Call `POST /v2/invoices/{facturapi_id}/stamp`; update row with UUID, XML URL, status=valid, issued_at. |
| Draft row clicks "Descargar preview" but Facturapi returns 404 (draft deleted out-of-band) | Surface 404 as toast; optionally mark local row with a warning flag (out of scope — surface the error only). |

---

## Error Handling

| Error Condition | User-Facing Behavior | Technical Response |
|-----------------|---------------------|-------------------|
| Missing customer fiscal fields when saving draft | Toast: "Información fiscal incompleta" | 400 with `detail="customer_name and customer_rfc are required..."` (same as stamp flow) |
| Facturapi API key not configured | Toast: "Facturapi no está configurado" | 503 with `detail="Facturapi API key not configured..."` (existing `_check_key`) |
| Facturapi rejects draft create | Toast shows Facturapi's error message | 502 with `detail={"facturapi_error": <body>}` |
| Facturapi rejects stamp-draft (not ready) | Toast: Facturapi's validation message | 400 with `detail={"facturapi_error": <body>}` |
| Network timeout to Facturapi | Toast: "Error de red con Facturapi" | 502 after 30s timeout (existing `httpx.AsyncClient(timeout=30)`) |
| PDF download for draft with missing `facturapi_id` | Toast: "Este borrador aún no se envió a Facturapi" | 400 with `detail="Draft must be pushed to Facturapi first"` |
| XML download for draft | Toast: "Los borradores no tienen XML hasta timbrar" | 400 (existing behavior kept) |

---

## UI/UX Details

**Modal (`frontend/src/app/(app)/facturas/page.tsx`):**
- `DialogContent` className: `max-w-5xl max-h-[90vh] overflow-y-auto` (from `max-w-3xl`).
- Line-items inner card: keep row 1 (`grid-cols-[160px_1fr]` Clave Producto + Description) — already fine.
- Line-items row 2: split into TWO grids stacked vertically:
  - Row 2a: `grid-cols-[5rem_1fr_5rem] gap-3` for Qty / Unit Price / Tax.
  - Row 2b: `grid-cols-2 gap-3` for Ret. ISR / Ret. IVA dropdowns (now full-width halves, no more clipping of "Sin retención").
- Footer (below Notes field): replace single submit with two buttons side-by-side:
  - `variant="outline"` — **"Guardar borrador (preview)"** — submits with `draft=true`.
  - `variant="default"` — **"Crear y timbrar"** — current submit.
- Disable BOTH buttons while the request is in-flight; show inline spinner on whichever one was clicked.

**List row actions (same file):**
- For rows with `status === "draft"` AND `facturapi_id`: show **"Descargar preview"** button alongside the existing "Timbrar" button. Reuse the PDF download helper; it hits the same `/facturas/{id}/pdf` endpoint.
- For rows with `status === "draft"` AND `!facturapi_id`: keep existing "Timbrar" button only; no preview download.

**Copy (Spanish):**
- "Guardar borrador (preview)" (primary draft button)
- "Crear y timbrar" (primary stamp-immediately button)
- "Descargar preview" (row action)
- "Timbrar" (row action, unchanged)
- Toast on draft save: "Borrador guardado. Puedes descargar el preview PDF."
- Toast on stamp success: "Factura timbrada correctamente." (unchanged)

---

## Business Rules

- A draft in Facturapi still requires full fiscal data (customer RFC, legal_name, tax_system, zip, items with product_key, prices). Validate the same way as stamp.
- The `facturapi_id` column is the canary: its presence means Facturapi has the resource; its absence means local-only.
- Never call Facturapi twice for the same local factura — when stamping, if `facturapi_id` exists, use the stamp-draft endpoint instead of creating a new invoice.
- A draft's `total` / `subtotal` / `tax` stored locally should match what Facturapi returns from the draft create. Reconcile after push (update local row with Facturapi's computed total, same as current stamp flow does).
- XML is never available for drafts — keep the 400 on `GET /facturas/{id}/xml` when status is draft.

---

## Out of Scope (Explicit)

- Editing an existing Facturapi draft (`updateDraftInvoice`) — not requested; user can delete + recreate.
- Emailing the preview PDF directly from the ERP — out of scope; Pepe will download + email manually.
- Automatic polling of `is_ready_to_stamp` field — UI just tries to stamp and surfaces any Facturapi error.
- Draft listing filter in the list header — drafts are already visible via the existing status filter.
- Migrating existing local-only drafts to Facturapi-drafts on load — they stay local until the user explicitly acts.
- Any changes to egreso invoice flow (`create_egreso_invoice`) — requested scope is ingreso drafts only.

---

## Tasks

### Phase 1: Backend

- [x] 🟩 **Step 1: Extend Facturapi service with draft support** (`backend/src/facturas/service.py`)
  - [x] 🟩 Add `create_draft_invoice(payload: dict) -> dict` — same as `create_invoice` but merges `{"status": "draft"}` into the payload before POST.
  - [x] 🟩 Add `stamp_draft_invoice(facturapi_id: str) -> dict` — `POST /v2/invoices/{id}/stamp` with same auth + error handling.
  - [x] 🟩 Add `delete_draft_invoice(facturapi_id: str) -> None` — `DELETE /v2/invoices/{id}` (Facturapi distinguishes draft delete from valid-cancel via status).
  - [x] 🟩 Keep existing `create_invoice`, `cancel_invoice`, `download_pdf`, `download_xml` unchanged.

- [x] 🟩 **Step 2: Add `draft` flag to POST /facturas** (`backend/src/facturas/router.py` + `schemas.py`)
  - [x] 🟩 Add optional `draft: bool = False` query param to `POST /facturas` (simpler than schema change; matches Pydantic FastAPI style).
  - [x] 🟩 After local Factura is built, if `draft=True`: build Facturapi payload, call `create_draft_invoice`, store `facturapi_id` and Facturapi-computed totals on the local row.
  - [x] 🟩 Keep `status="draft"` for BOTH draft variants (local-only and Facturapi-pushed) — `facturapi_id` is the differentiator.
  - [x] 🟩 On Facturapi error, rollback the DB flush so no orphan local draft is saved.

- [x] 🟩 **Step 3: Make stamp endpoint idempotent with drafts** (`backend/src/facturas/router.py`)
  - [x] 🟩 In `POST /facturas/{id}/stamp`: branch on `factura.facturapi_id`.
  - [x] 🟩 If set → call `facturapi.stamp_draft_invoice(factura.facturapi_id)`.
  - [x] 🟩 If not set → current path (build payload + `create_invoice`).
  - [x] 🟩 Map Facturapi response fields identically in both branches.

- [x] 🟩 **Step 4: Unlock PDF download for Facturapi drafts** (`backend/src/facturas/router.py`)
  - [x] 🟩 Replace the `if not factura.facturapi_id: 400` guard — allow any factura with `facturapi_id` to download the PDF regardless of status.
  - [x] 🟩 Leave XML endpoint guard unchanged (drafts have no XML per Facturapi).

- [x] 🟩 **Step 5: Cascade draft delete to Facturapi** (`backend/src/facturas/router.py`)
  - [x] 🟩 In `DELETE /facturas/{id}`, if `status=="draft"` AND `facturapi_id`, call `delete_draft_invoice(facturapi_id)` before the local hard-delete.
  - [x] 🟩 If Facturapi delete fails, abort local delete and surface 502.

- [x] 🟩 **Step 6: Backend tests** (`backend/tests/test_facturas_router.py`)
  - [x] 🟩 `test_create_factura_draft_true_pushes_to_facturapi_and_saves_facturapi_id` (happy path, mock Facturapi `create_draft_invoice`).
  - [x] 🟩 `test_create_factura_draft_true_facturapi_error_rollbacks_local` (assert no DB row after 502).
  - [x] 🟩 `test_create_factura_draft_false_unchanged_behavior` (regression — current create path).
  - [x] 🟩 `test_stamp_factura_with_facturapi_id_calls_stamp_draft` (asserts `stamp_draft_invoice` called, not `create_invoice`).
  - [x] 🟩 `test_stamp_factura_without_facturapi_id_calls_create_invoice` (regression for legacy path).
  - [x] 🟩 `test_download_pdf_draft_with_facturapi_id_succeeds` (returns bytes with correct content-type).
  - [x] 🟩 `test_download_pdf_draft_without_facturapi_id_returns_400`.
  - [x] 🟩 `test_download_xml_draft_returns_400_even_with_facturapi_id` (regression — drafts still have no XML).
  - [x] 🟩 `test_delete_draft_with_facturapi_id_cascades_to_facturapi` (asserts `delete_draft_invoice` called).

### Phase 2: Frontend

- [x] 🟩 **Step 7: Widen modal + restructure line items** (`frontend/src/app/(app)/facturas/page.tsx`)
  - [x] 🟩 Change `DialogContent` className: `max-w-3xl` → `max-w-5xl`.
  - [x] 🟩 Replace the single 5-column grid at line ~601 with two stacked grids:
        - `grid grid-cols-[5rem_1fr_5rem] gap-3` for Qty / Unit Price / Tax.
        - `grid grid-cols-2 gap-3 mt-3` for Ret. ISR / Ret. IVA.
  - [x] 🟩 Verify the "Add Item" button is fully visible at 1440px viewport.

- [x] 🟩 **Step 8: Two submit buttons in the create form** (`facturas/page.tsx`)
  - [x] 🟩 Add `submitting: "draft" | "stamp" | null` state.
  - [x] 🟩 In `handleCreate`, accept a `draft: boolean` param and append `?draft=true` to the POST URL when true.
  - [x] 🟩 Render two buttons in the form footer: outline + default variants as per UI/UX.
  - [x] 🟩 Disable both while `submitting != null`; show spinner on the active one only.
  - [x] 🟩 Toast copy per UI/UX section.

- [x] 🟩 **Step 9: "Descargar preview" row action** (`facturas/page.tsx`)
  - [x] 🟩 Extract the existing PDF download helper if not already a function (`downloadPdf(facturaId)`).
  - [x] 🟩 In the actions cell, conditionally render a "Descargar preview" button when `row.status === "draft" && row.facturapi_id`.
  - [x] 🟩 Reuse the same endpoint; no new fetch helper.

- [x] 🟩 **Step 10: Frontend tests** (`frontend/tests/facturas/...` — add if dir doesn't exist)
  - [x] 🟩 Modal render test: both buttons visible, have correct labels.
  - [x] 🟩 Form submit test: clicking "Guardar borrador (preview)" posts to `/facturas?draft=true`; "Crear y timbrar" posts to `/facturas` (no query).
  - [x] 🟩 Row action test: "Descargar preview" only renders for drafts with `facturapi_id`.
  - [x] 🟩 Row action test: "Descargar preview" click fetches `/facturas/{id}/pdf` with correct href/URL.

### Phase 3: Verification

- [x] 🟩 **Step 11: Automated test runs**
  - [x] 🟩 `cd backend && pytest tests/test_facturas_router.py -v` — all pass.
  - [x] 🟩 `cd frontend && npx vitest run` — all pass (or the narrower path for facturas tests if suite is large).
  - [x] 🟩 `cd frontend && npx tsc --noEmit` — no type errors.
  - [x] 🟩 `cd frontend && npm run lint` (if configured) — clean.

### Phase 4: Browser Verification (MANDATORY)

- [x] 🟩 **Step 12: Manual QA against Facturapi sandbox** (assumes the `.env` has a test key)
  - [x] 🟩 Start backend + frontend: `make dev` (or separate terminals).
  - [x] 🟩 Navigate to `http://localhost:3001/facturas`.
  - [x] 🟩 Open **New CFDI Invoice**; visually confirm NO fields are clipped at 1440px and at ~1100px viewport.
  - [x] 🟩 Fill in manual-entry fields with a valid RFC (e.g. `XAXX010101000` for test), one line item.
  - [x] 🟩 Click "Guardar borrador (preview)" → toast appears, modal closes, new row shows status `draft` + `facturapi_id` populated.
  - [x] 🟩 Click "Descargar preview" on that row → PDF downloads, contains the line items (no SAT seal).
  - [x] 🟩 Click "Timbrar" on the same row → row updates to status `valid` with UUID; downloaded PDF now has SAT stamp + XML is available.
  - [x] 🟩 Repeat flow using "Crear y timbrar" path → confirm legacy one-shot flow still works.
  - [x] 🟩 Delete a Facturapi draft → row removed AND Facturapi shows it as deleted.
  - [x] 🟩 Console must be clean (zero errors) throughout all flows.

### Phase 5: Documentation

- [x] 🟩 **Step 13: Update docs**
  - [x] 🟩 Add a short section to `docs/plan-eva-erp.md` (or the facturas how-to if it exists) describing the two-step draft flow.
  - [x] 🟩 If no facturas doc exists, create `docs/how-facturas-drafts.md` with: create draft → share PDF → stamp.

### Phase 6: Finalize

- [x] 🟩 **Step 14: Finalize plan + commit**
  - [x] 🟩 Re-read this plan; set all completed checkboxes to `[x] 🟩`; update Overall Progress to `100%`.
  - [x] 🟩 Archive plan to `docs/archive/plans/plan-facturas-draft-and-modal.md`.
  - [x] 🟩 Stage + commit with message like `feat(facturas): draft mode + wider create modal`.
  - [x] 🟩 Do NOT push until Pepe explicitly says to ship.

---

## Technical Details

### Facturapi draft API (confirmed via docs)

- **Create draft:** `POST /v2/invoices` with body `{...normalPayload, "status": "draft"}`. Returns an invoice resource with an `id` (the `facturapi_id` we store), `is_ready_to_stamp: true|false`, computed totals, and a PDF URL. No UUID, no XML.
- **Preview PDF:** `GET /v2/invoices/{id}/pdf` — same endpoint used for stamped invoices, works for drafts too.
- **No XML for drafts:** `GET /v2/invoices/{id}/xml` returns 400 for drafts.
- **Stamp a draft:** `POST /v2/invoices/{id}/stamp` — promotes draft to valid, returns the stamped resource with UUID + XML URL.
- **Delete a draft:** `DELETE /v2/invoices/{id}` (no cancellation motive needed for drafts).

Docs consulted:
- https://docs.facturapi.io/en/docs/guides/drafts/
- https://docs.facturapi.io/en/api/

### Files touched

**Backend:**
- `backend/src/facturas/service.py` — add `create_draft_invoice`, `stamp_draft_invoice`, `delete_draft_invoice`.
- `backend/src/facturas/router.py` — `POST /facturas` accepts `?draft=true`; `POST /facturas/{id}/stamp` branches on `facturapi_id`; `GET /facturas/{id}/pdf` drops the draft-block; `DELETE /facturas/{id}` cascades to Facturapi for Facturapi-drafts.
- `backend/tests/test_facturas_router.py` — new tests (9 listed in Phase 1 Step 6).

**Frontend:**
- `frontend/src/app/(app)/facturas/page.tsx` — modal width, grid restructure, two-button footer, row action.
- `frontend/tests/facturas/*.test.tsx` — new tests (create dir if missing).

**Docs:**
- `docs/how-facturas-drafts.md` — new (or appended to existing facturas doc).

### Data flow — draft push

```
Frontend "Guardar borrador" click
  → POST /facturas?draft=true  body={customer_id?, line_items, ...}
    → router: build Factura model in DB flush (not committed yet)
    → build Facturapi payload
    → facturapi.create_draft_invoice(payload)   [adds status:"draft"]
    → on success: factura.facturapi_id = resp["id"]; totals = resp totals
    → await db.flush() + refresh
  → response: FacturaResponse with facturapi_id populated
Frontend: toast "Borrador guardado"; refetch list
```

### Data flow — stamp existing draft

```
Frontend "Timbrar" click on draft row with facturapi_id
  → POST /facturas/{id}/stamp
    → router: fetch local Factura; status must be "draft"
    → if facturapi_id:
        facturapi.stamp_draft_invoice(facturapi_id)
      else:
        build payload + facturapi.create_invoice(payload)  [legacy]
    → update local row: status=valid, cfdi_uuid, xml_url, series, folio_number, issued_at
  → response: updated FacturaResponse
Frontend: toast + refetch
```

---

## Generalization Check

- [ ] No hardcoded industry-specific terms — facturas are SAT CFDIs, generic Mexican invoicing.
- [ ] Labels configurable — Spanish copy lives in the page file; if/when i18n is added, moves cleanly.
- [ ] Works for any Eva ERP tenant that has a Facturapi key configured.
- [ ] No per-industry branching — the draft flow is fiscal-infrastructure level, not domain-specific.

---

## Comprehensiveness Checklist

- [ ] Re-read the entire conversation.
- [ ] Every feature mentioned is in Features.
- [ ] Every edge case discussed is in Edge Cases.
- [ ] Every error condition has defined behavior.
- [ ] Every decision is documented with rationale.
- [ ] Out of Scope lists what we're NOT doing.
- [ ] A different agent could implement this from the plan alone.

---

## Notes

- **Facturapi account posture:** draft mode assumes the configured API key supports draft creation. If Facturapi's "Drafts" feature requires a specific plan tier, surface a clear error from the first draft push attempt — don't block proactively.
- **Why not a POST body field instead of `?draft=true`:** keeping it a query param avoids a `FacturaCreate` schema bump and is clearer at the URL level ("this request is asking for draft behavior"). If we later want more modes (e.g. async stamping), bump to a body field.
- **Why two buttons not a checkbox:** a checkbox named "do not stamp" is double-negative and confusing; two labeled buttons make the user's intent explicit and reduce mistakes (Pepe has mentioned accidentally stamping is costly).
