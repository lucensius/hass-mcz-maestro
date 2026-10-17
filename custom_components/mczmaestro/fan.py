# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""Stove fans: automatic mode (default), manual levels, off where allowed."""
from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import CONTROLLER, COORDINATOR, DOMAIN, PARAMETERS
from .entity import MczEntity
from .maestro.parameters import FanConfig, fitted_fans

PRESET_AUTO = "auto"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one fan entity per fan the stove is fitted with."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    fans = fitted_fans(data[PARAMETERS])
    async_add_entities(
        MczFanEntity(data[CONTROLLER], data[COORDINATOR], fan, fans) for fan in fans
    )


class MczFanEntity(MczEntity, FanEntity):
    """A stove fan."""

    def __init__(self, controller, coordinator, fan: FanConfig, all_fans: list[FanConfig]) -> None:
        """Initialize the fan."""
        super().__init__(controller, coordinator, fan.key)
        self._fan = fan
        self._all_fans = all_fans
        self._attr_speed_count = fan.maximum - fan.minimum + 1
        features = FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON
        if fan.auto_allowed:
            features |= FanEntityFeature.PRESET_MODE
            self._attr_preset_modes = [PRESET_AUTO]
        if fan.off_allowed and len(all_fans) > 1:
            # the app never switches off the last running fan
            features |= FanEntityFeature.TURN_OFF
        self._attr_supported_features = features

    def _level(self, fan: FanConfig | None = None) -> int | None:
        fan = fan or self._fan
        try:
            return int(self.coordinator.data[fan.info_field])
        except (KeyError, TypeError, ValueError):
            return None

    @property
    def available(self) -> bool:
        """Unavailable when the stove disabled the fan."""
        return super().available and self._fan.enabled and self._level() is not None

    @property
    def is_on(self) -> bool | None:
        """Whether the fan runs (manual level or automatic)."""
        level = self._level()
        return None if level is None else level != 0

    @property
    def preset_mode(self) -> str | None:
        """Automatic mode."""
        return PRESET_AUTO if self._level() == self._fan.auto_value else None

    @property
    def percentage(self) -> int | None:
        """Manual level as percentage; None in automatic mode."""
        level = self._level()
        if level is None or level == self._fan.auto_value:
            return None
        if level == 0:
            return 0
        return ranged_value_to_percentage((self._fan.minimum, self._fan.maximum), level)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Raw level for automations: 0 off, 1-5 manual, 6 automatic."""
        return {"level": self._level(), "silent_mode": self._silent_mode}

    @property
    def _silent_mode(self) -> bool:
        return str(self.coordinator.data.get("Silent_Mode")) == "1"

    async def _async_set_level(self, level: int) -> None:
        if self._silent_mode:
            raise HomeAssistantError("The stove controls the fans while silent mode is on")
        await self.async_write_parameter(self._fan.param, level)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Switch to automatic mode."""
        if preset_mode != PRESET_AUTO or not self._fan.auto_allowed:
            raise HomeAssistantError(f"Unsupported fan mode: {preset_mode}")
        await self._async_set_level(self._fan.auto_value)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set a manual level."""
        if percentage == 0:
            await self.async_turn_off()
            return
        level = math.ceil(
            percentage_to_ranged_value((self._fan.minimum, self._fan.maximum), percentage)
        )
        await self._async_set_level(level)

    async def async_turn_on(
        self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any
    ) -> None:
        """Turn on; automatic mode unless a level is given."""
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        elif percentage:
            await self.async_set_percentage(percentage)
        elif self._fan.auto_allowed:
            await self._async_set_level(self._fan.auto_value)
        else:
            await self._async_set_level(self._fan.maximum)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off ("no air"), only if another fan keeps running, as the app requires."""
        if not self._fan.off_allowed:
            raise HomeAssistantError("This fan cannot be switched off")
        others_running = any(
            (self._level(fan) or 0) > 0 for fan in self._all_fans if fan is not self._fan
        )
        if not others_running:
            raise HomeAssistantError("At least one fan must keep running")
        await self._async_set_level(0)
