# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2022-2024 Matthieu Bourgain (Aohzan), originally Apache-2.0, modified by lucensius
# Copyright (C) 2026 lucensius
"""Config flow to configure the MCZ Maestro integration."""

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_EXTERNAL_SENSOR, DOMAIN
from .maestro import MaestroController

BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="192.168.120.1"): str,
        vol.Required(CONF_PORT, default=81): int,
        vol.Required(CONF_SCAN_INTERVAL, default=30): int,
    }
)


@config_entries.HANDLERS.register(DOMAIN)
class MczConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a mczmaestro config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Options: external thermometer for the smart mode."""
        return MczOptionsFlow()

    def __init__(self) -> None:
        """Initialize class variables."""
        self.base_input: dict[str, Any] = {}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=BASE_SCHEMA, errors=errors
            )

        entry = await self.async_set_unique_id(
            "_".join([DOMAIN, user_input[CONF_HOST], str(user_input[CONF_PORT])])
        )

        if entry:
            self._abort_if_unique_id_configured()

        controller = MaestroController(user_input[CONF_HOST], user_input[CONF_PORT])

        if not controller.connected:
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user", data_schema=BASE_SCHEMA, errors=errors
            )

        self.base_input = user_input
        return self.async_create_entry(
            title=f"MCZ Maestro {controller.host}:{controller.port}",
            data=user_input,
        )


class MczOptionsFlow(config_entries.OptionsFlow):
    """Choose the external thermometer used by the smart mode."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(CONF_EXTERNAL_SENSOR)
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_EXTERNAL_SENSOR,
                    description={"suggested_value": current} if current else None,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
