# Changelog

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
