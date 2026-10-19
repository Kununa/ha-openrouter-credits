"""Config flow for OpenRouter Credits."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import OpenRouterAuthError, OpenRouterClient, OpenRouterError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

API_KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _key_id(api_key: str) -> str:
    """Stable unique id derived from the key without storing it in the id."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


class OpenRouterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenRouter Credits."""

    VERSION = 1

    async def _validate(self, api_key: str) -> tuple[dict[str, str], dict[str, Any]]:
        errors: dict[str, str] = {}
        info: dict[str, Any] = {}
        client = OpenRouterClient(async_get_clientsession(self.hass), api_key)
        try:
            info = await client.async_get_key()
        except OpenRouterAuthError:
            errors["base"] = "invalid_auth"
        except OpenRouterError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error validating OpenRouter key")
            errors["base"] = "unknown"
        return errors, info

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initial step: ask for the API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            await self.async_set_unique_id(_key_id(api_key))
            self._abort_if_unique_id_configured()
            errors, info = await self._validate(api_key)
            if not errors:
                # The key label is just the masked key, so don't use it as a name
                title = user_input.get(CONF_NAME) or "OpenRouter"
                return self.async_create_entry(
                    title=title,
                    data={CONF_API_KEY: api_key},
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): API_KEY_SELECTOR,
                    vol.Optional(CONF_NAME): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "keys_url": "https://openrouter.ai/settings/keys",
                "management_keys_url": "https://openrouter.ai/settings/management-keys",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when the key stops working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            errors, _ = await self._validate(api_key)
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    unique_id=_key_id(api_key),
                    data_updates={CONF_API_KEY: api_key},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): API_KEY_SELECTOR}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow changing the API key from the UI."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            errors, _ = await self._validate(api_key)
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    unique_id=_key_id(api_key),
                    data_updates={CONF_API_KEY: api_key},
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): API_KEY_SELECTOR}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OpenRouterOptionsFlow:
        """Return the options flow."""
        return OpenRouterOptionsFlow()


class OpenRouterOptionsFlow(OptionsFlow):
    """Options: polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )

        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
