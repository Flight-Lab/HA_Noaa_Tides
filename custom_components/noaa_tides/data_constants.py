"""Data processing constants for NOAA Tides integration."""

from typing import Final


# Non-temperature unit conversion factors (still needed for manual conversion)
METERS_TO_FEET_FACTOR: Final = 3.28084
MS_TO_MPH_FACTOR: Final = 2.23694
HPA_TO_INHG_FACTOR: Final = 0.02953

# Data validation thresholds
SLACK_WATER_THRESHOLD: Final = 0.1
MAX_WIND_SPEED: Final = 200  # mph, for validation
MAX_WAVE_HEIGHT: Final = 100  # feet, for validation

# Minimum data line requirements
MIN_METEO_DATA_LINES: Final = 3  # Header, units, and at least one data line
MIN_WAVE_DATA_LINES: Final = 2   # Header and at least one data line
MIN_CURRENT_DATA_LINES: Final = 2

# Data processing constants
DECIMAL_PRECISION: Final = 2  # Standard rounding precision for sensor values
MAX_DATA_LINES_TO_CHECK: Final = 12  # Maximum recent data lines to validate
CARDINAL_DIRECTION_STEP: Final = 22.5  # Degrees per cardinal direction

# Time formatting
TIDE_TIME_FORMAT: Final = "%-I:%M %p"  # Format for tide time display
ISO_TIME_FORMAT: Final = "%Y-%m-%d %H:%M"

# Error handling constants
MAX_CONSECUTIVE_FAILURES: Final = 3
DEFAULT_RETRY_DELAY: Final = 2  # seconds

# API response limits
MAX_PREDICTION_HOURS: Final = 48  # Hours of predictions to fetch
MIN_REQUIRED_PREDICTIONS: Final = 2  # Minimum predictions needed for calculations


class LogMessages:
    """Centralized log message templates."""
    
    # Station/Buoy identification
    STATION_NOT_FOUND: Final = "Station {station_id}: Not found"
    BUOY_NOT_FOUND: Final = "Buoy {buoy_id}: Not found"
    
    # Data processing
    INVALID_SENSOR_DATA: Final = "{source_type} {source_id}: Invalid data for sensor {sensor_id}: {value}"
    INSUFFICIENT_DATA: Final = "{source_type} {source_id}: Insufficient data in {data_type} response"
    PROCESSING_SENSOR: Final = "{source_type} {source_id}: Processing {sensor_count} sensors"
    
    # Error conditions
    CONNECTION_TIMEOUT: Final = "{source_type} {source_id}: Connection timed out during {operation}"
    RATE_LIMITED: Final = "{source_type} {source_id}: Rate limited, retrying after {delay} seconds"
    SERVER_ERROR: Final = "{source_type} {source_id}: Server error {status_code} during {operation}"
    
    # Success conditions
    DATA_FETCHED: Final = "{source_type} {source_id}: Successfully fetched {data_type} data"
    SENSORS_DISCOVERED: Final = "{source_type} {source_id}: Discovered {sensor_count} sensors"


class ErrorCodes:
    """Standardized error codes for API responses."""
    
    TIMEOUT: Final = "timeout"
    STATION_NOT_FOUND: Final = "station_not_found"
    BUOY_NOT_FOUND: Final = "buoy_not_found"
    SERVER_ERROR: Final = "server_error"
    RATE_LIMIT: Final = "rate_limit"
    CONNECTION_ERROR: Final = "connection_error"
    INVALID_DATA: Final = "invalid_data"
    DECODE_ERROR: Final = "decode_error"
    UNKNOWN_ERROR: Final = "unknown_error"
