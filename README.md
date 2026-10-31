# HA Grocy Ticket Importer

Import supermarket receipt PDFs or images into **Grocy** on **Home Assistant OS**, using OpenAI to extract receipt items.

## Current status

The first version is running **locally** in Home Assistant at `/config/grocy_ticket_importer`. A Carrefour test and a Froiz receipt have been processed; the Froiz run resulted in 23 new stock products and three non-stock expense lines. The Grocy catalog was subsequently confirmed to contain 27 products.

**Important:** the working `extract.py` and `importer.py` source files have **not yet been migrated to this repository**. This README describes the verified workflow, not a downloadable production release.

## Planned workflow

1. Upload a PDF or photo of a receipt from a simple authenticated Home Assistant/mobile interface.
2. Extract line items, quantities, units, prices, and totals using the OpenAI API.
3. Preview proposed changes, flag ambiguous lines, and avoid duplicate imports.
4. Create or match Grocy products and register purchases in stock.
5. Keep non-stock expense records separately until expense-accounting integration is implemented.

## Safety

- Never commit `.env`, API keys, real receipts, extraction JSON, or local ledgers.
- Keep `OPENAI_API_KEY`, `GROCY_URL`, and `GROCY_API_KEY` only in the Home Assistant deployment's `.env`.
- Dry-run before commit; on a failed or interrupted commit, reconcile changes before retrying.
- A local expenses ledger is **not** the same as Grocy expense accounting.

## Migration backlog

- [ ] Copy and review the **actual working** `extract.py` and `importer.py` from Home Assistant (redact any embedded secrets first).
- [ ] Add a pinned dependency specification and automated tests.
- [ ] Build and secure the mobile upload interface.
- [ ] Add import history, idempotency, and recovery from partial imports.
- [ ] Package a reproducible Home Assistant deployment.

## Development

This repository is the intended source of truth for future development. Deployment on Home Assistant should stay separate from source control and keep secrets local.

## Web interface prototype (not yet deployed)

The repository now contains a local-only Flask prototype, `web.py`. It has three inventory actions:

- **Añadir ticket**: upload a PDF or photo, extract with OpenAI, preview the receipt, run a dry-run, then explicitly confirm import.
- **Añadir producto**: scan/type an EAN/UPC to add one unit to stock; create a new catalog item if the barcode is unknown and a name is supplied.
- **Eliminar producto (una unidad)**: find a barcode, ask for confirmation, and **consume one stock unit without deleting the catalog product**.

Additional actions: associate a previously unknown barcode to an existing Grocy product (no stock change) and look up a photo by exact barcode from Open Food Facts.

**Image limitation:** photos are shown as a preview in this prototype; they are **not yet persisted to Grocy product pictures**. The Grocy 4.7 image API must be verified before enabling this.

**Deployment limitation:** this currently binds to `127.0.0.1`, is **not a Home Assistant ingress add-on** and is **not reachable from the mobile HA app**. Do not expose the Flask server directly to the internet. A secured HA add-on/ingress deployment is planned.

### Local setup (development only)

Install `Flask` and `python-dotenv`. Keep a local `.env` with the existing `OPENAI_API_KEY`, `GROCY_URL`, `GROCY_API_KEY`, plus a unique `WEB_PASSWORD` and long random `WEB_SESSION_SECRET`. **Do not commit .env.**

Run `python web.py` for local-only access at `127.0.0.1:8765`.

Tests run without calling OpenAI or Grocy:

```bash
python -m unittest discover -v -p 'test_*.py'
```

GitHub Actions compiles all Python files and runs tests on push/PR using Python 3.11 and 3.13.
