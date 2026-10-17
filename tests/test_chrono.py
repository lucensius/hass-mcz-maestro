# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""Tests for the chrono protocol helpers (run with pytest)."""
import importlib.util
from pathlib import Path
import sys

import pytest

_path = Path(__file__).parents[1] / "custom_components/mczmaestro/maestro/chrono.py"
_spec = importlib.util.spec_from_file_location("chrono", _path)
chrono = importlib.util.module_from_spec(_spec)
sys.modules["chrono"] = chrono
_spec.loader.exec_module(chrono)

# Frame as read from a stove
FRAME = (
    "04|000000000000000000000000|000000000000000000000000|000000000000000000000000"
    "|000000000000000000540000|000000000000000000000000|000000001500000000000000"
    "|000000000000000540000000|10|11|12"
)


def test_parse_real_frame():
    program = chrono.parse_chrono(FRAME)
    assert program.temperatures == [16, 17, 18]
    assert chrono.describe_day(program.days[0]) == "off"
    assert chrono.describe_day(program.days[3]) == "18:00–19:30 (T1)"
    assert chrono.describe_day(program.days[5]) == "08:30–10:00 (T1)"
    assert chrono.describe_day(program.days[6]) == "15:00–16:30 (T1)"


def test_roundtrip():
    for day in FRAME.split("|")[1:8]:
        assert chrono.encode_day(chrono.decode_day(day)) == day


def test_ranges_to_slots():
    slots = chrono.ranges_to_slots(
        [
            {"start": "06:00", "end": "08:30", "temperature": "T2"},
            {"start": "22:00", "end": "00:00", "temperature": "T3"},
        ]
    )
    assert chrono.slots_to_ranges(slots) == [
        {"start": "06:00", "end": "08:30", "temperature": "T2"},
        {"start": "22:00", "end": "24:00", "temperature": "T3"},
    ]
    assert chrono.encode_day(slots)[:6] == "000000"
    assert slots[12:17] == [2] * 5


def test_invalid_input():
    with pytest.raises(ValueError):
        chrono.time_to_slot("06:15")
    with pytest.raises(ValueError):
        chrono.ranges_to_slots([{"start": "08:00", "end": "06:00", "temperature": "T1"}])
    with pytest.raises(ValueError):
        chrono.decode_day("00")
