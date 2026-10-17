# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""Temporary changes on top of the weekly chrono program.

The stove only knows one weekly table. Start/stop, smart mode and one-off
calendar entries write into that table and have to be undone afterwards,
otherwise they would repeat a week later. An overlay remembers, per concrete
30 minute slot (local date and time), the original level and which owners
(boost, smart, once, skip) changed it.

All datetimes are naive local times, the same clock the stove runs on.
"""
from __future__ import annotations

from datetime import datetime, timedelta

SLOT = timedelta(minutes=30)
WEEK = timedelta(days=7)

OWNER_BOOST = "boost"
OWNER_SMART = "smart"
OWNER_ONCE = "once"
OWNER_SKIP = "skip"  # level 0: switch a slot of the base program off once
OWNER_SMART_OFF = "smart_off"  # level 0: smart mode reached the target, overrides everything


def floor_slot(value: datetime) -> datetime:
    """Start of the slot containing value."""
    return value.replace(minute=value.minute - value.minute % 30, second=0, microsecond=0)


def ceil_slot(value: datetime) -> datetime:
    """Next slot boundary at or after value."""
    start = floor_slot(value)
    return start if start == value else start + SLOT


def day_slot(value: datetime) -> tuple[int, int]:
    """Protocol day (0 = Sunday) and slot index of a slot start."""
    return (value.weekday() + 1) % 7, (value.hour * 60 + value.minute) // 30


def _key(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M")


class OverlayTable:
    """Slots changed temporarily, keyed by their local start time."""

    def __init__(self, data: dict | None = None) -> None:
        """Initialize from stored data."""
        self.slots: dict[str, dict] = data or {}

    def as_dict(self) -> dict:
        """Data to store."""
        return self.slots

    def _items(self):
        for key, entry in self.slots.items():
            yield datetime.fromisoformat(key), entry

    def add(
        self,
        owner: str,
        start: datetime,
        end: datetime,
        level: int,
        days: list[list[int]],
        now: datetime,
    ) -> None:
        """Set [start, end) to level for owner. Limited to the coming week."""
        limit = floor_slot(now) + WEEK
        current = max(floor_slot(start), floor_slot(now))
        while current < end and current < limit:
            entry = self.slots.get(_key(current))
            if entry is None:
                day, slot = day_slot(current)
                entry = self.slots[_key(current)] = {"orig": days[day][slot], "owners": {}}
            entry["owners"][owner] = level
            current += SLOT

    def remove(
        self,
        owner: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[tuple[int, int], int]:
        """Remove an owner (or all owners) in a range; return slots to restore."""
        restore = {}
        for when, entry in list(self._items()):
            if start is not None and when < floor_slot(start):
                continue
            if end is not None and when >= end:
                continue
            if owner is None:
                entry["owners"].clear()
            else:
                entry["owners"].pop(owner, None)
            if not entry["owners"]:
                restore[day_slot(when)] = entry["orig"]
                del self.slots[_key(when)]
        return restore

    def expire(self, now: datetime) -> dict[tuple[int, int], int]:
        """Remove slots that are over; return slots to restore."""
        restore = {}
        for when, entry in list(self._items()):
            if when + SLOT <= now:
                restore[day_slot(when)] = entry["orig"]
                del self.slots[_key(when)]
        return restore

    def set_base(self, day: int, slots: list[int]) -> None:
        """The base program of a day changed: update the remembered originals."""
        for when, entry in self._items():
            entry_day, slot = day_slot(when)
            if entry_day == day:
                entry["orig"] = slots[slot]

    @staticmethod
    def level(entry: dict, exclude: str | None = None) -> int:
        """Level a slot gets with its overlays (except exclude) applied."""
        owners = {o: lvl for o, lvl in entry["owners"].items() if o != exclude}
        if not owners:
            return entry["orig"]
        if OWNER_SMART_OFF in owners:
            return 0
        levels = [lvl for owner, lvl in owners.items() if owner != OWNER_SKIP]
        if not levels:
            return 0
        if OWNER_SKIP in owners:
            return max(levels)
        return max([entry["orig"], *levels])

    def apply(self, days: list[list[int]], exclude: str | None = None) -> list[list[int]]:
        """Days as they must be written to the stove (optionally ignoring one owner)."""
        result = [list(day) for day in days]
        for when, entry in self._items():
            day, slot = day_slot(when)
            result[day][slot] = self.level(entry, exclude)
        return result

    def base_days(self, days: list[list[int]]) -> list[list[int]]:
        """The weekly program without temporary changes."""
        result = [list(day) for day in days]
        for when, entry in self._items():
            day, slot = day_slot(when)
            result[day][slot] = entry["orig"]
        return result

    def owner_end(self, owner: str) -> datetime | None:
        """End of the last slot held by owner."""
        ends = [when + SLOT for when, entry in self._items() if owner in entry["owners"]]
        return max(ends) if ends else None

    def owner_at(self, owner: str, when: datetime) -> bool:
        """Whether owner holds the slot containing when."""
        entry = self.slots.get(_key(floor_slot(when)))
        return bool(entry) and owner in entry["owners"]

    def has_owner(self, owner: str) -> bool:
        """Whether owner holds any slot."""
        return any(owner in entry["owners"] for entry in self.slots.values())

    def ranges(self) -> list[dict]:
        """Contiguous overlay ranges with the same level and owners."""
        result: list[dict] = []
        for when, entry in sorted(self._items(), key=lambda item: item[0]):
            level = self.level(entry)
            owners = sorted(entry["owners"])
            last = result[-1] if result else None
            if last and last["end"] == when and last["level"] == level and last["owners"] == owners:
                last["end"] = when + SLOT
            else:
                result.append({"start": when, "end": when + SLOT, "level": level, "owners": owners})
        return result


def active_period(days: list[list[int]], now: datetime) -> tuple[datetime, datetime] | None:
    """The contiguous heating period (level > 0) containing now, or None."""

    def active(when: datetime) -> bool:
        day, slot = day_slot(when)
        return days[day][slot] > 0

    current = floor_slot(now)
    if not active(current):
        return None
    start = current
    while active(start - SLOT) and current - start < WEEK:
        start -= SLOT
    end = current + SLOT
    while active(end) and end - current < WEEK:
        end += SLOT
    return start, end
