# CLAUDE.md

A Home Assistant custom integration, `openrouter_credits`, that shows OpenRouter credits and API key usage as sensors. See README.md for what users see.

## Layout

- `custom_components/openrouter_credits/`: the integration.
  - `api.py`: `OpenRouterClient` (aiohttp, Home Assistant's shared session) and `OpenRouterData`. `/key` always, `/credits` (403 → `None`), `/keys` only for management keys, paged by `offset`.
  - `coordinator.py`: `OpenRouterCoordinator`, one per entry, interval from `options[CONF_SCAN_INTERVAL]` in minutes. Auth errors raise `ConfigEntryAuthFailed`, everything else `UpdateFailed`.
  - `sensor.py`: `SENSORS` (account and own-key sensors on the account device) and `KEY_SENSORS` (one device per key from `/keys`). Per-key entities are added from a coordinator listener when new hashes appear.
  - `config_flow.py`: user, reauth and reconfigure steps (all ask for the key), plus an options flow for the interval.
  - `strings.json` and `translations/en.json`: keep these identical. Edit `strings.json`, then copy it over `en.json`.
  - `brand/`: PNG icons (`icon`, `dark_icon`, each with `@2x`), generated. Don't edit them by hand. There's deliberately no `logo.png`, so Home Assistant falls back to the icon.
- `tests/`: tests built on pytest-homeassistant-custom-component. `conftest.py` has the fake API payloads and `mock_api()` / `mock_management_api()`, which register them on `aioclient_mock`.
- `brand-src/`: `icon.svg` (original artwork: a credit gauge over a coin stack) and `make_brand.py`, which renders the light and dark PNGs with headless Edge and Pillow. **Never use OpenRouter's logo.**

## API facts

These are verified against OpenRouter's docs and a real account. Don't "fix" them.

- **`/api/v1/credits` needs a management key.** Regular keys get 403, which means "no account sensors", not an error.
- **Management keys can't run models**, so their own `usage*` is always 0. Own-key sensors are skipped for them (`is_management_key` / `is_provisioning_key`).
- **`/api/v1/keys` lists only enabled keys** by default. A key missing from the list makes its entities unavailable.
- **There's no endpoint for the account email** on personal accounts. `/organization/*` endpoints return 404 for personal management keys. Entries are titled "OpenRouter" unless the user names them; the key `label` is a masked key and is never used as a name.
- Limits: `limit` is `null` without a limit. `limit_reset` is `null` (never resets), `daily`, `weekly` or `monthly`.

## Home Assistant conventions

- **Unique IDs:**
  - config entries: the first 16 hex chars of the key's SHA-256 (`_key_id`), so the key isn't stored in the ID. It changes on reauth/reconfigure.
  - entities: `f"{entry.entry_id}_{key}"` and `f"{entry.entry_id}_{key_hash}_{key}"` for per-key sensors. Built on `entry_id`, not the entry's unique ID, so swapping keys keeps entity IDs.
- **Devices:** the account device is `(DOMAIN, entry_id)`; per-key devices are `(DOMAIN, f"{entry_id}_{key_hash}")` with `via_device_id` pointing at the account device. `via_device` is deprecated (2026.7) and logs a warning; there's a `hasattr` fallback for older cores.
- **Stale sensors:** on setup, account-level sensors whose `available_fn` is false are removed from the entity registry (e.g. after switching from a regular to a management key).
- **Device registry:** `device_registry.async_get_device` is deprecated. Use `async_entries_for_config_entry` or `async_get_device_id_by_identifier`.

## Testing

Home Assistant imports `fcntl`, so **the tests can't run natively on Windows**. Run them in Docker. If Docker Desktop is stopped, start it first.

```sh
docker build -f Dockerfile.test -t openrouter-credits-test .
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/src:ro" openrouter-credits-test -q   # Git Bash; PowerShell: -v "${PWD}:/src:ro"
```

- Rebuild the image only when `requirements_test.txt` changes. The source is mounted read-only.
- The version in `requirements_test.txt` follows the Home Assistant version the integration runs on. `pytest-homeassistant-custom-component==X` pins a specific `homeassistant` release, so check PyPI for which one.
- Look entities up with `entity_id_for(...)` (by unique ID) rather than hard-coding them, except where the test checks the entity ID itself.
- Entities added from the coordinator listener need `hass.async_block_till_done(wait_background_tasks=True)`.

## Releasing

Releases go through `.github/workflows/release.yml`, started by hand from the Actions tab with a version such as `0.2.0`. The workflow:

1. runs the tests
2. writes the version into `manifest.json` and commits it to `main` if it changed
3. tags `v<version>`
4. publishes a GitHub release with `openrouter_credits.zip`

`hacs.json` sets `zip_release: true`, so HACS installs that zip and needs at least one published release. Don't bump `manifest.json`'s version by hand. Leave it to the workflow.

## Deploying

The integration can be deployed by copying `custom_components/openrouter_credits/` into `/config/custom_components/` on the Home Assistant host, then restarting Home Assistant. Python changes need a restart. Exclude `__pycache__`. The host-specific SSH details live in the user's Claude memory, not in this repo.
