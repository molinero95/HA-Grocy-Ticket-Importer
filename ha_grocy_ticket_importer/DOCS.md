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


## Alexa Devices shopping synchronization (experimental)

Requires Home Assistant Alexa Devices with the primary shopping-list `todo` entity working. The add-on declares `homeassistant_api: true` and uses its Supervisor token internally. **Do not manually expose a long-lived token.**

New option: `shopping_sync_enabled` (boolean, default `false`). The background process runs only when enabled and checks every two minutes. It uses the default Grocy shopping list (ID 1), not the Home Assistant generic shopping list. The main Alexa shopping entity is currently fixed in code and must be made configurable before shipping generally.

The state file `/data/shopping-sync.json` is persistent across restarts. Preserve it in backups. The first run merges pending items; subsequent runs propagate adds/removes. Historical completed Alexa items are excluded. Existing catalog stock is never changed. Unknown items may be added as Grocy shopping-list notes.

**Release gate:** do not enable this feature until HA service responses, Grocy writes, error recovery and CI have been tested against the installed versions. The proposed 0.7.11 release is not installed merely because GitHub contains the code.


**Selección de lista Alexa:** configura `alexa_shopping_list_entity` con el identificador `todo.*` de la lista deseada (por ejemplo, desde Herramientas para desarrolladores → Estados). Es obligatorio cuando `shopping_sync_enabled` está activado; vacío por defecto. Cada entidad tiene su propio archivo de estado para no reutilizar eliminaciones de otra lista. Cambiar de lista inicia una nueva unión inicial sin borrar los artículos existentes.
