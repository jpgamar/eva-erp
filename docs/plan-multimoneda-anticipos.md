# Plan: Control de Anticipos y Tipo de Cambio

**Status:** In Progress
**Overall Progress:** 85%

---

## Phase 1 — Proveedores Module (Backend + Frontend)
> Anticipos need a vendor to reference. Today vendors are just a text field on Expense.

- [x] 🟩 **1.1** Create `backend/src/proveedores/` module (models.py, schemas.py, router.py)
- [x] 🟩 **1.2** Alembic migration for `proveedores` table
- [x] 🟩 **1.3** Register model in `backend/src/models/__init__.py`
- [x] 🟩 **1.4** Frontend: types in `types/index.ts`, API client `lib/api/proveedores.ts`
- [x] 🟩 **1.5** Frontend: `/proveedores` page with table + create/edit dialog
- [x] 🟩 **1.6** Add sidebar nav item for Proveedores

---

## Phase 2 — Exchange Rate Enhancements
> Today there's one rate row. We need daily history + Banxico auto-fetch.

- [x] 🟩 **2.1** Extend `ExchangeRate` model: add `rate_type` field (FIX, SPOT, MANUAL)
- [ ] 🟥 **2.2** Banxico FIX auto-fetch: new service `backend/src/finances/banxico_service.py`
- [x] 🟩 **2.3** Alembic migration: add `rate_type` column
- [ ] 🟥 **2.4** Frontend: exchange rate history view
- [ ] 🟥 **2.5** Frontend: "Sync Banxico" button

---

## Phase 3 — Freeze Exchange Rate on Existing Tables
> Every financial transaction should lock its rate at creation time.

- [ ] 🟥 **3.1-3.5** Add exchange_rate + base_amount_mxn to existing tables (income, expenses, deposits, cash)
  - Deferred — existing tables work fine, new tables (anticipos, facturas_prov) have this built-in

---

## Phase 4 — Anticipos Module (Backend)

- [x] 🟩 **4.1** Create `backend/src/anticipos/` module (models.py, schemas.py, router.py)
- [x] 🟩 **4.2** Model `Anticipo` with frozen exchange_rate, base_amount_mxn, status tracking
- [x] 🟩 **4.3** Model `AnticipoApplication` (junction: anticipo ↔ factura_proveedor with exchange diff)
- [x] 🟩 **4.4** All endpoints: CRUD + apply + summary
- [x] 🟩 **4.5** Alembic migration
- [x] 🟩 **4.6** Register models in `models/__init__.py` and routers in `main.py`

---

## Phase 5 — Facturas Proveedor (Vendor Bills)

- [x] 🟩 **5.1** Create `backend/src/facturas_proveedor/` module
- [x] 🟩 **5.2** Model `FacturaProveedor` with exchange_rate, base_total_mxn, paid_amount tracking
- [x] 🟩 **5.3** CRUD endpoints + cancel
- [x] 🟩 **5.4** Alembic migration
- [x] 🟩 **5.5** Register model and router

---

## Phase 6 — Diferencias Cambiarias (Exchange Gain/Loss Tracking)

- [x] 🟩 **6.1** Model `DiferenciaCambiaria` in facturas_proveedor/models.py
- [x] 🟩 **6.2** Auto-create entries when anticipo is applied to bill
- [x] 🟩 **6.3** Endpoints: list + summary with period filtering
- [x] 🟩 **6.4** Alembic migration (same migration as phases 1/4/5)

---

## Phase 7 — Frontend: Anticipos Page

- [x] 🟩 **7.1** Types in `types/index.ts`
- [x] 🟩 **7.2** API client `lib/api/anticipos.ts`
- [x] 🟩 **7.3** Page `/anticipos` with summary cards + table + filters
- [x] 🟩 **7.4** Create anticipo dialog with auto exchange rate
- [x] 🟩 **7.5** Apply anticipo dialog with exchange difference preview

---

## Phase 8 — Frontend: Facturas Proveedor Page

- [x] 🟩 **8.1** Types + API client
- [x] 🟩 **8.2** Page `/facturas-proveedor` with summary, table, filters
- [x] 🟩 **8.3** Create dialog with total preview

---

## Phase 9 — Frontend: Diferencias Cambiarias Report

- [x] 🟩 **9.1** Types + API client
- [x] 🟩 **9.2** Standalone `/diferencias-cambiarias` page with summary cards + period breakdown + table
- [ ] 🟥 **9.3** Export to CSV/Excel

---

## Phase 10 — Sidebar Navigation + Integration

- [x] 🟩 **10.1** Add nav items: Proveedores, Anticipos, Facturas Proveedor, Dif. Cambiarias
- [x] 🟩 **10.2** Page titles in layout.tsx
- [ ] 🟥 **10.3** Dashboard widget: open anticipos count + pending amount

---

## Remaining (nice-to-have, can ship without)

- [ ] 🟥 Banxico FIX auto-fetch service (Phase 2.2)
- [ ] 🟥 Exchange rate history UI (Phase 2.4-2.5)
- [ ] 🟥 Freeze rates on existing finance tables (Phase 3)
- [ ] 🟥 CSV export for diferencias cambiarias (Phase 9.3)
- [ ] 🟥 Dashboard widget for anticipos (Phase 10.3)
