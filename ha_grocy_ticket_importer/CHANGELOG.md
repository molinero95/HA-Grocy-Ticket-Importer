# Changelog

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
