"""Tests for setting up and unloading the OpenRouter Credits integration."""

from datetime import timedelta

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.openrouter_credits.const import API_BASE, CONF_SCAN_INTERVAL

from .conftest import mock_api, setup_entry


async def test_setup_and_unload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The entry loads and unloads cleanly."""
    mock_api(aioclient_mock)
    entry = await setup_entry(hass, mock_config_entry)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_invalid_key_starts_reauth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A rejected key fails setup and asks the user to re-authenticate."""
    aioclient_mock.get(f"{API_BASE}/key", status=401)
    aioclient_mock.get(f"{API_BASE}/credits", status=401)
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]


async def test_server_error_retries(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A temporary API error puts the entry into retry, not error."""
    aioclient_mock.get(f"{API_BASE}/key", status=500)
    aioclient_mock.get(f"{API_BASE}/credits", status=403)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_scan_interval_from_options(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The coordinator polls at the interval set in the options."""
    mock_api(aioclient_mock)
    entry = await setup_entry(hass, mock_config_entry)
    assert entry.runtime_data.update_interval == timedelta(minutes=15)

    hass.config_entries.async_update_entry(entry, options={CONF_SCAN_INTERVAL: 42})
    await hass.async_block_till_done()
    # Changing options reloads the entry with a new coordinator
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.update_interval == timedelta(minutes=42)
