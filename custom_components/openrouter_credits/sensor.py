"""Sensors for OpenRouter Credits."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import OpenRouterData
from .const import DOMAIN
from .coordinator import OpenRouterConfigEntry, OpenRouterCoordinator

CURRENCY = "USD"


def _credits_remaining(d: OpenRouterData) -> float | None:
    if d.credits is None:
        return None
    return round(
        (d.credits.get("total_credits") or 0) - (d.credits.get("total_usage") or 0), 4
    )


def _is_inference_key(d: OpenRouterData) -> bool:
    """Management keys can't run completions, so their own usage is always 0."""
    return not (d.key.get("is_management_key") or d.key.get("is_provisioning_key"))


def _has_limit(d: OpenRouterData) -> bool:
    return _is_inference_key(d) and d.key.get("limit") is not None


@dataclass(frozen=True, kw_only=True)
class OpenRouterSensorDescription(SensorEntityDescription):
    """Describes an OpenRouter sensor."""

    value_fn: Callable[[OpenRouterData], Any]
    # Only created when this returns True for the first fetched data
    available_fn: Callable[[OpenRouterData], bool] = lambda d: True


def _money(key: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "key": key,
        "translation_key": key,
        "device_class": SensorDeviceClass.MONETARY,
        "native_unit_of_measurement": CURRENCY,
        "state_class": SensorStateClass.TOTAL,
        "suggested_display_precision": 2,
        **kwargs,
    }


SENSORS: tuple[OpenRouterSensorDescription, ...] = (
    # Account-level (management key only)
    OpenRouterSensorDescription(
        **_money("credits_remaining"),
        value_fn=_credits_remaining,
        available_fn=lambda d: d.credits is not None,
    ),
    OpenRouterSensorDescription(
        **_money("total_credits"),
        value_fn=lambda d: d.credits.get("total_credits") if d.credits else None,
        available_fn=lambda d: d.credits is not None,
    ),
    OpenRouterSensorDescription(
        **_money("total_usage"),
        value_fn=lambda d: d.credits.get("total_usage") if d.credits else None,
        available_fn=lambda d: d.credits is not None,
    ),
    # Key-level
    OpenRouterSensorDescription(
        **_money("key_usage"),
        value_fn=lambda d: d.key.get("usage"),
        available_fn=_is_inference_key,
    ),
    OpenRouterSensorDescription(
        **_money("key_usage_daily"),
        value_fn=lambda d: d.key.get("usage_daily"),
        available_fn=_is_inference_key,
    ),
    OpenRouterSensorDescription(
        **_money("key_usage_weekly"),
        value_fn=lambda d: d.key.get("usage_weekly"),
        available_fn=_is_inference_key,
    ),
    OpenRouterSensorDescription(
        **_money("key_usage_monthly"),
        value_fn=lambda d: d.key.get("usage_monthly"),
        available_fn=_is_inference_key,
    ),
    OpenRouterSensorDescription(
        **_money("key_limit"),
        value_fn=lambda d: d.key.get("limit"),
        available_fn=_has_limit,
    ),
    OpenRouterSensorDescription(
        **_money("key_limit_remaining"),
        value_fn=lambda d: d.key.get("limit_remaining"),
        available_fn=_has_limit,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenRouterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    active = [d for d in SENSORS if d.available_fn(coordinator.data)]
    async_add_entities(OpenRouterSensor(coordinator, d) for d in active)

    # Drop account-level sensors that no longer apply, e.g. after switching key type
    ent_reg = er.async_get(hass)
    for description in SENSORS:
        if description in active:
            continue
        unique_id = f"{entry.entry_id}_{description.key}"
        if entity_id := ent_reg.async_get_entity_id(Platform.SENSOR, DOMAIN, unique_id):
            ent_reg.async_remove(entity_id)

    # Per-key sensors (management key only). Keys created later get added on refresh.
    known: set[str] = set()

    @callback
    def _add_new_keys() -> None:
        keys = coordinator.data.keys or {}
        new = [h for h in keys if h not in known]
        if not new:
            return
        known.update(new)
        async_add_entities(
            OpenRouterKeySensor(coordinator, key_hash, description)
            for key_hash in new
            for description in KEY_SENSORS
            if description.available_fn(keys[key_hash])
        )

    _add_new_keys()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_keys))


class OpenRouterSensor(CoordinatorEntity[OpenRouterCoordinator], SensorEntity):
    """An OpenRouter sensor."""

    _attr_has_entity_name = True
    entity_description: OpenRouterSensorDescription

    def __init__(
        self,
        coordinator: OpenRouterCoordinator,
        description: OpenRouterSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        # entry_id stays stable when the API key is swapped via reauth/reconfigure
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="OpenRouter",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://openrouter.ai/settings/credits",
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)


@dataclass(frozen=True, kw_only=True)
class OpenRouterKeySensorDescription(SensorEntityDescription):
    """Describes a sensor for one API key from the /keys listing."""

    field: str
    available_fn: Callable[[dict[str, Any]], bool] = lambda k: True


KEY_SENSORS: tuple[OpenRouterKeySensorDescription, ...] = (
    OpenRouterKeySensorDescription(**_money("api_key_usage"), field="usage"),
    OpenRouterKeySensorDescription(**_money("api_key_usage_daily"), field="usage_daily"),
    OpenRouterKeySensorDescription(**_money("api_key_usage_weekly"), field="usage_weekly"),
    OpenRouterKeySensorDescription(**_money("api_key_usage_monthly"), field="usage_monthly"),
    OpenRouterKeySensorDescription(
        **_money("api_key_limit_remaining"),
        field="limit_remaining",
        available_fn=lambda k: k.get("limit") is not None,
    ),
)


class OpenRouterKeySensor(CoordinatorEntity[OpenRouterCoordinator], SensorEntity):
    """Usage of one API key, read via the management key."""

    _attr_has_entity_name = True
    entity_description: OpenRouterKeySensorDescription

    def __init__(
        self,
        coordinator: OpenRouterCoordinator,
        key_hash: str,
        description: OpenRouterKeySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._key_hash = key_hash
        entry = coordinator.config_entry
        info = (coordinator.data.keys or {})[key_hash]
        self._attr_unique_id = f"{entry.entry_id}_{key_hash}_{description.key}"
        self._device_name = info.get("name") or info.get("label") or key_hash[:8]

    @property
    def device_info(self) -> DeviceInfo:
        entry = self.coordinator.config_entry
        info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{self._key_hash}")},
            name=self._device_name,
            manufacturer="OpenRouter",
            model="API key",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://openrouter.ai/settings/keys",
        )
        parent = (DOMAIN, entry.entry_id)
        if hasattr(dr, "async_get_device_id_by_identifier"):
            # HA 2026.7+: via_device is deprecated in favour of via_device_id
            info["via_device_id"] = dr.async_get_device_id_by_identifier(
                self.hass, parent, config_entry_id=entry.entry_id
            )
        else:
            info["via_device"] = parent
        return info

    @property
    def _key(self) -> dict[str, Any] | None:
        return (self.coordinator.data.keys or {}).get(self._key_hash)

    @property
    def available(self) -> bool:
        # Deleted or disabled keys drop out of the listing
        return super().available and self._key is not None

    @property
    def native_value(self) -> Any:
        key = self._key
        return key.get(self.entity_description.field) if key else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        key = self._key
        if not key or self.entity_description.key != "api_key_usage":
            return None
        return {
            attr: key.get(attr)
            for attr in ("label", "limit", "limit_reset", "created_at", "expires_at")
            if key.get(attr) is not None
        }
