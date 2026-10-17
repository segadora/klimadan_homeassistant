"""Klimadan select: heat pump operating mode (device setting 0)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KlimadanConfigEntry, KlimadanHub
from .const import KIND_SETTINGS
from .entity import KlimadanEntity, to_int

MODES = {0: "OFF", 1: "Automatisk", 2: "Nødvarme"}


async def async_setup_entry(
    hass: HomeAssistant, entry: KlimadanConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ModeSelect(entry.runtime_data)])


class ModeSelect(KlimadanEntity, SelectEntity):
    kinds = (KIND_SETTINGS,)
    _attr_options = list(MODES.values())

    def __init__(self, hub: KlimadanHub) -> None:
        super().__init__(hub, "setting_0", "Varmepumpe indstillinger")

    @property
    def current_option(self) -> str | None:
        return MODES.get(to_int(self.hub.settings.get("0")))

    async def async_select_option(self, option: str) -> None:
        value = next(k for k, v in MODES.items() if v == option)
        await self.hub.async_set_setting("0", value)
