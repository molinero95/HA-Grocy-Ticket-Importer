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
