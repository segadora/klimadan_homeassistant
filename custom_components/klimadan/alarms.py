"""Decode klimaDan/alarm and klimaDan/setAlarmLog payloads (see tools/gen_homeassistant.py)."""
from __future__ import annotations

from typing import Any

from .alarm_texts import ALARM_NAMES, EMPTY_LOG_TEXT, FIRST_BIT, LOG_CODES, NONE_TEXT, UNKNOWN_TEXT

SLOTS = 10


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def active_alarms(payload: dict[str, Any], lang: str) -> list[str]:
    """Bit g (g = 32 * word + bit, A1..A4 = word 0..3) is alarm code 0x50 + g - FIRST_BIT."""
    words = [_int(payload.get(f"A{i}", payload.get(str(i), 0))) for i in range(1, 5)]
    active = []
    for n, name in enumerate(ALARM_NAMES[lang]):
        g = n + FIRST_BIT
        if words[g // 32] >> (g % 32) & 1:
            active.append(alarm_name(n, lang))
    return active


# klimaDan/setAlarmAck/<id> from the patched firmware: display alarm numbers n per outcome.
RESET_RESULTS = ("reset", "refused", "noReply")
RESET_LABELS = {
    "DK": {"reset": "Nulstillet", "refused": "Afvist", "noReply": "Intet svar"},
    "EN": {"reset": "Reset", "refused": "Refused", "noReply": "No reply"},
    "DE": {"reset": "Zurückgesetzt", "refused": "Abgelehnt", "noReply": "Keine Antwort"},
}
NOTHING_RESET_TEXT = {
    "DK": "Ingen aktive alarmer at nulstille",
    "EN": "No active alarms to reset",
    "DE": "Keine aktiven Alarme zum Zurücksetzen",
}


def alarm_name(n: int, lang: str) -> str:
    names = ALARM_NAMES[lang]
    return (names[n] if 0 <= n < len(names) else "") or f"Alarm 0x{0x50 + n:02x}"


def reset_result(payload: dict[str, Any], lang: str) -> dict[str, list[str]]:
    """Alarm names per outcome; an alarm in "refused" can be reset again after ~2 minutes."""
    out = {}
    for key in RESET_RESULTS:
        raw = payload.get(key)
        out[key] = [alarm_name(_int(n), lang) for n in raw] if isinstance(raw, list) else []
    return out


def reset_result_state(payload: dict[str, Any], lang: str) -> str:
    result = reset_result(payload, lang)
    parts = [
        f"{RESET_LABELS[lang][key]}: {', '.join(names)}"
        for key, names in result.items()
        if names
    ]
    return ("; ".join(parts) if parts else NOTHING_RESET_TEXT[lang])[:255].rstrip()


def alarm_state(payload: dict[str, Any], lang: str) -> str:
    active = active_alarms(payload, lang)
    return (", ".join(active) if active else NONE_TEXT[lang])[:255].rstrip()


def alarm_log(payload: dict[str, Any], lang: str) -> list[dict[str, Any]]:
    """setAlarmLog entries, newest first.

    Each slot is [marker, code, hour, minute, day, month]; marker 0 is the next slot to
    be overwritten (the oldest entry), so the newest entry is the slot before it.
    """
    entries = []
    for i in range(SLOTS):
        raw = payload.get(str(i), payload.get(f"A{i}", []))
        values = [_int(v) for v in raw] if isinstance(raw, list) else []
        entries.append((values + [0] * 6)[:6])

    newest = 0
    for i, entry in enumerate(entries):
        if entry[0] == 0:
            newest = (SLOTS - 1 if entries[SLOTS - 1][1] else -1) if i == 0 else i - 1
            break
    if newest < 0:
        return []

    out = []
    for n in range(SLOTS):
        slot = (newest - n) % SLOTS
        marker, code, hour, minute, day, month = entries[slot]
        if code == 0:
            break
        out.append({
            "slot": slot,
            "time": f"{day:02d}/{month:02d} {hour:02d}:{minute:02d}",
            "code": code,
            "text": LOG_CODES[lang].get(code, f"{UNKNOWN_TEXT[lang]} {code}"),
        })
        if marker == 0:
            break
    return out


def alarm_log_state(log: list[dict[str, Any]], lang: str) -> str:
    return (f"{log[0]['time']} {log[0]['text']}" if log else EMPTY_LOG_TEXT[lang])[:255].rstrip()
