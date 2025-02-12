"""Constants for the NOAA Tides integration."""

from __future__ import annotations

from typing import Final, Literal, TypedDict

# Domain and Platform Configuration
DOMAIN: Final = "noaa_tides"
PLATFORMS: Final[list[str]] = ["sensor"]

# Configuration Constants
CONF_STATION_ID: Final = "station_id"
CONF_BUOY_ID: Final = "buoy_id"
CONF_TIMEZONE: Final = "timezone"
CONF_UNIT_SYSTEM: Final = "unit_system"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_DATA_SECTIONS: Final = "data_sections"
CONF_HUB_TYPE: Final = "hub_type"

# Hub Types
HUB_TYPE_NOAA: Final = "noaa_station"
HUB_TYPE_NDBC: Final = "ndbc_buoy"
HubType: type = Literal["noaa_station", "ndbc_buoy"]

# Timezone Options
TIMEZONE_GMT: Final = "gmt"
TIMEZONE_LST: Final = "lst"
TIMEZONE_LST_LDT: Final = "lst_ldt"
TimezoneType: type = Literal["gmt", "lst", "lst_ldt"]

TIMEZONE_OPTIONS: Final[dict[TimezoneType, str]] = {
    TIMEZONE_GMT: "GMT",
    TIMEZONE_LST: "Local Standard Time",
    TIMEZONE_LST_LDT: "Local Standard/Daylight Time",
}

# Unit System Options
UNIT_METRIC: Final = "Metric"
UNIT_IMPERIAL: Final = "Imperial"
UnitSystemType: type = Literal["Metric", "Imperial"]

UNIT_OPTIONS: Final[dict[UnitSystemType, str]] = {
    UNIT_METRIC: "Metric",
    UNIT_IMPERIAL: "Imperial",
}

# NDBC Data Sections
DATA_METEOROLOGICAL: Final = "Meteorological"
DATA_SPECTRAL_WAVE: Final = "Spectral Wave"
DATA_OCEAN_CURRENT: Final = "Ocean Current"
DataSectionType: type = Literal["Meteorological", "Spectral Wave", "Ocean Current"]

DATA_SECTIONS: Final[dict[DataSectionType, str]] = {
    DATA_METEOROLOGICAL: "Meteorological Data",
    DATA_SPECTRAL_WAVE: "Spectral Wave Data",
    DATA_OCEAN_CURRENT: "Ocean Current Data",
}


# API Endpoints
class NoaaApiEndpoints(TypedDict):
    """NOAA API endpoint configuration."""

    base_url: str
    products_url: str
    sensors_url: str
    data_url: str


class NdbcApiEndpoints(TypedDict):
    """NDBC API endpoint configuration."""

    base_url: str
    meteo_url: str
    spec_url: str
    current_url: str


NOAA_BASE_URL: Final = "https://api.tidesandcurrents.noaa.gov"
NOAA_PRODUCTS_URL: Final = (
    f"{NOAA_BASE_URL}/mdapi/prod/webapi/stations/{{station_id}}/products.json"
)
NOAA_SENSORS_URL: Final = (
    f"{NOAA_BASE_URL}/mdapi/prod/webapi/stations/{{station_id}}/sensors.json"
)
NOAA_DATA_URL: Final = f"{NOAA_BASE_URL}/api/prod/datagetter"

NDBC_BASE_URL: Final = "https://www.ndbc.noaa.gov/data/realtime2"
NDBC_METEO_URL: Final = f"{NDBC_BASE_URL}/{{buoy_id}}.txt"
NDBC_SPEC_URL: Final = f"{NDBC_BASE_URL}/{{buoy_id}}.spec"
NDBC_CURRENT_URL: Final = f"{NDBC_BASE_URL}/{{buoy_id}}.adcp"

# Default Values
DEFAULT_NAME_NOAA: Final = "NOAA Station"
DEFAULT_NAME_NDBC: Final = "NDBC Buoy"
DEFAULT_TIMEZONE: Final = TIMEZONE_LST_LDT
DEFAULT_UNIT_SYSTEM: Final = UNIT_IMPERIAL
DEFAULT_UPDATE_INTERVAL: Final = 300  # 5 minutes in seconds

# Error Messages
ERROR_INVALID_STATION: Final = "Invalid station ID provided"
ERROR_INVALID_BUOY: Final = "Invalid buoy ID provided"
ERROR_NO_DATA_SECTIONS: Final = "At least one data section must be selected"
ERROR_INVALID_TIMEZONE: Final = "Invalid timezone selection"
ERROR_INVALID_UNIT_SYSTEM: Final = "Invalid unit system selection"
ERROR_NO_SENSORS: Final = "No available sensors found for this station/buoy"
ERROR_UNKNOWN: Final = "An unexpected error occurred"


# NOAA Tide State Sensor Attributes
class TideAttributes(TypedDict):
    """Tide sensor attributes."""

    tide_state: Literal["rising", "falling"]
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


# NOAA Tide State Attribute Constants
ATTR_TIDE_STATE: Final = "tide_state"
ATTR_NEXT_TIDE_TYPE: Final = "next_tide_type"
ATTR_NEXT_TIDE_TIME: Final = "next_tide_time"
ATTR_NEXT_TIDE_LEVEL: Final = "next_tide_level"
ATTR_FOLLOWING_TIDE_TYPE: Final = "following_tide_type"
ATTR_FOLLOWING_TIDE_TIME: Final = "following_tide_time"
ATTR_FOLLOWING_TIDE_LEVEL: Final = "following_tide_level"
ATTR_LAST_TIDE_TYPE: Final = "last_tide_type"
ATTR_LAST_TIDE_TIME: Final = "last_tide_time"
ATTR_LAST_TIDE_LEVEL: Final = "last_tide_level"
ATTR_TIDE_FACTOR: Final = "tide_factor"
ATTR_TIDE_PERCENTAGE: Final = "tide_percentage"


# NOAA Predicted Currents sensor attributes
class PredictedCurrentsAttributes(TypedDict):
    """Predicted currents sensor attributes."""

    currents_speed: float
    currents_direction: str
    currents_time: str


# NOAA Predicted Currents sensor attribute constants
ATTR_CURRENTS_SPEED: Final = "currents_speed"
ATTR_CURRENTS_DIRECTION: Final = "currents_direction"
ATTR_CURRENTS_TIME: Final = "currents_time"
