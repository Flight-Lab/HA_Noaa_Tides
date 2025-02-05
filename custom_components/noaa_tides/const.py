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
    # NOAA sensor options:
    "tide_state": "Tide State",
    "measured_level": "Measured Level",
    "water_temp": "Water Temperature",
    "air_temp": "Air Temperature",
    # NDBC sensor options:
    "wind_speed": "Wind Speed",
    "wind_direction": "Wind Direction",
    "wave_height": "Wave Height",
    "barometric_pressure": "Barometric Pressure",
}
