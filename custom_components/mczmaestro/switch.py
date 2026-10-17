# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2022-2024 Matthieu Bourgain (Aohzan), originally Apache-2.0, modified by lucensius
# Copyright (C) 2026 lucensius
"""Support for the MCZ switches."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONTROLLER, COORDINATOR, DOMAIN, MANAGER
from .entity import MczEntity, MczManagerEntity
from .maestro import MaestroController

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MCZ platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    controller = data[CONTROLLER]
    coordinator = data[COORDINATOR]

    entities = [
        MczSwitchEntity(controller, coordinator, "Eco_Mode", 41),
        MczSwitchEntity(controller, coordinator, "Silent_Mode", 45),
        MczSwitchEntity(controller, coordinator, "Active_Mode", 35),
        MczSwitchEntity(controller, coordinator, "Control_Mode", 40),
    ]
    manager = data[MANAGER]
    entities += [
        MczChronoSwitch(controller, coordinator, "Chronostat", 1111, manager),
        MczSmartSwitch(manager, "Smart_Mode"),
    ]
    if entities:
        async_add_entities(entities)


class MczSwitchEntity(MczEntity, SwitchEntity):
    """Representation of a MCZ switch."""

    def __init__(
        self,
        controller: MaestroController,
        coordinator: DataUpdateCoordinator,
        command_name: str,
        command_id: int,
    ) -> None:
        """Initialize the switch."""
        super().__init__(controller, coordinator, command_name)
        self._command_id: int = command_id

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return int(self.coordinator.data[self._command_name]) == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.async_write_parameter(self._command_id, 1)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.async_write_parameter(self._command_id, 0)
        await self.coordinator.async_request_refresh()


class MczChronoSwitch(MczSwitchEntity):
    """Chrono mode. While on, the integration switches it back on if it gets turned off elsewhere."""

    def __init__(self, controller, coordinator, command_name, command_id, manager) -> None:
        """Initialize the switch."""
        super().__init__(controller, coordinator, command_name, command_id)
        self.manager = manager

    @property
    def extra_state_attributes(self) -> dict:
        """Show whether the chrono is kept on."""
        return {"keep_on": self.manager.settings["keep_chrono"]}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the chrono on and keep it on."""
        await self.manager.async_set_setting("keep_chrono", True)
        await super().async_turn_on(**kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the chrono off on purpose."""
        await self.manager.async_set_setting("keep_chrono", False)
        await super().async_turn_off(**kwargs)


class MczSmartSwitch(MczManagerEntity, SwitchEntity):
    """Smart mode: heat via the chrono until the external thermometer reaches the target."""

    _attr_icon = "mdi:home-thermometer-outline"

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return bool(self.manager.settings["smart_enabled"])

    @property
    def extra_state_attributes(self) -> dict:
        """Show what the smart mode is doing."""
        return {
            "status": self.manager.smart_state,
            "external_sensor": self.manager.external_sensor,
            "external_temperature": self.manager.external_temperature,
            "target": self.manager.settings["smart_target"],
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable smart mode."""
        await self.manager.async_set_setting("smart_enabled", True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable smart mode."""
        await self.manager.async_set_setting("smart_enabled", False)
