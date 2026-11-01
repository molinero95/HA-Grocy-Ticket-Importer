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

## Despensa 1.15.0 — actualización de la instalación existente

La versión 1.15.0 sirve React en `/`, conserva `/react/` como alias y ofrece compras
sin JavaScript en `/basic`. El frontend completo anterior está retirado.
En la tienda de complementos, selecciona **Buscar actualizaciones** y actualiza
la instalación existente a 1.15.0. Publicar el manifiesto no instala automáticamente la actualización.

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
ID, historial, códigos y fotos. No hay combinación automática.

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


## Duplicate review and native merge (1.9.0)

Acciones → Revisar duplicados y auditoría provides Son diferentes and Revisar combinación per canonical pair. Differences persist in an additive table in the existing generic catalog SQLite file, survive reloads/renames, and can be explicitly undone. Archived products are not active suggestions.

The user chooses which product survives, keeping its name/description/photo/settings. Require exact typed destination name and a freshly rechecked snapshot. The app calls Grocy 4.7.1's native transactional merge once under app/worker locks and verifies lots, movement history, codes, shopping/recipe/meal-plan references and chosen metadata. Derived meal-plan recipes may be regenerated by Grocy; their date/type/unit totals must remain equal. No stock adjustment or consumption simulates a merge.

Require compatible units/conversions and no unsupported hierarchy/tare/source custom fields, double default-shopping references or source local receipt/variant/Alexa bindings. Preserve source local files/journals and block rather than rewrite those identities. Choosing the referenced product as destination may remove the blocker. Native merge is irreversible; uncertain outcomes require checking Grocy before another operation and are never automatically replayed. External writers cannot join the add-on's lock.


## Archived history deletion and status feedback (1.10.0)

The user explicitly authorizes deleting an archived product's Grocy movement history. The preview reports history_count; when nonzero, require a separate delete_history acknowledgement plus exact typed name and fresh snapshot. Recheck before the journaled DELETE and verify both product and history absence. Stock, active Grocy/local/Alexa dependencies and pending receipt imports remain blockers. Completed local receipt ledger entries are preserved byte-for-byte for deduplication. Native merge still uses its stricter source receipt guard.

Successful status notices are green. The fullscreen button/component has been removed; internal Back navigation remains. These changes supersede the older 1.8 history/fullscreen descriptions above.


## Per-product visual warnings (1.10.0)

Product sheets expose a threshold (default 0) and “No avisar de stock bajo”. Enabled warnings use amount <= threshold; positive amounts display Stock bajo and zero/negative amounts Sin existencias. Opting out suppresses both color and badges while retaining the threshold. Archived rows remain neutral.

Persist display-only metadata in the existing generic catalog SQLite file with an additive, serialized schema migration. Reads return zero/enabled defaults; writes compare expected amount and enabled state. Grocy min_stock_amount is deliberately unchanged because its API can auto-add shopping rows. Neither stock nor shopping is mutated. Settings and duplicate decisions survive upgrades in the existing catalog volume.


## Create from unknown shopping/Alexa entries (1.11.0)

Unknown arrivals remain reviewable with no candidates. Contextual creation prefills the editable source name, forces zero initial stock and automatically associates a newly created product while preserving shopping row ID/quantity/note. It never calls Alexa or stock mutations. An existing name/barcode match requires explicit reuse confirmation.

A server-prepared created_product_id is scoped to the active source generation; it validates the edited canonical product name by ID and survives advisory reranking without weakening ordinary candidate guards. New source episodes clear the proof; inactive/missing products cannot be chosen. Existing attached rows cannot be rebound. Active prepared products block deletion/native merge. Names containing slashes use path-safe routes.

Creation is journaled once. Known partial outcomes retain the product ID; a fresh context read and explicit choose finish the association, detecting a row already converted without rewriting it. Uncertain creation cannot be resent with the same command. Native product creation still checks duplicate names/barcodes and never adds stock to existing products.


## Receipt line review (1.12.0)

Receipt review edits purchased quantity, stock unit and pack contents, selects an existing product by canonical ID or explicitly creates a new one during confirmed import. Existing selection uses its audited current purchase conversion; stock unit and pack controls remain locked to that configuration. Live calculated stock is read-only and recomputed server-side. Monetary receipt quantities/prices and line costs remain unchanged, so stock corrections preserve total reconciliation. Weighed quantities retain three-decimal precision; pieces stay integral.

An optional merchant/original-text mapping is stored only after a successful line import in the additive `receipt_product_mappings` table of the existing receipt ledger. It does not replace or reset `receipt_items`. Keys normalize case/whitespace without fuzzy matching or crossing merchants. New reviews preselect a valid canonical ID; missing/archived targets or changed units/conversions require explicit review. No mappings or remote stock/products are written during simulation. Preserve the existing ledger in upgrades and backups.

Every edit invalidates confirmation. Unresolved REVIEW/pending lines cannot authorize partial import; a catalog preflight under the shared worker lock must still pass at commit. One-shot receipt markers and source-hash deduplication remain. Uncertain outcomes are never retried automatically.


## Alexa stock endpoint and complete product-photo fallback (1.13.0)

`POST /alexa/despensa` runs in a dedicated Flask/Gunicorn process on internal TCP 8100 only when `alexa_skill_enabled` is true and both `alexa_skill_id` and `alexa_skill_user_id` are configured. Port publishing defaults to null; the existing ingress listener stays restricted to the HA proxy. The voice app has no frontend or ordinary API routes. Configure only the exact voice path in Cloudflare after installing; see the repository's `docs/ALEXA_SKILL.md`. Do not proxy the ingress application or expose port 8765. No installed options, tunnel or Amazon skill is changed automatically.

The voice endpoint verifies `Signature-256`, the certificate chain against system roots, SAN `echo-api.amazon.com`, timestamp within 150 seconds, skill ID and owner ID. Certificate retrieval is HTTPS-only under `s3.amazonaws.com/echo.api/`, rejects redirects and is bounded in size/time. Stock uses three read-only Grocy calls with short timeouts; unknown/unavailable products are not reported as zero. Low-stock summaries respect opt-outs. Metadata aliases/thresholds are read through read-only SQLite connections.

The UI offers full-photo identification after barcode lookup has no product name or fails. Since 1.14.0, “Tomar otra foto para buscar con IA” requests a fresh rear-camera photo of the product front or label. Barcode-scanner frames are not captured or reused for recognition. The new photo stays local until the explicit OpenAI analysis button. The authenticated CSRF-protected photo API sanitizes and resizes the full frame, removes EXIF, requests structured suggestions with `store=false` and never writes stock/products/photos or auto-retries. A suggestion changes the name only after explicit acceptance. Existing duplicate/EAN checks remain on save; the image/model never replaces the scanned code or pack configuration. The existing OpenAI API key is reused and normal API usage applies. Public barcode lookup remains the first attempt.

1.14.0 saves the newly analyzed front/label photo through the existing sanitized local-photo endpoint after a genuinely new product is created. Snapshot the file with creation variables and never send it inside the product JSON. Existing duplicates keep their images. Photo failures are advisory and must not replay catalog creation or stock. Raw recognition uploads are still not persisted by the analysis endpoint; saving the new product is the persistence action.


En **Mi despensa**, el icono de filtro junto a la cámara permite elegir **Todos los productos**, **Falta de stock** o **En la lista de la compra**. Falta de stock respeta el umbral inclusivo y los avisos activados de cada producto; compra muestra cantidades pendientes mayores que cero. El filtro se combina con la búsqueda por nombre/código y se puede quitar con la X sin borrar la búsqueda. No modifica existencias ni compras.
