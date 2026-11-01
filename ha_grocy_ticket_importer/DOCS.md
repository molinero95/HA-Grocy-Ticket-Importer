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
**Lista de la compra** suggestion queue even with sync disabled. This only writes local
review metadata; the background worker does not write remote lists while sync is disabled. Explicit manual choices/removals are separate: they update Grocy immediately without enabling sync, and never directly call Alexa or change stock.

### Identity-aware v2 behavior

The worker uses canonical Grocy product IDs for exact unique matches and
explicitly approved Alexa suggestions. Ambiguous or unknown Alexa names remain
free-text shopping notes. Alexa summaries are never renamed by the matching
process. The first v2 run performs a non-destructive union; later runs use
verified checkpoints for deletion propagation.

The inline review **Lista de la compra → Elegir producto** persists explicit
selections in `/config/alexa-match-queue-<entity-hash>.sqlite3`. It never
merges Grocy products. Saving immediately associates its existing free-text row with that product, preserving row ID, amount and note; without a note it reuses or creates one product row. The row can immediately be marked bought or removed.
A collision with another canonical row or a concurrent edit fails closed.
Keep-original preserves or creates a manageable Grocy note and dismisses the suggestion. Remove is also available before choosing: durable removal intents prevent re-import, and only an enabled worker propagates them to Alexa. Manual decisions and worker writes share a process lock; a verified source disappearance permits a fresh same-name episode. Stale selections,
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

## Despensa 1.8.0 — actualización de la instalación existente

La versión 1.8.0 sirve React en `/`, conserva `/react/` como alias y ofrece compras
sin JavaScript en `/basic`. El frontend completo anterior está retirado.
En la tienda de complementos, selecciona **Buscar actualizaciones** y actualiza
la instalación existente a 1.8.0. Publicar el manifiesto no instala automáticamente la actualización.

**Nuevo producto** está únicamente en Mi despensa. Los productos archivados se consultan y restauran desde **Acciones → Productos archivados**.

La búsqueda de Mi despensa es automática por nombre o código, con campo de texto y cámara; no requiere botón Buscar.

La ficha usa un único ajuste de **Existencias**: escribe la cantidad total que queda.
Se ha retirado el formulario «Consumir producto». Por ejemplo, si tienes 3 y queda 1,
indica 1 en Cantidad final. La ficha contiene información del producto y stock, sin formulario para añadir a la compra. Las compras se gestionan desde Mi despensa o Lista de la compra; ajustar existencias no añade artículos a la compra.

No se requieren opciones nuevas ni reinicializar bases de datos. Conservar
`/config` y `/data`: ledger de tickets, fotos, variantes, colas, checkpoints y
`stock-commands.sqlite3`. Antes de actualizar hacer copia HA; no desinstalar.
Los comandos con respuesta incierta no deben repetirse borrando sus registros.
Si el consumo se confirmó y falló la reposición, añadir únicamente la compra.

Pack es compra, Piece es stock. La conversión oficial de Grocy se verifica
antes de añadir existencias. Cambiar la compra afecta al futuro, nunca convierte
stock previo. Los controles rápidos de compra usan la unidad de stock.

Archivar exige cero stock y ausencia de referencias activas; restaurar mantiene
ID, historial, códigos y fotos. No hay consolidación automática.

La suite prueba Grocy oficial 4.7.1 con datos temporales, importador real,
worker Alexa, navegador móvil/ingress y reinicio. OpenAI, proveedor público de
fotos y HA todo se sustituyen. Las lecturas adicionales de Grocy instalado
confirman 4.7.1 y el esquema; la entidad HA/Alexa devuelve pendientes válidos.
Se utiliza su servicio y clave existentes, sin cambiar seguridad ni datos.
Cámara física, escrituras Alexa y actualización Supervisor requieren aceptación
en la instalación real; no se dan por verificadas al publicar la versión.
Véanse `docs/VALIDATION_V1.md` y `docs/REACT_PARITY.md` en el repositorio.


## Product discovery and form controls (1.2.0)

Open Food Facts and Open Products Facts remain enabled. Open Beauty Facts adds exact-code cosmetics lookup. Discovered images require trusted HTTPS image hosts; uploaded photos keep priority. A catalog may lack the product, its photo, or a complete name. Creation shows the returned name and offers **Usar este nombre**; it never overwrites typed names automatically. Manual name entry and sanitized photo upload remain available.

Creation, camera, duplicate-review and native file-selection controls share the application button styling with keyboard focus and 44px touch targets. File selection retains native browser/camera behavior and existing upload validations.

## Universal discovery (1.3.0)

Exact barcode lookup starts at the Open Facts universal v3 endpoint (`product_type=all`). Redirects are restricted to the existing Food, Products and Beauty HTTPS hosts before following them; attribution links to the final catalog. No Pet Food source is enabled. A universal 404 is a normal missing product. Direct catalog queries remain as fallback for failed or incomplete universal responses, including name-only results that might have a photo elsewhere. Existing photos, manual names and stock are preserved.

## Alexa recovery and alias management (1.6.0)

Actions → Alias de Alexa manages multiple names per selected product. Missing/archived product aliases can also be removed. Stale delete requests cannot remove an alias since reassigned to another product.

The shopping view reports sanitized worker health and refreshes periodically. An exact-name free-text note is shown for explicit association: choose the matching product to preserve row ID, quantity and note, or remove only that list item. No automatic conversion, duplicate merge or stock change occurs. Existing duplicate product/note rows still need explicit review. The worker keeps its verified checkpoint after failures and does not write remotes with sync disabled. Updating requires preserving the existing queue, aliases, command journal and checkpoints.

## Live suggestions and local synchronization events (1.7.0)

Shopping reads refresh local advisory candidates from the active catalog; product creation, renames and archives appear without waiting for the worker. Choices are revalidated on save, preserving source episodes, explicit decisions, removal intents and row identity.

Successful local list/catalog/alias edits and receipt commits signal the background worker through a scoped `.wake` marker checked every 250 ms. The marker contains no list data. Notification failures retain periodic polling; they never change an already committed HTTP result. HA event subscriptions and the configured 120-second default interval remain available. The UI refreshes every five seconds. Alexa-origin latency depends on the integration delivering the change to HA. Disabled sync remains read-only; no options are changed automatically.


## Pantry, archived deletion and navigation (1.8.0)

Active pantry products with zero or negative stock appear amber with “Sin existencias”; shopping quantities do not control this state. Archived rows stay neutral.

Acciones → Productos archivados → product sheet → Revisar eliminación audits permanent removal. Require an archived product with known zero stock and no movement/ticket history, shopping/recipe/meal-plan/child references, variants, Alexa aliases, active choices/removals or sync checkpoint bindings. Fail closed on incomplete reads. Exact typed-name confirmation and a fresh snapshot are required; the server reaudits, journals one dispatch and verifies absence. Grocy cascades remove only the unused product's barcode/conversion/custom-field metadata; local photos, journals and metadata are retained. A lost response is never automatically retried. Check Grocy before reopening the sheet.

The cascade audit is verified against Grocy 4.7.1. The app and worker share mutation locks; external Grocy writers cannot participate in that lock and the generic Grocy DELETE API has no atomic condition. Avoid concurrent external edits of the product during confirmation.

Browser Back closes the top dialog (including camera) before returning through visited sections; the root exits normally to its host. Same-document history preserves ingress paths and host state. Fullscreen is an explicit action under Acciones and depends on the iframe/browser/Android WebView permissions. The host can reject it or exit fullscreen on the first Back. This does not reconfigure the Home Assistant menu or native Android navigation.

Permanent deletion is enabled only for the audited Grocy 4.7.1 release; a different version stays archived until its cascades have been reviewed.
