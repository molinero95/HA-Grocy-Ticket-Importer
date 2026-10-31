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
