"""Klimadan switches: on/off device settings and the optional SG relay board."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KlimadanConfigEntry, KlimadanHub
from .const import KIND_SETTINGS, RELAY_AVAILABILITY, RELAYS
from .entity import KlimadanEntity, to_int

# Device setting number -> name (klimaDan/updateDeviceSettings {"<n>": 0|1}).
SETTING_SWITCHES = [
    ("65", "Brugsvand"),
    ("10", "Centralvarme"),
    ("2", "Smart grid styring"),
    ("3", "Tillad elpatron ved Boost"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: KlimadanConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub = entry.runtime_data
    entities: list[SwitchEntity] = [SettingSwitch(hub, key, name) for key, name in SETTING_SWITCHES]
    if hub.relay_id:
        entities += [RelaySwitch(hub, relay) for relay in RELAYS]
    async_add_entities(entities)


class SettingSwitch(KlimadanEntity, SwitchEntity):
    kinds = (KIND_SETTINGS,)
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, hub: KlimadanHub, key: str, name: str) -> None:
        super().__init__(hub, f"setting_{key}", name)
        self._key = key

    @property
    def is_on(self) -> bool | None:
        value = to_int(self.hub.settings.get(self._key))
        return None if value is None else value == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.hub.async_set_setting(self._key, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.hub.async_set_setting(self._key, 0)


class RelaySwitch(KlimadanEntity, SwitchEntity):
    """SG1/SG2 on the relay board (klimaDan/relay<id>/{in,out}/r1|r2)."""

    def __init__(self, hub: KlimadanHub, relay: str) -> None:
        super().__init__(hub, f"relay_{relay}", f"SG{relay[1:]}")
        self._relay = relay
        self.kinds = (f"relay_{relay}", f"relay_{RELAY_AVAILABILITY}")

    @property
    def available(self) -> bool:
        return self.hub.data.get(f"relay_{RELAY_AVAILABILITY}") == "online"

    @property
    def is_on(self) -> bool | None:
        state = self.hub.data.get(f"relay_{self._relay}")
        return None if state not in ("ON", "OFF") else state == "ON"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.hub.async_set_relay(self._relay, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.hub.async_set_relay(self._relay, False)
