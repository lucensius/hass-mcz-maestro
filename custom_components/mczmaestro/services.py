# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""Services for the MCZ Maestro chronothermostat."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    MANAGER,
    SERVICE_COPY_CHRONO_DAY,
    SERVICE_SET_CHRONO_DAY,
    SERVICE_START_HEATING,
    SERVICE_STOP_HEATING,
)
from .maestro.chrono import DAYS, LEVELS, ranges_to_slots

_LOGGER = logging.getLogger(__name__)

DAY_GROUPS = {
    "weekdays": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    "weekend": ["saturday", "sunday"],
    "all": DAYS,
}
DAY_CHOICES = DAYS + list(DAY_GROUPS)

RANGE_SCHEMA = vol.Schema(
    {
        vol.Required("start"): cv.string,
        vol.Required("end"): cv.string,
        vol.Required("temperature"): vol.In(LEVELS[1:]),
    }
)

SET_CHRONO_DAY_SCHEMA = vol.Schema(
    {
        vol.Required("day"): vol.All(cv.ensure_list, [vol.In(DAY_CHOICES)]),
        vol.Optional("schedule", default=[]): vol.All(cv.ensure_list, [RANGE_SCHEMA]),
        vol.Optional("config_entry_id"): cv.string,
    }
)

COPY_CHRONO_DAY_SCHEMA = vol.Schema(
    {
        vol.Required("source"): vol.In(DAYS),
        vol.Required("target"): vol.All(cv.ensure_list, [vol.In(DAY_CHOICES)]),
        vol.Optional("config_entry_id"): cv.string,
    }
)


START_HEATING_SCHEMA = vol.Schema(
    {
        vol.Optional("hours"): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=24)),
        vol.Optional("temperature"): vol.In(LEVELS[1:]),
        vol.Optional("config_entry_id"): cv.string,
    }
)

STOP_HEATING_SCHEMA = vol.Schema({vol.Optional("config_entry_id"): cv.string})


def _expand_days(days: list[str]) -> list[int]:
    """Turn day names and groups into protocol day indexes."""
    result: list[int] = []
    for day in days:
        for name in DAY_GROUPS.get(day, [day]):
            index = DAYS.index(name)
            if index not in result:
                result.append(index)
    return result


def _entries(hass: HomeAssistant, call: ServiceCall) -> list[dict]:
    """Return the integration data of the targeted config entries."""
    data = hass.data.get(DOMAIN, {})
    if entry_id := call.data.get("config_entry_id"):
        if entry_id not in data:
            raise ServiceValidationError(f"Unknown MCZ Maestro config entry: {entry_id}")
        return [data[entry_id]]
    return list(data.values())


async def _write_days(entry: dict, days: dict[int, list[int]]) -> None:
    """Write the weekly program of some days (temporary changes are kept)."""
    for day, slots in days.items():
        await entry[MANAGER].async_set_base_day(day, slots)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the chrono services once."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_CHRONO_DAY):
        return

    async def set_chrono_day(call: ServiceCall) -> None:
        try:
            slots = ranges_to_slots(call.data["schedule"])
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        days = _expand_days(call.data["day"])
        for entry in _entries(hass, call):
            await _write_days(entry, {day: slots for day in days})

    async def copy_chrono_day(call: ServiceCall) -> None:
        source = DAYS.index(call.data["source"])
        for entry in _entries(hass, call):
            base = entry[MANAGER].base_days
            if base is None:
                raise HomeAssistantError("Chrono program not loaded yet")
            slots = base[source]
            targets = [d for d in _expand_days(call.data["target"]) if d != source]
            await _write_days(entry, {day: slots for day in targets})

    async def start_heating(call: ServiceCall) -> None:
        level = call.data.get("temperature")
        for entry in _entries(hass, call):
            await entry[MANAGER].async_start_boost(
                call.data.get("hours"), LEVELS.index(level) if level else None
            )

    async def stop_heating(call: ServiceCall) -> None:
        for entry in _entries(hass, call):
            await entry[MANAGER].async_stop_boost()

    hass.services.async_register(
        DOMAIN, SERVICE_START_HEATING, start_heating, schema=START_HEATING_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_HEATING, stop_heating, schema=STOP_HEATING_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_CHRONO_DAY, set_chrono_day, schema=SET_CHRONO_DAY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_COPY_CHRONO_DAY, copy_chrono_day, schema=COPY_CHRONO_DAY_SCHEMA
    )
