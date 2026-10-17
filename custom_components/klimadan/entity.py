"""Base entity for the Klimadan integration."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import KlimadanHub


def to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class KlimadanEntity(Entity):
    """Entity updated from one or more of the hub's topics."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    kinds: tuple[str, ...] = ()

    def __init__(self, hub: KlimadanHub, key: str, name: str) -> None:
        self.hub = hub
        self._attr_unique_id = f"{hub.unit_id}_{key}"
        self._attr_name = name
        self._attr_device_info = hub.device_info

    async def async_added_to_hass(self) -> None:
        for kind in self.kinds:
            self.async_on_remove(
                async_dispatcher_connect(self.hass, self.hub.signal(kind), self.async_write_ha_state)
            )
