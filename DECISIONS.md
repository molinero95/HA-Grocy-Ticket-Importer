# DECISIONS.md — Product and implementation decisions

Last reviewed: 2026-10-31. This records the user's explicitly requested behavior, and distinguishes it from incomplete validation.

## Navigation and shopping list
- **Lista de la compra is the default landing page.** Other primary views: Mi despensa; Acciones.
- Reuse **Grocy's shopping list**, not a separate application-owned list. Show quantity and unit on each shopping item; allow marking purchased or removing it without changing inventory.
- From **Mi despensa**, if a product is *not* on the shopping list, show only **🛒 Añadir**. On successful addition, replace the cart button with **− / quantity / +**. When quantity reaches zero, return to the cart view.
- Update these controls in place with asynchronous requests; never reload or jump the page/scroll on successful add/remove. Show an in-row error and keep a safe HTML form fallback.
- For products whose stock unit is kg, step by **0.10 kg** (100 g). For Piece, step by **1**. Show at most two decimals.
- Shopping-list action buttons must remain aligned irrespective of product name length or photo presence, especially on mobile. Long names wrap in their own column, not into controls.

## Product catalog
- **Añadir producto** is for a *new* product only. Search by name and barcode; if either exists, do not create a duplicate or modify stock. Show a link to the existing product sheet for editing.
- For truly new products, allow name, optional barcode, unit of measurement and initial stock (zero allowed, at most two decimals).
- Barcode association lives in the product sheet; remove the redundant stand-alone Asociar código action tile.
- Product sheet supports name, stock unit/purchase setup, photo/barcode association and direct stock quantity editing, with clear safety checks. Do not require an extra confirmation page for stock changes.
- **Pack is a purchase unit, Piece is the stock/consumption unit.** If one purchased pack contains 5 pieces, a receipt for 1 pack should add 5 pieces; consumption should subtract individual pieces. Grocy purchase factor must reflect this. Never automatically rewrite existing products' stock quantities (possible data corruption). Migrating existing Pack stock requires deliberate validation and/or reconciliation.
- Only show **Piezas por pack** when the purchasing unit is Pack.

## Consumption
- Choose exact quantity to consume (at most two decimals) and optionally replenish the same amount to the shopping list.
- Do not consume more than available. If stock consumption succeeds but shopping-list update fails, report partial success and do not invite blind retry.

## Photos
- On barcode scanning/typing, automatically search for an image by exact code in **Open Food Facts** for both product creation and existing product sheets.
- Show stored product photos in **Lista de la compra**, **Mi despensa** and product sheets.
- Store only a trusted image URL reference in Grocy product metadata/description; do not perform a network photo lookup per product on every page load.
- No photo must be a valid state; a failed lookup should not block product creation or barcode association.

## Security, delivery and open questions
- Home Assistant OS add-on via ingress; connected Grocy and OpenAI use credentials held in private options. Never disclose secrets.
- Changes should be accompanied by regression tests and an add-on version bump. GitHub Actions green status must be observed, not assumed.
- The Pack-to-Piece implementation and some Grocy shopping API endpoints need integration validation against the installed Grocy instance; actual production data must not be modified during exploratory tests.
- Developer action items, test gaps and potential stale documentation are tracked in `ROADMAP.md`.


## Alexa shopping list integration — 2026-10-31
- Synchronize **only the main Alexa shopping list** with Grocy's default shopping list; other Alexa lists remain independent.
- Exclude Alexa's completed/historical entries; do not resurrect old purchases.
- Bidirectional creation and removal; avoid duplicate items and synchronization loops using persistent checkpoints.
- First sync must preserve Grocy's existing shopping list, even when Alexa is empty.
- Items spoken to Alexa that are not yet in the Grocy catalog must be supported as free-text shopping notes, without inventing stock.
- Keep sync disabled until validated end to end. Do not silently remove products or modify inventory.
- Initial implementation intentionally does not synchronize quantities, units or completion states; this remains a future product decision.


## Generic products and supermarket variants — staged migration
- Grocy remains the only stock source: one canonical Grocy product per generic, shared quantity across variants.
- Variant metadata (barcode, supermarket, brand, purchase factor) is additive and cannot independently change stock.
- Existing products are not merged or deleted automatically. First export and audit products, barcodes, units, stock and shopping references; require explicit approval for any consolidation.
- Validate barcode ownership in both Grocy and local metadata; reject conflicts. Preserve shopping list entries and sync checkpoints.
- Alexa ambiguity must retain original free-text entry pending selection. Identity-aware bidirectional sync and UI remain pending; do not activate feature before integration tests.
- Generic metadata foundation is not yet connected to production routes or the Alexa worker. No installable release is claimed.

## Generic variant staged implementation (PR #5)

- Product-sheet variant registration writes only barcode association in Grocy
  and additive metadata in the persistent add-on SQLite database.
- Purchase factors on variants are descriptive until Grocy/receipt unit
  conversion is explicitly implemented and tested.
- The read-only JSON catalog audit must precede any consolidation proposal.
  No automatic migration of existing product IDs, stock or shopping entries.
- Alexa identity-aware matching and ambiguous-item review are still pending;
  preserve original shopping notes and sync checkpoints.

## Alexa ambiguous match review (PR #5)

- Pending suggestions and explicit manual choices are advisory metadata in
  `/config/alexa-match-queue.sqlite3`. They never mutate shopping entries,
  quantities, stock or synchronization checkpoints by themselves.
- No automatic note-to-product conversion until identity-aware sync and
  integration tests are implemented.

## Identity-aware Alexa reconciliation (PR #5, pending release validation)

- The v2 planner keys Grocy products by canonical product ID and notes by
  normalized free text. Exact unique catalog matches and explicitly chosen
  ambiguous matches may share a product identity without renaming Alexa text.
- A manual choice may add a missing canonical product to the Grocy shopping
  list, but it never rewrites/deletes an existing Grocy note or touches stock.
  Existing notes matching the Alexa original or canonical product name block
  the cycle rather than being silently converted.
- Each selected Alexa entity has separate v2 checkpoints and review queues.
  The v1 checkpoint and old unscoped queue remain intact; v2 starts with a
  non-destructive union and old choices must be reviewed again.
- Persist the v2 checkpoint only after verifying both remote snapshots.
  Previously verified bindings cannot silently change identity. Before
  deleting a Grocy shopping entry, revalidate its ID, product, note and amount.
- Implementation and network-free tests are on PR #5, not yet a production
  release. Real API behavior, mobile UX and persistence still require validation.
