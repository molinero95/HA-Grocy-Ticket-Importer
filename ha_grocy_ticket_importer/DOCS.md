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

## Despensa 1.22.0 — actualización de la instalación existente

La versión 1.22.0 sirve React en `/`, conserva `/react/` como alias y ofrece compras
sin JavaScript en `/basic`. El frontend completo anterior está retirado.
En la tienda de complementos, selecciona **Buscar actualizaciones** y actualiza
la instalación existente a 1.22.0. Publicar el manifiesto no instala automáticamente la actualización.

**Nuevo producto** está únicamente en Mi despensa. La vista y los controles de productos archivados están retirados desde 1.22.0.

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

Actions → Alias de Alexa now uses the 1.21 editable table: alias selector left, product selector right, search over either column and per-row save/discard/delete. Saved aliases and active cached review names populate the alias selector; an explicit custom-name option remains. Missing/archived targets remain removable or can be explicitly reassigned. PUT uses expected source name/product under the worker lock and an atomic SQLite transaction. Since 1.22, a colliding destination is replaced by the new association; stale source edits still fail closed. POST also upserts the newest explicit association under the unique normalized key. POST/delete compatibility remains. No extra HA calls are made for selectors.

The shopping view reports sanitized worker health and refreshes periodically. An exact-name free-text note is shown for explicit association: choose the matching product to preserve row ID, quantity and note, or remove only that list item. No automatic conversion, duplicate merge or stock change occurs. Existing duplicate product/note rows still need explicit review. The worker keeps its verified checkpoint after failures and does not write remotes with sync disabled. Updating requires preserving the existing queue, aliases, command journal and checkpoints.

## Live suggestions and local synchronization events (1.7.0)

Shopping reads refresh local advisory candidates from the active catalog; product creation, renames and archives appear without waiting for the worker. Choices are revalidated on save, preserving source episodes, explicit decisions, removal intents and row identity.

Successful local list/catalog/alias edits and receipt commits signal the background worker through a scoped `.wake` marker checked every 250 ms. The marker contains no list data. Notification failures retain periodic polling; they never change an already committed HTTP result. HA event subscriptions and the configured 120-second default interval remain available. The UI refreshes every five seconds. Alexa-origin latency depends on the integration delivering the change to HA. Disabled sync remains read-only; no options are changed automatically.


## Pantry, archived deletion and navigation (1.8.0)

Active pantry products with zero or negative stock appear amber with “Sin existencias”; shopping quantities do not control this state. Archived rows stay neutral.

Acciones → Productos archivados → product sheet → Revisar eliminación audits permanent removal. Require an archived product with known zero stock and no movement/ticket history, shopping/recipe/meal-plan/child references, variants, Alexa aliases, active choices/removals or sync checkpoint bindings. Fail closed on incomplete reads. Exact typed-name confirmation and a fresh snapshot are required; the server reaudits, journals one dispatch and verifies absence. Grocy cascades remove only the unused product's barcode/conversion/custom-field metadata; local photos, journals and metadata are retained. A lost response is never automatically retried. Check Grocy before reopening the sheet.

The cascade audit is verified against Grocy 4.7.1. The app and worker share mutation locks; external Grocy writers cannot participate in that lock and the generic Grocy DELETE API has no atomic condition. Avoid concurrent external edits of the product during confirmation.

Browser Back closes the top dialog (including camera) before returning through visited sections; the root exits normally to its host. Same-document history preserves ingress paths and host state. Fullscreen is an explicit action under Acciones and depends on the iframe/browser/Android WebView permissions. The host can reject it or exit fullscreen on the first Back. This does not reconfigure the Home Assistant menu or native Android navigation.

Permanent deletion is enabled only for the audited Grocy 4.7.1 release; a different version blocks deletion until its cascades have been reviewed.


## Duplicate review and native merge (1.9.0)

Acciones → Revisar duplicados y auditoría provides Son diferentes and Revisar combinación per canonical pair. Differences persist in an additive table in the existing generic catalog SQLite file, survive reloads/renames, and can be explicitly undone. Archived products are not active suggestions.

The user chooses which product survives, keeping its name/description/photo/settings. Require exact typed destination name and a freshly rechecked snapshot. The app calls Grocy 4.7.1's native transactional merge once under app/worker locks and verifies lots, movement history, codes, shopping/recipe/meal-plan references and chosen metadata. Derived meal-plan recipes may be regenerated by Grocy; their date/type/unit totals must remain equal. No stock adjustment or consumption simulates a merge.

Require compatible units/conversions and no unsupported hierarchy/tare/source custom fields, double default-shopping references or source local receipt/variant/Alexa bindings. Preserve source local files/journals and block rather than rewrite those identities. Choosing the referenced product as destination may remove the blocker. Native merge is irreversible; uncertain outcomes require checking Grocy before another operation and are never automatically replayed. External writers cannot join the add-on's lock.


## Archived history deletion and status feedback (1.10.0)

Since 1.17.0, the Yes/No deletion modal explicitly covers the selected stock and movement history; no typed name or additional checkbox is required. Expected-state, dependency and journal guards still apply.

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

## Current interaction model (1.17.0)

Pantry +/− adjusts actual stock: 1 stock unit or 0.10 kg. The UI batches a rapid burst over 500 ms into a single absolute stock update with an expected amount and unique operation ID. A requested edit still commits when changing tabs. Preserve three-decimal weighed inventory; manual absolute stock editing stays at two decimals. No shopping/Alexa lock or refresh is part of stock completion. Uncertain outcomes freeze controls until a fresh read; commands are never automatically retried.

Shopping rows offer **Editar cantidad**, a pencil text action aligned under the displayed amount. On mobile, purchase/removal buttons use a fixed, stacked column; wider layouts keep both actions side by side. PUT `/api/v1/shopping/<id>/quantity` checks row ID, default list, expected amount, product and done status; updates only amount and verifies preserved metadata. It is journaled and holds the worker lock only for the short row operation. It never calls Alexa or changes stock. The UI updates the cached row instead of awaiting full synchronization. Zero is removed via the separate Quitar action.

The archive action is retired. **Eliminar producto** opens a focus-trapped Yes/No dialog with stock/history counts and irreversible consequences. Confirmed deletion of active or legacy archived products uses a fresh snapshot token and at-most-once journal. Grocy 4.7.1 cascades remove the selected stock/history/codes/conversions; readbacks verify absence. Active shopping/recipe/parent/variant/Alexa dependencies and pending/uncertain receipt imports remain blockers. Existing local ledgers, photos and metadata are preserved. Legacy records retain backend compatibility; the frontend archive/restore controls were removed in 1.22.

New-product forms select the real Piece ID by name when available, preserving any explicitly chosen unit. There is no AI photo capture/upload UI. Public photo lookup by barcode remains first; explicit **Buscar imagen y código con IA** searches by name even if the scanned code is not in the catalogs. Search only the existing Open Facts domains and verify cited GTINs through exact-code catalog APIs. Picking an image never replaces an existing scanned code. `/photos/discover` issues a signed, session-bound choice token; `/catalog/products/<id>/photo-discovery` validates its expiry, current name/code, source and trusted image host before saving after genuinely-new creation. A name/code edit invalidates the selection. Existing photos are preserved and failures do not replay creation. Manual sanitized image uploads remain available in product details. The old photo-identification endpoint is kept for compatibility; the current UI does not call it.

Duplicate review normalizes accents, punctuation, stop words and equivalent printed sizes, compares word order independently and tolerates small typos. Generic/variant candidates are explicitly labeled for brand/format review; no automatic merge, stock transfer or deletion. Saved per-pair differences remain respected.

All automated OpenAI and public-catalog tests use mocked providers. No installed options/data, Amazon/Cloudflare setup or paid requests are changed by this release.

Alexa warnings now expand into sanitized fixed cause codes, last check/success timestamps when available and the current list of actionable review rows. Pending/unassigned, stale-selection and duplicate-identity/name rows are shown first with a distinct background and text label. Generic connectivity errors are explicitly global and do not falsely blame normal rows. No extra HA/Alexa API calls or remote exception text are required for these details.


## Shopping search (1.18.0)

The shopping list has instant case/accent-insensitive name search over both persisted rows (including purchased items) and unresolved Alexa arrivals. Filtering is local, does not add requests or writes, preserves issue priority and keeps global sync notices/details visible. Show matching/total counts and a dedicated no-match state; clear resets the query. Background polling and row updates preserve the query. Hide the global clear-completed action while searching so hidden rows cannot be deleted by that action.


## Contextual creation sync fix (1.19.0)

`resolved_choices` now marks a selected ID as trusted contextual creation evidence only when it equals the durable `created_product_id` of the current active source episode and remains an active catalog candidate. The identity planner honors that internal evidence, as it already does validated persistent aliases, while still rejecting stale ordinary fuzzy selections, missing products, duplicate identities and changed checkpoints. This also covers explicitly accepted existing products prepared through the contextual creation flow. Source disappearance/reactivation resets the scoped metadata as before; no permanent alias is inferred.

The previous UI/API creation tests stopped at materializing a shopping row, leaving the next worker identity pass untested. New regressions run the complete worker through sync, purchase removal and another cycle without re-import; the real Grocy contract also validates both canonical identities after contextual creation. No production list/stock or checkpoint reset is performed.

Identity-conflict exceptions can carry positive product IDs only. Sanitized health stores/exposes these IDs without names, keys or raw remote exception bodies. The shopping read includes dismissed choices named by the worker, and the UI highlights their product rows even when bought. Generic connection errors still identify no individual product. Existing installations recover their intentional contextual bindings after updating; a new sync cycle verifies the real result.


## Name photo search from product details and native receipt capture (1.21.0)

Product details reuse the explicit OpenAI/catalog search with a product-bound token. Search uses the saved name and does not require or assign a barcode. Tokens bind session, product ID, saved name and current local/remote photo snapshot, expire after 30 minutes and are revalidated before saving. The selected source/code is verified again against a trusted exact-code catalog API; browser image URLs are never accepted. An existing photo requires explicit replacement. Legacy creation tokens cannot replace existing images. Previous local bytes are retained as a private version only after the remote photo URL persists; a failed write keeps the active local image. No stock, barcode or name write occurs. Mocked-provider tests and a real Grocy metadata contract cover this path; real paid-provider acceptance remains separate.

The native capture picker introduced in 1.21 is superseded by the live camera implementation below because the installed WebView opened the gallery instead. The existing image/PDF picker remains available.


## Direct camera and alias replacement (1.22.0)

ReceiptCamera requests getUserMedia only after the user opens it, with audio=false and a preferred environment camera. No BarcodeDetector is required. Capture draws the complete video frame without cropping, limits the longest side to 2560 px and encodes a JPEG (quality 0.92, maximum 8 MiB). The local preview can be discarded/retaken; only “Usar esta foto” calls the existing receipt upload/review flow. Close, Back, unmount, capture and late permission results release tracks; discarded previews revoke blob URLs and late encodings are ignored. Stage buttons have distinct keys so a rapid capture double click cannot reuse the capture element for another action. Missing/denied camera access gives an explicit file/PDF fallback, never an automatic picker or permission retry. Physical Android/WebView permission acceptance remains a deployment check. No ingress policy or installed option is changed.

Alias rows include every saved alias and normalized/deduplicated cached active review name, with unassigned product selectors shown immediately. Pending names can be assigned with POST or hidden for the current view; hiding/deleting aliases never deletes remote list items or products. A new normalized alias assignment atomically replaces its old product. Renaming a reviewed alias onto an existing destination deletes that older destination and renames the source in the same SQLite transaction. Stale source name/product and stale delete guards remain. Refresh removes superseded rows and clears their obsolete drafts; unrelated aliases are preserved.

Archived-product frontend navigation, inventory mode, restore controls and unused frontend API helpers have been removed at the user's request. Backend compatibility/data-integrity helpers remain for existing callers and deletion audits; no production archive records, stock or history are erased by this release.
