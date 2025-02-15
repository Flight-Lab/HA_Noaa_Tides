"""Utility functions for the NOAA Tides integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any, Final, Optional, TypedDict, cast

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import const

_LOGGER: Final = logging.getLogger(__name__)


class NoaaProductResponse(TypedDict):
    """NOAA product response type."""

    products: list[dict[str, Any]]


class NoaaSensorResponse(TypedDict):
    """NOAA sensor response type."""

    sensors: list[dict[str, Any]]


class NdbcHeaderData(TypedDict):
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


@dataclass
class ApiError:
    """Class to represent API errors with user-friendly messages."""

    code: str
    message: str
    technical_detail: Optional[str] = None
    help_url: Optional[str] = None


async def handle_noaa_api_error(error: Exception, station_id: str) -> ApiError:
    """Handle NOAA API errors and return user-friendly messages."""
    if isinstance(error, asyncio.TimeoutError):
        return ApiError(
            code="timeout",
            message=f"Station {station_id}: Connection timed out. Please check your internet connection.",
            technical_detail=str(error),
            help_url="https://tidesandcurrents.noaa.gov/stations.html",
        )

    if isinstance(error, aiohttp.ClientResponseError):
        if error.status == 404:
            return ApiError(
                code="station_not_found",
                message=f"Station {station_id}: Not found. Please verify the station ID.",
                help_url="https://tidesandcurrents.noaa.gov/stations.html",
            )
        if error.status in (500, 502, 503, 504):
            return ApiError(
                code="server_error",
                message=f"Station {station_id}: NOAA service is temporarily unavailable. Please try again later.",
                technical_detail=f"Status: {error.status}",
            )
        if error.status == 429:
            return ApiError(
                code="rate_limit",
                message=f"Station {station_id}: Too many requests to NOAA API. Please try again later.",
                technical_detail=f"Status: {error.status}",
            )
        return ApiError(
            code=f"http_error_{error.status}",
            message=f"Station {station_id}: Unexpected HTTP error occurred.",
            technical_detail=f"Status: {error.status}",
        )

    if isinstance(error, aiohttp.ClientConnectionError):
        return ApiError(
            code="connection_error",
            message=f"Station {station_id}: Could not connect to NOAA service. Please check your internet connection.",
            technical_detail=str(error),
        )

    if isinstance(error, ValueError):
        return ApiError(
            code="invalid_data",
            message=f"Station {station_id}: Received invalid data from NOAA service.",
            technical_detail=str(error),
        )

    return ApiError(
        code="unknown",
        message=f"Station {station_id}: An unexpected error occurred while connecting to NOAA.",
        technical_detail=str(error),
    )


async def handle_ndbc_api_error(error: Exception, buoy_id: str) -> ApiError:
    """Handle NDBC API errors and return user-friendly messages."""
    if isinstance(error, asyncio.TimeoutError):
        return ApiError(
            code="timeout",
            message=f"Buoy {buoy_id}: Connection timed out. Please check your internet connection.",
            technical_detail=str(error),
            help_url="https://www.ndbc.noaa.gov/stations.shtml",
        )

    if isinstance(error, aiohttp.ClientResponseError):
        if error.status == 404:
            return ApiError(
                code="buoy_not_found",
                message=f"Buoy {buoy_id}: Not found. Please verify the buoy ID.",
                help_url="https://www.ndbc.noaa.gov/stations.shtml",
            )
        if error.status in (500, 502, 503, 504):
            return ApiError(
                code="server_error",
                message=f"Buoy {buoy_id}: NDBC service is temporarily unavailable. Please try again later.",
                technical_detail=f"Status: {error.status}",
            )
        if error.status == 429:
            return ApiError(
                code="rate_limit",
                message=f"Buoy {buoy_id}: Too many requests to NDBC API. Please try again later.",
                technical_detail=f"Status: {error.status}",
            )
        return ApiError(
            code=f"http_error_{error.status}",
            message=f"Buoy {buoy_id}: Unexpected HTTP error occurred.",
            technical_detail=f"Status: {error.status}",
        )

    if isinstance(error, aiohttp.ClientConnectionError):
        return ApiError(
            code="connection_error",
            message=f"Buoy {buoy_id}: Could not connect to NDBC service. Please check your internet connection.",
            technical_detail=str(error),
        )

    if isinstance(error, ValueError):
        return ApiError(
            code="invalid_data",
            message=f"Buoy {buoy_id}: Received invalid data from NDBC service.",
            technical_detail=str(error),
        )

    if isinstance(error, UnicodeDecodeError):
        return ApiError(
            code="decode_error",
            message=f"Buoy {buoy_id}: Could not read NDBC data format.",
            technical_detail=str(error),
        )

    return ApiError(
        code="unknown",
        message=f"Buoy {buoy_id}: An unexpected error occurred while connecting to NDBC.",
        technical_detail=str(error),
    )


async def validate_noaa_station(hass: HomeAssistant, station_id: str) -> bool:
    """Validate a NOAA station ID by checking the products endpoint.

    Args:
        hass: HomeAssistant instance
        station_id: NOAA station identifier to validate

    Returns:
        bool: True if station is valid, False otherwise

    """
    try:
        session = async_get_clientsession(hass)
        url = const.NOAA_PRODUCTS_URL.format(station_id=station_id)

        async with session.get(url) as response:
            if response.status != 200:
                return False
            data = cast(NoaaProductResponse, await response.json())
            return bool(data.get("products"))

    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
        _LOGGER.error("Station %s: Error validating: %s", station_id, err)
        return False


async def validate_ndbc_buoy(
    hass: HomeAssistant, buoy_id: str, data_sections: list[str]
) -> bool:
    """Validate an NDBC buoy ID by checking the specified data sections."""
    try:
        session = async_get_clientsession(hass)

        # If no data sections specified, default to meteorological
        if not data_sections:
            data_sections = [const.DATA_METEOROLOGICAL]

        tasks: list[asyncio.Task[aiohttp.ClientResponse]] = []

        # Create validation tasks based on selected data sections
        for section in data_sections:
            if section == const.DATA_METEOROLOGICAL:
                url = const.NDBC_METEO_URL.format(buoy_id=buoy_id)
            elif section == const.DATA_SPECTRAL_WAVE:
                url = const.NDBC_SPEC_URL.format(buoy_id=buoy_id)
            elif section == const.DATA_OCEAN_CURRENT:
                url = const.NDBC_CURRENT_URL.format(buoy_id=buoy_id)
            else:
                continue

            # Add timeout to request
            tasks.append(
                asyncio.create_task(
                    session.get(url, timeout=aiohttp.ClientTimeout(total=10))
                )
            )

        if not tasks:
            return False

        # Wait for all tasks to complete
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Consider buoy valid if ANY selected data section is available
        valid_responses = 0
        for response in responses:
            if isinstance(response, Exception):
                _LOGGER.debug(
                    "NDBC Buoy %s: Error checking data: %s", buoy_id, response
                )
                continue

            if response.status == 200:
                try:
                    text = await response.text()
                    if len(text.strip().split("\n")) > 1:
                        valid_responses += 1
                except Exception as err:
                    _LOGGER.debug(
                        "NDBC Buoy %s: Error reading response: %s", buoy_id, err
                    )
                    continue

        # Consider valid if at least one data section is available
        return valid_responses > 0

    except Exception as err:
        _LOGGER.error("NDBC Buoy: Error validating: %s", buoy_id, err)
        return False


async def discover_noaa_sensors(hass: HomeAssistant, station_id: str) -> dict[str, str]:
    """Discover available sensors for a NOAA station.

    Args:
        hass: HomeAssistant instance
        station_id: NOAA station identifier

    Returns:
        dict[str, str]: Dictionary mapping sensor keys to display names
    """
    _LOGGER.debug("NOAA Station %s: Starting NOAA sensor discovery", station_id)
    try:
        session = async_get_clientsession(hass)
        sensors: dict[str, str] = {}

        # Create tasks for both endpoints
        products_url = const.NOAA_PRODUCTS_URL.format(station_id=station_id)
        sensors_url = const.NOAA_SENSORS_URL.format(station_id=station_id)

        async with asyncio.TaskGroup() as tg:
            products_task = tg.create_task(session.get(products_url))
            sensors_task = tg.create_task(session.get(sensors_url))

        # Process products endpoint response
        if products_task.result().status == 200:
            products_data = cast(
                NoaaProductResponse, await products_task.result().json()
            )
            products = products_data.get("products", [])
            _LOGGER.debug("NOAA Station %s: Found products: %s", station_id, products)

            # Map product names to sensors
            for product in products:
                name = product.get("name", "").lower()
                _LOGGER.debug(
                    "NOAA Station %s: Processing product name: %s", station_id, name
                )

                if "water levels" in name:
                    sensors["water_level"] = "Water Level"
                if "tide predictions" in name:
                    sensors["tide_predictions"] = "Tide Predictions"
                if "currents" in name:
                    sensors["currents_speed"] = "Currents Speed"
                    sensors["currents_direction"] = "Currents Direction"
                if "current predictions" in name:
                    sensors["currents_predictions"] = "Currents Predictions"

        # Process sensors endpoint response
        if sensors_task.result().status == 200:
            try:
                sensors_data = cast(
                    NoaaSensorResponse, await sensors_task.result().json()
                )
                available_sensors = sensors_data.get("sensors", [])
                _LOGGER.debug(
                    "NOAA Station %s: Raw sensors data: %s", station_id, sensors_data
                )

                for sensor in available_sensors:
                    sensor_name = sensor.get("name", "").lower()
                    _LOGGER.debug(
                        "NOAA Station %s: Found NOAA sensor name: %s",
                        station_id,
                        sensor_name,
                    )

                    # Map sensor names to our sensors
                    if "water temperature" in sensor_name:
                        sensors["water_temperature"] = "Water Temperature"
                    elif "air temperature" in sensor_name:
                        sensors["air_temperature"] = "Air Temperature"
                    elif "wind" in sensor_name:
                        sensors["wind_speed"] = "Wind Speed"
                        sensors["wind_direction"] = "Wind Direction"
                    elif "barometric pressure" in sensor_name:
                        sensors["air_pressure"] = "Barometric Pressure"
                    elif "humidity" in sensor_name:
                        sensors["humidity"] = "Humidity"
                    elif "conductivity" in sensor_name:
                        sensors["conductivity"] = "Conductivity"

            except Exception as err:
                _LOGGER.debug(
                    "NOAA Station %s: Error processing sensors data: %s",
                    station_id,
                    err,
                )

        _LOGGER.debug(
            "NOAA Station %s: Final discovered sensors: %s", station_id, sensors
        )
        return sensors

    except Exception as err:
        _LOGGER.error("NOAA Station %s: Error discovering sensors: %s", station_id, err)
        return {}


async def discover_ndbc_sensors(
    hass: HomeAssistant, buoy_id: str, data_sections: list[str]
) -> dict[str, str]:
    """Discover available sensors for an NDBC buoy."""
    try:
        session = async_get_clientsession(hass)
        sensors: dict[str, str] = {}

        # Mapping of NDBC headers to sensor names
        meteo_mapping: Final[dict[str, str]] = {
            "WDIR": "Wind Direction",
            "WSPD": "Wind Speed",
            "GST": "Wind Gust",
            "WVHT": "Wave Height",
            "DPD": "Dominant Wave Period",
            "APD": "Average Wave Period",
            "MWD": "Wave Direction",
            "PRES": "Barometric Pressure",
            "ATMP": "Air Temperature",
            "WTMP": "Water Temperature",
            "DEWP": "Dew Point",
            "PTDY": "Pressure Tendency",
            "TIDE": "Tide",
        }

        for section in data_sections:
            if section == const.DATA_METEOROLOGICAL:
                url = const.NDBC_METEO_URL.format(buoy_id=buoy_id)
                async with session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        lines = text.strip().split("\n")
                        if (
                            len(lines) >= 3
                        ):  # Need header, units, and at least one data line
                            headers = lines[0].strip().split()
                            units = lines[1].strip().split()  # Skip units line

                            # Get actual data lines, skipping headers and units
                            data_lines = [line.strip().split() for line in lines[2:7]]

                            for i, header in enumerate(headers):
                                if header in meteo_mapping:
                                    # Check if sensor has valid data in recent readings
                                    valid_readings = False
                                    for data_line in data_lines:
                                        try:
                                            if (
                                                i < len(data_line)
                                                and data_line[i] != "MM"
                                                and data_line[i] != "999.0"
                                                and data_line[i] != "999"
                                                and float(data_line[i])
                                            ):  # Verify it's a valid number
                                                valid_readings = True
                                                break
                                        except ValueError:
                                            continue

                                    _LOGGER.debug(
                                        "NDBC Buoy %s: Checking sensor %s: valid_readings=%s, first_value=%s",
                                        buoy_id,
                                        header,
                                        valid_readings,
                                        data_lines[0][i]
                                        if i < len(data_lines[0])
                                        else "out of range",
                                    )

                                    if valid_readings:
                                        sensor_id = f"meteo_{header.lower()}"
                                        sensors[sensor_id] = meteo_mapping[header]
                                        _LOGGER.debug(
                                            "NDBC Buoy %s: Added sensor: %s -> %s",
                                            buoy_id,
                                            sensor_id,
                                            meteo_mapping[header],
                                        )

            elif section == const.DATA_SPECTRAL_WAVE:
                # Mapping of spectral wave headers to sensor names
                wave_mapping: Final[dict[str, str]] = {
                    "WVHT": "Wave Height",
                    "SwH": "Swell Height",
                    "SwP": "Swell Period",
                    "WWH": "Wind Wave Height",
                    "WWP": "Wind Wave Period",
                    "SwD": "Swell Direction",
                    "WWD": "Wind Wave Direction",
                    "STEEPNESS": "Wave Steepness",
                    "APD": "Average Wave Period",
                    "MWD": "Mean Wave Direction",
                }

                url = const.NDBC_SPEC_URL.format(buoy_id=buoy_id)
                async with session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        lines = text.strip().split("\n")
                        if len(lines) >= 2:  # Need header and at least one data line
                            headers = lines[0].strip().split()
                            # Get recent data lines for validation
                            data_lines = [line.strip().split() for line in lines[1:6]]

                            for i, header in enumerate(headers):
                                if header in wave_mapping:
                                    # Validate sensor data
                                    valid_readings = False
                                    for data_line in data_lines:
                                        try:
                                            if (
                                                i < len(data_line)
                                                and data_line[i] != "MM"
                                                and data_line[i] != "999.0"
                                                and data_line[i] != "999"
                                                and float(data_line[i])
                                            ):
                                                valid_readings = True
                                                break
                                        except ValueError:
                                            continue

                                    if valid_readings:
                                        sensor_id = f"spec_wave_{header.lower()}"
                                        sensors[sensor_id] = wave_mapping[header]
                                        _LOGGER.debug(
                                            "NDBC Buoy %s: Added spectral wave sensor: %s -> %s",
                                            buoy_id,
                                            sensor_id,
                                            wave_mapping[header],
                                        )

            elif section == const.DATA_OCEAN_CURRENT:
                # Mapping of ocean current headers to sensor names
                current_mapping: Final[dict[str, str]] = {
                    "DEPTH": "Current Depth",
                    "DRCT": "Current Direction",
                    "SPDD": "Current Speed",
                }

                url = const.NDBC_CURRENT_URL.format(buoy_id=buoy_id)
                async with session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        lines = text.strip().split("\n")
                        if len(lines) >= 2:  # Need header and at least one data line
                            headers = lines[0].strip().split()
                            # Get recent data lines for validation
                            data_lines = [line.strip().split() for line in lines[1:6]]

                            for i, header in enumerate(headers):
                                if header in current_mapping:
                                    # Validate sensor data
                                    valid_readings = False
                                    for data_line in data_lines:
                                        try:
                                            if (
                                                i < len(data_line)
                                                and data_line[i] != "MM"
                                                and data_line[i] != "999.0"
                                                and data_line[i] != "999"
                                                and float(data_line[i])
                                            ):
                                                valid_readings = True
                                                break
                                        except ValueError:
                                            continue

                                    if valid_readings:
                                        sensor_id = f"current_{header.lower()}"
                                        sensors[sensor_id] = current_mapping[header]
                                        _LOGGER.debug(
                                            "NDBC Buoy %s: Added ocean current sensor: %s -> %s",
                                            buoy_id,
                                            sensor_id,
                                            current_mapping[header],
                                        )

        _LOGGER.debug("NDBC Buoy %s: Final discovered sensors: %s", buoy_id, sensors)
        return sensors

    except Exception as err:
        _LOGGER.error("NDBC Buoy %s: Error discovering sensors: %s", err)
        return {}


def degrees_to_cardinal(degrees: float | None) -> str | None:
    """Convert degrees to cardinal direction.

    Args:
        degrees: Direction in degrees from 0-360

    Returns:
        str: Cardinal direction (N, NNE, NE, etc.) or None if degrees is None
    """
    if degrees is None:
        return None

    directions = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]

    # Convert degrees to 0-15 range for array index
    index = int((degrees + 11.25) / 22.5) % 16
    return directions[index]
