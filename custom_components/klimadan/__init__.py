"""Klimadan heat pump (kl_tft v064) over MQTT."""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval

from .alarms import active_alarms, reset_result
from .const import (
    ALARM_LOG_DELAY,
    ALARM_LOG_INTERVAL,
    CMD_GET_ALARM_LOG,
    CMD_GET_SETTINGS,
    CMD_UPDATE_SETTINGS,
    CONF_LANGUAGE,
    CONF_RELAY_ID,
    CONF_UNIT_ID,
    DEFAULT_NAME,
    DOMAIN,
    EVENT_ALARM_ACK,
    JSON_KINDS,
    MISSING_RETRY,
    KIND_ALARM,
    KIND_ALARM_ACK,
    KIND_ALARM_LOG,
    KIND_SETTINGS,
    KIND_SETTINGS_RECEIVED,
    RELAY_AVAILABILITY,
    RELAYS,
    SETTINGS_INTERVAL,
    SETTINGS_REFRESH_FALLBACK,
    STARTUP_DELAY,
    STATE_KINDS,
    TOPIC_PREFIX,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type KlimadanConfigEntry = ConfigEntry[KlimadanHub]


class KlimadanHub:
    """Subscribes to one unit's topics and keeps the latest payload per topic."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.unit_id: str = entry.data[CONF_UNIT_ID]
        self.language: str = entry.data[CONF_LANGUAGE]
        self.relay_id: str | None = entry.data.get(CONF_RELAY_ID) or None
        self.data: dict[str, Any] = {}
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unit_id)},
            name=entry.data.get(CONF_NAME, DEFAULT_NAME),
            manufacturer="Klimadan",
            model="kl_tft v064",
            serial_number=self.unit_id,
        )
        self._unsubs: list[Callable[[], None]] = []
        self._pending: dict[str, Callable[[], None]] = {}
        self._alarm_active: bool | None = None
        self._last_sent: dict[str, float] = {}

    def topic(self, kind: str) -> str:
        return f"{TOPIC_PREFIX}/{kind}/{self.unit_id}"

    def relay_topic(self, direction: str, name: str) -> str:
        return f"{TOPIC_PREFIX}/relay{self.relay_id}/{direction}/{name}"

    def signal(self, kind: str) -> str:
        return f"{DOMAIN}_{self.entry.entry_id}_{kind}"

    @property
    def settings(self) -> dict[str, Any]:
        return self.data.get(KIND_SETTINGS, {})

    async def async_start(self) -> None:
        for kind in STATE_KINDS:
            self._unsubs.append(
                await mqtt.async_subscribe(self.hass, self.topic(kind), self._handler(kind))
            )
        if self.relay_id:
            for name in (*RELAYS, RELAY_AVAILABILITY):
                self._unsubs.append(
                    await mqtt.async_subscribe(
                        self.hass, self.relay_topic("out", name), self._handler(f"relay_{name}")
                    )
                )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._poll_settings, SETTINGS_INTERVAL)
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._poll_alarm_log, ALARM_LOG_INTERVAL)
        )
        # Not right away: the subscriptions above may not have reached the broker yet,
        # and a quick reply from the unit would be lost.
        self._unsubs.append(async_call_later(self.hass, STARTUP_DELAY, self._startup_requests))

    @callback
    def async_stop(self) -> None:
        for unsub in (*self._unsubs, *self._pending.values()):
            unsub()
        self._unsubs.clear()
        self._pending.clear()

    def _handler(self, kind: str) -> Callable[[mqtt.ReceiveMessage], None]:
        @callback
        def handle(msg: mqtt.ReceiveMessage) -> None:
            value: Any = msg.payload
            if kind == KIND_ALARM_ACK:
                # Earlier patched builds sent no payload: keep the ack, without results.
                try:
                    value = json.loads(msg.payload)
                except ValueError:
                    value = None
                if not isinstance(value, dict):
                    value = {}
            elif kind in JSON_KINDS:
                try:
                    value = json.loads(msg.payload)
                except ValueError:
                    _LOGGER.debug("Ignoring non-JSON payload on %s: %r", msg.topic, msg.payload)
                    return
                if not isinstance(value, dict):
                    return
            if kind == KIND_SETTINGS:
                value = {**self.settings, **value}
            self.data[kind] = value

            if kind == KIND_ALARM:
                self._on_alarm(value)
            elif kind == KIND_SETTINGS_RECEIVED:
                self.hass.async_create_task(self.async_send(CMD_GET_SETTINGS, ""))
            elif kind == KIND_ALARM_ACK:
                result = reset_result(value, self.language)
                self.hass.bus.async_fire(EVENT_ALARM_ACK, {
                    "unit_id": self.unit_id,
                    "reset": result["reset"],
                    "refused": result["refused"],
                    "no_reply": result["noReply"],
                })
                self._send_later(CMD_GET_ALARM_LOG, "1", ALARM_LOG_DELAY)
            async_dispatcher_send(self.hass, self.signal(kind))
            if kind in STATE_KINDS:
                self._request_missing()

        return handle

    async def _startup_requests(self, _now: Any) -> None:
        await self.async_send(CMD_GET_SETTINGS, "")
        await self.async_send(CMD_GET_ALARM_LOG, "1")

    @callback
    def _request_missing(self) -> None:
        """The unit is online: ask again for what never arrived (e.g. it was off at start-up)."""
        now = time.monotonic()
        for kind, command, payload in (
            (KIND_SETTINGS, CMD_GET_SETTINGS, ""),
            (KIND_ALARM_LOG, CMD_GET_ALARM_LOG, "1"),
        ):
            last = self._last_sent.get(command)
            if kind not in self.data and (last is None or now - last >= MISSING_RETRY):
                self._last_sent[command] = now
                self.hass.async_create_task(self.async_send(command, payload))

    @callback
    def _on_alarm(self, payload: dict[str, Any]) -> None:
        """Fetch the alarm log when an alarm becomes active (the unit only sends it on request)."""
        active = bool(active_alarms(payload, self.language))
        if active and self._alarm_active is False:
            self._send_later(CMD_GET_ALARM_LOG, "1", ALARM_LOG_DELAY)
        self._alarm_active = active

    async def async_send(self, command: str, payload: str) -> None:
        self._last_sent[command] = time.monotonic()
        await mqtt.async_publish(self.hass, self.topic(command), payload)

    async def async_set_setting(self, key: str, value: int) -> None:
        """Change one device setting; the unit confirms with deviceSettingsReceived."""
        await self.async_send(CMD_UPDATE_SETTINGS, json.dumps({key: value}, separators=(",", ":")))
        self._send_later(CMD_GET_SETTINGS, "", SETTINGS_REFRESH_FALLBACK)

    async def async_set_relay(self, name: str, on: bool) -> None:
        await mqtt.async_publish(self.hass, self.relay_topic("in", name), "ON" if on else "OFF")

    @callback
    def _send_later(self, command: str, payload: str, delay: float) -> None:
        if cancel := self._pending.pop(command, None):
            cancel()

        async def send(_now: Any) -> None:
            self._pending.pop(command, None)
            await self.async_send(command, payload)

        self._pending[command] = async_call_later(self.hass, delay, send)

    async def _poll_settings(self, _now: Any) -> None:
        await self.async_send(CMD_GET_SETTINGS, "")

    async def _poll_alarm_log(self, _now: Any) -> None:
        await self.async_send(CMD_GET_ALARM_LOG, "1")


async def async_setup_entry(hass: HomeAssistant, entry: KlimadanConfigEntry) -> bool:
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT is not available")
    hub = KlimadanHub(hass, entry)
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await hub.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KlimadanConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.async_stop()
    return unloaded
