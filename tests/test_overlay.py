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


def test_smart_off_overrides_everything():
    days = empty_week()
    days[6][30:34] = [1, 1, 1, 1]  # Saturday 15:00-17:00 T1
    table = overlay.OverlayTable()
    now = SAT.replace(hour=16, minute=10)
    table.add("boost", SAT.replace(hour=16), SAT.replace(hour=17), 3, days, now)
    table.add("smart_off", SAT.replace(hour=16), SAT.replace(hour=17), 0, days, now)
    live = table.apply(days)
    assert live[6][30:34] == [1, 1, 0, 0]
    # ignoring smart_off shows the period the smart mode regulates
    assert table.apply(days, exclude="smart_off")[6][32:34] == [3, 3]
    assert table.owner_at("smart_off", now)
    assert not table.owner_at("smart_off", SAT.replace(hour=15, minute=40))


def test_active_period():
    days = empty_week()
    days[6][30:34] = [1, 1, 1, 1]  # Saturday 15:00-17:00
    assert overlay.active_period(days, SAT.replace(hour=16, minute=10)) == (
        SAT.replace(hour=15),
        SAT.replace(hour=17),
    )
    assert overlay.active_period(days, SAT.replace(hour=17)) is None
    assert overlay.active_period(days, SAT.replace(hour=14, minute=59)) is None


def test_active_period_over_midnight():
    days = empty_week()
    days[6][46:48] = [2, 2]  # Saturday 23:00-24:00
    days[0][0:2] = [2, 2]  # Sunday 00:00-01:00
    start, end = overlay.active_period(days, SAT.replace(hour=23, minute=40))
    assert (start, end) == (SAT.replace(hour=23), datetime(2026, 10, 18, 1, 0))


def test_smart_chrono_scenario():
    """Program 15:00-17:00, target reached at 16:10, cold again at 16:40."""
    days = empty_week()
    days[6][30:34] = [1, 1, 1, 1]
    table = overlay.OverlayTable()
    reached = SAT.replace(hour=16, minute=10)
    start, end = overlay.active_period(table.apply(days, exclude="smart_off"), reached)
    table.add("smart_off", reached, end, 0, days, reached)
    assert table.apply(days)[6][30:34] == [1, 1, 0, 0]  # off from 16:00
    cold = SAT.replace(hour=16, minute=40)
    restore = table.remove("smart_off", start=cold)
    days_after = table.apply(days)
    for (d, s), orig in restore.items():
        days_after[d][s] = orig
    assert days_after[6][33] == 1  # 16:30-17:00 heats again
    assert table.expire(SAT.replace(hour=17)) == {(6, 32): 1}  # past slot restored later


def test_cleanup_cutoff():
    assert overlay.cleanup_cutoff(SAT.replace(hour=1, minute=59)) == datetime(2026, 10, 16)
    assert overlay.cleanup_cutoff(SAT.replace(hour=2)) == SAT
    assert overlay.cleanup_cutoff(SAT.replace(hour=16)) == SAT


def test_no_restore_during_the_day():
    """The bug: removing the slot that just ended switched the stove off at 16:00."""
    days = empty_week()
    days[6][35:38] = [1, 1, 1]  # base 17:30-19:00
    table = overlay.OverlayTable()
    started = SAT.replace(hour=15, minute=38)
    table.add("boost", started, SAT.replace(hour=17, minute=30), 1, days, started)
    at_16 = SAT.replace(hour=16, minute=0, second=1)
    assert table.expire(overlay.cleanup_cutoff(at_16)) == {}  # nothing touched today
    assert table.apply(days)[6][31:38] == [1] * 7
    # next day 02:00: yesterday's slots are restored
    restore = table.expire(overlay.cleanup_cutoff(datetime(2026, 10, 18, 2, 0)))
    assert set(restore) == {(6, s) for s in range(31, 35)}
    assert table.slots == {}


def test_stop_keeps_past_slots_until_cleanup():
    days = empty_week()
    table = overlay.OverlayTable()
    start = SAT.replace(hour=15)
    table.add("boost", start, SAT.replace(hour=17), 3, days, start)
    stop = SAT.replace(hour=16, minute=10)
    restore = table.remove("boost", start=stop)
    assert set(restore) == {(6, 32), (6, 33)}  # current slot 16:00 and later
    assert not table.has_owner("boost", stop)  # inactive from now on
    assert table.has_owner("boost")  # past slots still remembered for the cleanup


def test_pending_restores():
    days = empty_week()
    days[6][30] = 3  # we had set T3, original was off
    days[6][31] = 2  # we had set T3, but someone changed it to T2 in the app
    pending = {"6:30": [0, 3], "6:31": [0, 3]}
    overlay.apply_pending(days, pending)
    assert days[6][30] == 0  # restored
    assert days[6][31] == 2  # foreign change kept
    assert pending == {"6:30": [0, 3]}
