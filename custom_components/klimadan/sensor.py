"""Klimadan sensors: temperatures, pwmWatt values, status and alarms."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KlimadanConfigEntry, KlimadanHub
from .alarms import (
    active_alarms,
    alarm_log,
    alarm_log_state,
    alarm_state,
    reset_result,
    reset_result_state,
)
from .const import KIND_ALARM, KIND_ALARM_ACK, KIND_ALARM_LOG, KIND_PWM_WATT, KIND_TEMPERATURE
from .entity import KlimadanEntity, to_float, to_int

# Index into klimaDan/temperature/<id> (keys T0..T11 in payload order).
TEMPERATURES = [
    (0, "Varme frem"),
    (1, "Varme retur"),
    (2, "System frem"),
    (3, "VV top"),
    (4, "VV bund"),
    (5, "Ude"),
    (6, "Brine frem"),
    (7, "Brine retur"),
    (8, "Sugerør"),
    (9, "Væske"),
    (10, "Trykrør"),
    (11, "Ønsket fremløb"),
]

# klimaDan/pwmWatt/<id>: (key, name, divisor). Values are zero-padded strings, e.g.
# {"d2": "04.14", "d9": "-0037"}. COP/SCOP are plain ratios. Behov is shown as is
# ("00019" = 19, "-0037" = -37 on the display).
PWM_VALUES = [("d2", "COP", 1), ("d3", "SCOP", 1), ("d9", "Behov", 1)]

STATUS = {
    0: "noConnection",
    1: "off",
    2: "standby",
    3: "varme",
    4: "brugsvand",
    5: "frost",
    6: "evuLock",
    7: "motionering",
    8: "manuel",
    9: "pcbTest",
}

def temperatures(hub: KlimadanHub) -> list[float | None]:
    payload = hub.data.get(KIND_TEMPERATURE)
    if not payload:
        return []
    if "T0" in payload:
        values = [payload.get(f"T{i}") for i in range(len(payload))]
    else:
        values = list(payload.values())
    return [to_float(v) for v in values]


async def async_setup_entry(
    hass: HomeAssistant, entry: KlimadanConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub = entry.runtime_data
    entities: list[SensorEntity] = [TemperatureSensor(hub, i, name) for i, name in TEMPERATURES]
    entities.append(TapWaterAverageSensor(hub))
    entities += [PwmValueSensor(hub, *spec) for spec in PWM_VALUES]
    entities += [HeatOutputSensor(hub), StatusSensor(hub), AlarmSensor(hub), AlarmLogSensor(hub),
                 AlarmResetSensor(hub)]
    async_add_entities(entities)


class TemperatureSensor(KlimadanEntity, SensorEntity):
    kinds = (KIND_TEMPERATURE,)
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, hub: KlimadanHub, index: int, name: str) -> None:
        super().__init__(hub, f"t{index}", name)
        self._index = index

    @property
    def native_value(self) -> float | None:
        values = temperatures(self.hub)
        return values[self._index] if self._index < len(values) else None


class TapWaterAverageSensor(KlimadanEntity, SensorEntity):
    """Mean of VV top (T3) and VV bund (T4)."""

    kinds = (KIND_TEMPERATURE,)
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, hub: KlimadanHub) -> None:
        super().__init__(hub, "vv", "VV")

    @property
    def native_value(self) -> float | None:
        values = temperatures(self.hub)
        if len(values) < 5 or values[3] is None or values[4] is None:
            return None
        return round((values[3] + values[4]) / 2, 2)


class PwmValueSensor(KlimadanEntity, SensorEntity):
    kinds = (KIND_PWM_WATT,)
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, hub: KlimadanHub, key: str, name: str, divisor: int) -> None:
        super().__init__(hub, key, name)
        self._key = key
        self._divisor = divisor

    @property
    def native_value(self) -> float | None:
        value = to_float(self.hub.data.get(KIND_PWM_WATT, {}).get(self._key))
        return None if value is None else round(value / self._divisor, 2)


class HeatOutputSensor(KlimadanEntity, SensorEntity):
    kinds = (KIND_PWM_WATT,)
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT

    def __init__(self, hub: KlimadanHub) -> None:
        super().__init__(hub, "d4", "Varmeeffekt")

    @property
    def native_value(self) -> float | None:
        return to_float(self.hub.data.get(KIND_PWM_WATT, {}).get("d4"))


class StatusSensor(KlimadanEntity, SensorEntity):
    kinds = (KIND_PWM_WATT,)
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(STATUS.values())

    def __init__(self, hub: KlimadanHub) -> None:
        super().__init__(hub, "status", "Status")

    @property
    def native_value(self) -> str | None:
        return STATUS.get(to_int(self.hub.data.get(KIND_PWM_WATT, {}).get("d1")))


class AlarmSensor(KlimadanEntity, SensorEntity):
    kinds = (KIND_ALARM,)
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, hub: KlimadanHub) -> None:
        super().__init__(hub, "alarmer", "Aktuelle alarmer")

    @property
    def native_value(self) -> str | None:
        payload = self.hub.data.get(KIND_ALARM)
        return None if payload is None else alarm_state(payload, self.hub.language)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        payload = self.hub.data.get(KIND_ALARM)
        if payload is None:
            return None
        active = active_alarms(payload, self.hub.language)
        return {"alarmer": active, "antal": len(active), "raw": payload}


class AlarmLogSensor(KlimadanEntity, SensorEntity):
    kinds = (KIND_ALARM_LOG,)
    _attr_icon = "mdi:clipboard-text-clock-outline"

    def __init__(self, hub: KlimadanHub) -> None:
        super().__init__(hub, "alarmlog", "Alarmhistorik")

    @property
    def native_value(self) -> str | None:
        payload = self.hub.data.get(KIND_ALARM_LOG)
        if payload is None:
            return None
        return alarm_log_state(alarm_log(payload, self.hub.language), self.hub.language)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        payload = self.hub.data.get(KIND_ALARM_LOG)
        if payload is None:
            return None
        log = alarm_log(payload, self.hub.language)
        return {"log": [f"{e['time']}  {e['text']}" for e in log], "entries": log}


class AlarmResetSensor(KlimadanEntity, SensorEntity):
    """Outcome of the last resetAlarms (patched firmware), per alarm."""

    kinds = (KIND_ALARM_ACK,)
    _attr_icon = "mdi:alarm-light-off-outline"

    def __init__(self, hub: KlimadanHub) -> None:
        super().__init__(hub, "alarmnulstilling", "Sidste alarmnulstilling")

    @property
    def native_value(self) -> str | None:
        payload = self.hub.data.get(KIND_ALARM_ACK)
        if not payload:  # nothing yet, or firmware without results
            return None
        return reset_result_state(payload, self.hub.language)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        payload = self.hub.data.get(KIND_ALARM_ACK)
        if not payload:
            return None
        result = reset_result(payload, self.hub.language)
        return {
            "nulstillet": result["reset"],
            "afvist": result["refused"],
            "intet_svar": result["noReply"],
            "raw": payload,
        }
