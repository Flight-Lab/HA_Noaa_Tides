"""Utility functions for the NOAA Tides integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Final, cast

import aiohttp

from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import const
from .api_constants import (
    get_ndbc_current_url,
    get_ndbc_meteo_url,
    get_ndbc_spec_url,
    get_noaa_products_url,
    get_noaa_sensors_url,
    INVALID_DATA_VALUES,
)
from .data_constants import (
    CARDINAL_DIRECTION_STEP,
    MAX_DATA_LINES_TO_CHECK,
    LogMessages,
)
from .types import (
    StationType,
    NoaaProductResponse,
    NoaaSensorResponse,
    NoaaTidesSensorEntityDescription,
)

_LOGGER: Final = logging.getLogger(__name__)


async def validate_noaa_station(hass: HomeAssistant, station_id: str) -> bool:
    """Validate a NOAA station ID by checking the products endpoint.

    Args:
        hass: HomeAssistant instance
        station_id: NOAA station identifier to validate

    Returns:
        bool: True if station is valid, False otherwise

    """
    return await validate_data_source(hass, station_id, const.STATION_TYPE_NOAA)


async def validate_ndbc_buoy(
    hass: HomeAssistant, buoy_id: str, data_sections: list[str] | None = None
) -> bool:
    """Validate an NDBC buoy ID by checking the specified data sections.

    Args:
        hass: HomeAssistant instance
        buoy_id: NDBC buoy identifier to validate
        data_sections: Data sections to check for validation (optional)

    Returns:
        bool: True if buoy is valid, False otherwise

    """
    # Always check all sections regardless of what was passed
    all_sections = list(const.DATA_SECTIONS)
    _LOGGER.debug(f"NDBC Buoy {buoy_id}: Validating buoy ID with all data sections")
    return await validate_data_source(hass, buoy_id, const.STATION_TYPE_NDBC, all_sections)


def _deduplicate_overlapping_sensors(sensors: dict[str, str]) -> dict[str, str]:
    """Remove duplicate sensors, preferring spectral wave data over meteorological.

    Prioritizes higher quality data sources when the same measurement is available
    from multiple sources. Currently handles wave height, wave period, and wave direction.

    Args:
        sensors: Dictionary of discovered sensors

    Returns:
        dict[str, str]: Deduplicated sensors dictionary

    """
    result = sensors.copy()

    # Check for overlapping sensors and remove the lower quality ones
    for meteo_sensor, spec_sensor in const.OVERLAPPING_SENSORS.items():
        if meteo_sensor in result and spec_sensor in result:
            # If both sensors exist, remove the meteorological one
            sensor_type = "wave measurement"
            if "wvht" in meteo_sensor:
                sensor_type = "wave height"
            elif "apd" in meteo_sensor:
                sensor_type = "average wave period"
            elif "mwd" in meteo_sensor:
                sensor_type = "wave direction"

            result.pop(meteo_sensor)
            _LOGGER.debug(
                f"Preferring {spec_sensor} over {meteo_sensor} for {sensor_type} measurement"
            )

    return result


def determine_required_data_sections(selected_sensors: list[str]) -> list[str]:
    """Determine which data sections are needed based on selected sensors.

    Args:
        selected_sensors: List of selected sensor IDs

    Returns:
        list[str]: List of required data sections

    """
    required_sections = set()

    for sensor in selected_sensors:
        for section, sensors in const.SENSOR_SECTION_MAP.items():
            if sensor in sensors:
                required_sections.add(section)
                break

    return list(required_sections)


async def discover_noaa_sensors(hass: HomeAssistant, station_id: str) -> dict[str, str]:
    """Discover available sensors for a NOAA station.

    Args:
        hass: HomeAssistant instance
        station_id: NOAA station identifier

    Returns:
        dict[str, str]: Dictionary mapping sensor keys to display names

    """
    _LOGGER.debug(f"NOAA Station {station_id}: Starting NOAA sensor discovery")
    try:
        session = async_get_clientsession(hass)
        sensors: dict[str, str] = {}

        # Create tasks for both endpoints
        products_url = get_noaa_products_url(station_id)
        sensors_url = get_noaa_sensors_url(station_id)

        async with asyncio.TaskGroup() as tg:
            products_task = tg.create_task(session.get(products_url))
            sensors_task = tg.create_task(session.get(sensors_url))

        # Process products endpoint response
        if products_task.result().status == 200:
            products_data = cast(
                NoaaProductResponse, await products_task.result().json()
            )
            products = products_data.get("products", [])
            _LOGGER.debug(f"NOAA Station {station_id}: Found products: {products}")

            # Map product names to sensors
            for product in products:
                name = product.get("name", "").lower()
                _LOGGER.debug(
                    f"NOAA Station {station_id}: Processing product name: {name}"
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
                    f"NOAA Station {station_id}: Raw sensors data: {sensors_data}"
                )

                for sensor in available_sensors:
                    sensor_name = sensor.get("name", "").lower()
                    _LOGGER.debug(
                        f"NOAA Station {station_id}: Found NOAA sensor name: {sensor_name}"
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
                    f"NOAA Station {station_id}: Error processing sensors data: {err} ({type(err).__name__})"
                )

        _LOGGER.debug(
            LogMessages.SENSORS_DISCOVERED.format(
                source_type="NOAA Station",
                source_id=station_id,
                sensor_count=len(sensors)
            )
        )
        return sensors

    except Exception as err:
        _LOGGER.error(
            f"NOAA Station {station_id}: Error discovering sensors: {err} ({type(err).__name__})"
        )
        return {}


async def discover_ndbc_sensors(
    hass: HomeAssistant, buoy_id: str, data_sections: list[str]
) -> dict[str, str]:
    """Discover available sensors for an NDBC buoy.

    Args:
        hass: HomeAssistant instance
        buoy_id: NDBC buoy identifier
        data_sections: Selected data sections to check

    Returns:
        dict[str, str]: Dictionary mapping sensor keys to display names

    """
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
                url = get_ndbc_meteo_url(buoy_id)
                async with session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        lines = text.strip().split("\n")
                        if (
                            len(lines) >= 3
                        ):  # Need header, units, and at least one data line
                            headers = lines[0].strip().split()
                            units = lines[1].strip().split()  # Skip units line

                            # Get actual data lines, skipping headers and units (limit to prevent infinite loops)
                            data_lines = [line.strip().split() for line in lines[2:MAX_DATA_LINES_TO_CHECK]]

                            for i, header in enumerate(headers):
                                if header in meteo_mapping:
                                    # Check if sensor has valid data in recent readings
                                    valid_readings = False
                                    for data_line in data_lines:
                                        try:
                                            if (
                                                i < len(data_line)
                                                and data_line[i] not in INVALID_DATA_VALUES
                                                and float(data_line[i])
                                            ):  # Verify it's a valid number
                                                valid_readings = True
                                                break
                                        except ValueError:
                                            continue

                                    _LOGGER.debug(
                                        f"NDBC Buoy {buoy_id}: Checking sensor {header}: valid_readings={valid_readings}, "
                                        f"first_value={data_lines[0][i] if i < len(data_lines[0]) else 'out of range'}"
                                    )

                                    if valid_readings:
                                        sensor_id = f"meteo_{header.lower()}"
                                        sensors[sensor_id] = meteo_mapping[header]
                                        _LOGGER.debug(
                                            f"NDBC Buoy {buoy_id}: Added sensor: {sensor_id} -> {meteo_mapping[header]}"
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

                url = get_ndbc_spec_url(buoy_id)
                async with session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        lines = text.strip().split("\n")
                        if len(lines) >= 2:  # Need header and at least one data line
                            headers = lines[0].strip().split()
                            # Get recent data lines for validation (limit to prevent infinite loops)
                            data_lines = [line.strip().split() for line in lines[1:6]]

                            for i, header in enumerate(headers):
                                if header in wave_mapping:
                                    # Validate sensor data
                                    valid_readings = False
                                    for data_line in data_lines:
                                        try:
                                            if (
                                                i < len(data_line)
                                                and data_line[i] not in INVALID_DATA_VALUES
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
                                            f"NDBC Buoy {buoy_id}: Added spectral wave sensor: "
                                            f"{sensor_id} -> {wave_mapping[header]}"
                                        )

            elif section == const.DATA_OCEAN_CURRENT:
                # Mapping of ocean current headers to sensor names
                current_mapping: Final[dict[str, str]] = {
                    "DEPTH": "Current Depth",
                    "DRCT": "Current Direction",
                    "SPDD": "Current Speed",
                }

                url = get_ndbc_current_url(buoy_id)
                async with session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        lines = text.strip().split("\n")
                        if len(lines) >= 2:  # Need header and at least one data line
                            headers = lines[0].strip().split()
                            # Get recent data lines for validation (limit to prevent infinite loops)
                            data_lines = [line.strip().split() for line in lines[1:6]]

                            for i, header in enumerate(headers):
                                if header in current_mapping:
                                    # Validate sensor data
                                    valid_readings = False
                                    for data_line in data_lines:
                                        try:
                                            if (
                                                i < len(data_line)
                                                and data_line[i] not in INVALID_DATA_VALUES
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
                                            f"NDBC Buoy {buoy_id}: Added ocean current sensor: "
                                            f"{sensor_id} -> {current_mapping[header]}"
                                        )

        # Deduplicate overlapping sensors, preferring spectral wave over meteorological
        deduplicated_sensors = _deduplicate_overlapping_sensors(sensors)

        if len(deduplicated_sensors) < len(sensors):
            _LOGGER.debug(
                f"NDBC Buoy {buoy_id}: Deduplicated overlapping wave sensors for better accuracy"
            )

        _LOGGER.debug(
            LogMessages.SENSORS_DISCOVERED.format(
                source_type="NDBC Buoy",
                source_id=buoy_id,
                sensor_count=len(deduplicated_sensors)
            )
        )
        return deduplicated_sensors

    except Exception as err:
        _LOGGER.error(
            f"NDBC Buoy {buoy_id}: Error discovering sensors: {err} ({type(err).__name__})"
        )
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
    index = int((degrees + 11.25) / CARDINAL_DIRECTION_STEP) % 16
    return directions[index]


def get_unit_for_sensor(
    sensor_description: NoaaTidesSensorEntityDescription,
    unit_system: str,
    station_type: str,
    sensor_id: str,
) -> str | None:
    """Get the appropriate unit for a sensor based on unit system and station type.

    Note: Temperature sensors no longer use this logic as HA handles conversion automatically.

    Args:
        sensor_description: The sensor entity description
        unit_system: The chosen unit system (UNIT_METRIC or UNIT_IMPERIAL)
        station_type: The station type (STATION_TYPE_NOAA or STATION_TYPE_NDBC)
        sensor_id: The sensor identifier

    Returns:
        str | None: The appropriate unit or None if not applicable

    """
    # For NOAA sensors with explicit unit configuration in description
    if (
        not sensor_description.is_ndbc
        and sensor_description.unit_metric
        and sensor_description.unit_imperial
    ):
        return (
            sensor_description.unit_metric
            if unit_system == const.UNIT_METRIC
            else sensor_description.unit_imperial
        )

    # For NDBC sensors (non-temperature conversions only)
    if sensor_description.is_ndbc:
        if unit_system == const.UNIT_IMPERIAL:
            # Wind speed conversions (WSPD, GST) - m/s to mph
            if sensor_id.endswith(("_wspd", "_gst")):
                return UnitOfSpeed.MILES_PER_HOUR
            # Wave height conversions (WVHT, SwH, WWH) - meters to feet
            elif sensor_id.endswith(("_wvht", "_swh", "_wwh")):
                return UnitOfLength.FEET
            # Pressure conversion (PRES) - hPa to inHg
            elif sensor_id.endswith("_pres"):
                return UnitOfPressure.INHG
        elif sensor_id.endswith(("_wvht", "_swh", "_wwh")):
            return UnitOfLength.METERS

        # Temperature sensors: Always return Celsius (HA handles conversion)
        if sensor_id.endswith(("_atmp", "_wtmp", "_dewp")):
            return UnitOfTemperature.CELSIUS

    # Default: use the native unit from the description
    return sensor_description.native_unit_of_measurement


# Composite sensor group definitions
COMPOSITE_SENSOR_GROUPS: dict[str, list[str]] = {
    "wind_direction": ["wind_speed"],
    "wind_speed": ["wind_direction"],
    "currents_direction": ["currents_speed"],
    "currents_speed": ["currents_direction"],
}


def is_part_of_composite_sensor(sensor_key: str) -> bool:
    """Check if a sensor is part of a composite sensor group.

    Some sensors like wind_direction and wind_speed are related and
    are fetched together from the API.

    Args:
        sensor_key: The sensor key to check

    Returns:
        bool: True if this sensor is part of a composite group

    """
    return sensor_key in COMPOSITE_SENSOR_GROUPS


def get_related_sensors(sensor_key: str) -> list[str]:
    """Get the related sensors for a composite sensor.

    Args:
        sensor_key: The sensor key to get related sensors for

    Returns:
        list[str]: List of related sensor keys

    """
    return COMPOSITE_SENSOR_GROUPS.get(sensor_key, [])
