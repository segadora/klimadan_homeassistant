"""Klimadan numbers: temperature device settings."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KlimadanConfigEntry, KlimadanHub
from .const import KIND_SETTINGS
from .entity import KlimadanEntity, to_int

# (setting, name, min, max, offset): the unit stores value + offset (curve shifts use 100 = 0).
SETTING_NUMBERS = [
    ("67", "Brugsvand start temperatur", 25, 55, 0),
    ("68", "Brugsvand slut temperatur", 30, 62, 0),
    ("12", "Varmestop", 0, 40, 0),
    ("13", "Fremløb maksimum", 25, 80, 0),
    ("14", "0C punkt", 25, 80, 0),
    ("15", "Fremløb minimum", 20, 80, 0),
    ("22", "Forskydning af varmekurve", -15, 15, 100),
    ("38", "Varmekurve forskydning - Komfort", -10, 10, 100),
    ("39", "Varmekurve forskydning - Boost", -15, 15, 100),
    ("80", "SG Komfort start temp - Brugsvand", 20, 50, 0),
    ("81", "SG Komfort stop temp - Brugsvand", 20, 60, 0),
    ("82", "SG Boost start temp - Brugsvand", 20, 55, 0),
    ("83", "SG Boost stop temp - Brugsvand", 20, 70, 0),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: KlimadanConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub = entry.runtime_data
    async_add_entities(SettingNumber(hub, *spec) for spec in SETTING_NUMBERS)


class SettingNumber(KlimadanEntity, NumberEntity):
    kinds = (KIND_SETTINGS,)
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_step = 1

    def __init__(
        self, hub: KlimadanHub, key: str, name: str, minimum: int, maximum: int, offset: int
    ) -> None:
        super().__init__(hub, f"setting_{key}", name)
        self._key = key
        self._offset = offset
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum

    @property
    def native_value(self) -> int | None:
        value = to_int(self.hub.settings.get(self._key))
        return None if value is None else value - self._offset

    async def async_set_native_value(self, value: float) -> None:
        await self.hub.async_set_setting(self._key, int(round(value)) + self._offset)
