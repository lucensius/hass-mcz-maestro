# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2022-2024 Matthieu Bourgain (Aohzan), originally Apache-2.0, modified by lucensius
# Copyright (C) 2026 lucensius
"""Support for MCZ numbers."""
import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CHRONO, CONTROLLER, COORDINATOR, DOMAIN, MANAGER
from .entity import MczEntity, MczManagerEntity
from .maestro import MaestroController
from .maestro.chrono import TEMPERATURE_MAX, TEMPERATURE_MIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MCZ numbers."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    controller = data[CONTROLLER]
    coordinator = data[COORDINATOR]
    entities = [
        MczChronoTemperatureEntity(
            controller, coordinator, f"Chronostat_T{index + 1}", index
        )
        for index in range(3)
    ]
    manager = data[MANAGER]
    entities += [
        MczSettingNumber(manager, "boost_hours", 0.5, 12, 0.5,
                         UnitOfTime.HOURS, "mdi:timer-outline", None),
        MczSettingNumber(manager, "smart_target", 5, 30, 0.5,
                         UnitOfTemperature.CELSIUS, "mdi:home-thermometer", NumberDeviceClass.TEMPERATURE),
        MczSettingNumber(manager, "smart_hysteresis", 0.1, 3, 0.1,
                         UnitOfTemperature.CELSIUS, "mdi:thermometer-chevron-down", None, EntityCategory.CONFIG),
        MczSettingNumber(manager, "smart_min_runtime", 30, 240, 30,
                         UnitOfTime.MINUTES, "mdi:timer-sand", None, EntityCategory.CONFIG),
    ]
    async_add_entities(entities, True)


class MczChronoTemperatureEntity(MczEntity, NumberEntity):
    """Chronothermostat temperature T1, T2 or T3."""

    _attr_native_max_value = TEMPERATURE_MAX
    _attr_native_min_value = TEMPERATURE_MIN
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        controller: MaestroController,
        coordinator: DataUpdateCoordinator,
        command_name: str,
        index: int,
    ) -> None:
        """Initialize the number."""
        super().__init__(controller, coordinator, command_name)
        self._index = index

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        chrono = self.coordinator.data.get(CHRONO)
        return chrono.temperatures[self._index] if chrono else None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value, keeping T1 < T2 < T3 as the stove requires."""
        chrono = self.coordinator.data.get(CHRONO)
        if chrono:
            temps = list(chrono.temperatures)
            temps[self._index] = int(value)
            if not temps[0] < temps[1] < temps[2]:
                raise HomeAssistantError(
                    f"Chrono temperatures must satisfy T1 < T2 < T3, got {temps}"
                )
        await self.hass.async_add_executor_job(
            self.controller.write_chrono_temperature, self._index, int(value)
        )
        await self.coordinator.async_request_refresh()


class MczSettingNumber(MczManagerEntity, NumberEntity):
    """A setting of the chrono manager (stored in Home Assistant)."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        manager,
        key: str,
        minimum: float,
        maximum: float,
        step: float,
        unit: str,
        icon: str,
        device_class: NumberDeviceClass | None,
        category: EntityCategory | None = None,
    ) -> None:
        """Initialize the number."""
        super().__init__(manager, f"Setting_{key}")
        self._key = key
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_entity_category = category
        if key == "boost_hours":
            self._attr_mode = NumberMode.SLIDER

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.manager.settings[self._key]

    async def async_set_native_value(self, value: float) -> None:
        """Store the new value."""
        await self.manager.async_set_setting(self._key, value)
