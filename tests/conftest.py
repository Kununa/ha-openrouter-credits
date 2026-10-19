"""Common fixtures for the OpenRouter Credits tests."""

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.openrouter_credits.const import (
    API_BASE,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"

API_KEY = "sk-or-v1-test"

REGULAR_KEY: dict[str, Any] = {
    "label": "sk-or-v1-abc...123",
    "is_management_key": False,
    "is_provisioning_key": False,
    "limit": 10,
    "limit_remaining": 7.5,
    "usage": 2.5,
    "usage_daily": 0.25,
    "usage_weekly": 1.0,
    "usage_monthly": 2.0,
}

MANAGEMENT_KEY: dict[str, Any] = {
    "label": "sk-or-v1-mgm...999",
    "is_management_key": True,
    "is_provisioning_key": False,
    "limit": None,
    "limit_remaining": None,
    "usage": 0,
    "usage_daily": 0,
    "usage_weekly": 0,
    "usage_monthly": 0,
}

CREDITS = {"total_credits": 10, "total_usage": 4.5}

KEYS = [
    {
        "hash": "hash_agent",
        "name": "Agent",
        "label": "sk-or-v1-111...aaa",
        "disabled": False,
        "limit": None,
        "usage": 2.18,
        "usage_daily": 0.1,
        "usage_weekly": 0.5,
        "usage_monthly": 1.87,
    },
    {
        "hash": "hash_mail",
        "name": "Mail",
        "label": "sk-or-v1-222...bbb",
        "disabled": False,
        "limit": 2,
        "limit_remaining": 1.29,
        "usage": 0.71,
        "usage_daily": 0,
        "usage_weekly": 0,
        "usage_monthly": 0.21,
    },
]


def mock_api(
    aioclient_mock: AiohttpClientMocker,
    *,
    key: dict[str, Any] | None = None,
    credits_status: int = 403,
    keys: list[dict[str, Any]] | None = None,
) -> None:
    """Register OpenRouter responses. /credits answers 403 unless told otherwise."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API_BASE}/key", json={"data": key or REGULAR_KEY})
    aioclient_mock.get(
        f"{API_BASE}/credits",
        status=credits_status,
        json={"data": CREDITS} if credits_status == 200 else {"error": {}},
    )
    # The first page holds every key; the next offset returns an empty page
    aioclient_mock.get(
        f"{API_BASE}/keys",
        params={"offset": 0},
        json={"data": keys or []},
    )
    aioclient_mock.get(
        f"{API_BASE}/keys",
        params={"offset": len(keys or [])},
        json={"data": []},
    )


def mock_management_api(aioclient_mock: AiohttpClientMocker) -> None:
    """Responses for a management key with two API keys on the account."""
    mock_api(aioclient_mock, key=MANAGEMENT_KEY, credits_status=200, keys=KEYS)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load integrations from custom_components."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OpenRouter",
        data={CONF_API_KEY: API_KEY},
        options={CONF_SCAN_INTERVAL: 15},
        unique_id="test_unique_id",
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    """Add and set up the entry."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity_id_for(hass: HomeAssistant, entry_id: str, suffix: str) -> str | None:
    """Look up a sensor entity_id by the integration's unique_id scheme."""
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry_id}_{suffix}"
    )
