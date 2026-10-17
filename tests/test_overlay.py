# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""Tests for the overlay table (temporary chrono changes)."""
from datetime import datetime
import importlib.util
from pathlib import Path
import sys

_path = Path(__file__).parents[1] / "custom_components/mczmaestro/maestro/overlay.py"
_spec = importlib.util.spec_from_file_location("overlay", _path)
overlay = importlib.util.module_from_spec(_spec)
sys.modules["overlay"] = overlay
_spec.loader.exec_module(overlay)

SAT = datetime(2026, 10, 17)  # a Saturday -> protocol day 6


def empty_week():
    return [[0] * 48 for _ in range(7)]


def test_slot_helpers():
    t = SAT.replace(hour=14, minute=10)
    assert overlay.floor_slot(t) == SAT.replace(hour=14)
    assert overlay.ceil_slot(t) == SAT.replace(hour=14, minute=30)
    assert overlay.ceil_slot(SAT.replace(hour=14)) == SAT.replace(hour=14)
    assert overlay.day_slot(SAT.replace(hour=15, minute=30)) == (6, 31)


def test_boost_and_restore():
    days = empty_week()
    days[6][30] = 1  # base program: Saturday 15:00-15:30 T1
    table = overlay.OverlayTable()
    now = SAT.replace(hour=14, minute=10)
    table.add("boost", now, SAT.replace(hour=16), 3, days, now)
    live = table.apply(days)
    assert live[6][28:32] == [3, 3, 3, 3]  # 14:00-16:00 on T3
    assert live[6][32] == 0
    assert table.base_days(live)[6][30] == 1
    restore = table.remove("boost")
    assert restore[(6, 30)] == 1 and restore[(6, 28)] == 0
    assert table.slots == {}


def test_overlay_keeps_higher_base_level():
    days = empty_week()
    days[6][28] = 3
    table = overlay.OverlayTable()
    now = SAT.replace(hour=14)
    table.add("boost", now, SAT.replace(hour=14, minute=30), 1, days, now)
    assert table.apply(days)[6][28] == 3


def test_skip_switches_base_off_but_boost_wins():
    days = empty_week()
    days[6][30] = 2
    table = overlay.OverlayTable()
    now = SAT.replace(hour=12)
    table.add("skip", SAT.replace(hour=15), SAT.replace(hour=15, minute=30), 0, days, now)
    assert table.apply(days)[6][30] == 0
    table.add("boost", SAT.replace(hour=15), SAT.replace(hour=15, minute=30), 1, days, now)
    assert table.apply(days)[6][30] == 1


def test_expire_restores_past_slots_only():
    days = empty_week()
    table = overlay.OverlayTable()
    now = SAT.replace(hour=14)
    table.add("boost", now, SAT.replace(hour=15), 3, days, now)
    restore = table.expire(SAT.replace(hour=14, minute=30))
    assert list(restore) == [(6, 28)]
    assert len(table.slots) == 1


def test_never_wraps_into_next_week():
    days = empty_week()
    table = overlay.OverlayTable()
    now = SAT.replace(hour=14)
    table.add("once", now, datetime(2026, 10, 25, 14), 1, days, now)
    assert len(table.slots) == 7 * 48  # exactly one week, no slot twice


def test_set_base_updates_originals():
    days = empty_week()
    table = overlay.OverlayTable()
    now = SAT.replace(hour=14)
    table.add("smart", now, SAT.replace(hour=15), 3, days, now)
    table.set_base(6, [2] * 48)
    assert table.remove("smart") == {(6, 28): 2, (6, 29): 2}


def test_owner_end_and_ranges():
    days = empty_week()
    table = overlay.OverlayTable()
    now = SAT.replace(hour=14)
    table.add("smart", now, SAT.replace(hour=15), 3, days, now)
    assert table.owner_end("smart") == SAT.replace(hour=15)
    assert table.has_owner("smart") and not table.has_owner("boost")
    assert table.ranges() == [
        {"start": SAT.replace(hour=14), "end": SAT.replace(hour=15), "level": 3, "owners": ["smart"]}
    ]


def test_roundtrip_storage():
    days = empty_week()
    table = overlay.OverlayTable()
    now = SAT.replace(hour=14)
    table.add("boost", now, SAT.replace(hour=15), 3, days, now)
    again = overlay.OverlayTable(table.as_dict())
    assert again.apply(days) == table.apply(days)
