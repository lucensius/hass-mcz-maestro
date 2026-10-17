# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""Buttons: start/stop heating through the chrono, sync the stove clock."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANAGER
from .entity import MczManagerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the buttons."""
    manager = hass.data[DOMAIN][config_entry.entry_id][MANAGER]
    async_add_entities(
        [
            MczStartButton(manager, "Boost_Start"),
            MczStopButton(manager, "Boost_Stop"),
            MczClockButton(manager, "Clock_Sync"),
        ]
    )


class MczStartButton(MczManagerEntity, ButtonEntity):
    """Heat from now for the configured duration."""

    _attr_icon = "mdi:fire"

    async def async_press(self) -> None:
        """Start heating."""
        await self.manager.async_start_boost()


class MczStopButton(MczManagerEntity, ButtonEntity):
    """End the heating period started with the start button."""

    _attr_icon = "mdi:fire-off"

    async def async_press(self) -> None:
        """Stop heating."""
        await self.manager.async_stop_boost()


class MczClockButton(MczManagerEntity, ButtonEntity):
    """Set the stove clock to the Home Assistant time."""

    _attr_icon = "mdi:clock-check-outline"
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Sync the clock."""
        await self.manager.async_sync_clock(force=True)
