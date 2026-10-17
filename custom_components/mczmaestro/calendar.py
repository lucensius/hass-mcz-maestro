# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""The chrono program as a Home Assistant calendar.

- Weekly program  -> recurring events (FREQ=WEEKLY), editing them changes the program.
- Temporary changes (start button, smart mode, one-off entries) -> single events.
- Creating an event without repetition heats once; with weekly/daily repetition it
  becomes part of the weekly program.
- Deleting one occurrence of a recurring event switches that slot off once.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re

from homeassistant.components.calendar import (
    EVENT_END,
    EVENT_RRULE,
    EVENT_START,
    EVENT_SUMMARY,
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANAGER
from .entity import MczManagerEntity
from .maestro.chrono import SLOTS_PER_DAY
from .maestro.overlay import (
    OWNER_BOOST,
    OWNER_ONCE,
    OWNER_SMART,
    SLOT,
    OverlayTable,
    ceil_slot,
    day_slot,
    floor_slot,
)

BYDAY = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"]  # protocol day order
OWNER_LABELS = {OWNER_BOOST: "Start", OWNER_SMART: "Smart", OWNER_ONCE: "One-off"}
RECURRENCE_FORMAT = "%Y%m%dT%H%M%S"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar."""
    manager = hass.data[DOMAIN][config_entry.entry_id][MANAGER]
    async_add_entities([MczChronoCalendar(manager, "Chrono_Calendar")])


def _local(value: datetime | date) -> datetime:
    if not isinstance(value, datetime):
        raise HomeAssistantError("Chrono entries need a start and end time, not all-day")
    return dt_util.as_local(value).replace(tzinfo=None)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=dt_util.get_default_time_zone())


def _level_from_summary(summary: str | None, default: int) -> int:
    match = re.search(r"T([123])", summary or "", re.IGNORECASE)
    return int(match.group(1)) if match else default


class MczChronoCalendar(MczManagerEntity, CalendarEntity):
    """Chrono program calendar."""

    _attr_icon = "mdi:calendar-clock"
    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT
    )

    # ------------------------------------------------------------- reading

    def _summary(self, level: int, owners: list[str] | None) -> str:
        chrono = self.manager.chrono
        temp = f" ({chrono.temperatures[level - 1]} °C)" if chrono else ""
        label = f"Heat T{level}{temp}"
        if owners:
            names = [OWNER_LABELS[o] for o in owners if o in OWNER_LABELS]
            if names:
                label += " – " + ", ".join(names)
        return label

    def _events_for_date(self, day_date: date) -> list[CalendarEvent]:
        """Events of one concrete date: base program plus overlays of that date."""
        base = self.manager.base_days
        if base is None:
            return []
        day = (day_date.weekday() + 1) % 7
        midnight = datetime.combine(day_date, time())
        overlays = self.manager.overlays.slots

        # (level, owners or None for the weekly program) for every slot
        cells: list[tuple[int, tuple | None]] = []
        for slot in range(SLOTS_PER_DAY):
            when = midnight + slot * SLOT
            entry = overlays.get(when.strftime("%Y-%m-%dT%H:%M"))
            if entry:
                cells.append((OverlayTable.level(entry), tuple(sorted(entry["owners"]))))
            else:
                cells.append((base[day][slot], None))

        events = []
        slot = 0
        while slot < SLOTS_PER_DAY:
            level, owners = cells[slot]
            start = slot
            while slot < SLOTS_PER_DAY and cells[slot] == (level, owners):
                slot += 1
            if not level:
                continue
            begin, end = midnight + start * SLOT, midnight + slot * SLOT
            if owners is None:
                events.append(
                    CalendarEvent(
                        start=_aware(begin),
                        end=_aware(end),
                        summary=self._summary(level, None),
                        uid=f"chrono-{day}-{start}-{slot}",
                        rrule=f"FREQ=WEEKLY;BYDAY={BYDAY[day]}",
                        recurrence_id=begin.strftime(RECURRENCE_FORMAT),
                    )
                )
            else:
                events.append(
                    CalendarEvent(
                        start=_aware(begin),
                        end=_aware(end),
                        summary=self._summary(level, list(owners)),
                        uid=f"overlay-{begin.strftime(RECURRENCE_FORMAT)}-{end.strftime(RECURRENCE_FORMAT)}",
                    )
                )
        return events

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return events between start_date and end_date."""
        events = []
        current = dt_util.as_local(start_date).date() - timedelta(days=1)
        last = dt_util.as_local(end_date).date()
        while current <= last:
            for event in self._events_for_date(current):
                if event.end > start_date and event.start < end_date:
                    events.append(event)
            current += timedelta(days=1)
        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Current or next heating period."""
        now = dt_util.now()
        today = now.date()
        for offset in range(8):
            for event in self._events_for_date(today + timedelta(days=offset)):
                if event.end > now:
                    return event
        return None

    # ------------------------------------------------------------- editing

    async def async_create_event(self, **kwargs) -> None:
        """Create a weekly program entry (with repetition) or a one-off entry."""
        start = _local(kwargs[EVENT_START])
        end = _local(kwargs[EVENT_END])
        if floor_slot(start) != start or ceil_slot(end) != end:
            start, end = floor_slot(start), ceil_slot(end)  # chrono works in 30 minute steps
        if end <= start:
            raise HomeAssistantError("The end must be after the start")
        if end - start > timedelta(days=1) or (end.date() != start.date() and end.time() != time()):
            raise HomeAssistantError("A chrono entry must not span more than one day")
        level = _level_from_summary(kwargs.get(EVENT_SUMMARY), int(self.manager.settings["level"]))
        rrule = kwargs.get(EVENT_RRULE)

        if not rrule:
            await self.manager.async_add_once(start, end, level)
            return

        rules = dict(part.split("=", 1) for part in rrule.upper().split(";") if "=" in part)
        if rules.get("FREQ") == "DAILY":
            days = list(range(7))
        elif rules.get("FREQ") == "WEEKLY":
            byday = rules.get("BYDAY")
            days = (
                [BYDAY.index(d[-2:]) for d in byday.split(",")]
                if byday
                else [day_slot(start)[0]]
            )
        else:
            raise HomeAssistantError("Only daily or weekly repetition is supported by the chrono")

        first = day_slot(start)[1]
        last = SLOTS_PER_DAY if end.time() == time() else day_slot(end)[1]
        base = self.manager.base_days
        for day in days:
            slots = list(base[day])
            slots[first:last] = [level] * (last - first)
            await self.manager.async_set_base_day(day, slots)

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete a program entry, one occurrence of it, or a one-off entry."""
        kind, *parts = uid.split("-")
        if kind == "overlay":
            start = datetime.strptime(parts[0], RECURRENCE_FORMAT)
            end = datetime.strptime(parts[1], RECURRENCE_FORMAT)
            await self.manager.async_remove_overlays(start, end)
            return
        if kind != "chrono":
            raise HomeAssistantError(f"Unknown chrono entry: {uid}")

        day, first, last = (int(p) for p in parts)
        if recurrence_id and recurrence_range != "THISANDFUTURE":
            begin = datetime.strptime(recurrence_id, RECURRENCE_FORMAT)
            await self.manager.async_skip_once(begin, begin + (last - first) * SLOT)
            return
        slots = list(self.manager.base_days[day])
        slots[first:last] = [0] * (last - first)
        await self.manager.async_set_base_day(day, slots)
