# Grocy Ticket Importer — Home Assistant

Despensa is a Home Assistant add-on that manages a Grocy pantry with a mobile barcode scanner, searchable inventory, product editing and receipt imports.

## Installation and configuration

Add the repository URL in **Settings → Apps → Install app → ⋮ → Repositories**. Install **Grocy Ticket Importer**, then open its **Configuration** tab and set:

- `grocy_url`: internal Grocy URL reachable from the add-on (for example `http://a0d7b954-grocy:80`).
- `grocy_api_key`: Grocy API key (password field).
- `openai_api_key`: OpenAI API key for receipt extraction (password field).
- `grocy_location_id`: target Grocy location ID (defaults to 2).

Do not commit keys, receipts or databases to GitHub. Credentials are loaded at startup from the Home Assistant managed `/data/options.json`; `.env` is not needed in the add-on.

## Existing local installation — read before switching repositories

**Do not uninstall the existing local add-on until the receipt ledger has been backed up and migrated.** A repository add-on has a different Home Assistant app ID from the local add-on, even when its slug matches.

The receipt import ledger is `grocy_imports.sqlite3` in the add-on's private `app_config` directory. For an existing installation, first **copy** (never move) that file to the remote add-on's `app_config` folder. Keep the original local add-on running until the new one has been verified. Back up via Home Assistant before migration.

For a completely new installation the add-on creates an empty ledger. An existing imported-ticket user must **never** skip migration: doing so may import receipts twice. No existing ledger is deleted or overwritten by the bootstrap.

The session key and receipt upload working files are in `/data` and managed by Home Assistant backups. Do not expose the internal ingress service directly to the internet.

## Updates

Home Assistant detects a new version when the app's `config.yaml` version changes in the added GitHub repository. Choose **Check for updates** in the app store if necessary. The repository must be publicly readable by Supervisor; keeping GitHub source public does **not** make Grocy API keys public.


## Alexa ↔ Grocy shopping synchronization (experimental)

The add-on declares `homeassistant_api: true` and uses a Supervisor token
internally, or the optional `homeassistant_access_token` configured privately.
Set `alexa_shopping_list_entity` to the desired Alexa Devices `todo.*`
entity. The worker reads only its pending items and Grocy shopping list ID 1.
`shopping_sync_enabled` defaults to `false`. Do not enable it before
validating the Home Assistant and Grocy APIs on the installed versions.
When the Alexa entity is configured, a read-only worker refreshes the
**Coincidencias Alexa** queue even with sync disabled. This only writes local
review metadata; no remote shopping-list or stock writes occur until sync is
enabled explicitly.

### Identity-aware v2 behavior

The worker uses canonical Grocy product IDs for exact unique matches and
explicitly approved Alexa suggestions. Ambiguous or unknown Alexa names remain
free-text shopping notes. Alexa summaries are never renamed by the matching
process. The first v2 run performs a non-destructive union; later runs use
verified checkpoints for deletion propagation.

The review screen **Acciones → Coincidencias Alexa** persists explicit
selections in `/config/alexa-match-queue-<entity-hash>.sqlite3`. It never
merges Grocy products. An explicit choice may associate its existing free-text
row with that product during enabled sync, preserving row ID, amount and note.
A collision with another canonical row or a concurrent edit fails closed.
Keep-original dismissal leaves the remote note unchanged. Stale selections,
duplicate identities, changed quantities and concurrent edits also stop
mutations. A successful cycle re-reads both remote lists and atomically saves
the checkpoint only after identity verification.

New checkpoints use
`/data/shopping-sync-<entity-hash>-identity-v2.json`. The older v1
name-based checkpoint and unscoped Alexa queue are intentionally retained
without automatic migration: their identities cannot be safely inferred.
After upgrading, the first v2 run unions both lists and can reintroduce a
previously removed note. Previously chosen ambiguous matches must be
reselected for the configured list. Preserve the old files in backups.

Shopping sync does not change stock. It does not synchronize quantities,
units, completed items or renames. A deletion removes only a shopping-list
entry, never the underlying Grocy product. Verify the real Grocy 4.7.1
shopping API, Home Assistant todo response and restart recovery before
enabling this feature.

## Generic product variants (development)

A canonical Grocy product owns all inventory and shopping references. The
product sheet can add supermarket-specific variants (barcode, brand, store,
display name and purchase factor) after auditing barcode ownership in Grocy.
No product consolidation or stock migration happens automatically.

Variant metadata is persisted at `/config/generic_catalog.sqlite3` in the
existing `app_config` mount. Back it up with the receipt ledger and Alexa
review queues. The read-only catalog audit under
**Acciones → Detectar duplicados** includes product IDs, stock, units,
barcodes, shopping references and variants. Review it before any proposed
consolidation; explicit approval is required.

Variant factors are descriptive metadata; the canonical product purchase
configuration controls receipt conversion. Barcode association and restart
persistence are tested against isolated Grocy 4.7.1. Physical camera and
Supervisor upgrade acceptance remain deployment checks.

## Candidata Despensa 1.0 (sin publicar)

La rama sirve React en `/`, conserva `/react/` como alias y ofrece compras
sin JavaScript en `/basic`. El frontend completo anterior está retirado solo
en esta rama. No se despliega ni cambia la versión estable 0.16.4.

No se requieren opciones nuevas ni reinicializar bases de datos. Conservar
`/config` y `/data`: ledger de tickets, fotos, variantes, colas, checkpoints y
`stock-commands.sqlite3`. Antes de actualizar hacer copia HA; no desinstalar.
Los comandos con respuesta incierta no deben repetirse borrando sus registros.
Si el consumo se confirmó y falló la reposición, añadir únicamente la compra.

Pack es compra, Piece es stock. La conversión oficial de Grocy se verifica
antes de añadir existencias. Cambiar la compra afecta al futuro, nunca convierte
stock previo. Se pueden añadir cantidades exactas en las unidades verificadas.

Archivar exige cero stock y ausencia de referencias activas; restaurar mantiene
ID, historial, códigos y fotos. No hay borrado permanente ni consolidación.

La suite prueba Grocy oficial 4.7.1 con datos temporales, importador real,
worker Alexa, navegador móvil/ingress y reinicio. OpenAI, proveedor público de
fotos y HA todo se sustituyen. La consulta a la instalación real devolvió 403;
no se han debilitado protecciones ni modificado datos. Cámara física, entidad
Alexa real y actualización Supervisor requieren aceptación antes de publicar.
Véanse `docs/VALIDATION_V1.md` y `docs/REACT_PARITY.md` en el repositorio.
