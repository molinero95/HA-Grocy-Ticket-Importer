# AGENTS.md — Despensa / Grocy Ticket Importer

## Current handoff — 2026-11-01

Main has 1.12.0 (PR #25, merge 697c494). Current branch `feat/alexa-stock-photo-lookup` prepares 1.13.0 with two user-authorized features: a dedicated read-only Alexa stock endpoint, and advisory full-product-photo recognition when public barcode lookup has no name/is unavailable. The user explicitly defers Cloudflare/Amazon configuration until after implementation. Do not change installed HA options, tunnel routing, Amazon accounts or invoke paid recognition on private photos during development.

Voice runs only when enabled, in its own process/listener on internal port 8100, with only POST /alexa/despensa; ordinary panel APIs stay on existing authenticated ingress. Verify SHA-256, system-trusted X.509 chain/SAN, timestamp, exact configured skill and user; never add an unsigned test mode to production. Read stock via GET and metadata through read-only SQLite. Recognition uses explicit CSRF-protected upload, full-frame resized/sanitized image, existing OpenAI credentials, store=false, no auto-retry or automatic catalog/stock/barcode/pack mutation. Ignore late UI responses and keep manual entry.

See docs/ALEXA_SKILL.md and the es-ES interaction model. Local checks: 346 Python, 100 Vitest with coverage, TypeScript/Vite build, 14 real Grocy contracts and 28 Chromium scenarios passed; mobile photo preview visually reviewed. Final-head CI must be observed and recorded in the PR. Preserve all existing receipt/variant/photo/queue/journal state. No subagents unless user/skill asks.

Read `DECISIONS.md`, `ROADMAP.md`, `docs/REACT_PARITY.md`, `README.md` and the add-on `DOCS.md`. Verify actual GitHub branch/checks before work. Never describe a deployment or CI success without observing it. Installed Grocy read-only checks now pass using its existing internal service port 80 and existing API key; ingress proxy alone returned 403. Grocy 4.7.1 / PHP 8.5.12 matches isolated validation. Do not change security/options or use production stock for exploratory tests. The configured HA todo entity also returned valid pending uid/summary/status records.

## Implementation

- Canonical React 19 / TypeScript 7 / Vite 7 / Vitest 4 frontend: `ha_grocy_ticket_importer/frontend/`. Root `frontend` is a development symlink. Docker builds static assets. The candidate serves React at `/`, retains `/react/` as alias, and has a small script-free `/basic` shopping fallback. The old full inline PAGE, scripts and form routes have been removed on this feature branch after isolated Grocy/browser validation.
- `web.py`: ingress prefix, session/CSRF/authentication, static files, fallback and API registration. `api_*.py`: JSON adapters. Browser never receives Grocy credentials.
- `barcode_stock.py`, `purchase_units.py`: catalog, stock, shopping and verified per-product Pack conversions. `catalog_lifecycle.py`: reversible archive/restore and audited deletion of unused archives; movement history requires explicit acknowledgement.
- `importer.py`: receipt ledger and Grocy import. `stock_commands.py`: persistent at-most-once command journal; uncertain writes require reconciliation, never automatic replay.
- `api_photos.py`, `product_images.py`: sanitized local photos and trusted exact-barcode lookup. Existing photos take precedence.
- `generic_catalog.py`, `variant_catalog.py`: additive variant metadata with audited Grocy barcode ownership. Variant factors are descriptive; the canonical product purchase configuration controls stock conversion. No automatic consolidation.
- `shopping_identity_*`, `shopping_sync_*`: optional canonical-ID Alexa synchronization, scoped v2 checkpoint and first-run union. `shopping_match_queue.py`: scoped review SQLite; `shopping_choice_conversion.py`: explicitly selected note association, preserving row ID, amount and note. Explicit manual choices/keep-original now create or associate a single manageable Grocy row immediately. Queue metadata records attached row IDs, review generations and removal intent; shared file locking serializes manual actions and worker. Worker-only read mode never writes Alexa. Explicit removals override first-union re-import and propagate to Alexa only in enabled sync, with source-absence verification. Preserve removal metadata and the command journal.

## Binding safety rules

- Grocy is the sole source of truth for products, stock and its default shopping list. No secondary shopping database; no speculative production writes.
- Preserve receipt ledger, photos, variant SQLite, queues, checkpoints and command journal. Never delete pending records to enable retries, uninstall an existing add-on to upgrade, or overwrite existing data in bootstrap.
- Root application Python modules and their `ha_grocy_ticket_importer/` copies MUST remain byte-identical. Include every runtime module in Docker COPY and CI mirror checks. Tests remain at root/`tests/`.
- Every mutation requires session/ingress authorization and CSRF. Respect shared mutation lock, expected-state guards and uncertain/partial outcomes. Never automatically retry consumption or import.
- Keep secrets/options, actual receipts, private lists, photos and production databases out of output, Git and artifacts. Do not dump HA add-on configuration.
- Pack is purchase unit; Piece is stock/consumption unit. Discover unit IDs by names, never fixed numeric IDs. Conversion lives in `quantity_unit_conversions`; Grocy can create factor-1 rows automatically. Never rewrite existing Pack stock into pieces.
- Rename preserves description, photo and purchase configuration. Stock-unit edits require known zero stock and compatible purchase settings. Purchase edits affect future purchases only, verify unchanged stock and reject shopping references.
- Manual catalog/shopping quantities max two decimals; weighed receipt quantities preserve up to three decimals; kg step 0.10, Piece step 1. Mutate shopping by verified row ID in list 1, preserving notes, completed rows and other lists.
- Archive only known-zero-stock products with no active dependencies; restore changes only `active`. Retain stock history, barcode ownership and metadata when archiving. Guarded permanent deletion is explicitly authorized for unused archived products only. Native guarded consolidation is now user-authorized; no production merge should be performed by the agent.
- Photo lookup is advisory and exact-code only. Validate trusted HTTPS hosts server-side; sanitize uploads. A missing image must not block catalog operations.

## UX requirements

Spanish, mobile first. Default Lista de la compra; other tabs Mi despensa and Acciones. Cart becomes inline quantity stepper without page reload/scroll reset. Consistent action columns for long names/photos. Product sheets hold barcode/variant, photo, stock and purchase editing. Create-product checks duplicate name/EAN, links existing sheet and never adds stock on duplicate. Product sheets contain product information and the final-stock total; no consumption or add-to-shopping form. Shopping controls stay in pantry/list rows. Standalone creation is in Mi despensa; shopping/Alexa review also offers contextual zero-stock creation + association. Archives are in Acciones. The consumption API/journal and its protections remain intact. Tickets require reviewed simulation of unchanged bytes before commit. Camera has manual input fallback.

## Verification

```bash
python -m unittest discover -v -p 'test_*.py'
cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

CI also runs the unmodified, SHA-verified Grocy 4.7.1 release with disposable local data using PHP 8.5 + pdo_sqlite, intl, mbstring, fileinfo, gd, ctype. See `docs/VALIDATION_V1.md` for reproduction and actual service boundaries. With `GROCY_TEST_DIST` set, all real-stack browser tests run; without it they explicitly skip. Test routes and local authentication bypass live only in `tests/real_stack_server.py`, never production modules.

Check final-head GitHub Actions: frontend, AMD64 and ARM64 container build/start, mirror checks and Python regressions. An empty combined status is not CI success. Physical Android camera and installed HA/Alexa upgrade smoke are deployment acceptance, distinct from automated isolated validation.

Frontend QA: 91 Vitest tests, 317 Python tests, 12 real Grocy contracts and 27 configured Chromium scenarios after removing the unused shopping and consumption components/tests and adding stock/navigation regressions. `npm run test:coverage` produces V8 HTML/LCOV/JSON reports and CI uploads `frontend-coverage`; reports are excluded from Git, Docker context and install archives. New regressions cover uncertain/duplicate writes, remaining-total stock adjustment, receipts/preview readiness, session expiry/late reads, pack factors, variants/photos, camera cleanup and keyboard/responsive layouts. Local browser runs without `GROCY_TEST_DIST` execute 19 and explicitly skip 8. Keep the auth query observed when expiring/logging out; remove private caches after the authenticated view unmounts to prevent recreating active reads.

## Release maintenance

A version bump requires matching entries in BOTH identical `CHANGELOG.md` files and aligned README/DOCS. Manifest, frontend package/lockfile and visible footer versions must match (1.13.0 for this minor release). Home Assistant reads the default-branch manifest; no GitHub Release or new installation is required for update detection. Keep the previous installation and Home Assistant backup until the installed upgrade is accepted.

Permanent deletion is enabled only for the audited Grocy 4.7.1 release; a different version stays archived until its cascades have been reviewed.

`stock_thresholds.py` stores display-only amount/warning_enabled in the existing generic catalog. Do not use Grocy min_stock_amount: it may auto-add shopping rows. Defaults are 0/enabled, inclusive <= comparison; opt-out suppresses color/status badges and retains its threshold. API uses expected amount/enabled guards and never writes Grocy. Include this module in mirrors/Docker/CI.
