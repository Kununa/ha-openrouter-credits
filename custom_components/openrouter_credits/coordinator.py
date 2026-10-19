"""Data update coordinator for OpenRouter Credits."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenRouterAuthError, OpenRouterClient, OpenRouterData, OpenRouterError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type OpenRouterConfigEntry = ConfigEntry[OpenRouterCoordinator]


class OpenRouterCoordinator(DataUpdateCoordinator[OpenRouterData]):
    """Polls OpenRouter periodically."""

    config_entry: OpenRouterConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: OpenRouterConfigEntry,
        client: OpenRouterClient,
    ) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=minutes),
        )
        self.client = client

    async def _async_update_data(self) -> OpenRouterData:
        try:
            return await self.client.async_get_data()
        except OpenRouterAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except OpenRouterError as err:
            raise UpdateFailed(str(err)) from err
