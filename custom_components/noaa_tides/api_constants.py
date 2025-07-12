"""API-specific constants for NOAA Tides integration."""

from typing import Final


# Data validation constants
INVALID_DATA_VALUES: Final = frozenset(["MM", "999", "999.0", "", "N/A"])

# API timeouts and retry settings
DEFAULT_TIMEOUT: Final = 30
MAX_RETRY_ATTEMPTS: Final = 3
BASE_RETRY_DELAY: Final = 2

# API Response validation
MIN_RESPONSE_LENGTH: Final = 10  # Minimum characters for valid response


def get_ndbc_meteo_url(buoy_id: str) -> str:
    """Generate NDBC meteorological data URL for given buoy ID.
    
    Args:
        buoy_id: The NDBC buoy identifier
        
    Returns:
        str: Complete URL for meteorological data
    """
    return f"https://www.ndbc.noaa.gov/data/realtime2/{buoy_id}.txt"


def get_ndbc_spec_url(buoy_id: str) -> str:
    """Generate NDBC spectral wave data URL for given buoy ID.
    
    Args:
        buoy_id: The NDBC buoy identifier
        
    Returns:
        str: Complete URL for spectral wave data
    """
    return f"https://www.ndbc.noaa.gov/data/realtime2/{buoy_id}.spec"


def get_ndbc_current_url(buoy_id: str) -> str:
    """Generate NDBC ocean current data URL for given buoy ID.
    
    Args:
        buoy_id: The NDBC buoy identifier
        
    Returns:
        str: Complete URL for ocean current data
    """
    return f"https://www.ndbc.noaa.gov/data/realtime2/{buoy_id}.adcp"


def get_noaa_products_url(station_id: str) -> str:
    """Generate NOAA products URL for given station ID.
    
    Args:
        station_id: The NOAA station identifier
        
    Returns:
        str: Complete URL for station products
    """
    return f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station_id}/products.json"


def get_noaa_sensors_url(station_id: str) -> str:
    """Generate NOAA sensors URL for given station ID.
    
    Args:
        station_id: The NOAA station identifier
        
    Returns:
        str: Complete URL for station sensors
    """
    return f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station_id}/sensors.json"


def get_noaa_data_url() -> str:
    """Get the NOAA data API base URL.
    
    Returns:
        str: NOAA data API base URL
    """
    return "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
