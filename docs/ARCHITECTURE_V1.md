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
