# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2022-2024 Matthieu Bourgain (Aohzan), originally Apache-2.0, modified by lucensius
# Copyright (C) 2026 lucensius
"""Entity related."""

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import slugify

from .const import DOMAIN
from .maestro import MaestroController


class MczEntity(CoordinatorEntity):
    """Representation of a generic MCZ entity.

    Names come from the translations (key = slugified command name) and are
    shown after the device name, which the user can choose freely.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        controller: MaestroController,
        coordinator: DataUpdateCoordinator,
        command_name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.controller = controller
        self._command_name = command_name

        self._attr_translation_key = slugify(command_name)
        self._attr_unique_id = slugify(
            f"{DOMAIN}_{controller.host}_{controller.port}_{command_name}"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, controller.host + controller.port)},
        }

        self._state = None

    async def async_write_parameter(self, param: int, value: int | float) -> None:
        """Write a stove parameter without blocking the event loop."""
        await self.hass.async_add_executor_job(
            self.controller.write_parameter, param, value
        )


class MczManagerEntity(MczEntity):
    """Entity that also follows the chrono manager state."""

    def __init__(self, manager, command_name: str) -> None:
        """Initialize the entity."""
        super().__init__(manager.controller, manager.coordinator, command_name)
        self.manager = manager

    async def async_added_to_hass(self) -> None:
        """Register for manager updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))
