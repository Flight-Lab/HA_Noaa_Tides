"""Sensor definitions for NOAA Tides integration."""

from __future__ import annotations

from .ndbc_sensors import NDBC_SENSOR_TYPES
from .noaa_sensors import NOAA_SENSOR_TYPES

__all__ = ["NOAA_SENSOR_TYPES", "NDBC_SENSOR_TYPES"]
