# Despensa 1.0 — Legacy/React parity gate

Current implementation status: 2026-11-01. PR #10 is an unreleased migration branch.
Stable `main` and the default ingress UI remain at 0.16.4. Historical roadmap notes
are not evidence of validation on the current head.

Canonical frontend: `ha_grocy_ticket_importer/frontend/`; root `frontend` is a
symlink. The add-on Dockerfile builds static assets and serves `/react/` as an
opt-in preview. Python adapters and their root/package mirrors remain identical.

| Workflow | React implementation | Remaining migration gate |
| --- | --- | --- |
| Shopping read, complete, remove, clear completed | v1 API, pending states, aligned mobile actions, product-sheet links | Full failure recovery and live Grocy semantics |
| Alexa ambiguous product selection | Inline suggestions, selection, durable keep-original dismissal | Isolated live list/checkpoint restart test; no automatic conversion |
| Inventory, name/barcode search, shopping +/- | Automatic exact-code filtering, race isolation, cart/stepper in place | Physical mobile camera validation |
| Variants | List/create/edit, barcode scanner, server ownership checks | Browser lifecycle, upgrade persistence and isolated Grocy integration |
| Receipt upload, preview, commit | Simulation digest, shared preview/commit lock, write-ahead marker, UI resubmission block | Full browser import/restart workflow with isolated Grocy |
| Product creation/editing | Duplicate detection, existing-sheet link, verified Pack conversion, preserves purchase/photo metadata on rename | Live Pack contract and partial-create reconciliation |
| Product deletion | Read-only eligibility audit, destructive operation blocked | Complete dependency/history contract; no stock-consuming deletion |
| Stock adjustments | Expected-stock guard, current product query, no extra confirmation screen | Live units and audit verification |
| Consumption | Product ID without EAN, precise quantity, optional refill, durable operation replay/uncertainty guard | Isolated Grocy endpoint and restart integration |
| Barcode association/removal | API safeguards, variant ownership protection, scanner, photo discovery | Complete reassignment and browser regression matrix |
| Product merge | Read-only dependency preview, disabled merge | Explicitly approved consolidation plan and complete reference migration |
| Product photos | Exact-code preview/save, trusted server URL, sanitized local upload, all three views, cache version | Physical camera and upgrade persistence validation |
| Catalog audit | Read-only review and JSON export | Integration against installed Grocy schema |
| Standalone authentication | Public CSRF bootstrap, rotation, logout, expired-session cache clearing | Final security review of candidate deployment |
| Mobile and HA ingress | Three primary tabs, focus/scroll management, fixed action columns, prefixed assets/APIs | Physical Android/HA validation and broader browser coverage |
| Packaging | Multi-stage React build, runtime API modules, npm lockfile, source/dependency checks | Final-head Docker CI result and isolated container startup |

## Validation and release criteria

1. Preserve the stable UI until every required workflow is implemented or the user explicitly scopes it out. Keep `PAGE`, legacy routes and their dependencies until then.
2. Run Python tests, source-mirror checks, embedded JavaScript syntax, React tests, TypeScript/build, mobile/ingress Playwright and container build on the **final** head.
3. Browser fixtures replace external Grocy/Alexa I/O; passing them is not validation against the installed services.
4. Test upgrade persistence of receipt ledger, photos, generic/variant catalog, scoped Alexa queue/checkpoints and stock-command journal. Never delete persistent state as source cleanup.
5. Live Pack validation and destructive product lifecycle remain release blockers. Do not describe the migration as complete, enable destructive operations or remove legacy based only on a passing frontend build.
6. Only after parity and green CI: switch the default UI, separately remove obsolete HTML/JS/routes, then prepare release notes and 1.0.0. No version bump or publication is authorized before these gates.
