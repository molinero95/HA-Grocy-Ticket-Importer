# Grocy Ticket Importer — Home Assistant app (experimental)

The interface uses Home Assistant Ingress. It is intended to appear as **Despensa** in the sidebar.

**Not ready for production installation.** This initial packaging has not yet been built and smoke-tested on Home Assistant OS. It has privileged read/write access to the Home Assistant configuration directory, including other integration credentials. A narrower storage strategy is planned.

## Migration and prerequisites

- Home Assistant OS, aarch64 or amd64.
- Existing Grocy in Home Assistant, with `/config/grocy_ticket_importer/.env` containing `OPENAI_API_KEY`, `GROCY_URL`, and `GROCY_API_KEY`.
- Existing `/config/grocy_ticket_importer/grocy_imports.sqlite3` must be preserved. **Do not delete or overwrite it**, otherwise the deduplication ledger is lost.
- Grocy URL inside an app container must resolve to the Grocy add-on on the internal network.
- This repository is private. HA Supervisor may not be able to add it as a normal remote app repository; local installation or publishing a compatible release mechanism must be arranged first.

## Security

Requests enter through Ingress on port 8099; nginx allows the Supervisor gateway only. No app port is exposed to the LAN. Authentication is provided by Home Assistant. CSRF protection is enforced for changes. The app copies `.env` into its ephemeral container at startup. Personal receipt JSON files are kept under persistent `/data/receipts`, not in Git. Keep backups of the ledger.

The interface currently supports receipt upload/review/commit, adding and consuming a stock unit by barcode, associating a barcode to an existing product, and searching a public product image by EAN. The image is not yet saved to Grocy.
