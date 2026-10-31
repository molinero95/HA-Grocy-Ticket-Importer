# Despensa 1.0 — Legacy/React parity gate

The stable Home Assistant UI must remain available until the React frontend replaces its workflows. The versioned JSON API is extracted into `api_inventory.py`, `api_shopping.py` and `api_variants.py`. **Do not delete `PAGE`, legacy routes, or their dependencies just because the React build passes.**

| Workflow | Legacy route(s) | React status | Migration gate |
| --- | --- | --- | --- |
| Shopping list read, complete, remove | `/shopping/*` | Implemented through v1 API | End-to-end ingress and CSRF smoke test |
| Alexa ambiguous product selection | `/alexa/match/choose` | Implemented through v1 API | Verify keeping original does not requeue the same suggestion |
| Inventory, name/barcode search, shopping +/- | `/inventory/barcode-lookup`, `/shopping/step/*` | Implemented through v1 API | Test mobile camera and scanner fallback |
| Generic product variants | `/product/*/variant` | Variant list and edit/create in React | Verify barcode ownership conflicts and stock invariants |
| Receipt upload, preview and commit | `/upload`, `/preview/*`, `/commit/*` | Implemented through v1 API and React | Add v1 API and React workflow with import tests |
| Product creation, editing and deletion | `/barcode/add`, `/product/*/edit`, `/product/*/delete` | Create/edit implemented; deletion read-only safety check, destructive action blocked | Confirm safe product lifecycle and Grocy errors |
| Stock adjustments | `/product/*/stock-save`, `/product/*/edit-all` | Implemented with stale-stock guard | Validate units/packs and audit trail |
| Barcode association and removal | `/barcode/associate`, `/barcode/remove*`, `/product/*/barcode` | Implemented with variant ownership checks | Add reassignment/removal safeguards |
| Product merge | `/product/*/merge-preview` | Read-only preview and dependency audit; merge disabled | Preview and conflict-confirmation flow |
| Product photos | `/product/*/photo*`, `/photo/lookup`, `/barcode/photo` | Upload implemented; display/lookup parity incomplete | Upload, fetch and persistence tests |
| Catalog audit | `/catalog/audit` | Read-only audit and JSON export implemented | Expose audit read-only and review UI |
| Clear completed shopping | `/shopping/clear-completed` | Implemented in React with confirmation | Confirm bulk-operation semantics |
| Login/logout outside HA ingress | `/login`, `/logout` | Implemented in v1 API and React; HA ingress bypass preserved | Test CSRF, session expiry, failed password and logout |

## Release criteria

1. Maintain stable add-on and old UI until missing workflows are implemented or explicitly scoped out with user approval.
2. Keep root and packaged Python modules identical; run Python unit tests, frontend tests, typecheck, build and container build in CI.
3. Test Home Assistant ingress prefix, authenticated session, CSRF rejection, barcode conflicts, shopping synchronization, receipt import and failure recovery.
4. Verify mobile UI without page reload or scroll reset; document any supported-browser limitations.
5. Only after parity and green CI: switch the default UI to React, release notes, then remove obsolete HTML/JS and legacy endpoints in a separate cleanup PR.
