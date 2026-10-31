# Grocy Ticket Importer — Home Assistant app (experimental)

This experimental Home Assistant add-on uses Ingress, with the sidebar title **Despensa**. Its Python logic and container packaging are checked by GitHub Actions, but it has not yet been smoke-tested on a real Home Assistant OS instance.

## Isolated configuration and safe migration

The add-on maps **only its own app configuration** (type `app_config`) as `/config`, rather than the whole Home Assistant configuration. This limits exposure to unrelated Home Assistant credentials.

Before starting the add-on, **copy (do not move)** these two existing files from the old local working directory `/config/grocy_ticket_importer/` into this add-on's dedicated `app_configs/local_ha_grocy_ticket_importer/` directory, once Home Assistant has created it:

- `.env` containing `OPENAI_API_KEY`, `GROCY_URL`, `GROCY_API_KEY` (never add it to GitHub).
- `grocy_imports.sqlite3` — the existing receipt import ledger. Preserve it to avoid duplicate imports.

**If the ledger is missing, the add-on deliberately refuses to start.** Do not create an empty database or retry imported tickets without checking prior state.

Depending on your editor's add-on access, the dedicated folder may appear under `/addon_configs/local_ha_grocy_ticket_importer/` or `/app_configs/local_ha_grocy_ticket_importer/`. Confirm the actual folder in your Home Assistant editor before copying anything.

Personal uploaded receipts are written only to the add-on's own persistent `/data/receipts` directory. Its generated web session key is stored at `/data/session_secret`.

## Installation warning

This GitHub repository is private. Home Assistant Supervisor may not be able to fetch it as a standard remote repository. The packaged ZIP is intended for manual local-app installation, not a directly installable remote repository. The exact local placement and reboot/reload steps must be verified on your device before proceeding.

Do not open port 8099 on your router. Ingress requests enter via the Supervisor gateway; the internal nginx only allows that gateway. Authentication comes from Home Assistant.

## Current actions

Upload and preview receipt, dry-run then confirm Grocy changes; scan/type barcodes for stock addition or one-unit consumption; associate barcodes with existing products; search photos by exact barcode via Open Food Facts. Pictures are previewed, but **not yet saved** into Grocy.

## Further checks before production

- Verify installing and starting with Home Assistant OS on aarch64.
- Verify Ingress path and authentication.
- Verify import ledger migration and repeat-import blocking without modifying stock.
- Verify Grocy API stock consumption and creation behavior on the installed Grocy version.
