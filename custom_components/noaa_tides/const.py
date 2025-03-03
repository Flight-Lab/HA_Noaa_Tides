"""Constants for the NOAA Tides integration."""

from __future__ import annotations

from typing import Final

from .types import DataSectionType, TimezoneType, UnitSystemType

# Domain and Platform Configuration
DOMAIN: Final = "noaa_tides"
PLATFORMS: Final[list[str]] = ["sensor"]

# Hub Types
HUB_TYPE_NOAA: Final = "noaa_station"
HUB_TYPE_NDBC: Final = "ndbc_buoy"

# Configuration Constants
CONF_STATION_ID: Final = "station_id"
CONF_BUOY_ID: Final = "buoy_id"
CONF_TIMEZONE: Final = "timezone"
CONF_UNIT_SYSTEM: Final = "unit_system"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_DATA_SECTIONS: Final = "data_sections"
CONF_HUB_TYPE: Final = "hub_type"

# Timezone Options
TIMEZONE_GMT: Final = "gmt"
TIMEZONE_LST: Final = "lst"
TIMEZONE_LST_LDT: Final = "lst_ldt"

TIMEZONE_OPTIONS: Final[dict[TimezoneType, str]] = {
    TIMEZONE_GMT: "GMT",
    TIMEZONE_LST: "Local Standard Time",
    TIMEZONE_LST_LDT: "Local Standard/Daylight Time",
}

# Unit System Options
UNIT_METRIC: Final = "Metric"
UNIT_IMPERIAL: Final = "Imperial"

UNIT_OPTIONS: Final[dict[UnitSystemType, str]] = {
    UNIT_METRIC: "Metric",
    UNIT_IMPERIAL: "Imperial",
}

# NDBC Data Sections
DATA_METEOROLOGICAL: Final = "Meteorological"
DATA_SPECTRAL_WAVE: Final = "Spectral Wave"
DATA_OCEAN_CURRENT: Final = "Ocean Current"

DATA_SECTIONS: Final[dict[DataSectionType, str]] = {
    DATA_METEOROLOGICAL: "Meteorological Data",
    DATA_SPECTRAL_WAVE: "Spectral Wave Data",
    DATA_OCEAN_CURRENT: "Ocean Current Data",
}

# API Endpoints
# NOAA API Endpoints
NOAA_BASE_URL: Final = "https://api.tidesandcurrents.noaa.gov"
NOAA_PRODUCTS_URL: Final = (
    f"{NOAA_BASE_URL}/mdapi/prod/webapi/stations/{{station_id}}/products.json"
)
NOAA_SENSORS_URL: Final = (
    f"{NOAA_BASE_URL}/mdapi/prod/webapi/stations/{{station_id}}/sensors.json"
)
NOAA_DATA_URL: Final = f"{NOAA_BASE_URL}/api/prod/datagetter"

# NDBC API Endpoints
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
DEFAULT_TIMEOUT: Final = 30  # seconds

# Error Messages
ERROR_INVALID_STATION: Final = "Invalid station ID provided"
ERROR_INVALID_BUOY: Final = "Invalid buoy ID provided"
ERROR_NO_DATA_SECTIONS: Final = "At least one data section must be selected"
ERROR_INVALID_TIMEZONE: Final = "Invalid timezone selection"
ERROR_INVALID_UNIT_SYSTEM: Final = "Invalid unit system selection"
ERROR_NO_SENSORS: Final = "No available sensors found for this station/buoy"
ERROR_UNKNOWN: Final = "An unexpected error occurred"

# Attribute Constants (moved from multiple separate sections)
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
ATTR_CURRENTS_SPEED: Final = "currents_speed"
ATTR_CURRENTS_DIRECTION: Final = "currents_direction"
ATTR_CURRENTS_TIME: Final = "currents_time"

# Sensor data section mapping
METEO_SENSORS: Final = [
    "meteo_wdir",
    "meteo_wspd",
    "meteo_gst",
    "meteo_wvht",
    "meteo_dpd",
    "meteo_apd",
    "meteo_mwd",
    "meteo_pres",
    "meteo_atmp",
    "meteo_wtmp",
    "meteo_dewp",
    "meteo_ptdy",
    "meteo_tide",
]

SPEC_WAVE_SENSORS: Final = [
    "spec_wave_wvht",
    "spec_wave_swh",
    "spec_wave_swp",
    "spec_wave_wwh",
    "spec_wave_wwp",
    "spec_wave_swd",
    "spec_wave_wwd",
    "spec_wave_steepness",
    "spec_wave_apd",
    "spec_wave_mwd",
]

OCEAN_CURRENT_SENSORS: Final = ["current_depth", "current_drct", "current_spdd"]

# Mapping for which section contains which sensors
SENSOR_SECTION_MAP: Final = {
    DATA_METEOROLOGICAL: METEO_SENSORS,
    DATA_SPECTRAL_WAVE: SPEC_WAVE_SENSORS,
    DATA_OCEAN_CURRENT: OCEAN_CURRENT_SENSORS,
}

# Mapping for overlapping sensors (when same measurement exists in multiple sections)
# Prioritize spectral wave data over meteorological data for better accuracy
OVERLAPPING_SENSORS: Final = {
    # Wave height
    "meteo_wvht": "spec_wave_wvht",  # Prefer spectral wave height over meteorological
    # Wave period
    "meteo_apd": "spec_wave_apd",  # Prefer spectral average wave period over meteorological
    # Wave direction
    "meteo_mwd": "spec_wave_mwd",  # Prefer spectral mean wave direction over meteorological
}
