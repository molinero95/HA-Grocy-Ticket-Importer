# Despensa 1.0 — architecture and migration

## Invariants
- Grocy remains the source of truth for catalog, stock, quantities and shopping list.
- Never merge catalog entries, mutate stock, or resolve ambiguous Alexa identities without explicit authorized action.
- Preserve existing Home Assistant add-on settings, data paths, ingress and synchronization.
- Release 0.16.4 remains the production implementation until feature parity and e2e tests pass.

## Target boundaries
- `frontend/`: React + TypeScript, Vite, TanStack Query, mobile-first components; **no Grocy credentials** in browser.
- `/api/v1/`: Flask JSON adapter, authenticated via existing ingress/session boundaries; explicit validation and consistent errors.
- Python domain services: Grocy catalog, stock, barcode identity, Alexa synchronization, receipt import.
- Home Assistant packaging: build static frontend in CI/Docker; serve it under ingress prefix with Flask API on the same origin.

## Rollout
1. Read-only shopping JSON endpoint and preview React UI (current branch).
2. CSRF-protected shopping commands, per-item Alexa candidate selection and optimistic UI with rollback.
3. Inventory, product details, barcode camera and supermarket variants.
4. Ticket upload, review, simulation, stock mutations and all remaining screens.
5. Playwright ingress/mobile e2e, data-preservation regression tests, accessibility and API contract tests.
6. Remove inline Flask templates only after parity; publish 1.0.0 with migration notes.

## Safety
Do not switch the ingress entrypoint to the React app before authentication, write actions, error handling and feature parity are complete. Preview must not change existing add-on behavior.

## Cleanup and removal ledger

| Legacy component | Replacement | Removal gate |
| --- | --- | --- |
| Inline `PAGE` HTML/CSS/JS in `web.py` | React components and styles | Every screen has passing parity/e2e tests |
| Flask form POST + redirects | Typed `/api/v1` commands | All clients use JSON commands with CSRF |
| Duplicated root/add-on Python modules | Single Python source package | Docker and local tests import same package |
| Legacy browser-JavaScript syntax check | Vite TypeScript build and frontend tests | Inline scripts removed |
| Unused dependencies and transitional adapters | Audited runtime dependencies | No remaining imports and clean container build |

**Do not remove** SQLite data, Home Assistant options, Grocy product/stock data, or Alexa sync checkpoints as part of source cleanup. Deletions must be independently reviewed and tested; the first 1.0 preview does not change production entrypoints.

## Implementation update — 2026-11-01

The canonical frontend now lives inside the add-on build context at
`ha_grocy_ticket_importer/frontend/`; `/frontend` is a development symlink.
Docker builds it with Node 22 and the npm lockfile, copies the resulting static
assets, and includes every extracted API module. Flask exposes an opt-in
`/react/` preview with an ingress-root base URL; stable `/` is unchanged.

`api_photos.py` centralizes photo discovery/upload and local image URLs.
`stock_commands.py` isolates the durable consumption-command journal from the
receipt ledger. SQLite write-ahead records reject uncertain repeats; they do not
pretend to make the remote Grocy write transactional. Product metadata edits
preserve purchase setup and descriptions, with fail-closed unit changes.

CI uses network-free Python/React regressions and Chromium mobile/ingress tests
against disposable Flask fixtures. Pack conversion, destructive catalog lifecycle
and real Grocy/HA upgrade verification still gate default rollout and legacy removal.

Pack conversion uses Grocy 4's `objects/quantity_unit_conversions` contract,
verified before initial stock; stock writes are already in Piece units. Receipt
imports read the same conversion table and preserve pending/imported markers.
No `qu_factor_purchase_to_stock` field is written to product objects. Reference:
https://github.com/grocy/grocy/blob/master/services/StockService.php
(`ExternalBarcodeLookup` and `GetProductDetails`). Live schema validation is still required.
