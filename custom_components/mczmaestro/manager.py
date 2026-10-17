# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""Chrono based control: start/stop, smart mode, chrono watchdog, clock sync.

Everything is done through the stove's weekly chrono table, the chrono mode
itself is never switched off by this integration.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CHRONO, CONF_EXTERNAL_SENSOR, DOMAIN
from .maestro import CONNECTION_ERRORS, MaestroController
from .maestro.chrono import DAYS, ChronoProgram, describe_day
from .maestro.overlay import (
    OWNER_BOOST,
    OWNER_ONCE,
    OWNER_SKIP,
    OWNER_SMART,
    SLOT,
    OverlayTable,
    ceil_slot,
    floor_slot,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

DEFAULT_SETTINGS: dict[str, Any] = {
    "boost_hours": 2.0,
    "level": 3,
    "smart_enabled": False,
    "smart_target": 21.0,
    "smart_hysteresis": 0.5,
    "smart_min_runtime": 60,
    "keep_chrono": True,
}

SMART_LOOKAHEAD = timedelta(minutes=60)
SMART_EXTEND_BEFORE = timedelta(minutes=30)
CHRONO_FIX_INTERVAL = timedelta(minutes=2)
CLOCK_MAX_DRIFT = timedelta(minutes=2)
CLOCK_SYNC_INTERVAL = timedelta(hours=1)

SMART_OFF = "off"
SMART_NO_SENSOR = "no_sensor"
SMART_IDLE = "idle"
SMART_HEATING = "heating"


def now_local() -> datetime:
    """Current local time without tzinfo, like the stove clock."""
    return dt_util.now().replace(tzinfo=None, second=0, microsecond=0)


class ChronoManager:
    """Owns all writes to the chrono table."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        controller: MaestroController,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.controller = controller
        self.coordinator = coordinator
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.settings: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.overlays = OverlayTable()
        self.boost_until: datetime | None = None
        self.smart_started: datetime | None = None
        self.external_sensor: str | None = entry.options.get(CONF_EXTERNAL_SENSOR)
        self._lock = asyncio.Lock()
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[Callable[[], None]] = []
        self._update_task: asyncio.Task | None = None
        self._last_chrono_fix: datetime | None = None
        self._last_clock_sync: datetime | None = None

    # ----------------------------------------------------------------- setup

    async def async_setup(self) -> None:
        """Load stored state and start listening."""
        if stored := await self._store.async_load():
            self.settings.update(stored.get("settings", {}))
            self.overlays = OverlayTable(stored.get("overlays"))
            if boost := stored.get("boost_until"):
                self.boost_until = datetime.fromisoformat(boost)
            if started := stored.get("smart_started"):
                self.smart_started = datetime.fromisoformat(started)
        self._unsubs.append(self.coordinator.async_add_listener(self._schedule_update))
        if self.external_sensor:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, [self.external_sensor], self._handle_sensor_event
                )
            )

    async def async_unload(self) -> None:
        """Stop listening and save."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._update_task:
            self._update_task.cancel()
        await self._store.async_save(self._data_to_store())

    def _data_to_store(self) -> dict:
        return {
            "settings": self.settings,
            "overlays": self.overlays.as_dict(),
            "boost_until": self.boost_until.isoformat() if self.boost_until else None,
            "smart_started": self.smart_started.isoformat() if self.smart_started else None,
        }

    def _save(self) -> None:
        self._store.async_delay_save(self._data_to_store, 2)

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        """Register an entity callback for state changes of the manager."""
        self._listeners.append(update)
        return lambda: self._listeners.remove(update)

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()

    # -------------------------------------------------------------- settings

    async def async_set_setting(self, key: str, value: Any) -> None:
        """Change a setting and react to it."""
        self.settings[key] = value
        self._save()
        self._notify()
        if key.startswith("smart_"):
            await self.async_evaluate_smart()

    # ----------------------------------------------------------------- state

    @property
    def chrono(self) -> ChronoProgram | None:
        """Program as last read from the stove (with overlays applied)."""
        return (self.coordinator.data or {}).get(CHRONO)

    @property
    def base_days(self) -> list[list[int]] | None:
        """Weekly program without temporary changes."""
        return self.overlays.base_days(self.chrono.days) if self.chrono else None

    @property
    def boost_active(self) -> bool:
        """Whether a start/stop heating period is running."""
        return self.boost_until is not None and self.boost_until > now_local()

    @property
    def smart_state(self) -> str:
        """State of the smart mode."""
        if not self.settings["smart_enabled"]:
            return SMART_OFF
        if self.external_temperature is None:
            return SMART_NO_SENSOR
        return SMART_HEATING if self.overlays.has_owner(OWNER_SMART) else SMART_IDLE

    @property
    def external_temperature(self) -> float | None:
        """Temperature of the external thermometer."""
        if not self.external_sensor:
            return None
        state = self.hass.states.get(self.external_sensor)
        try:
            return float(state.state) if state else None
        except ValueError:
            return None

    # ---------------------------------------------------------------- writes

    async def _async_run(
        self, mutate: Callable[[ChronoProgram], dict[tuple[int, int], int]]
    ) -> None:
        """Read the table, let mutate change the overlays, write what changed."""
        async with self._lock:
            try:
                fresh = await self.hass.async_add_executor_job(self.controller.read_chrono)
                days = [list(day) for day in fresh.days]
                for (day, slot), level in mutate(fresh).items():
                    days[day][slot] = level
                days = self.overlays.apply(days)
                for day in range(7):
                    if days[day] != fresh.days[day]:
                        _LOGGER.info(
                            "Chrono %s: %s -> %s",
                            DAYS[day],
                            describe_day(fresh.days[day]),
                            describe_day(days[day]),
                        )
                        await self.hass.async_add_executor_job(
                            self.controller.write_chrono_day, day, days[day]
                        )
            except (*CONNECTION_ERRORS, ValueError) as err:
                raise HomeAssistantError(f"Could not write chrono program: {err}") from err
            finally:
                self._save()
        await self.coordinator.async_request_refresh()
        self._notify()

    async def _async_ensure_chrono(self) -> None:
        """Switch the chrono on if it is off and should be kept on."""
        data = self.coordinator.data or {}
        if not self.settings["keep_chrono"] or str(data.get("Chronostat")) != "0":
            return
        now = now_local()
        if self._last_chrono_fix and now - self._last_chrono_fix < CHRONO_FIX_INTERVAL:
            return
        self._last_chrono_fix = now
        _LOGGER.info("Chrono mode was switched off, switching it on again")
        await self.hass.async_add_executor_job(self.controller.write_parameter, 1111, 1)

    async def async_start_boost(self, hours: float | None = None, level: int | None = None) -> None:
        """Heat from now for the given number of hours."""
        hours = hours if hours is not None else self.settings["boost_hours"]
        level = level if level is not None else self.settings["level"]
        now = now_local()
        end = ceil_slot(now + timedelta(hours=hours))

        def mutate(fresh: ChronoProgram) -> dict:
            restore = self.overlays.remove(OWNER_BOOST)
            days = [list(day) for day in fresh.days]
            for (day, slot), orig in restore.items():
                days[day][slot] = orig
            self.overlays.add(OWNER_BOOST, now, end, level, days, now)
            return restore

        self.boost_until = end
        await self._async_run(mutate)
        await self._async_ensure_chrono()

    async def async_stop_boost(self) -> None:
        """End the start/stop heating period now."""
        self.boost_until = None
        await self._async_run(lambda fresh: self.overlays.remove(OWNER_BOOST))

    async def async_set_base_day(self, day: int, slots: list[int]) -> None:
        """Replace the weekly program of one day, keeping temporary changes."""

        def mutate(fresh: ChronoProgram) -> dict:
            self.overlays.set_base(day, slots)
            return {(day, slot): level for slot, level in enumerate(slots)}

        await self._async_run(mutate)

    async def async_add_once(self, start: datetime, end: datetime, level: int) -> None:
        """Heat once in [start, end) without changing the weekly program."""
        now = now_local()
        if end <= now or start >= floor_slot(now) + timedelta(days=7):
            raise HomeAssistantError("One-off entries must lie within the next 7 days")

        def mutate(fresh: ChronoProgram) -> dict:
            self.overlays.add(OWNER_ONCE, start, end, level, fresh.days, now)
            return {}

        await self._async_run(mutate)

    async def async_skip_once(self, start: datetime, end: datetime) -> None:
        """Switch the weekly program off once in [start, end)."""
        now = now_local()

        def mutate(fresh: ChronoProgram) -> dict:
            self.overlays.add(OWNER_SKIP, start, end, 0, fresh.days, now)
            return {}

        await self._async_run(mutate)

    async def async_remove_overlays(self, start: datetime, end: datetime) -> None:
        """Remove all temporary changes in [start, end)."""
        await self._async_run(lambda fresh: self.overlays.remove(None, start, end))

    async def async_sync_clock(self, force: bool = False) -> None:
        """Set the stove clock if it drifted (or always with force)."""
        now = now_local()
        if not force:
            data = self.coordinator.data or {}
            try:
                stove = datetime(
                    int(data["Date_Year"]),
                    int(data["Date_Month"]),
                    int(data["Date_Day_Of_Month"]),
                    int(data["Date_Time_Hours"]),
                    int(data["Date_Time_Minutes"]),
                )
            except (KeyError, ValueError):
                return
            if abs(stove - now) <= CLOCK_MAX_DRIFT:
                return
            if self._last_clock_sync and now - self._last_clock_sync < CLOCK_SYNC_INTERVAL:
                return
            _LOGGER.info("Stove clock is %s, setting it to %s", stove, now)
        self._last_clock_sync = now
        await self.hass.async_add_executor_job(self.controller.set_clock, dt_util.now())

    # ------------------------------------------------------------ smart mode

    async def async_evaluate_smart(self) -> None:
        """Start or stop heating depending on the external thermometer."""
        now = now_local()
        heating = self.overlays.has_owner(OWNER_SMART)
        temperature = self.external_temperature

        if not self.settings["smart_enabled"]:
            if heating:
                self.smart_started = None
                await self._async_run(lambda fresh: self.overlays.remove(OWNER_SMART))
            return
        if temperature is None:
            return  # keep the current state until the sensor is back

        target = float(self.settings["smart_target"])
        hysteresis = float(self.settings["smart_hysteresis"])
        min_runtime = timedelta(minutes=int(self.settings["smart_min_runtime"]))

        if heating:
            ran_long_enough = self.smart_started is None or now - self.smart_started >= min_runtime
            if temperature >= target and ran_long_enough:
                _LOGGER.info("Smart mode: %.1f °C reached target %.1f °C, stopping", temperature, target)
                self.smart_started = None
                await self._async_run(lambda fresh: self.overlays.remove(OWNER_SMART))
                return
        elif temperature <= target - hysteresis:
            _LOGGER.info("Smart mode: %.1f °C below target %.1f °C, starting", temperature, target)
            self.smart_started = now
        else:
            return

        end = self.overlays.owner_end(OWNER_SMART)
        if end is None or end - now < SMART_EXTEND_BEFORE:
            level = self.settings["level"]
            until = ceil_slot(now + SMART_LOOKAHEAD)

            def mutate(fresh: ChronoProgram) -> dict:
                self.overlays.add(OWNER_SMART, now, until, level, fresh.days, now)
                return {}

            await self._async_run(mutate)
            await self._async_ensure_chrono()

    # -------------------------------------------------------- periodic tasks

    @callback
    def _schedule_update(self) -> None:
        if self._update_task is None or self._update_task.done():
            self._update_task = self.hass.async_create_task(self._async_periodic())

    @callback
    def _handle_sensor_event(self, event: Event) -> None:
        self._notify()
        self._schedule_update()

    async def _async_periodic(self) -> None:
        """Housekeeping after every poll."""
        try:
            now = now_local()
            if self.boost_until and self.boost_until <= now:
                self.boost_until = None
                self._save()
            if any(
                datetime.fromisoformat(key) + SLOT <= now for key in self.overlays.slots
            ):
                await self._async_run(lambda fresh: self.overlays.expire(now))
            await self._async_ensure_chrono()
            await self.async_sync_clock()
            await self.async_evaluate_smart()
        except (HomeAssistantError, ValueError, *CONNECTION_ERRORS) as err:
            _LOGGER.warning("MCZ chrono housekeeping failed: %s", err)
        self._notify()
