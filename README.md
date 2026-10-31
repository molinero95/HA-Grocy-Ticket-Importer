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
