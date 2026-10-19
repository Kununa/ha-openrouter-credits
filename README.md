<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/openrouter_credits/brand/dark_icon@2x.png">
    <img src="custom_components/openrouter_credits/brand/icon@2x.png" alt="OpenRouter Credits icon" width="128">
  </picture>
</p>

# OpenRouter Credits for Home Assistant

[![Tests](https://github.com/Kununa/ha-openrouter-credits/actions/workflows/tests.yml/badge.svg)](https://github.com/Kununa/ha-openrouter-credits/actions/workflows/tests.yml)
[![Validate](https://github.com/Kununa/ha-openrouter-credits/actions/workflows/validate.yml/badge.svg)](https://github.com/Kununa/ha-openrouter-credits/actions/workflows/validate.yml)

> **Vibe coded.** This integration was written almost entirely by an AI
> (Claude Code) in conversation with its owner. It runs on Home Assistant
> 2026.10 with a real OpenRouter account and has an automated test suite, but
> the code has not been reviewed line by line by a human. Use it at your own
> risk, and expect rough edges.

Shows your [OpenRouter](https://openrouter.ai) credit balance and API key usage as sensors in Home Assistant. Everything is set up in the UI.

## Requirements

- Home Assistant. This integration is developed and tested on 2026.10.
- An OpenRouter API key. A **management key** is recommended, see [Which key to use](#which-key-to-use).

## Installation

### HACS

1. In HACS, open the menu and choose **Custom repositories**. Add `https://github.com/Kununa/ha-openrouter-credits` as an **Integration**.
2. Install **OpenRouter Credits**, then restart Home Assistant.

### Manual

1. Copy `custom_components/openrouter_credits` to `/config/custom_components/openrouter_credits` on your Home Assistant host.
2. Restart Home Assistant.

## Setup

Go to **Settings → Devices & services → Add integration → OpenRouter Credits** and enter:

- **API key**: a management key or a regular API key.
- **Name** (optional): defaults to "OpenRouter". Entity IDs are built from it, e.g. `sensor.openrouter_credits_remaining`.

### Which key to use

| Key type | What you get |
|---|---|
| **Management key** ([create one](https://openrouter.ai/settings/management-keys)) | The account balance, plus one device per API key on your account with that key's usage |
| Regular API key ([create one](https://openrouter.ai/settings/keys)) | Only that key's own usage and limit |

OpenRouter only reveals the account balance to management keys. A management key can't call models itself, so the integration doesn't create usage sensors for the management key.

## Entities

All values are in US dollars.

**Account** (management key):

| Sensor | Meaning |
|---|---|
| Credits remaining | Credits purchased minus usage |
| Total credits purchased | All credits ever bought |
| Total usage | All usage on the account |

**Per API key** (management key): one device for each enabled key, named after the key.

| Sensor | Meaning |
|---|---|
| Usage | All-time usage of the key. Attributes: label, limit, limit reset, created and expiry dates |
| Usage today / this week / this month | Usage in the current UTC day, week and month |
| Limit remaining | Only for keys with a spending limit |

Keys you create later appear at the next update. Deleted or disabled keys become unavailable; remove their devices yourself if you don't need them.

**Own key** (regular key): *Key usage*, *Key usage today / this week / this month*, and *Key limit* and *Key limit remaining* if the key has a limit.

## Options

- **Configure**: how often to poll OpenRouter, from 1 to 1440 minutes (default 15). Each update makes a few read-only requests, which don't cost credits.
- **Reconfigure**: swap the API key, e.g. to switch to a management key. Entities keep their IDs; sensors that no longer apply are removed.
- If the key is revoked, Home Assistant asks you to re-authenticate.

## Example automation

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.openrouter_credits_remaining
    below: 5
actions:
  - action: notify.notify
    data:
      message: "OpenRouter credits are low: ${{ states('sensor.openrouter_credits_remaining') }}"
```

## Development

Home Assistant doesn't run on Windows, so the tests run in a Linux container:

```sh
docker build -f Dockerfile.test -t openrouter-credits-test .
docker run --rm -v "${PWD}:/src:ro" openrouter-credits-test
```

On Linux or macOS you can also run them directly:

```sh
pip install -r requirements_test.txt
pytest
```

GitHub Actions runs the same tests on every push to `main` and on pull requests (see [`tests.yml`](.github/workflows/tests.yml)).

**Releasing:** GitHub → *Actions* → *Release* → *Run workflow*, enter the new version (e.g. `0.2.0`). The workflow runs the tests, sets the version in `manifest.json`, tags `v0.2.0`, and publishes a release with generated notes and `openrouter_credits.zip`, which HACS installs. Tick *dry run* to try it without publishing anything.

The icon is original artwork for this project, not OpenRouter's logo. The PNGs in `custom_components/openrouter_credits/brand/` are generated from [`brand-src/icon.svg`](brand-src/icon.svg) with [`brand-src/make_brand.py`](brand-src/make_brand.py).

## Disclaimer

This is an unofficial project and isn't affiliated with or endorsed by OpenRouter. *OpenRouter* is a trademark of its respective owner.
