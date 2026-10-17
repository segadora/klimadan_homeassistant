"""Klimadan buttons: request settings / alarm log, reset alarms."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KlimadanConfigEntry, KlimadanHub
from .const import CMD_GET_ALARM_LOG, CMD_GET_SETTINGS, CMD_RESET_ALARMS
from .entity import KlimadanEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: KlimadanConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub = entry.runtime_data
    async_add_entities([
        CommandButton(hub, "update", "Opdater", CMD_GET_SETTINGS, "", ButtonDeviceClass.UPDATE),
        CommandButton(hub, "hent_alarmlog", "Hent alarmhistorik", CMD_GET_ALARM_LOG, "1",
                      icon="mdi:refresh"),
        # Needs the patched firmware (patches/DK/src/alarm_reset.c).
        CommandButton(hub, "nulstil_alarmer", "Nulstil alarmer", CMD_RESET_ALARMS, "1",
                      icon="mdi:alarm-light-off-outline"),
    ])


class CommandButton(KlimadanEntity, ButtonEntity):
    def __init__(
        self,
        hub: KlimadanHub,
        key: str,
        name: str,
        command: str,
        payload: str,
        device_class: ButtonDeviceClass | None = None,
        icon: str | None = None,
    ) -> None:
        super().__init__(hub, key, name)
        self._command = command
        self._payload = payload
        self._attr_device_class = device_class
        self._attr_icon = icon

    async def async_press(self) -> None:
        await self.hub.async_send(self._command, self._payload)
