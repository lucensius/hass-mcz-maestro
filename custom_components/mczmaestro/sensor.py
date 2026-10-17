# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2022-2024 Matthieu Bourgain (Aohzan), originally Apache-2.0, modified by lucensius
# Copyright (C) 2026 lucensius
"""Support for the MCZ sensors."""

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CHRONO, CONTROLLER, COORDINATOR, DOMAIN, MANAGER
from .entity import MczEntity, MczManagerEntity
from .maestro import MaestroController, get_maestro_state_description
from .maestro.chrono import DAYS, describe_day, slots_to_ranges

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
        MczStateEntity(controller, coordinator, command_name="state"),
        MczSensorEntity(
            controller,
            coordinator,
            "Ambient_Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
    ]
    # Monday first in the UI; the protocol starts with Sunday.
    entities += [
        MczChronoDayEntity(controller, coordinator, DAYS.index(day))
        for day in DAYS[1:] + DAYS[:1]
    ]
    manager = data[MANAGER]
    entities += [
        MczBoostUntilSensor(manager, "Boost_Until"),
        MczSmartStatusSensor(manager, "Smart_Status"),
    ]

    if entities:
        async_add_entities(entities)


class MczStateEntity(MczEntity, SensorEntity):
    """Representation of a debug sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return the state."""
        _LOGGER.debug("State entity debug")
        _LOGGER.debug(self.coordinator.data)
        if "Stove_State" in self.coordinator.data:
            return get_maestro_state_description(
                int(self.coordinator.data["Stove_State"])
            )
        return "unknown"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        if self.coordinator.data:
            return {k: v for k, v in self.coordinator.data.items() if k != CHRONO}
        return {}


class MczSensorEntity(MczEntity, SensorEntity):
    """Representation of a MCZ sensor."""

    def __init__(
        self,
        controller: MaestroController,
        coordinator,
        command_name,
        device_class: SensorDeviceClass,
        unit_of_measurement: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(controller, coordinator, command_name)
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit_of_measurement

    @property
    def native_value(self) -> float:
        """Return the state."""
        return self.coordinator.data[self._command_name]


class MczChronoDayEntity(MczEntity, SensorEntity):
    """Weekly program of one day."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, controller: MaestroController, coordinator, day: int) -> None:
        """Initialize the sensor."""
        super().__init__(controller, coordinator, f"Chrono_{DAYS[day]}")
        self._day = day

    @property
    def native_value(self) -> str | None:
        """Return a short summary of the day."""
        chrono = self.coordinator.data.get(CHRONO)
        return describe_day(chrono.days[self._day])[:255] if chrono else None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the program as ranges."""
        chrono = self.coordinator.data.get(CHRONO)
        if not chrono:
            return {}
        return {
            "day": DAYS[self._day],
            "schedule": slots_to_ranges(chrono.days[self._day]),
            "temperatures": dict(zip(("T1", "T2", "T3"), chrono.temperatures)),
        }


class MczBoostUntilSensor(MczManagerEntity, SensorEntity):
    """End of the heating period started with the start button."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-play-outline"

    @property
    def native_value(self):
        """Return the end time, or nothing when no heating period runs."""
        if not self.manager.boost_active:
            return None
        return self.manager.boost_until.replace(tzinfo=dt_util.get_default_time_zone())


class MczSmartStatusSensor(MczManagerEntity, SensorEntity):
    """What the smart mode is doing."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["off", "no_sensor", "idle", "heating"]
    _attr_icon = "mdi:robot-outline"

    @property
    def native_value(self) -> str:
        """Return the status."""
        return self.manager.smart_state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return details."""
        return {
            "external_sensor": self.manager.external_sensor,
            "external_temperature": self.manager.external_temperature,
            "target": self.manager.settings["smart_target"],
            "hysteresis": self.manager.settings["smart_hysteresis"],
        }
