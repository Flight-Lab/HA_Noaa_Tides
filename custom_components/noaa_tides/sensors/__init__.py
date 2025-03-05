"""Sensor definitions for NOAA Tides integration."""

from __future__ import annotations

from .ndbc_sensors import NDBC_SENSOR_TYPES
from .noaa_sensors import NOAA_SENSOR_TYPES

__all__ = ["NDBC_SENSOR_TYPES", "NOAA_SENSOR_TYPES"]
