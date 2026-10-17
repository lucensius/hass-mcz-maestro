# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2022-2024 Matthieu Bourgain (Aohzan), originally Apache-2.0, modified by lucensius
# Copyright (C) 2026 lucensius
"""Support for the MCZ climate."""

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROLLER, COORDINATOR, DOMAIN, MANAGER
from .entity import MczEntity
from .maestro import get_maestro_power_state

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

    entities = []

    entities.append(
        MczClimateEntity(controller, coordinator, "stove", data[MANAGER]),
    )
    if entities:
        async_add_entities(entities)


class MczClimateEntity(MczEntity, ClimateEntity):
    """Representation of a MCZ climate."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.AUTO, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 0.5

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return float(self.coordinator.data["Ambient_Temperature"])

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return float(self.coordinator.data["Temperature_Setpoint"])

    _attr_name = None  # main feature of the device: shown with the device name only

    def __init__(self, controller, coordinator, command_name, manager) -> None:
        """Initialize the climate entity."""
        super().__init__(controller, coordinator, command_name)
        self._attr_translation_key = None
        self.manager = manager

    async def async_added_to_hass(self) -> None:
        """Follow the chrono manager too."""
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported."""
        if not get_maestro_power_state(int(self.coordinator.data["Stove_State"])):
            return HVACAction.OFF
        if int(self.coordinator.data["Active_Mode"]) == 1:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def hvac_mode(self) -> HVACMode:
        """Heat = start button period running, auto = chrono program, off otherwise."""
        if self.manager.boost_active:
            return HVACMode.HEAT
        if int(self.coordinator.data["Chronostat"]) == 1:
            return HVACMode.AUTO
        if get_maestro_power_state(int(self.coordinator.data["Stove_State"])):
            return HVACMode.HEAT
        return HVACMode.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.async_write_parameter(42, int(float(kwargs[ATTR_TEMPERATURE]) * 2))
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Map the modes onto the chrono, which is never switched off here."""
        if hvac_mode == HVACMode.HEAT:
            await self.manager.async_start_boost()
        elif hvac_mode == HVACMode.AUTO:
            if self.manager.boost_active:
                await self.manager.async_stop_boost()
            await self.async_write_parameter(1111, 1)
        elif hvac_mode == HVACMode.OFF:
            await self.manager.async_stop_boost()
            await self.manager.async_set_setting("smart_enabled", False)
            await self.async_write_parameter(34, 40)
        await self.coordinator.async_request_refresh()
