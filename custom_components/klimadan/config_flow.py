"""Config flow for Klimadan: one entry per unit (Cloud ID)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME

from .const import CONF_LANGUAGE, CONF_RELAY_ID, CONF_UNIT_ID, DEFAULT_NAME, DOMAIN, LANGUAGES


class KlimadanConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            unit_id = user_input[CONF_UNIT_ID].strip()
            relay_id = user_input.get(CONF_RELAY_ID, "").strip()
            if not unit_id.isdigit():
                errors[CONF_UNIT_ID] = "invalid_unit_id"
            elif relay_id and not relay_id.isalnum():
                errors[CONF_RELAY_ID] = "invalid_relay_id"
            else:
                await self.async_set_unique_id(unit_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_UNIT_ID: unit_id,
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_LANGUAGE: user_input[CONF_LANGUAGE],
                        CONF_RELAY_ID: relay_id,
                    },
                )

        schema = vol.Schema({
            vol.Required(CONF_UNIT_ID): str,
            vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Required(CONF_LANGUAGE, default="DK"): vol.In(LANGUAGES),
            vol.Optional(CONF_RELAY_ID, default=""): str,
        })
        return self.async_show_form(
            step_id="user", data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )
