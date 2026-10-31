# Changelog

## [0.7.11] — In development (not deployed)

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
