# Company CRM

The Empresas section is the source of truth for company relationships in the ERP. A company can exist before it has an Eva account, which supports outbound sales work where many companies are being contacted by text, call, email, WhatsApp, or office visit before they become customers.

## Account Links

- Each company stores the linked Eva account in `empresas.eva_account_id`.
- The Empresas card shows the linked Eva account name when available, or an unlinked state when no Eva account exists yet.
- Existing Eva accounts can be linked from the company edit modal.
- A new Eva account can be created from the company edit modal. The backend provisions the account and writes the new account id back to the Empresa before returning success.
- Account drafts that carry `empresa_id` link the Empresa when approved.
- `/api/v1/empresas/link-eva-accounts/auto-match` can auto-link exact company/account name matches and reports ambiguous, missing, or duplicate candidates.

## Follow-Ups

Company follow-ups live in `empresa_items`. Items can be plain todos or dated CRM events.

Supported item fields include:

- `kind`: `todo`, `event`, `note`, or `outreach`
- `description`
- `contact_method`: `sms`, `whatsapp`, `call`, `email`, `visit`, or `other`
- `due_at`, `start_at`, `end_at`, `reminder_at`
- `assigned_to`
- `done` and `completed_at`

Completing an item keeps `done` and `completed_at` in sync.

## Calendar

The Empresas page includes `Tarjetas`, `Pipeline`, and `Calendario` views. The calendar view calls:

`GET /api/v1/empresas/calendar?start=YYYY-MM-DD&end=YYYY-MM-DD`

By default, the calendar returns incomplete dated items only. Use `include_completed=true` to include completed history.

## Removed Sections

The separate Eva Customers, Strategy/OKRs, Eva AI, and Vault app surfaces are no longer mounted in the main ERP navigation. Historical database tables remain in place; this change only removes unused product surface and backend routes.
