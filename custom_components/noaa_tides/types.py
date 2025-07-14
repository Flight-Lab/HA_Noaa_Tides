"""Type definitions for the NOAA Tides integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, NotRequired

from homeassistant.components.sensor import SensorEntityDescription

# Station Types
StationType = Literal["noaa_station", "ndbc_buoy"]

# Timezone Options
TimezoneType = Literal["gmt", "lst", "lst_ldt"]

# Unit System Options
UnitSystemType = Literal["Metric", "Imperial"]

# Data Section Types
DataSectionType = Literal["Meteorological", "Spectral Wave", "Ocean Current"]


# API Endpoint Types
class NoaaApiEndpoints(dict[str, str]):
    """NOAA API endpoint configuration."""

    base_url: str
    products_url: str
    sensors_url: str
    data_url: str


class NdbcApiEndpoints(dict[str, str]):
    """NDBC API endpoint configuration."""

    base_url: str
    meteo_url: str
    spec_url: str
    current_url: str


# NOAA API Response Types
class NoaaProductResponse(dict[str, Any]):
    """NOAA product response type."""

    products: list[dict[str, Any]]


class NoaaSensorResponse(dict[str, Any]):
    """NOAA sensor response type."""

    sensors: list[dict[str, Any]]


class NoaaApiResponse(dict[str, Any]):
    """Type for NOAA API response."""

    data: list[dict[str, Any]]
    predictions: NotRequired[list[dict[str, Any]]]


# Sensor Data Types
class BaseSensorAttributes(dict[str, Any]):
    """Base attributes shared by all sensors."""

    time: NotRequired[str]
    units: NotRequired[str]
    flags: NotRequired[str]


class MeteoAttributes(BaseSensorAttributes):
    """Meteorological sensor attributes."""

    raw_value: str
    parameter: str


class WindAttributes(BaseSensorAttributes):
    """Wind sensor attributes."""

    direction: NotRequired[float]
    direction_cardinal: NotRequired[str]
    gust: NotRequired[float]


class WaterLevelAttributes(BaseSensorAttributes):
    """Water level sensor attributes."""

    datum: str


class SensorData(dict[str, Any]):
    """Type for sensor data."""

    state: float | str
    attributes: dict[str, Any]


# Tide Prediction Types
class TidePrediction(dict[str, Any]):
    """Type for tide prediction data."""

    time: datetime
    type: Literal["H", "L"]
    level: float


class TidePredictionAttributes(dict[str, Any]):
    """Type for tide prediction attributes."""

    next_tide_type: Literal["High", "Low"]
    next_tide_time: str
    next_tide_level: float
    following_tide_type: Literal["High", "Low"]
    following_tide_time: str
    following_tide_level: float
    last_tide_type: Literal["High", "Low"]
    last_tide_time: str
    last_tide_level: float
    tide_factor: float
    tide_percentage: float


class TidePredictionData(dict[str, Any]):
    """Type for complete tide prediction data."""

    state: str
    attributes: TidePredictionAttributes


class CurrentsPredictionData(dict[str, Any]):
    """Type for complete currents prediction data."""

    state: Literal["ebb", "slack", "flood"]
    attributes: dict[str, Any]


class CurrentsAttributes(BaseSensorAttributes):
    """Currents sensor attributes."""

    direction: NotRequired[float]
    speed: NotRequired[float]


# NDBC Sensor Attributes
class NdbcMeteoAttributes(BaseSensorAttributes):
    """NDBC meteorological sensor attributes."""

    raw_value: NotRequired[str]
    unit: NotRequired[str]


class NdbcWaveAttributes(BaseSensorAttributes):
    """NDBC wave sensor attributes."""

    steepness: NotRequired[str]
    raw_value: str
    unit: str


class NdbcCurrentAttributes(BaseSensorAttributes):
    """NDBC current sensor attributes."""

    depth: float
    raw_value: str
    unit: str


class NdbcHeaderData(dict[str, str]):
    """NDBC header data type."""

    WDIR: str
    WSPD: str
    GST: str
    WVHT: str
    DPD: str
    APD: str
    MWD: str
    PRES: str
    ATMP: str
    WTMP: str
    DEWP: str
    PTDY: str
    TIDE: str


# Config Flow Types
class ConfigFlowData(dict[str, Any]):
    """Config flow data type."""

    name: str
    sensors: list[str]
    station_type: str
    station_id: NotRequired[str]  # NOAA stations
    buoy_id: NotRequired[str]  # NDBC buoys
    timezone: str
    unit_system: str
    update_interval: int
    data_sections: NotRequired[list[str]]  # Only for NDBC


# Coordinator Data Type
class CoordinatorData(dict[str, Any]):
    """Type for coordinator data."""

    tide_predictions: NotRequired[TidePredictionData]
    water_level: NotRequired[SensorData]
    currents: NotRequired[SensorData]
    currents_predictions: NotRequired[CurrentsPredictionData]
    wind_speed: NotRequired[SensorData]
    wind_direction: NotRequired[SensorData]
    air_temperature: NotRequired[SensorData]
    water_temperature: NotRequired[SensorData]
    air_pressure: NotRequired[SensorData]
    humidity: NotRequired[SensorData]
    conductivity: NotRequired[SensorData]


class CompositeSensorGroupsType(dict[str, list[str]]):
    """Type for defining composite sensor relationships."""

    wind_direction: list[str]
    wind_speed: list[str]
    currents_direction: list[str]
    currents_speed: list[str]


@dataclass(frozen=True)
class NoaaTidesSensorEntityDescription(SensorEntityDescription):
    """Class describing NOAA Tides sensor entities."""

    unit_metric: str | None = None
    unit_imperial: str | None = None
    is_ndbc: bool = False


@dataclass
class ApiError:
    """Class to represent API errors with user-friendly messages."""

    code: str
    message: str
    technical_detail: str | None = None
    help_url: str | None = None
