# Klimadan for Home Assistant

Custom integration for Klimadan heat pumps with the kl_tft display (firmware v064).
It reads and controls the unit over Home Assistant's MQTT connection, using the topics
the display publishes (`klimaDan/<kind>/<Cloud ID>`). The display must be set up to
use your own MQTT broker, the one Home Assistant's MQTT integration is connected to.

## Installation

With [HACS](https://hacs.xyz):

1. HACS > three-dot menu > Custom repositories. Add
   `https://github.com/segadora/klimadan_homeassistant` with type *Integration*.
2. Search for "Klimadan", download it, and restart Home Assistant.

Manually: copy `custom_components/klimadan` to `<config>/custom_components/klimadan`
and restart Home Assistant.

## Setup

Settings > Devices & services > Add integration > "Klimadan". Enter:

- **Cloud ID**: the last part of the unit's topics, e.g. `100111` in `klimaDan/heartbeat/100111`.
- **Name** of the device.
- **Language** for the alarm texts (DK, EN, DE).
- **SG relay board ID** (optional): e.g. `72491` for `klimaDan/relay72491/...`.

## Entities

All on one device:

| Platform | Entities | Topic |
|---|---|---|
| sensor | 12 temperatures (T0-T11), VV (mean of T3/T4) | `temperature` |
| sensor | COP, SCOP, Behov, Varmeeffekt (kW), Status | `pwmWatt` |
| sensor / binary sensor | Aktuelle alarmer, Alarm aktiv | `alarm` |
| sensor | Alarmhistorik | `setAlarmLog` |
| sensor | Sidste alarmnulstilling (patched firmware) | `setAlarmAck` |
| switch | Brugsvand (65), Centralvarme (10), Smart grid styring (2), Tillad elpatron ved Boost (3) | `updateCloudSettings` / `updateDeviceSettings` |
| select | Varmepumpe indstillinger (0) | same |
| number | settings 67, 68, 12, 13, 14, 15, 22, 38, 39, 80-83 | same |
| button | Opdater, Hent alarmhistorik, Nulstil alarmer (patched firmware) | `getDeviceSettings`, `getAlarmLog`, `resetAlarms` |
| switch | SG1, SG2 (only with a relay board ID) | `relay<ID>/{in,out}/r1, r2` |

The integration requests the settings at start-up, every 10 minutes and after each change.
It requests the alarm log at start-up, every 30 minutes, when an alarm becomes active and
after an alarm reset.

### Resetting alarms

"Nulstil alarmer" and "Sidste alarmnulstilling" need the patched display firmware, which
adds the `resetAlarms` command. The unit then resets each active alarm the same way as on
the display. The bottom board refuses a reset for about 2 minutes after an alarm was raised
or last reset; those alarms are listed as refused, and can be reset again after that.

Each reset fires the event `klimadan_alarm_ack` with `unit_id` and the alarm names in
`reset`, `refused` and `no_reply`. For example, to try again after a refusal:

```yaml
automation:
  - alias: Klimadan - retry refused alarm reset
    trigger:
      - platform: event
        event_type: klimadan_alarm_ack
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.refused | length > 0 }}"
    action:
      - delay: "00:02:30"
      - service: button.press
        target:
          entity_id: button.nordic_10c_nulstil_alarmer
```

## Moving from a YAML setup

Remove the `mqtt:` entities for the unit (and any alarm-log automation) and reload MQTT
*before* adding the integration. The entity names are the same, so the entity IDs
(`sensor.nordic_10c_brine_frem`, ...) and their history carry over. If an entity ends up
with a `_2` suffix, delete the old MQTT entity and rename the new one.
