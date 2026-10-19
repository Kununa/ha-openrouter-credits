"""Tests for the OpenRouter Credits sensors."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.openrouter_credits.const import DOMAIN

from .conftest import (
    KEYS,
    MANAGEMENT_KEY,
    entity_id_for,
    mock_api,
    mock_management_api,
    setup_entry,
)

ACCOUNT_SUFFIXES = ("credits_remaining", "total_credits", "total_usage")
OWN_KEY_SUFFIXES = (
    "key_usage",
    "key_usage_daily",
    "key_usage_weekly",
    "key_usage_monthly",
    "key_limit",
    "key_limit_remaining",
)


def _state(hass: HomeAssistant, entry_id: str, suffix: str) -> str:
    entity_id = entity_id_for(hass, entry_id, suffix)
    assert entity_id is not None, f"no sensor with suffix {suffix}"
    return hass.states.get(entity_id).state


async def test_regular_key(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A regular key shows its own usage and limit, no account balance."""
    mock_api(aioclient_mock)
    entry = await setup_entry(hass, mock_config_entry)

    assert _state(hass, entry.entry_id, "key_usage") == "2.5"
    assert _state(hass, entry.entry_id, "key_usage_daily") == "0.25"
    assert _state(hass, entry.entry_id, "key_usage_weekly") == "1.0"
    assert _state(hass, entry.entry_id, "key_usage_monthly") == "2.0"
    assert _state(hass, entry.entry_id, "key_limit") == "10"
    assert _state(hass, entry.entry_id, "key_limit_remaining") == "7.5"
    for suffix in ACCOUNT_SUFFIXES:
        assert entity_id_for(hass, entry.entry_id, suffix) is None

    state = hass.states.get(entity_id_for(hass, entry.entry_id, "key_usage"))
    assert state.attributes["unit_of_measurement"] == "USD"
    assert state.attributes["device_class"] == "monetary"


async def test_regular_key_without_limit(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Limit sensors are only created when the key has a limit."""
    mock_api(aioclient_mock, key={"usage": 1, "limit": None})
    entry = await setup_entry(hass, mock_config_entry)

    assert _state(hass, entry.entry_id, "key_usage") == "1"
    assert entity_id_for(hass, entry.entry_id, "key_limit") is None
    assert entity_id_for(hass, entry.entry_id, "key_limit_remaining") is None


async def test_management_key(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A management key shows the account balance and one device per API key."""
    mock_management_api(aioclient_mock)
    entry = await setup_entry(hass, mock_config_entry)

    assert _state(hass, entry.entry_id, "credits_remaining") == "5.5"
    assert _state(hass, entry.entry_id, "total_credits") == "10"
    assert _state(hass, entry.entry_id, "total_usage") == "4.5"
    # The management key can't run models, so its own usage sensors are skipped
    for suffix in OWN_KEY_SUFFIXES:
        assert entity_id_for(hass, entry.entry_id, suffix) is None

    assert _state(hass, entry.entry_id, "hash_agent_api_key_usage") == "2.18"
    assert _state(hass, entry.entry_id, "hash_agent_api_key_usage_daily") == "0.1"
    assert _state(hass, entry.entry_id, "hash_agent_api_key_usage_weekly") == "0.5"
    assert _state(hass, entry.entry_id, "hash_agent_api_key_usage_monthly") == "1.87"
    assert entity_id_for(hass, entry.entry_id, "hash_agent_api_key_limit_remaining") is None
    assert _state(hass, entry.entry_id, "hash_mail_api_key_limit_remaining") == "1.29"

    usage = hass.states.get(
        entity_id_for(hass, entry.entry_id, "hash_mail_api_key_usage")
    )
    assert usage.attributes["limit"] == 2
    assert usage.attributes["label"] == "sk-or-v1-222...bbb"


async def test_devices(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Each API key gets a device linked to the account device."""
    mock_management_api(aioclient_mock)
    entry = await setup_entry(hass, mock_config_entry)

    dev_reg = dr.async_get(hass)
    devices = {d.name: d for d in dr.async_entries_for_config_entry(dev_reg, entry.entry_id)}
    assert set(devices) == {"OpenRouter", "Agent", "Mail"}

    account = devices["OpenRouter"]
    assert account.identifiers == {(DOMAIN, entry.entry_id)}
    assert account.entry_type is dr.DeviceEntryType.SERVICE
    for name in ("Agent", "Mail"):
        assert devices[name].model == "API key"
        assert devices[name].via_device_id == account.id

    entity_id = entity_id_for(hass, entry.entry_id, "hash_agent_api_key_usage")
    assert entity_id == "sensor.agent_usage"


async def test_new_and_removed_keys(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keys created later are added; deleted keys become unavailable."""
    mock_management_api(aioclient_mock)
    entry = await setup_entry(hass, mock_config_entry)

    new_key = {**KEYS[0], "hash": "hash_new", "name": "New", "usage": 0.42}
    mock_api(
        aioclient_mock,
        key=MANAGEMENT_KEY,
        credits_status=200,
        keys=[KEYS[1], new_key],
    )
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    # Entities added from a coordinator listener are set up in a background task
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _state(hass, entry.entry_id, "hash_new_api_key_usage") == "0.42"
    assert _state(hass, entry.entry_id, "hash_agent_api_key_usage") == STATE_UNAVAILABLE
    assert _state(hass, entry.entry_id, "hash_mail_api_key_usage") == "0.71"


async def test_switching_key_type_removes_stale_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Sensors that no longer apply are removed from the registry on setup."""
    mock_api(aioclient_mock)
    entry = await setup_entry(hass, mock_config_entry)
    assert entity_id_for(hass, entry.entry_id, "key_usage") is not None

    mock_management_api(aioclient_mock)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    for suffix in OWN_KEY_SUFFIXES:
        assert entity_id_for(hass, entry.entry_id, suffix) is None
    assert entity_id_for(hass, entry.entry_id, "credits_remaining") is not None
    assert not [
        e
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if hass.states.get(e.entity_id) is None
    ]
