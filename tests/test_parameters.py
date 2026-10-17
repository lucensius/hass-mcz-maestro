# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""Tests for the parameter frame and fan capabilities."""
import importlib.util
from pathlib import Path
import sys

import pytest

_path = Path(__file__).parents[1] / "custom_components/mczmaestro/maestro/parameters.py"
_spec = importlib.util.spec_from_file_location("parameters", _path)
parameters = importlib.util.module_from_spec(_spec)
sys.modules["parameters"] = parameters
_spec.loader.exec_module(parameters)

# Frame as read from a stove with one front fan
FRAME = "00|000005233250010501010105010100000105000000000105000001010101010a0132500a46325000"


def test_limits():
    params = parameters.parse_parameters(FRAME)
    assert params[parameters.INDEX_SETPOINT_MIN] == 5
    assert params[parameters.INDEX_SETPOINT_MAX] == 35
    assert params[parameters.INDEX_POWER_MIN] == 1
    assert params[parameters.INDEX_POWER_MAX] == 5


def test_fitted_fans():
    fans = parameters.fitted_fans(parameters.parse_parameters(FRAME))
    assert len(fans) == 1
    fan = fans[0]
    assert (fan.key, fan.param, fan.info_field) == ("Fan_State", 37, "Fan_State")
    assert fan.enabled and fan.auto_allowed and fan.off_allowed
    assert (fan.minimum, fan.maximum, fan.auto_value) == (1, 5, 6)


def test_all_fans_fitted():
    params = [0] * 40
    for first in (8, 14, 20):
        params[first : first + 6] = [1, 1, 1, 5, 1, 1]
    assert [f.param for f in parameters.fitted_fans(params)] == [37, 38, 39]


def test_invalid_frame():
    with pytest.raises(ValueError):
        parameters.parse_parameters("01|00")
