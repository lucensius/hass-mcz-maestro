# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 lucensius
"""Stove parameter frame (``00``) and the fans described in it.

Read with ``C|RecuperoParametri``. After the frame type the payload is one hex
string, one byte per value. Per fan there are six bytes:
fitted, enabled, minimum level, maximum level, automatic allowed, off allowed.

Fan level parameter: 0 = off, minimum..maximum = manual level,
maximum + 1 = automatic.
"""
from __future__ import annotations

from dataclasses import dataclass

FRAME_TYPE_PARAMETERS = "00"

INDEX_SETPOINT_MIN = 2
INDEX_SETPOINT_MAX = 3
INDEX_POWER_MIN = 6
INDEX_POWER_MAX = 7

# (key, write parameter, information frame field, first byte in the 00 frame)
FAN_LAYOUT = (
    ("Fan_State", 37, "Fan_State", 8),
    ("DuctedFan1", 38, "DuctedFan1", 14),
    ("DuctedFan2", 39, "DuctedFan2", 20),
)


@dataclass(frozen=True)
class FanConfig:
    """Capabilities of one fan."""

    key: str
    param: int
    info_field: str
    enabled: bool
    minimum: int
    maximum: int
    auto_allowed: bool
    off_allowed: bool

    @property
    def auto_value(self) -> int:
        """Level value meaning automatic."""
        return self.maximum + 1


def parse_parameters(frame: str) -> list[int]:
    """Split a ``00`` frame into its byte values."""
    kind, _, payload = frame.partition("|")
    if kind != FRAME_TYPE_PARAMETERS or len(payload) % 2:
        raise ValueError(f"Not a parameter frame: {frame!r}")
    return [int(payload[i : i + 2], 16) for i in range(0, len(payload), 2)]


def fitted_fans(params: list[int]) -> list[FanConfig]:
    """Fans the stove is fitted with."""
    fans = []
    for key, param, info_field, first in FAN_LAYOUT:
        if len(params) < first + 6 or params[first] != 1:
            continue
        fans.append(
            FanConfig(
                key=key,
                param=param,
                info_field=info_field,
                enabled=params[first + 1] == 1,
                minimum=params[first + 2],
                maximum=params[first + 3],
                auto_allowed=params[first + 4] != 0,
                off_allowed=params[first + 5] != 0,
            )
        )
    return fans
