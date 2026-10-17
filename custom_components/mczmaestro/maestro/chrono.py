# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""MCZ Maestro chronothermostat (weekly program).

Protocol (see docs/PROTOCOL.md):

- Read:  ``C|RecuperoGiornoChrono`` -> ``04|<day0>|...|<day6>|<T1>|<T2>|<T3>``
- Write: ``C|ScriviGiornoChrono|<day>|<24 hex chars>`` (stove answers with a ``01`` info frame)
- Temperatures T1..T3 are written with ``C|WriteParametri|1108..1110|<degrees>``

Day 0 is Sunday. Each day has 48 slots of 30 minutes, 2 bits per slot
(MSB first): 0 = off, 1 = T1, 2 = T2, 3 = T3.
"""
from __future__ import annotations

from dataclasses import dataclass

FRAME_TYPE_CHRONO = "04"
SLOTS_PER_DAY = 48
SLOT_MINUTES = 30

# Protocol day index -> name. Index 0 is Sunday, as in the app.
DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

LEVELS = ["off", "T1", "T2", "T3"]

TEMPERATURE_MIN = 5
TEMPERATURE_MAX = 35
TEMPERATURE_PARAMS = (1108, 1109, 1110)


@dataclass
class ChronoProgram:
    """Weekly program as stored in the stove."""

    days: list[list[int]]  # 7 x 48 slot levels, protocol day order
    temperatures: list[int]  # T1, T2, T3 in degrees Celsius


def decode_day(data: str) -> list[int]:
    """Decode 24 hex chars into 48 slot levels."""
    if len(data) != SLOTS_PER_DAY // 2:
        raise ValueError(f"Invalid chrono day data: {data!r}")
    slots = []
    for i in range(0, len(data), 2):
        byte = int(data[i : i + 2], 16)
        slots.extend((byte >> shift) & 0b11 for shift in (6, 4, 2, 0))
    return slots


def encode_day(slots: list[int]) -> str:
    """Encode 48 slot levels into 24 hex chars."""
    if len(slots) != SLOTS_PER_DAY or any(s not in (0, 1, 2, 3) for s in slots):
        raise ValueError("A chrono day needs 48 slot levels between 0 and 3")
    out = ""
    for i in range(0, SLOTS_PER_DAY, 4):
        a, b, c, d = slots[i : i + 4]
        out += f"{(a << 6) | (b << 4) | (c << 2) | d:02x}"
    return out


def parse_chrono(frame: str) -> ChronoProgram:
    """Parse a ``04`` frame."""
    fields = frame.split("|")
    if fields[0] != FRAME_TYPE_CHRONO or len(fields) < 11:
        raise ValueError(f"Not a chrono frame: {frame!r}")
    return ChronoProgram(
        days=[decode_day(f) for f in fields[1:8]],
        temperatures=[int(f, 16) for f in fields[8:11]],
    )


def slot_to_time(slot: int) -> str:
    """Return the start time of a slot as HH:MM (slot 48 is 24:00)."""
    minutes = slot * SLOT_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def time_to_slot(value: str) -> int:
    """Convert HH:MM (or HH:MM:SS) on a 30 minute boundary to a slot index."""
    parts = value.split(":")
    hours, minutes = int(parts[0]), int(parts[1])
    if minutes % SLOT_MINUTES or not 0 <= hours * 60 + minutes <= 24 * 60:
        raise ValueError(f"Time must be on a 30 minute boundary: {value}")
    return (hours * 60 + minutes) // SLOT_MINUTES


def slots_to_ranges(slots: list[int]) -> list[dict[str, str]]:
    """Convert slot levels into a list of {start, end, temperature} ranges."""
    ranges = []
    i = 0
    while i < len(slots):
        level = slots[i]
        start = i
        while i < len(slots) and slots[i] == level:
            i += 1
        if level:
            ranges.append(
                {
                    "start": slot_to_time(start),
                    "end": slot_to_time(i),
                    "temperature": LEVELS[level],
                }
            )
    return ranges


def ranges_to_slots(ranges: list[dict[str, str]]) -> list[int]:
    """Convert {start, end, temperature} ranges into slot levels."""
    slots = [0] * SLOTS_PER_DAY
    for item in ranges:
        start = time_to_slot(str(item["start"]))
        end = time_to_slot(str(item["end"]))
        if end == 0:
            end = SLOTS_PER_DAY  # "00:00" as end means midnight
        if end <= start:
            raise ValueError(f"Range end must be after start: {item}")
        level = LEVELS.index(str(item["temperature"]).upper().replace("OFF", "off"))
        slots[start:end] = [level] * (end - start)
    return slots


def describe_day(slots: list[int]) -> str:
    """Return a short summary, e.g. ``08:00–09:00, 15:00–16:00 (T1)``."""
    ranges = slots_to_ranges(slots)
    if not ranges:
        return "off"
    levels = {r["temperature"] for r in ranges}
    if len(levels) == 1:
        times = ", ".join(f"{r['start']}–{r['end']}" for r in ranges)
        return f"{times} ({levels.pop()})"
    return ", ".join(f"{r['start']}–{r['end']} {r['temperature']}" for r in ranges)
