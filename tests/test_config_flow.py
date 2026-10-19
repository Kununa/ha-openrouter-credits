"""Tests for the OpenRouter Credits config and options flows."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.openrouter_credits.config_flow import _key_id
from custom_components.openrouter_credits.const import (
    API_BASE,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)

from .conftest import API_KEY, mock_api


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Don't set up the entry the flow creates."""
    with patch(
        "custom_components.openrouter_credits.async_setup_entry",
        AsyncMock(return_value=True),
    ) as mock:
        yield mock


async def _start(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


@pytest.mark.parametrize(
    ("user_input", "title"),
    [
        ({CONF_API_KEY: API_KEY}, "OpenRouter"),
        ({CONF_API_KEY: f"  {API_KEY}  ", CONF_NAME: "Work"}, "Work"),
    ],
)
async def test_create_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
    user_input: dict[str, str],
    title: str,
) -> None:
    """A valid key creates an entry; the key label is never used as the title."""
    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        await _start(hass), user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == title
    assert result["data"] == {CONF_API_KEY: API_KEY}
    assert result["options"] == {CONF_SCAN_INTERVAL: 15}
    assert result["result"].unique_id == _key_id(API_KEY)
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("mock_kwargs", "error"),
    [
        ({"status": 401}, "invalid_auth"),
        ({"status": 500}, "cannot_connect"),
        ({"exc": ClientError()}, "cannot_connect"),
    ],
)
async def test_errors_then_recover(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_kwargs: dict,
    error: str,
) -> None:
    """Errors show on the form, and a working key afterwards still succeeds."""
    flow_id = await _start(hass)
    aioclient_mock.get(f"{API_BASE}/key", **mock_kwargs)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The same key can't be added twice."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: API_KEY}, unique_id=_key_id(API_KEY)
    ).add_to_hass(hass)
    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        await _start(hass), {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reauth stores the new key and updates the unique id."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    aioclient_mock.get(f"{API_BASE}/key", status=401)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "sk-or-v1-bad"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "sk-or-v1-new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "sk-or-v1-new"
    assert mock_config_entry.unique_id == _key_id("sk-or-v1-new")


async def test_reconfigure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reconfigure swaps the key and keeps the entry."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "sk-or-v1-other"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "sk-or-v1-other"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The options flow sets the polling interval in minutes."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 30}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_SCAN_INTERVAL: 30}
