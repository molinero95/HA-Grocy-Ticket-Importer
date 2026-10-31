# Changelog

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
