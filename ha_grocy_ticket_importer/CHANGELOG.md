# Changelog

## [1.12.0] — 2026-11-01

### Added
- Review each receipt line with editable purchased quantity, stock unit and pack contents; select an existing canonical product by ID or create a new product on confirmed import. Show the live calculated stock amount as read-only, computed again by the importer.
- Remember merchant + original receipt text -> product ID in an additive table in the existing receipt ledger, only after confirmed stock import. Apply valid mappings during future reviews; require explicit selection if the product disappears, is archived or its stock/purchase units change. Keep receipt text, monetary quantities/prices, hashes and imported/pending ledger entries intact.

### Fixed
- Keep original line costs and total reconciliation when correcting stock quantities. Re-simulate every edit, reject unresolved lines before confirmation and recheck the catalog before commit under the shared worker lock. Preserve one-shot and pending/uncertain recovery protections.
- Keep three-decimal weighed receipt quantities (for example 1.095 kg) while requiring whole pieces. Explicit product selection never falls back to creating a replacement.

### Tests
- Cover corrected amounts/costs, canonical ID selection, merchant isolation, restart persistence, stale mappings, invalid units, pending results and repeated uploads. Extend the real Grocy contract and mobile receipt flow.

## [1.11.0] — 2026-11-01

### Added
- Offer “Crear producto” directly on shopping/Alexa articles, including arrivals with no valid catalog candidates. Prefill the article name, allow product details, create with zero stock and automatically associate a genuinely new product to the original shopping row, preserving quantity and note.
- Persist a server-prepared product identity within the current review generation. Support an edited canonical name without losing the Alexa binding on candidate refresh; reset it only for a new source episode. Existing duplicate products require explicit confirmation before association.
- Journal creation once and retain known product IDs after partial association. Recover by reading the current state and completing association without recreating the product or rewriting a row already associated. Do not invoke Alexa or stock writes from manual creation.
- Keep unknown free-text articles reviewable; allow manual-name and barcode fallbacks and names containing slashes. Keep remove/original controls and protect existing associated rows.

### Tests
- Cover empty suggestions, edited names, source generations, existing product confirmation, quantity/note/row preservation, lost creation/association responses, CSRF and no stock/Alexa mutations. Add real Grocy and mobile flows for automatic association and manageable bought/remove controls.

## [1.10.0] — 2026-11-01

### Added
- Configure a per-product visual stock threshold (default 0) and opt out with “No avisar de stock bajo”. Highlight amounts at or below the threshold; distinguish positive low stock from zero stock. Persist display metadata in the existing catalog without touching Grocy minimum-stock settings or automatically adding shopping rows.

### Changed
- Allow deleting archived products with Grocy movement history, as explicitly requested. Show the movement count and require a separate irreversible-history acknowledgement plus the exact product name. Recheck the audited snapshot, journal one dispatch, and verify product/history absence.
- Keep zero-stock and active-reference guards. Completed local receipt ledger entries remain intact for duplicate-import prevention; pending/uncertain receipt imports still block deletion. Native merge keeps its stricter local receipt-identity guard.
- Remove the fullscreen action and its unused component; preserve internal Back navigation.

### Fixed
- Style successful status notices in green instead of error red, including saved duplicate differences and undo confirmations.

### Tests
- Cover history acknowledgement, pending/completed receipt distinctions, retained ledger bytes, lost-response protections, real Grocy cascade deletion and mobile confirmation/status styling.

## [1.9.0] — 2026-11-01

### Added
- Review duplicate pairs with “Son diferentes”, stored by canonical IDs in the existing persistent catalog database. Keep decisions across reloads and renames, list them for explicit undo, and suppress only that pair in three-way groups. Exclude archived products from active duplicate suggestions.
- Choose which product to keep and explicitly combine compatible products through Grocy 4.7.1’s native transaction. Preserve lots, stock history, barcodes, shopping quantities/notes and recipe/meal-plan references; keep the chosen product’s metadata. Verify source absence, destination metadata and migrated data after one journaled dispatch. Rebuild-derived meal-plan recipes are verified by date/type/unit totals.
- Require a fresh reference snapshot and the exact destination name. Block incompatible units/conversions, unknown amounts, hierarchies/tare/custom fields, default-list collisions and source local receipt/variant/Alexa bindings that cannot be migrated atomically. Show the reason and allow keeping the other product. Never replay uncertain merges.

### Tests
- Cover persistent differences/undo, independent pairs, rename/archive behavior, authentication, CSRF, stale state, transactional dispatch and uncertain outcomes; add component and real Grocy/browser flows for review, lot/history preservation and combining stocked products.

## [1.8.0] — 2026-11-01

### Added
- Highlight active pantry products without stock in amber, with an explicit “Sin existencias” label independent of shopping quantities. Keep archived rows neutral.
- Offer permanent deletion from an archived product sheet after a fresh reference audit and exact typed-name confirmation. Require zero stock, no Grocy movement history, shopping/recipe/meal-plan/child references, local receipt history, variants, Alexa aliases, pending choices/removals or identity checkpoints. Show blockers and fail closed on incomplete reads.
- Recheck the reviewed product and owned barcode/conversion metadata before dispatch, serialize with app/worker mutations, journal the operation and verify absence. Repeated commands return their recorded result; uncertain writes are never replayed. Preserve local journals, photos and metadata.
- Use same-document browser history for sections and nested dialogs, including Android Back where the host delegates navigation. Closing a dialog removes its history entry; replacing the create dialog with a product sheet preserves one step. Preserve the ingress URL and allow normal root exit.
- Add an explicit fullscreen action, with an explanatory status when Home Assistant/WebView denies the browser API.

### Tests
- Add guarded deletion/API regressions, real Grocy cascade/history contracts, reviewed browser deletion, mobile Back/nested camera/dialog replacement and zero-stock styling checks. Cover typed confirmation, failed audits, lost responses and fullscreen support.

## [1.7.0] — 2026-11-01

### Added
- Refresh Alexa review candidates from the current active catalog when reading the shopping list, including additions, renames and archives. Discover newly matching free-text notes without waiting for a worker cycle. Revalidate candidates again when saving a choice.
- Wake the background worker after successful local shopping, catalog, alias and receipt-commit changes, using an entity-scoped local marker observed every 250 ms. Keep Home Assistant events and periodic checks as fallbacks. Disabled synchronization remains read-only.
- Refresh the shopping view every five seconds to show incoming changes sooner; product creation invalidates suggestions before optional photo lookup finishes.

### Fixed
- Preserve explicit choices, dismissals, removal intents, source generations and checkpoints while refreshing candidates. Keep stale selections visible for review rather than silently replacing them; do not create a second row when an already associated item is pointed at a different product.
- Serialize quick shopping controls and the basic fallback with the worker. Failed/rejected operations and receipt previews do not trigger synchronization; marker failures never replay a saved mutation.

### Tests
- Cover live catalog ranking, new/renamed/archived products, stale choices and failed catalog reads, immediate local wake-up, API mutation boundaries and foreground cache invalidation. Add real Grocy API/browser coverage for a newly created product becoming selectable without another worker cycle.

## [1.6.0] — 2026-11-01

### Added
- Show sanitized Alexa worker health in the shopping list, including disabled, failed and stale synchronization. Refresh the view periodically; never expose credentials, list names or raw exceptions in health data.
- Offer explicit review for free-text Grocy notes matching a canonical product name. Association preserves the original shopping row, quantity and note; stock and unrelated lists are unchanged. Do not automatically convert or merge conflicting entries.

### Fixed
- Make exact-note conflicts resolvable from the UI instead of indefinitely blocking the worker with no corresponding suggestion. Existing products/duplicate notes still require explicit review or removal.
- Ignore obsolete aliases absent from the current Alexa list; retain guards when an active alias references a missing/archived product. Surface and allow removing unavailable-product aliases in the editor.
- Validate active alias targets, return structured failures, prevent stale deletion after an alias is reassigned, and lock editor context while saving.
- Include nested alias/event regressions in unittest discovery, remove shadow package imports, and cover new runtime modules in mirror checks and Docker packaging. Align the previously stale lockfile and documentation with the release.

### Validation
- Add regression coverage for exact-note recovery and bidirectional synchronization, status sanitization, stale alias deletion, API auth/CSRF, alias editing and mobile review. Validate note row/quantity/stock preservation against real isolated Grocy.

## [1.5.0] — 2026-11-01

### Changed
- Manage Alexa aliases by selecting a pantry product first, showing all its existing aliases and offering an explicit add-new action.
- Keep alias creation and removal scoped to the selected product, with responsive forms and empty/loading states.


## [1.4.1] — 2026-11-01

### Fixed
- Align action card icons and labels consistently on mobile.
- Style the Alexa alias editor with shared product-form controls, responsive spacing and consistent buttons.


## [1.4.0] — 2026-11-01

### Added
- Introduce persistent many-to-one Alexa aliases for canonical Grocy products.
- Add authenticated alias management endpoints and a React screen under Actions.
- Resolve trusted, explicitly saved aliases during identity-based shopping synchronization.

### Fixed
- Keep root and add-on Python modules synchronized to support both runtime entrypoints and CI.

### Tests
- Add regression coverage for alias collisions, persistence, missing products, purchase identity, and safe Alexa item removal.


## [1.3.0] — 2026-11-01

### Changed
- Keep product sheets focused on product information and stock. Remove the shopping-quantity form and unused frontend component/client methods; shopping remains available through the pantry cart and shopping list.
- Use the Open Facts universal v3 exact-barcode endpoint first, following only trusted Food, Products and Beauty HTTPS redirects and attributing the final catalog. Retain direct lookups for outages or incomplete metadata, and preserve name-only suggestions while looking for a photo. A universal 404 ends the lookup without redundant requests.

### Tests
- Cover universal response statuses, cross-catalog attribution, direct fallbacks, missing products, malformed responses, exact-code checks and redirect/image trust boundaries. Adapt the real Grocy browser flow to add shopping quantities from the pantry while verifying stock remains unchanged and archiving preserves history.

## [1.2.0] — 2026-11-01

### Changed
- Apply consistent primary/secondary buttons to product creation, camera scanning, duplicate review, audit/export and retry actions. Keep 44px touch targets, disabled/keyboard-focus styles, and matching native file-selector buttons.
- Give plain form buttons a shared fallback style. Duplicate review cards use the full width; single-column headings no longer inherit action-group flex layout.

### Added
- Query Open Beauty Facts for cosmetics, alongside the existing Open Food Facts and Open Products Facts sources. Validate exact barcode matches and trusted HTTPS image hosts, and allow beauty images in stored metadata and CSP.
- Display discovered product names and offer Use this name during creation. Applying a name is explicit, preserving typed names until chosen; incomplete catalog names remain editable.

### Fixed
- Treat catalog HTTP 404 as a normal missing product, not an outage. Continue past name-only matches to look for a photo in another catalog, while retaining useful name-only fallback data.
- Regression coverage for cosmetic code lookup, image metadata/CSP, absent/malformed/unsafe results, and mobile creation/duplicate/file-selector layouts. External catalogs remain optional; existing photos and stock are preserved.

## [1.1.0] — 2026-11-01

### Changed
- Simplify the product sheet to one stock control: set the total remaining quantity under Existencias. Remove the separate Consumir producto form and its unused frontend component.
- Clarify the remaining-total hint, move Products archived to Actions, remove the duplicate creation shortcut from Actions, and style New product as the pantry primary button. Refresh action cards and restore buttons with consistent accessible styles. Consumption API safeguards and persistent command history remain unchanged.
- Add a regression for reducing the final stock from 3 to 2 and adapt the real Grocy receipt/browser flow to adjust remaining stock before checking duplicate-import protection.
- Remove the redundant pantry Search button: name/barcode filtering stays automatic, with only the input and camera in the search bar.
- Saving an Alexa suggestion (or keeping its original name) immediately creates/reuses a manageable Grocy shopping row. Existing notes preserve their ID, quantity and text; duplicate and uncertain saves cannot increase amounts. Show a success message and refresh the list.
- Show Remove for unresolved Alexa suggestions as well as normal shopping rows. Persist explicit removal intent, prevent first-sync re-import, and apply Alexa removal only when synchronization is enabled. Manual shopping decisions and the worker share a process-safe lock; stock remains unchanged.

## [1.0.0] — 2026-11-01

### Changed

- React 19, TypeScript 7, Vite 7 and Vitest 4; mobile shopping, inventory, product sheets, receipt review/import, variants, photos and Alexa review. The root now serves React; script-free basic shopping remains. Removed the previous full inline frontend and obsolete routes.
- Trusted exact-barcode photo discovery, sanitized uploads, versioned shared images, standalone session/CSRF and ingress-prefixed APIs/assets.
- Durable at-most-once consumption commands and receipt submission guards; report uncertain/partial results without repeating stock changes.
- Verified Grocy Pack/Piece conversions, future-purchase editing, precise shopping quantities and row-ID mutations preserving notes, completed rows and other lists. No automatic conversion of existing stock.
- Explicit Alexa note association preserves row/amount/text; keep-original dismissal persists. Conflict checks and verified checkpoints remain mandatory; sync stays disabled by default.
- Reversible archive/restore preserves history and metadata; permanent deletion and automatic consolidation remain unavailable.
- Real unmodified Grocy 4.7.1 contracts and full mobile browser workflows with disposable data; CI builds/starts AMD64 and ARM64 containers. Python mirrors remain synchronized.
- Frontend QA: 67 Vitest tests, 13 Chromium scenarios, 200 Python tests and 5 real Grocy contracts; V8 coverage reports in CI. Fix session expiry/private-cache cleanup, ticket preview readiness and pack-factor validation.

### Updating from 0.16.4

- Home Assistant detects 1.0.0 from the add-on manifest. Refresh the add-on store and update the existing installation; do not uninstall it. Create a Home Assistant backup first and retain `/config` and `/data` (receipt ledger, photos, variants, command journal, Alexa queues and checkpoints).
- No new options or automatic stock conversion/consolidation. Pack is the purchase unit; Piece remains stock/consumption. Variant factors remain descriptive. Existing data is preserved.
- Permanent product deletion is replaced by reversible archive/restore. Legacy full HTML routes are removed; use React at `/` or basic shopping at `/basic`.
- Read-only installed Grocy 4.7.1/schema and configured HA/Alexa entity checks succeeded with existing credentials/listeners. Physical Android camera, real Alexa writes and the Supervisor upgrade still need validation on the installed system; publishing this version does not imply those checks or an installation have occurred. Keep Alexa sync disabled until its real write behavior has been checked.

## [0.16.4] — 2026-10-31

### Fixed
- Fix HTTP 500 on the shopping list caused by an invalid Alexa suggestion template attribute.
- Add a rendered-template regression test for inline Alexa product suggestions.


## [0.16.3] — 2026-10-31

### Fixed
- Generic Alexa names such as «arroz» now offer both basmati and integral variants instead of dropping the second candidate.
- Pending Alexa suggestions appear as expandable per-item buttons in the shopping list, not as a large panel at the top.
- Advisory choices do not alter Grocy stock or merge products.


## [0.16.2] — 2026-10-31

### Changed
- Show pending Alexa product-match suggestions directly above the shopping list, with inline candidate selection and a visible pending count.
- After saving a suggestion, return to the shopping list. The existing review screen remains available under Actions.
- Choices are advisory and do not change stock or shopping lists directly; synchronization still performs identity and conflict checks.


## [0.16.1] — 2026-10-31

### Fixed
- When an Alexa shopping-list entity is configured, the background worker now
  populates and refreshes the local **Coincidencias Alexa** review queue even
  with shopping synchronization disabled. This is a read-only preview: no
  Alexa/Grocy shopping-list writes or inventory changes are performed until
  `shopping_sync_enabled` is explicitly enabled.
- Parse Grocy shopping-list completion flags safely across boolean, numeric,
  and string representations. An active entry with `done="0"` is no longer
  mistaken for completed; unexpected flags stop synchronization instead of
  silently dropping items from the snapshot.

### Safety and validation
- Synchronization remains disabled by default. Existing Grocy products,
  stock, shopping entries, variants, checkpoints and receipt history are not
  migrated or modified by this update.
- Added regression tests for read-only worker startup and Grocy completion
  flags. GitHub Actions must pass before release; real mobile camera, Alexa
  write behavior and persistence still require validation in Home Assistant.

## [0.16.0] — 2026-10-31

### Added
- Generic Grocy products can register supermarket variants with barcode, brand,
  store, display name and purchase factor in persistent add-on SQLite metadata.
  Barcode ownership is checked against Grocy before association; no stock
  consolidation, product deletion or automatic inventory migration is performed.
- Mobile product sheet supports barcode camera scanning for variants, and
  Actions offers a read-only JSON audit of products, barcodes, stock, units,
  shopping references and variant metadata.
- Alexa review screen persists ambiguous-name suggestions and explicit product
  selections, without renaming Alexa entries or rewriting Grocy shopping notes.
- Identity-aware Alexa/Grocy synchronization uses canonical product IDs and
  distinct free-text notes, with v2 atomic checkpoints and per-list review
  queues. First v2 sync is a non-destructive union.

### Safety and migration
- Unresolved Alexa suggestions cannot create duplicate free-text shopping notes
  when a plausible canonical product is already on Grocy's shopping list;
  synchronization pauses for manual review instead.
- Sync remains **disabled by default**. The worker refuses stale choices,
  duplicate identities, conflicting Grocy notes and concurrent quantity
  changes; it verifies both remote lists before advancing the checkpoint.
- Back up `/config/generic_catalog.sqlite3`, existing receipt ledger,
  `/config/alexa-match-queue*.sqlite3` and `/data/shopping-sync*.json`
  before upgrading.
- Legacy v1 checkpoints and unscoped Alexa review choices are retained, not
  automatically migrated. The first v2 run may reintroduce previously removed
  free-text items; reselect old manual choices for the configured Alexa list.

### Known limitations / validation
- Variant purchase factors are informational and do not yet alter receipt
  conversion. Existing Grocy product IDs and stock are not merged.
- Automated tests and Docker packaging run in CI; real Grocy 4.7.1 and
  Home Assistant Alexa todo write semantics, camera UX and persistence across
  add-on upgrades require end-to-end validation before enabling sync.
- This entry documents a PR release candidate, **not a confirmed deployment**.

## [0.15.0] — 2026-10-31

### Changed
- Replace separate pantry name and barcode inputs with a single searchable field and camera scan button.
- Barcode matches now filter inventory rows in place instead of redirecting to a product sheet.
- Preserve product sheet navigation through the matching inventory row.

### Validation
- CI and Home Assistant verification pending.


## [0.14.2] — 2026-10-31

### Fixed
- Register duplicate detection as a supported view so its Actions link no longer falls back to the shopping list.
- Add a navigation regression test that opens the duplicate detector and checks its candidate links.

### Validation
- CI and live Home Assistant verification pending.


## [0.14.1] — 2026-10-31

### Added
- Read-only merge preview when a newly entered barcode belongs to another catalog product.
- Show both product names, stock amounts and unit identifiers, with navigation to either editor.
- Detect the conflict before writing name, stock or barcode updates; merging remains disabled pending safe reconciliation.

### Validation
- CI and live Home Assistant verification pending.


## [0.14.0] — 2026-10-31

### Added
- Read-only duplicate detector under Actions, checking identical barcodes, normalized exact names, and highly similar names.
- Review candidate groups and open product editors; no automatic deletion or merging.

### Validation
- CI and live Grocy verification pending.


## [0.13.2] — 2026-10-31

### Added
- Scan a new EAN/UPC barcode with the existing in-app camera directly from the product editor.
- Populate the new barcode field automatically; saving remains an explicit action.


## [0.13.1] — 2026-10-31

### Changed
- Remove redundant Photography section from the bottom of the product editor.
- Group photo capture and preview at the top, organize fields by purpose, and move destructive deletion into collapsed advanced options.
- Keep one Save changes action for regular product edits.

### Validation
- CI and live mobile UI verification pending.


## [0.13.0] — 2026-10-31

### Added
- Exact EAN lookup now falls back to Open Products Facts after Open Food Facts.
- Accept product photo URLs from both trusted Open Facts image hosts.
- Preserve existing Grocy catalog matching and manual product registration when neither source recognizes a barcode.

### Validation
- CI and live Sanytol barcode lookup pending; public databases may not contain every product.


## [0.12.0] — 2026-10-31

### Changed
- Capture product photographs directly using the in-app camera, without a visible file picker.
- Consolidate product name, units, stock, barcode, and photograph into one edit form with one Save changes button.
- Keep the destructive Delete product action separate.

### Validation
- CI and live Home Assistant testing pending; combined save is sequential, not transactional.


## [0.11.3] — 2026-10-31

### Changed
- Remove the Consume product shortcut and its dedicated screen from the interface.
- Preserve existing stock operations elsewhere and the underlying API for compatibility.


## [0.11.2] — 2026-10-31

### Fixed
- Prevent repeated taps on the receipt extraction submit button while processing.
- Display a visible busy state and restore the button after browser history navigation.
- Require a selected receipt photo or file before submitting.


## [0.11.1] — 2026-10-31

### Changed
- Remove the redundant system camera option from receipt uploads now that the in-app camera works.
- Keep the in-app camera and existing-file picker.


## [0.11.0] — 2026-10-31

### Added
- Suggest up to five similarly named existing Grocy products for each receipt item during review.
- Explicit user selection replaces the editable receipt name to reuse the existing catalog match; no automatic matching.

### Validation
- CI and live receipt smoke test pending.


## [0.10.0] — 2026-10-31

### Added
- In-page camera capture for receipts using getUserMedia, with native camera and file picker fallback.
- Edit extracted receipt item names before preview and import.

### Validation
- CI and live Android Home Assistant camera permissions pending.


## [0.9.0] — 2026-10-31

### Added
- Upload and persist product photographs locally from the product edit page (JPEG, PNG, WebP).
- Cache barcode-discovered Open Food Facts photographs in persistent add-on storage.
- Authenticated local image endpoint; image normalization and size limits.

### Notes
- Previously linked external photographs are not yet bulk-migrated; existing external links remain usable.
- CI and live Home Assistant validation pending.


## [0.8.3] — 2026-10-31

### Changed
- Replace the current barcode dropdown with an editable input in the product detail form.

### Pending
- User-uploaded product photos need durable local storage, image validation and a protected serving endpoint; not included in this patch.
- CI and mobile verification pending.


## [0.8.2] — 2026-10-31

### Fixed
- Receipt camera and existing-file pickers now display as distinct labeled buttons rather than native file upload fields.
- Mobile camera input requests the environment camera via image capture; selection status remains visible.

### Validation
- Android Home Assistant camera behavior and CI pending.


## [0.8.1] — 2026-10-31

### Fixed
- Product rename only sends fields that require changes, avoiding unnecessary unit and conversion updates that Grocy may reject.
- Applied to both development and packaged add-on copies.

### Validation
- Pending CI and real product rename smoke test.


## [0.8.0] — 2026-10-31

### Changed
- Adopt minor-version increments for new features; 0.8.0 consolidates inventory barcode lookup, shopping item product links and simplified unit editing.
- Remove obsolete pack conversion prefill during receipt upload.

### Fixed
- Receipt upload/extraction failures now log an exception with a short reference and display a helpful error instead of an unhandled server error.
- Prior missing barcode_stock.norm error was corrected in 0.7.26.

### Validation
- CI and real receipt smoke test pending.


## [0.7.27] — 2026-10-31

### Changed
- Product editing uses only pieces or kilograms and always sets purchase-to-stock factor to 1.
- Removed pack conversion and nonzero-stock restriction from the product edit backend.
- Product names, barcodes and saved photos are retained; no automatic migration of existing Grocy records.

### Validation
- Pending CI and Grocy edit smoke tests. Existing receipt and product-creation pack paths still require cleanup.


## [0.7.26] — 2026-10-31

### Fixed
- Receipt upload no longer calls nonexistent barcode_stock.norm (observed in addon logs).
- Shopping list entries linked to catalog products open their product details.

### Added
- Barcode camera scanning and manual EAN/UPC lookup from Mi despensa, opening existing product details.
- Simplified product editing form to show piece/kg choices and hide pack conversion fields; existing Grocy stock and historical pack metadata are not migrated.

### Validation
- CI and end-to-end mobile editing/scanning tests pending.


## [0.7.25] — 2026-10-31

### Improved
- Receipt upload now offers a clearly labeled camera capture option and a separate existing-file picker.
- Selecting a photo clears any previously selected file and vice versa, avoiding ambiguous uploads.
- Shows the selected photo or file name before extraction; stock is not changed by uploading.

### Validation
- CI and mobile camera behavior pending verification.


## [0.7.24] — 2026-10-31

### Added
- Shopping list button to delete all completed items in one action, with confirmation and count.
- Operates only on completed entries in Grocy's default shopping list; pending entries and inventory stock remain untouched.

### Validation
- Pending GitHub Actions and mobile smoke test.


## [0.7.23] — 2026-10-31

### Fixed
- Close missing JavaScript script tag that prevented the shopping-list live refresh from running.
- Add manual Refresh button and pull-down gesture at top of shopping page.
- Preserve shopping list and scroll while refreshing; polling remains every 10 seconds when visible.

### Validation
- GitHub Actions and mobile testing pending.


## [0.7.22] — 2026-10-31

### Added
- The open shopping-list view refreshes automatically every 10 seconds and on return to the tab, without a full page reload or scroll reset.
- Pause background refresh while the tab is hidden or a shopping-list form is focused; keep existing list on transient errors.

### Validation
- Pending GitHub Actions and Home Assistant mobile smoke test after installation.


## [0.7.21] — 2026-10-31

### Fixed
- Ignore read-only `todo.get_items` events generated by synchronization itself, preventing event feedback loops.
- Ignore unchanged todo state notifications while retaining changes and mutating todo services.
- Add regression tests for both cases. Polling fallback and inventory are unchanged.

### Validation
- Requires successful GitHub Actions and confirmation on Home Assistant after updating.


## [0.7.20] — 2026-10-31

### Fixed
- Fix immediate Home Assistant WebSocket listener `TypeError`: websocket-client's WebSocket object is not a context manager. Close the connection explicitly in a `finally` block.
- Preserve the polling fallback and existing shopping-list configuration; no inventory changes.

### Validation
- Requires CI and live event synchronization confirmation after installation.


## [0.7.19] — 2026-10-31

### Fixed
- Improve Home Assistant WebSocket event subscription and exact shopping-list event filtering.
- Remove redundant wait in shopping sync worker; log whether each run is startup, event or polling.
- Preserve 120-second polling fallback and existing configuration.

### Validation
- Correction PR #3 passed Python 3.11 and 3.13 CI, including add-on container build and tests. Live WebSocket validation pending after installation.


## [0.7.18] — 2026-10-31

### Added
- Hybrid Alexa/Grocy shopping sync: Home Assistant todo state and service events wake the worker immediately, while the configurable polling interval remains a safety fallback.
- Automatic Home Assistant WebSocket reconnect; no new configuration required when the existing access token is configured.


## [0.7.17] — 2026-10-31

### Added
- Configurable `shopping_sync_interval_seconds` setting for bidirectional Alexa ↔ Grocy shopping-list synchronization (30–3600 seconds).
- Default remains 120 seconds, preserving existing installations. Common choices: 30, 60, 120 and 300 seconds.
- Interval is validated during add-on startup and applied to the worker after restart.


## [0.7.16] — 2026-10-31

### Added
- Optional `homeassistant_access_token` password field in the Home Assistant add-on settings for a user-generated long-lived access token when Supervisor credentials are unavailable.
- When provided, the add-on uses the direct internal Home Assistant endpoint (`http://homeassistant:8123`) and passes the token privately to the shopping-sync worker. Existing Supervisor authentication remains the fallback when unset.

### Security
- Token values are never written to logs or release notes. Create and enter the token locally in Home Assistant; do not share it.

### Validation
- Requires configuring the token in Home Assistant and confirming Alexa-to-Grocy and Grocy-to-Alexa synchronization.


## [0.7.15] — 2026-10-31

### Fixed
- Enable Supervisor API access (`hassio_api: true`) in addition to Home Assistant API access to provide the add-on's scoped authentication token for Alexa todo synchronization.
- Preserve safe missing-token diagnostics in worker logs, without exposing credentials.

### Validation
- Pending real Home Assistant integration test: confirm that `Plátanos` syncs from Alexa to Grocy and reverse-direction sync works without duplicates.


## [0.7.14] — 2026-10-31

### Fixed
- Accept `HASSIO_TOKEN` as an additional Home Assistant API credential source alongside `SUPERVISOR_TOKEN` and `HA_TOKEN`.
- Explicitly identify missing API credentials in safe synchronization error logs without exposing token values.

### Known limitations
- Requires validation on the actual Home Assistant add-on; if Supervisor does not expose any supported token, synchronization will still fail and logs will explain why.


## [0.7.13] — 2026-10-31

### Fixed
- Publish release notes in the Home Assistant add-on directory so Supervisor can display the changelog in the add-on interface.
- No changes to stock, product catalog, or shopping-list data.

### Known limitations
- Alexa ↔ Grocy synchronization is still being diagnosed; this update does not claim to fix the RuntimeError.


## [0.7.12] — 2026-10-31

### Fixed
- Improved diagnostics for Alexa ↔ Grocy shopping-list synchronization: logs now identify whether reading Alexa or Grocy failed, including safe exception type and HTTP status where available.
- No change to shopping-list contents or stock during upgrade.

### Known limitations
- The real integration error is still under investigation; this release provides diagnostics, not a confirmed synchronization fix.


## [0.7.11] — 2026-10-31

### Added
- Experimental bidirectional synchronization between Alexa Devices' main shopping list and Grocy's default shopping list.
- Normalized-name reconciliation, persistent checkpoint and optional two-minute polling worker.
- Home Assistant Supervisor API access (`homeassistant_api: true`), disabled-by-default `shopping_sync_enabled` option.
- Read/write adapters for Alexa todo items and Grocy shopping list, including free-text shopping notes for products not in the catalog.
- Unit tests for reconciliation and checkpoint behavior.

### Safety and known limitations
- **Do not enable until integration tests and GitHub Actions have passed.** This release is a draft PR, not installed in Home Assistant.
- Only pending Alexa items; completed historical items are excluded.
- Does not synchronize quantities, units, completion status or renames.
- Duplicate normalized names and partial writes require end-to-end validation.
- No changes to inventory stock or catalog are intended.

## [0.7.10] — Existing installed version

- Prior shopping-list and pantry UI improvements. See repository history for details.

- Configurable `alexa_shopping_list_entity` and per-entity synchronization checkpoints.
