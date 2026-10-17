# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""Select the chrono level used by start/stop and smart mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANAGER
from .entity import MczManagerEntity

LEVEL_OPTIONS = ["T1", "T2", "T3"]
STRATEGY_OPTIONS = ["chrono", "extend"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select."""
    manager = hass.data[DOMAIN][config_entry.entry_id][MANAGER]
    async_add_entities(
        [
            MczLevelSelect(manager, "Heating_Level"),
            MczStrategySelect(manager, "Smart_Strategy"),
        ]
    )


class MczLevelSelect(MczManagerEntity, SelectEntity):
    """Chrono temperature (T1..T3) for start/stop and smart mode."""

    _attr_icon = "mdi:thermometer-lines"
    _attr_options = LEVEL_OPTIONS

    @property
    def current_option(self) -> str:
        """Return the selected level."""
        return LEVEL_OPTIONS[int(self.manager.settings["level"]) - 1]

    @property
    def extra_state_attributes(self) -> dict:
        """Show what the levels mean."""
        chrono = self.manager.chrono
        if not chrono:
            return {}
        return {f"T{i + 1}": f"{t} °C" for i, t in enumerate(chrono.temperatures)}

    async def async_select_option(self, option: str) -> None:
        """Change the level."""
        await self.manager.async_set_setting("level", LEVEL_OPTIONS.index(option) + 1)


class MczStrategySelect(MczManagerEntity, SelectEntity):
    """How the smart mode works: only within chrono periods, or additionally."""

    _attr_icon = "mdi:strategy"
    _attr_options = STRATEGY_OPTIONS

    @property
    def current_option(self) -> str:
        """Return the selected strategy."""
        return self.manager.settings["smart_strategy"]

    async def async_select_option(self, option: str) -> None:
        """Change the strategy."""
        await self.manager.async_set_setting("smart_strategy", option)
