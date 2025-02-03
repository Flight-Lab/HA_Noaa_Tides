"""Constants for the NOAA Tides integration."""

DOMAIN = "noaa_tides"

VERSION = "0.3.2"

# Configuration fields
CONF_STATION_ID = "station_id"
CONF_TIMEZONE = "timezone"
CONF_UNIT_SYSTEM = "unit_system"

DEFAULT_NAME = "NOAA Tides"
DEFAULT_TIMEZONE = "lst_ldt"
DEFAULT_UNIT_SYSTEM = "imperial"


# Platforms supported by the integration
PLATFORMS = ["sensor"]


# Mapping of internal sensor keys to friendly labels
SENSOR_OPTIONS = {
    "tide_state": "Tide State",
    "measured_level": "Measured Level",
    "water_temp": "Water Temperature",
    "air_temp": "Air Temperature",
}
