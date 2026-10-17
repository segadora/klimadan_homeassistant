"""Klimadan binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KlimadanConfigEntry, KlimadanHub
from .alarms import active_alarms
from .const import KIND_ALARM
from .entity import KlimadanEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: KlimadanConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([AlarmActiveSensor(entry.runtime_data)])


class AlarmActiveSensor(KlimadanEntity, BinarySensorEntity):
    kinds = (KIND_ALARM,)
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, hub: KlimadanHub) -> None:
        super().__init__(hub, "alarm_aktiv", "Alarm aktiv")

    @property
    def is_on(self) -> bool | None:
        payload = self.hub.data.get(KIND_ALARM)
        return None if payload is None else bool(active_alarms(payload, self.hub.language))
