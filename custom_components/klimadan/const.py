"""Constants for the Klimadan integration (kl_tft v064 MQTT protocol)."""
from datetime import timedelta

DOMAIN = "klimadan"

CONF_UNIT_ID = "unit_id"
CONF_LANGUAGE = "language"
CONF_RELAY_ID = "relay_id"

DEFAULT_NAME = "Nordic 10C"
LANGUAGES = ["DK", "EN", "DE"]

# klimaDan/<kind>/<unit id>
TOPIC_PREFIX = "klimaDan"

# Published by the unit.
KIND_TEMPERATURE = "temperature"
KIND_PWM_WATT = "pwmWatt"
KIND_SETTINGS = "updateCloudSettings"        # reply to getDeviceSettings
KIND_SETTINGS_RECEIVED = "deviceSettingsReceived"  # after an updateDeviceSettings was applied
KIND_ALARM = "alarm"
KIND_ALARM_LOG = "setAlarmLog"               # reply to getAlarmLog
KIND_ALARM_ACK = "setAlarmAck"               # after resetAlarms (patched firmware)

# Sent to the unit.
CMD_UPDATE_SETTINGS = "updateDeviceSettings"
CMD_GET_SETTINGS = "getDeviceSettings"
CMD_GET_ALARM_LOG = "getAlarmLog"
CMD_RESET_ALARMS = "resetAlarms"             # patched firmware only

JSON_KINDS = (KIND_TEMPERATURE, KIND_PWM_WATT, KIND_SETTINGS, KIND_ALARM, KIND_ALARM_LOG)
STATE_KINDS = JSON_KINDS + (KIND_SETTINGS_RECEIVED, KIND_ALARM_ACK)

# SG relay board (klimaDan/relay<id>/out/r1 ...), optional.
RELAYS = ("r1", "r2")
RELAY_AVAILABILITY = "lwt_availability"

SETTINGS_INTERVAL = timedelta(minutes=10)
ALARM_LOG_INTERVAL = timedelta(minutes=30)
SETTINGS_REFRESH_FALLBACK = 15  # s after a settings change, if deviceSettingsReceived never comes
STARTUP_DELAY = 5               # s after subscribing: HA sends SUBSCRIBE packets in batches
MISSING_RETRY = 60              # s between re-requests while settings / alarm log never arrived
ALARM_LOG_DELAY = 5             # s after an alarm became active or was reset

EVENT_ALARM_ACK = f"{DOMAIN}_alarm_ack"
