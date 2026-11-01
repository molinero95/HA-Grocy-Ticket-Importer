# AGENTS.md — Despensa / Grocy Ticket Importer

## Current handoff — 2026-11-01

PR #10 and release PR #11 are merged; main has Despensa 1.0.0. Current work in `fix/simplify-product-stock` prepares 1.1.0: remove the separate consumption form, keep the remaining-total stock adjustment, move archives to Actions, style New product in the pantry, remove its duplicate Actions shortcut and keep only input/camera for automatic search. Manual Alexa choices must materialize usable Grocy rows immediately; Remove must be available for unresolved suggestions too. The user manages Home Assistant; do not install/restart the production add-on, refresh its store or change sync options. Never claim installed acceptance without observing it.

Read `DECISIONS.md`, `ROADMAP.md`, `docs/REACT_PARITY.md`, `README.md` and the add-on `DOCS.md`. Verify actual GitHub branch/checks before work. Never describe a deployment or CI success without observing it. Installed Grocy read-only checks now pass using its existing internal service port 80 and existing API key; ingress proxy alone returned 403. Grocy 4.7.1 / PHP 8.5.12 matches isolated validation. Do not change security/options or use production stock for exploratory tests. The configured HA todo entity also returned valid pending uid/summary/status records.

## Implementation

- Canonical React 19 / TypeScript 7 / Vite 7 / Vitest 4 frontend: `ha_grocy_ticket_importer/frontend/`. Root `frontend` is a development symlink. Docker builds static assets. The candidate serves React at `/`, retains `/react/` as alias, and has a small script-free `/basic` shopping fallback. The old full inline PAGE, scripts and form routes have been removed on this feature branch after isolated Grocy/browser validation.
- `web.py`: ingress prefix, session/CSRF/authentication, static files, fallback and API registration. `api_*.py`: JSON adapters. Browser never receives Grocy credentials.
- `barcode_stock.py`, `purchase_units.py`: catalog, stock, shopping and verified per-product Pack conversions. `catalog_lifecycle.py`: reversible archive/restore, never cascading product deletion.
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
- Quantity max two decimals; kg step 0.10, Piece step 1. Mutate shopping by verified row ID in list 1, preserving notes, completed rows and other lists.
- Archive only known-zero-stock products with no active dependencies; restore changes only `active`. Retain stock history, barcode ownership and metadata. Merge remains read-only audit; no authorized catalog consolidation exists.
- Photo lookup is advisory and exact-code only. Validate trusted HTTPS hosts server-side; sanitize uploads. A missing image must not block catalog operations.

## UX requirements

Spanish, mobile first. Default Lista de la compra; other tabs Mi despensa and Acciones. Cart becomes inline quantity stepper without page reload/scroll reset. Consistent action columns for long names/photos. Product sheets hold barcode/variant, photo, stock and purchase editing. Create-product checks duplicate name/EAN, links existing sheet and never adds stock on duplicate. Product sheets use only the final-stock total; no separate consumption form. Creation is only in Mi despensa, archives are in Acciones. The consumption API/journal and its protections remain intact. Tickets require reviewed simulation of unchanged bytes before commit. Camera has manual input fallback.

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

Frontend QA: 66 Vitest tests, 222 Python tests, 6 real Grocy contracts and 15 configured Chromium scenarios after removing the unused consumption component/tests and adding stock/navigation regressions. `npm run test:coverage` produces V8 HTML/LCOV/JSON reports and CI uploads `frontend-coverage`; reports are excluded from Git, Docker context and install archives. New regressions cover uncertain/duplicate writes, remaining-total stock adjustment, receipts/preview readiness, session expiry/late reads, pack factors, variants/photos, camera cleanup and keyboard/responsive layouts. Local browser runs without `GROCY_TEST_DIST` execute 11 and explicitly skip 4. Keep the auth query observed when expiring/logging out; remove private caches after the authenticated view unmounts to prevent recreating active reads.

## Release maintenance

A version bump requires matching entries in BOTH identical `CHANGELOG.md` files and aligned README/DOCS. Manifest, frontend package/lockfile and visible footer versions must match (1.1.0 for this minor release). Home Assistant reads the default-branch manifest; no GitHub Release or new installation is required for update detection. Keep the previous installation and Home Assistant backup until the installed upgrade is accepted.
