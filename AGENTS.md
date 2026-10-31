# AGENTS.md — Despensa / Grocy Ticket Importer

## Mission
Maintain a Spanish, mobile-first Home Assistant OS add-on (panel "Despensa") backed by the user's existing Grocy installation. Prefer autonomous, small, tested commits and practical UX. The user's requests in `DECISIONS.md` are binding product requirements. Keep user-visible copy in Spanish and code comments/docs for agents in English when useful.

## First steps each session
1. Read `AGENTS.md`, `DECISIONS.md`, `ROADMAP.md`, `README.md`, and `ha_grocy_ticket_importer/DOCS.md`.
2. Inspect the latest code and GitHub Actions/checks before making assumptions about deployed versions. The add-on manifest version lives in `ha_grocy_ticket_importer/config.yaml`. The GitHub version may be ahead of the HA-installed version.
3. Inspect the relevant code and tests, implement the requested behavior, and add regression tests. Never report CI green without actually observing a successful run. If workflow-run access is unavailable, clearly say that.
4. When changing application files that exist in both places, keep root files and `ha_grocy_ticket_importer/` copies byte-identical. Examples include `web.py` and `barcode_stock.py`.
5. Increment the add-on version when preparing a new installable release; document user-visible behavior.

## Architecture and invariants
- `web.py`: Flask application, Jinja HTML/CSS/JavaScript, ingress URLs, session/CSRF, mobile UI.
- `barcode_stock.py`: product catalog, barcodes, Grocy stock, shopping list, unit conversions.
- `importer.py`: Grocy API client, receipt import and duplicate protection.
- `product_images.py`: exact-code lookup against Open Food Facts; image URL validation.
- `test_web.py`, `test_barcode_stock.py` and other `test_*.py`: network-free regression tests.
- `ha_grocy_ticket_importer/`: installable add-on package; includes manifest, bootstrap, copied application code.
- Grocy is the source of truth for inventory, products and its default shopping list. No secondary shopping list database.
- Preserve data: do not delete catalog products when stock goes to zero; avoid reimporting a receipt; do not uninstall or reinstall the add-on without considering its receipt ledger.
- Never print or commit API keys, add-on options, tokens, actual receipt data, private addresses or production databases. Sanitize Home Assistant connector output: add-on configuration can include real secrets.
- All mutating POST routes require CSRF checks and appropriate auth/ingress restrictions; keep user-visible error handling and protect against duplicate submissions.
- Do not silently convert existing Pack inventory to Piece. Grocy `qu_id_stock` is the consumption unit; `qu_id_purchase` and `qu_factor_purchase_to_stock` describe purchases. Validate changes against real Grocy behavior.
- Quantity inputs allow at most two decimals; kilogram shopping increments are 0.10 kg (100 g); piece increments are 1.
- Open Food Facts can be unavailable or lack a photo. Only use validated HTTPS URLs from `images.openfoodfacts.org`, never trust arbitrary client image URLs, and keep existing image metadata when changing product descriptions.

## User experience rules
- Opening Despensa defaults to **Lista de la compra**. Other main tabs are **Mi despensa** and **Acciones**.
- Products absent from the shopping list show a **🛒 Añadir** button in Mi despensa. First click turns the button into inline **− quantity +**; reducing to zero restores the cart. Do not reload the whole page or reset scroll. Preserve a non-JavaScript form fallback.
- In Lista de la compra, action buttons align consistently across rows regardless of name length, including mobile.
- Product sheets support editing product details/quantity and barcode association. The independent **Asociar código** tile was removed from Acciones.
- **Añadir producto** means create a new catalog product only. Check duplicate name/barcode first; if existing, link to its editable sheet and do not add stock. For new items, support zero stock, optional barcode, stock unit and Pack purchase factor.
- **Consumir producto** supports a precise quantity and an optional "add same amount to shopping list" checkbox. Avoid accidental double consumption on partial failure.
- Scanned barcodes trigger automatic photo lookup on new-product forms and product sheets. Saved photos appear in shopping, pantry and product detail.
- Minimize confirmation screens and avoid generic HTML errors where a clear in-app message is possible.

## Testing and common CI trap
Run:
```bash
python -m unittest discover -v -p 'test_*.py'
```
The CI Check stage parses the browser JavaScript extracted from Python/Jinja. **Never put raw `{{ ... }}` or `{% ... %}` expressions inside the JS `<script>` block**: Node syntax-check fails. Pass server URLs or data via HTML `data-*` attributes instead. There is a regression test for this.
Check syntax and tests before reporting any stage fixed. GitHub API commit combined status can be empty even when workflow runs exist, and commit-workflow listing may omit push-triggered runs. Do not treat an empty status list as success.
Check both desktop and narrow mobile layouts. Product-name length must not change the column/position of action buttons.

## Status / handoff
As of 2026-10-31 the repository's declared add-on version is **0.7.3** (verify before working); version visibility in Home Assistant can lag GitHub. Recent work includes shopping cart-to-stepper UI, no-scroll updates, Pack/Piece purchase conversion, image previews and fixed raw-Jinja-in-JavaScript syntax. CI success and end-to-end Grocy conversion behavior have **not** been conclusively confirmed from this agent environment. See `ROADMAP.md` for validation work.

## Working style
Favor actionable fixes, tests and concise Spanish summaries with commit/version links. Do not invent successful builds, deployments or real Grocy state. Favor defensive operations that cannot silently corrupt inventory.


## Alexa ↔ Grocy shopping sync (experimental 0.7.11)
- Work in PR #2 / `feature/alexa-grocy-sync` until CI and end-to-end integration tests pass; do not enable by default or claim deployed.
- Source: `shopping_sync.py` (pure planner), `shopping_sync_runtime.py` (checkpoint), `shopping_sync_adapters.py` (HA/Grocy APIs), `shopping_sync_worker.py` (120-second polling).
- The HA add-on requests `homeassistant_api: true`; use Supervisor token, never commit tokens or list contents. The Alexa entity is configurable with `alexa_shopping_list_entity`; validate its existence at runtime before enabling.
- Keep `/data/shopping-sync.json` across upgrades. First run merges, later runs propagate deletions. Do not advance checkpoint after partial failure.
- IMPORTANT: test Grocy note-only creation and HA `todo.get_items` response parsing against real APIs. Duplicate normalized names, completed items, quantities, external concurrent changes and deletion/re-add conflicts need careful testing. Do not change inventory stock.
- The runtime is optional behind `shopping_sync_enabled: false`. Do not merge/deploy merely because files compile.


## Mandatory release notes for every version
- Every change to `ha_grocy_ticket_importer/config.yaml` `version` MUST include an entry for that exact version at the top of `CHANGELOG.md` in the same PR/commit set.
- Describe user-visible additions, fixes, configuration or migration steps, and known limitations honestly. Never claim deployment or validated behavior without evidence.
- Keep `ha_grocy_ticket_importer/DOCS.md` and `README.md` aligned when configuration changes.
- Do not publish or merge a version bump without corresponding release notes.

- Home Assistant Supervisor displays add-on release notes from `ha_grocy_ticket_importer/CHANGELOG.md` (within the add-on directory), not only the repository-root `CHANGELOG.md`. Maintain both files identically for every version bump.
