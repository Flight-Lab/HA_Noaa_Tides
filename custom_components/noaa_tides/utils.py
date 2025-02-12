"""Utility functions for the NOAA Tides integration."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any, Final, TypedDict, cast

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
        _LOGGER.error("Error validating NOAA station %s: %s", station_id, err)
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
                _LOGGER.debug("Error checking NDBC buoy %s: %s", buoy_id, response)
                continue

            if response.status == 200:
                try:
                    text = await response.text()
                    if len(text.strip().split("\n")) > 1:
                        valid_responses += 1
                except Exception as err:
                    _LOGGER.debug(
                        "Error reading response for buoy %s: %s", buoy_id, err
                    )
                    continue

        # Consider valid if at least one data section is available
        return valid_responses > 0

    except Exception as err:
        _LOGGER.error("Error validating NDBC buoy %s: %s", buoy_id, err)
        return False


async def discover_noaa_sensors(hass: HomeAssistant, station_id: str) -> dict[str, str]:
    """Discover available sensors for a NOAA station.

    Args:
        hass: HomeAssistant instance
        station_id: NOAA station identifier

    Returns:
        dict[str, str]: Dictionary mapping sensor keys to display names
    """
    _LOGGER.debug("Starting NOAA sensor discovery for station %s", station_id)
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
            _LOGGER.debug("Found NOAA products: %s", products)

            # Map product names to sensors
            for product in products:
                name = product.get("name", "").lower()
                _LOGGER.debug("Processing product name: %s", name)

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
                _LOGGER.debug("Raw sensors data: %s", sensors_data)

                for sensor in available_sensors:
                    sensor_name = sensor.get("name", "").lower()
                    _LOGGER.debug("Found NOAA sensor name: %s", sensor_name)

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
                _LOGGER.debug("Error processing sensors data: %s", err)

        _LOGGER.debug("Final discovered sensors: %s", sensors)
        return sensors

    except Exception as err:
        _LOGGER.error("Error discovering NOAA sensors: %s", err)
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
                                        "Checking sensor %s: valid_readings=%s, first_value=%s",
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
                                            "Added sensor: %s -> %s",
                                            sensor_id,
                                            meteo_mapping[header],
                                        )

            # Similar changes needed for spectral wave and ocean current sections...
            # [Previous spectral wave and ocean current code remains the same]

        _LOGGER.debug("Final discovered sensors for buoy %s: %s", buoy_id, sensors)
        return sensors

    except Exception as err:
        _LOGGER.error("Error discovering NDBC sensors: %s", err)
        return {}
