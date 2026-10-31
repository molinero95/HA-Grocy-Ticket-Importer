# ROADMAP.md — Despensa backlog and validation checklist

Last reviewed: 2026-10-31. Prioritized by correctness/safety, not by release date.

## P0 — Validate before claiming a release is ready
- [ ] Obtain and inspect **GitHub Actions Check** and other CI job results after each code change. A prior failure was **Browser JavaScript syntax**, caused by raw Jinja expressions inside a `<script>` block. This was addressed in v0.7.3, but a successful workflow result was not confirmed by the connected API.
- [ ] Execute all `test_*.py` tests and fix failures (especially legacy fixtures expecting Pack stock rather than Piece stock); add direct regression tests for important flows.
- [ ] Verify package-root source mirrors remain identical.
- [ ] Check Grocy API request formats and semantics in the actual Grocy version for shopping-list add/remove, display quantities, Pack purchase factors, and product photo metadata. Do not modify real stock merely to probe APIs.
- [ ] Verify zero stock, repeated clicks, duplicate barcodes, out-of-stock consumption and partial API failures.

## P1 — Pack/Piece and purchasing correctness
- [ ] Ensure new Pack products save `qu_id_stock=Piece`, `qu_id_purchase=Pack` and the correct `qu_factor_purchase_to_stock`.
- [ ] Confirm purchased 2 packs of 5 become exactly 10 stock pieces, and consuming 1 subtracts one piece.
- [ ] Audit receipt importer handling: a receipt item expressed as Pack should be converted to Piece using product-specific factors. Do not assume product creation/stock edit changes automatically apply to ticket import.
- [ ] Design an explicit, backed-up migration for **existing** products currently using Pack as the stock unit. Never change quantities silently.
- [ ] Confirm the Add product and product-sheet UI makes stock unit vs purchase unit clear, and editing Piece↔Pack with existing inventory results in a useful in-app error rather than a generic ingress/Cloudflare page.

## P1 — Mobile shopping UX
- [ ] Manually test the no-list **🛒 Añadir → − quantity + → 🛒 Añadir** flow, with no reload/scroll jump.
- [ ] Verify amounts and display for kg (0.10 kg increments), Piece (increments of 1), and products with previously purchased/completed entries.
- [ ] Test shopping-list button alignment with one-word and very long names on a narrow Android viewport; long text should wrap without moving action columns.
- [ ] Inspect single-request failure handling and state recovery after interrupted network calls.

## P2 — Photos, documentation and maintenance
- [ ] Verify barcode scan triggers Open Food Facts lookup and photo persists for new/existing products, then appears in all three views.
- [ ] Clean stale explanatory copy in README and add-on DOCS: prior versions described Pack as a stock unit and photos as not saved. Use `DECISIONS.md` as current product intent.
- [ ] Review source-of-truth packaging, dependencies, release tagging and CI availability; ensure new agents have adequate access to workflow logs.
- [ ] Maintain a concise changelog for shipped versions when CI is confirmed.

## Release process
1. Read `AGENTS.md` and `DECISIONS.md`; inspect source, tests and installed add-on version.
2. Make a coherent change with regression coverage; synchronize mirrored files.
3. Run tests and inspect CI, including JavaScript syntax checks.
4. Increment `ha_grocy_ticket_importer/config.yaml` version only when preparing a releasable set of changes.
5. Report what is committed, what is tested, and what remains unverified; do not imply Home Assistant has installed GitHub's latest version.


## P0 — Alexa ↔ Grocy synchronization (PR #2, experimental)
- [x] Pure normalization/reconciliation planner and initial tests.
- [x] Initial Alexa/Grocy read/write adapters, durable checkpoint and optional 120-second worker.
- [x] Package proposed v0.7.11 with `homeassistant_api: true` and disabled-by-default `shopping_sync_enabled`.
- [ ] Verify `todo.get_items` REST response and Supervisor token access in the actual add-on.
- [ ] Verify Grocy note-only `objects/shopping_list` create, and delete semantics with actual Grocy 4.7.1.
- [ ] Test interruption between remote writes and checkpoint, duplicate names, completed items, concurrent edits and quantity preservation.
- [ ] Run all Python tests and GitHub Actions including packaging/build; verify success explicitly.
- [x] Replace hardcoded Alexa entity ID with configurable option and document discovery.
- [ ] Validate configured entity exists and belongs to Alexa Devices (not an unrelated todo list).
- [ ] Validate real two-way flow with a disposable item, then activate on Home Assistant; do not touch inventory stock.
- [ ] Decide how to handle completion vs deletion, rename and quantity changes.

## P0 — Generic catalog and supermarket variants (PR #5)

- [x] Additive SQLite metadata for canonical Grocy products and variants.
- [x] Reject cross-product barcode ownership in both Grocy and local metadata.
- [x] Product-sheet variant form with camera scanner; no stock writes.
- [x] Read-only JSON audit export of Grocy stock, units, barcodes, shopping
  references and locally registered variants.
- [ ] Verify current PR head CI and Docker image build (do not infer from earlier commits).
- [ ] Verify real Grocy barcode association and persistence across an HA upgrade.
- [ ] Implement identity-aware Alexa sync with durable ambiguity queue,
  manual selection and no loss of original free-text items.
- [ ] Validate duplicate product migration plan and obtain explicit approval
  before any product consolidation or deletion.
- [ ] Prepare version bump and identical root/add-on changelogs only when
  shipping a tested increment.

### Alexa review progress (PR #5)
- [x] Persist ambiguous Alexa candidate suggestions without modifying the
  original Alexa/Grocy shopping entry.
- [x] Allow manual selection in an authenticated CSRF-protected screen.
- [ ] Consume explicit selections in an identity-aware reconciliation planner
  without changing/removing original notes until the full operation is verified.
- [ ] Handle concurrent edits, quantity preservation and restart recovery.

### Identity-aware Alexa v2 progress (PR #5)

- [x] Implement ID-keyed planner with free-text notes, explicit choices and
  collision detection for both original and canonical product names.
- [x] Implement atomic v2 checkpoint and persisted Alexa name-to-product
  bindings, with fail-closed checks for stale choices and changed identities.
- [x] Add adapter guards against concurrent Grocy quantity/note edits and
  duplicate Alexa removals, plus network-free regression coverage.
- [x] Scope manual-choice queues and v2 checkpoints to the configured Alexa
  entity; preserve legacy data without unsafe automatic migration.
- [ ] Validate CI for the final PR head after all edits and inspect Docker build.
- [ ] Verify live Home Assistant todo service and Grocy 4.7.1 shopping API
  read/write semantics with disposable items, including restart recovery.
- [ ] Validate mobile variant editor, camera, stock invariants and persistent
  app_config metadata on the installed add-on before enabling sync.
- [ ] Prepare a release version with identical root/add-on changelogs and
  merge only after the above release gates pass.

### Read-only integration verification — 2026-10-31
- [x] Home Assistant MCP access recovered; installed Grocy and Despensa add-ons both report started.
- [x] Main Alexa todo entity is discoverable and readable via Home Assistant; 8 active items observed. Do not store their names or personal data in the repository.
- [x] Installed Despensa remains 0.15.0; PR candidate 0.16.0 is **not** deployed.
- [ ] Validate add/remove and restart recovery against disposable items on the candidate build. Read-only access alone does not establish write semantics.
- [ ] Validate variant camera, Grocy barcode persistence and shopping API on the installed candidate before merge.


## PR #5 finalization handoff — 2026-10-31

- Removed unused duplicate `shopping_sync_identity.py` preview and its mirror/test;
  `shopping_identity_sync.py` is the single authoritative v2 planner.
- Added fail-closed protection when an unresolved Alexa suggestion overlaps a
  product already present in Grocy's shopping list, plus regression tests.
  Do not create a duplicate free-text note or infer the product automatically.
- The preceding GitHub Actions run 41240799152 passed Python 3.11/3.13,
  embedded JS checks, source mirrors, Docker build and tests. **The newer
  commit requires its own successful CI run** (41240890623 was running when
  last inspected); recheck the current PR head before merging.
- Home Assistant MCP returned HTTP 403 when rechecking the live todo list and
  add-on logs in this run. Treat it as a connection blocker, not evidence of
  broken Grocy/Alexa behavior. Do not expose private add-on configuration.
- Do not merge until live API smoke tests, camera and upgrade persistence
  checks have passed. No production stock or shopping entries were changed.
