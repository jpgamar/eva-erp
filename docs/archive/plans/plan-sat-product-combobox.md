# SAT Product Key Combobox Implementation Plan

**Overall Progress:** `100%`

> **Implementation:** Use the `/implement-plan` skill to execute this plan.

---

## Requirements Extraction

### Original Request
> "update the sat key to say clave de producto and put a list there with a search bar with the whole sat list"

### Additional Requirements (from conversation)
- Replace the plain text `<Input>` for "SAT Key" in the invoice line items form with a searchable combobox
- Label must read **"Clave de Producto"** instead of "SAT Key"
- The combobox must show a curated list of the ~200 most common SAT product/service codes
- Users must be able to search by code number or description text
- Users must be able to type a custom code if theirs isn't in the curated list

### Decisions Made During Planning
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data source for SAT catalog | Top ~200 common codes as static constant | Full 53K catalog too heavy for bundle; backend endpoint overkill for this use case |
| UI component | Combobox (Popover + Command from shadcn) | Already installed (`cmdk` + `radix-ui popover`), no new dependencies needed |
| Custom entry support | Allow free-text input for codes not in list | Users may need niche SAT codes outside the top 200 |

### User Preferences
- Keep it simple — static data, no backend changes
- Use existing shadcn components

---

## Intended Outcome

When creating a new invoice, each line item shows a **"Clave de Producto"** field that opens a searchable dropdown on click. The dropdown lists ~200 common SAT product codes (e.g. `43232408 - Software`). The user can type to filter by code or description. Selecting an item fills the field. If the desired code isn't listed, the user can type any code manually and it will be accepted.

---

## Features

1. **SAT product codes constant** — ~200 curated entries in `frontend/src/lib/constants/sat-products.ts` with `{ value: string; label: string }` format
2. **SatProductCombobox component** — reusable Popover + Command combobox that searches the catalog and allows free-text entry
3. **Form integration** — replace the `<Input>` at line 512-514 of `facturas/page.tsx` with the new combobox, wired to `updateLineItem(idx, "product_key", value)`
4. **Label rename** — change "SAT Key *" to "Clave de Producto *"

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User types a code not in the curated list | Accept it as-is — free-text entry works |
| User clears the field | Field resets to empty, form validation still requires it (`required`) |
| User searches with no results | Show "No results — type a custom code" message |
| User opens combobox then clicks away | Popover closes, current value preserved |
| Multiple line items | Each line item has its own independent combobox instance |
| Very long description in dropdown | Truncate with ellipsis, show full text on hover/title attr |

---

## Error Handling

| Error Condition | User-Facing Behavior | Technical Response |
|-----------------|---------------------|-------------------|
| Empty product key on submit | Form validation prevents submit (existing `required` attr) | Browser native validation |
| Invalid SAT code sent to Facturapi | Toast error from Facturapi response (already handled) | Existing error handling in `handleCreate` unchanged |

---

## UI/UX Details

- Combobox trigger button styled to match existing `Input` elements (rounded-lg, same height, same text-sm)
- When no value selected: show placeholder "Buscar clave..." in muted text
- When value selected: show the code + short description (e.g. "43232408 - Software")
- Dropdown: search input at top, scrollable list below (max-h-[200px])
- Each dropdown item shows: code in monospace on left, description on right
- "No results" state shows helpful text encouraging manual entry
- Clear button (small X) to reset selection

---

## Out of Scope (Explicit)

- Full 53K SAT catalog — deferred, curated list covers common cases
- Backend search endpoint — not needed for ~200 items
- Virtualized rendering — not needed for ~200 items
- Unit key (c_ClaveUnidad) combobox — separate task if needed
- Autocomplete from Facturapi API — unnecessary complexity

---

## Tasks

### Phase 1: Data (no backend needed)
- [ ] 🟥 **Step 1: Create SAT product codes constant**
  - [ ] 🟥 Create `frontend/src/lib/constants/sat-products.ts`
  - [ ] 🟥 Add ~200 most common SAT product/service codes as `SAT_PRODUCT_KEYS: { value: string; label: string }[]`
  - [ ] 🟥 Organize by category (services, software, consulting, food, retail, construction, medical, transport, etc.)

### Phase 2: Frontend Component
- [ ] 🟥 **Step 2: Build SatProductCombobox component**
  - [ ] 🟥 Create `frontend/src/components/sat-product-combobox.tsx`
  - [ ] 🟥 Use `Popover` + `PopoverTrigger` + `PopoverContent` from `@/components/ui/popover`
  - [ ] 🟥 Use `Command` + `CommandInput` + `CommandList` + `CommandEmpty` + `CommandGroup` + `CommandItem` from `@/components/ui/command`
  - [ ] 🟥 Props: `value: string`, `onChange: (value: string) => void`
  - [ ] 🟥 Trigger shows selected code+description or placeholder "Buscar clave..."
  - [ ] 🟥 Search filters `SAT_PRODUCT_KEYS` by code or description (case-insensitive, handled by cmdk)
  - [ ] 🟥 Empty state: "No results — type custom code" with an input to accept free text
  - [ ] 🟥 Style to match existing form inputs (rounded-lg, text-sm, same height)

- [ ] 🟥 **Step 3: Integrate into facturas form**
  - [ ] 🟥 Import `SatProductCombobox` in `facturas/page.tsx`
  - [ ] 🟥 Replace the `<Input>` at lines 512-514 with `<SatProductCombobox value={li.product_key} onChange={(v) => updateLineItem(idx, "product_key", v)} />`
  - [ ] 🟥 Change label from "SAT Key *" to "Clave de Producto *"
  - [ ] 🟥 Remove placeholder="43232408" (combobox handles its own placeholder)

### Phase 3: Verification
- [ ] 🟥 **Step 4: Verify**
  - [ ] 🟥 TypeScript compiles: `cd frontend && npx tsc --noEmit`
  - [ ] 🟥 Dev server runs without errors
  - [ ] 🟥 Browser test: open New Factura dialog, verify combobox opens, search works, selection fills field, custom entry works, invoice submits successfully

---

## Technical Details

### File changes
| File | Action |
|------|--------|
| `frontend/src/lib/constants/sat-products.ts` | **Create** — curated SAT product codes |
| `frontend/src/components/sat-product-combobox.tsx` | **Create** — reusable combobox component |
| `frontend/src/app/(app)/facturas/page.tsx` | **Edit** — swap Input for combobox, rename label |

### Component API
```tsx
interface SatProductComboboxProps {
  value: string;
  onChange: (value: string) => void;
}
```

### Dependencies (all already installed)
- `cmdk` ^1.1.1 — powers Command component
- `radix-ui` — powers Popover component
- `lucide-react` — icons (Check, ChevronsUpDown, Search)

### SAT Product Codes Structure
```ts
export const SAT_PRODUCT_KEYS = [
  { value: "01010101", label: "01010101 - No existe en el catalogo" },
  { value: "43232408", label: "43232408 - Software" },
  { value: "80141600", label: "80141600 - Servicios de marketing" },
  // ... ~200 entries
];
```

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

- No backend changes required — this is purely a frontend enhancement
- The `product_key` field name in the form state and API payload stays the same — only the UI input changes
- The existing form validation (`required`) continues to work since the combobox sets the value via `onChange`
