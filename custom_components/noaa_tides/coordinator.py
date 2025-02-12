"""Data update coordinator for the NOAA Tides integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import math
from typing import Any, Final, Literal, NotRequired, TypedDict

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const

_LOGGER = logging.getLogger(__name__)


# Type definitions for the data structures
class TidePrediction(TypedDict):
    """Type for tide prediction data."""

    time: datetime
    type: Literal["H", "L"]
    level: float


class SensorData(TypedDict):
    """Type for sensor data."""

    state: float | str
    attributes: dict[str, Any]


class TidePredictionAttributes(TypedDict):
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


class TidePredictionData(TypedDict):
    """Type for complete tide prediction data."""

    state: Literal["rising", "falling"]
    attributes: TidePredictionAttributes


class CurrentsPredictionData(TypedDict):
    """Type for complete currents prediction data."""

    state: Literal["ebb", "slack", "flood"]
    attributes: dict[str, Any]


class NoaaApiResponse(TypedDict):
    """Type for NOAA API response."""

    data: list[dict[str, Any]]
    predictions: NotRequired[list[dict[str, Any]]]


class CoordinatorData(TypedDict):
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


class NoaaTidesDataUpdateCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Class to manage fetching NOAA Tides data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        hub_type: Literal[const.HUB_TYPE_NOAA, const.HUB_TYPE_NDBC],
        station_id: str,
        selected_sensors: list[str],
        timezone: str = const.DEFAULT_TIMEZONE,
        unit_system: str = const.DEFAULT_UNIT_SYSTEM,
        update_interval: int = const.DEFAULT_UPDATE_INTERVAL,
        data_sections: list[str] | None = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: The Home Assistant instance
            hub_type: The type of hub (NOAA or NDBC)
            station_id: The station or buoy ID
            selected_sensors: List of selected sensor types
            timezone: The timezone setting
            unit_system: The unit system to use
            update_interval: Update interval in seconds
            data_sections: Selected data sections for NDBC
        """
        self.station_id: Final = station_id
        self.hub_type: Final = hub_type
        self.selected_sensors: Final = selected_sensors
        self.timezone: Final = timezone
        self.unit_system: Final = unit_system
        self.data_sections: Final = data_sections or []
        self.session: Final = async_get_clientsession(hass)

        super().__init__(
            hass,
            _LOGGER,
            name=const.DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch data from NOAA/NDBC APIs."""
        try:
            async with asyncio.timeout(30):
                if self.hub_type == const.HUB_TYPE_NOAA:
                    return await self._fetch_noaa_data()
                return await self._fetch_ndbc_data()
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout fetching data: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def _fetch_noaa_data(self) -> dict[str, Any]:
        """Fetch data from NOAA API."""
        data = {}
        tasks = []

        # Prepare tasks for selected sensors
        has_wind = (
            "wind_speed" in self.selected_sensors
            or "wind_direction" in self.selected_sensors
        )
        has_currents = (
            "currents_speed" in self.selected_sensors
            or "currents_direction" in self.selected_sensors
        )

        for sensor in self.selected_sensors:
            if sensor == "tide_predictions":
                tasks.append(self._fetch_tide_predictions())
            elif sensor == "currents_predictions":
                tasks.append(self._fetch_noaa_currents_predictions())
            elif sensor in "currents_speed, currents_direction":
                if has_currents:
                    tasks.append(self._fetch_noaa_currents_data())
                    has_currents = False  # Prevent duplicate tasks
            elif sensor == "water_level":
                tasks.append(self._fetch_noaa_sensor_data(sensor))
            elif sensor in ["wind_speed", "wind_direction"]:
                # Only add wind task once if either wind sensor is selected
                if has_wind:
                    tasks.append(self._fetch_noaa_wind_data())
                    has_wind = False  # Prevent duplicate tasks
            else:
                tasks.append(self._fetch_noaa_sensor_reading(sensor))

        # Execute all tasks concurrently
        async with asyncio.TaskGroup() as tg:
            results = [tg.create_task(task) for task in tasks]

        # Combine results
        for result in results:
            try:
                sensor_data = result.result()
                if sensor_data:
                    data.update(sensor_data)
            except Exception as err:
                _LOGGER.error("Error processing sensor data: %s", err)

        return data

    async def _fetch_tide_predictions(self) -> dict[str, Any]:
        """Fetch tide predictions and calculate tide state."""
        params = {
            "station": self.station_id,
            "product": "predictions",
            "datum": "MLLW",
            "time_zone": self.timezone,
            "units": "metric" if self.unit_system == const.UNIT_METRIC else "english",
            "format": "json",
            "interval": "hilo",  # Get only high/low predictions
            "begin_date": datetime.now().strftime("%Y%m%d"),
            "range": 48,  # Get 48 hours of predictions
        }

        try:
            async with self.session.get(const.NOAA_DATA_URL, params=params) as response:
                if response.status != 200:
                    raise UpdateFailed(
                        f"Error fetching tide predictions: {response.status}"
                    )

                data = await response.json()
                predictions = data.get("predictions", [])

                if not predictions:
                    return {}

                now = datetime.now()

                # Convert predictions to datetime objects
                formatted_predictions = []
                for pred in predictions:
                    pred_time = datetime.strptime(pred.get("t", ""), "%Y-%m-%d %H:%M")
                    formatted_predictions.append(
                        {
                            "time": pred_time,
                            "type": pred.get("type", ""),
                            "level": float(pred.get("v", 0)),
                        }
                    )

                # Sort predictions by time
                formatted_predictions.sort(key=lambda x: x["time"])

                # Find last tide and next tide
                last_tide = None
                next_tide = None
                following_tide = None

                for pred in formatted_predictions:
                    if pred["time"] <= now:
                        last_tide = pred
                    elif next_tide is None:
                        next_tide = pred
                    elif following_tide is None:
                        following_tide = pred
                        break

                if not (last_tide and next_tide):
                    return {}

                # Calculate tide factor and percentage
                predicted_period = (
                    next_tide["time"] - last_tide["time"]
                ).total_seconds()
                elapsed_time = (now - last_tide["time"]).total_seconds()

                if elapsed_time < 0 or elapsed_time > predicted_period:
                    return {}

                if next_tide["type"] == "H":
                    tide_factor = 50 - (
                        50 * math.cos(elapsed_time * math.pi / predicted_period)
                    )
                else:
                    tide_factor = 50 + (
                        50 * math.cos(elapsed_time * math.pi / predicted_period)
                    )

                tide_percentage = (elapsed_time / predicted_period) * 50
                if next_tide["type"] == "H":
                    tide_percentage += 50

                return {
                    "tide_predictions": {
                        "state": "rising" if next_tide["type"] == "H" else "falling",
                        "attributes": {
                            const.ATTR_NEXT_TIDE_TYPE: "High"
                            if next_tide["type"] == "H"
                            else "Low",
                            const.ATTR_NEXT_TIDE_TIME: next_tide["time"].strftime(
                                "%-I:%M %p"
                            ),
                            const.ATTR_NEXT_TIDE_LEVEL: next_tide["level"],
                            const.ATTR_FOLLOWING_TIDE_TYPE: "High"
                            if following_tide["type"] == "H"
                            else "Low",
                            const.ATTR_FOLLOWING_TIDE_TIME: following_tide[
                                "time"
                            ].strftime("%-I:%M %p"),
                            const.ATTR_FOLLOWING_TIDE_LEVEL: following_tide["level"],
                            const.ATTR_LAST_TIDE_TYPE: "High"
                            if last_tide["type"] == "H"
                            else "Low",
                            const.ATTR_LAST_TIDE_TIME: last_tide["time"].strftime(
                                "%-I:%M %p"
                            ),
                            const.ATTR_LAST_TIDE_LEVEL: last_tide["level"],
                            const.ATTR_TIDE_FACTOR: round(tide_factor, 2),
                            const.ATTR_TIDE_PERCENTAGE: round(tide_percentage, 2),
                        },
                    }
                }

        except Exception as err:
            _LOGGER.error("Error calculating tide predictions: %s", err)
            return {}

    async def _fetch_noaa_sensor_data(self, sensor_type: str) -> dict[str, Any]:
        """Fetch data for a specific NOAA sensor."""
        params = {
            "station": self.station_id,
            "product": sensor_type,
            "time_zone": self.timezone,
            "units": "metric" if self.unit_system == const.UNIT_METRIC else "english",
            "format": "json",
            "date": "latest",
        }

        # Add datum parameter for water level requests
        if sensor_type == "water_level":
            params["datum"] = "MLLW"  # Mean Lower Low Water datum

        try:
            _LOGGER.debug(
                "Fetching NOAA sensor data for %s with params: %s", sensor_type, params
            )

            async with self.session.get(const.NOAA_DATA_URL, params=params) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Error fetching %s data. Status: %s",
                        sensor_type,
                        response.status,
                    )
                    return {}

                data = await response.json()
                _LOGGER.debug("Received data for %s: %s", sensor_type, data)

                if not data.get("data"):
                    _LOGGER.error(
                        "No data returned for %s. Response: %s", sensor_type, data
                    )
                    return {}

                latest = data["data"][0]
                return {
                    sensor_type: {
                        "state": float(latest.get("v", 0)),
                        "attributes": {
                            "time": latest.get("t"),
                            "units": "meters"
                            if self.unit_system == const.UNIT_METRIC
                            else "feet",
                            "datum": "MLLW",  # Add datum to attributes
                        },
                    }
                }
        except Exception as err:
            _LOGGER.error(
                "Error fetching NOAA sensor data for %s: %s", sensor_type, err
            )
            return {}

    async def _fetch_noaa_currents_predictions(self) -> dict[str, Any]:
        """Fetch NOAA currents predictions.

        Handles two different API response formats:
        1. Predictions with explicit Type (slack/ebb/flood)
        2. Predictions with just Velocity_Major where direction must be inferred

        The method determines the current state based on either:
        - The explicit Type field if available
        - The Velocity_Major value where:
            - Velocity > 0: flood (water moving inland)
            - Velocity < 0: ebb (water moving seaward)
            - -0.1 <= Velocity <= 0.1: slack (minimal current)
        """
        params = {
            "station": self.station_id,
            "product": "currents_predictions",
            "time_zone": self.timezone,
            "units": "metric" if self.unit_system == const.UNIT_METRIC else "english",
            "format": "json",
            "begin_date": datetime.now().strftime("%Y%m%d"),
            "range": 48,  # Get 48 hours of predictions
        }

        try:
            async with self.session.get(const.NOAA_DATA_URL, params=params) as response:
                if response.status != 200:
                    raise UpdateFailed(
                        f"Error fetching currents predictions: {response.status}"
                    )

                data = await response.json()
                _LOGGER.debug("Raw currents prediction response: %s", data)

                # Get the predictions array
                predictions = data.get("current_predictions", {}).get("cp", [])

                if not predictions:
                    _LOGGER.debug("No currents predictions data available")
                    return {}

                # Get the most recent prediction
                latest = predictions[0]
                _LOGGER.debug("Latest prediction data: %s", latest)

                # Extract common values
                time = latest.get("Time", "")
                velocity = float(latest.get("Velocity_Major", 0))

                # First check for explicit Type field (Structure A)
                type_value = latest.get("Type", "").lower()

                # If no explicit type, infer from velocity (Structure B)
                if not type_value:
                    if abs(velocity) <= 0.1:  # Define slack water threshold
                        type_value = "slack"
                    elif velocity > 0:
                        type_value = "flood"
                    else:
                        type_value = "ebb"

                # Get appropriate direction based on current type
                direction = float(
                    latest.get("meanFloodDir", 0)
                    if type_value == "flood"
                    else latest.get("meanEbbDir", 0)
                    if type_value == "ebb"
                    else 0  # Use 0 for slack water
                )

                return_data = {
                    "currents_predictions": {
                        "state": type_value,
                        "attributes": {
                            const.ATTR_CURRENTS_DIRECTION: direction,
                            const.ATTR_CURRENTS_SPEED: abs(velocity),
                            const.ATTR_CURRENTS_TIME: time,
                        },
                    }
                }
                _LOGGER.debug("Returning currents prediction data: %s", return_data)
                return return_data

        except Exception as err:
            _LOGGER.error("Error fetching currents predictions: %s", err)
            return {}

    async def _fetch_noaa_currents_data(self) -> dict[str, Any]:
        """Fetch NOAA currents data."""
        params = {
            "station": self.station_id,
            "product": "currents",
            "time_zone": self.timezone,
            "units": "metric" if self.unit_system == const.UNIT_METRIC else "english",
            "format": "json",
            "date": "latest",
        }

        try:
            async with self.session.get(const.NOAA_DATA_URL, params=params) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Error fetching currents data. Status: %s", response.status
                    )
                    return {}

                data = await response.json()
                if not data.get("data"):
                    return {}

                latest = data["data"][0]
                speed = float(latest.get("s", 0))
                direction = float(latest.get("d", 0))

                return {
                    "currents_speed": {
                        "state": speed,
                        "attributes": {
                            "direction": direction,
                            "time": latest.get("t"),
                            "units": "m/s"
                            if self.unit_system == const.UNIT_METRIC
                            else "knots",
                        },
                    },
                    "currents_direction": {
                        "state": direction,
                        "attributes": {
                            "speed": speed,
                            "time": latest.get("t"),
                        },
                    },
                }

        except Exception as err:
            _LOGGER.error("Error fetching currents data: %s", err)
            return {}

    async def _fetch_noaa_wind_data(self) -> dict[str, Any]:
        """Fetch wind data from NOAA API."""
        _LOGGER.debug("Fetching wind data")

        params = {
            "station": self.station_id,
            "product": "wind",
            "time_zone": self.timezone,
            "units": "metric" if self.unit_system == const.UNIT_METRIC else "english",
            "format": "json",
            "date": "latest",
        }

        try:
            async with self.session.get(const.NOAA_DATA_URL, params=params) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "Error fetching wind data. Status: %s", response.status
                    )
                    return {}

                data = await response.json()
                if not data.get("data"):
                    return {}

                latest = data["data"][0]
                speed = float(latest.get("s", 0))
                direction = float(latest.get("d", 0))
                gust = latest.get("g")
                direction_cardinal = latest.get("dr", "")

                return {
                    "wind_speed": {
                        "state": speed,
                        "attributes": {
                            "direction": direction,
                            "direction_cardinal": direction_cardinal,
                            "gust": float(gust) if gust else None,
                            "time": latest.get("t"),
                            "flags": latest.get("f"),
                        },
                    },
                    "wind_direction": {
                        "state": direction,
                        "attributes": {
                            "direction_cardinal": direction_cardinal,
                            "speed": speed,
                            "gust": float(gust) if gust else None,
                            "time": latest.get("t"),
                            "flags": latest.get("f"),
                        },
                    },
                }

        except Exception as err:
            _LOGGER.error("Error fetching wind data: %s", err)
            return {}

    async def _fetch_noaa_sensor_reading(self, sensor_type: str) -> dict[str, Any]:
        """Fetch the latest reading for a NOAA environmental sensor."""
        if sensor_type == "wind":
            return await self._fetch_noaa_wind_data()
        params = {
            "station": self.station_id,
            "date": "latest",
            "time_zone": self.timezone,
            "units": "metric" if self.unit_system == const.UNIT_METRIC else "english",
            "format": "json",
        }

        # Map sensor types to their API parameter names
        product_map = {
            "water_temperature": "water_temperature",
            "air_temperature": "air_temperature",
            "air_pressure": "air_pressure",
            "humidity": "relative_humidity",
            "conductivity": "conductivity",
        }

        if sensor_type not in product_map:
            return {}

        params["product"] = product_map[sensor_type]

        try:
            async with self.session.get(const.NOAA_DATA_URL, params=params) as response:
                if response.status != 200:
                    return {}

                data = await response.json()
                if not data.get("data"):
                    return {}

                latest = data["data"][0]
                value = latest.get("v", None)
                if value is None:
                    return {}

                # For all other sensors, return single value
                return {
                    sensor_type: {
                        "state": float(value),
                        "attributes": {
                            "time": latest.get("t"),
                            "flags": latest.get("f"),  # Quality flags if available
                        },
                    }
                }

        except Exception as err:
            _LOGGER.error("Error fetching NOAA sensor reading: %s", err)
            return {}

    async def _fetch_ndbc_data(self) -> dict[str, Any]:
        """Fetch data from NDBC APIs."""
        data = {}
        tasks = []

        # Create tasks based on selected data sections
        if const.DATA_METEOROLOGICAL in self.data_sections:
            tasks.append(self._fetch_ndbc_meteorological())
        if const.DATA_SPECTRAL_WAVE in self.data_sections:
            tasks.append(self._fetch_ndbc_spectral_wave())
        if const.DATA_OCEAN_CURRENT in self.data_sections:
            tasks.append(self._fetch_ndbc_ocean_current())

        # Execute all tasks concurrently
        async with asyncio.TaskGroup() as tg:
            results = [tg.create_task(task) for task in tasks]

        # Combine results
        for result in results:
            try:
                section_data = result.result()
                if section_data:
                    data.update(section_data)
            except Exception as err:
                _LOGGER.error("Error processing NDBC data: %s", err)

        return data

    async def _fetch_ndbc_meteorological(self) -> dict[str, Any]:
        """Fetch meteorological data from NDBC."""
        try:
            url = const.NDBC_METEO_URL.format(buoy_id=self.station_id)
            async with self.session.get(url) as response:
                if response.status != 200:
                    return {}

                text = await response.text()
                lines = text.strip().split("\n")

                if len(lines) < 3:  # Need header, units, and at least one data line
                    return {}

                headers = lines[0].strip().split()
                units = lines[1].strip().split()  # Units line
                data = lines[2].strip().split()  # Most recent data line

                result = {}
                for i, header in enumerate(headers):
                    sensor_id = f"meteo_{header.lower()}"
                    if sensor_id in self.selected_sensors:
                        try:
                            if i < len(data) and data[i] != "MM" and data[i] != "999":
                                result[sensor_id] = {
                                    "state": float(data[i]),
                                    "attributes": {
                                        "raw_value": data[i],
                                        "unit": units[i] if i < len(units) else None,
                                    },
                                }
                        except (ValueError, IndexError):
                            _LOGGER.debug(
                                "Invalid data for sensor %s: %s",
                                sensor_id,
                                data[i] if i < len(data) else "missing",
                            )
                            continue

                return result

        except Exception as err:
            _LOGGER.error("Error fetching NDBC meteorological data: %s", err)
            return {}

    async def _fetch_ndbc_spectral_wave(self) -> dict[str, Any]:
        """Fetch spectral wave data from NDBC."""
        try:
            url = const.NDBC_SPEC_URL.format(buoy_id=self.station_id)
            async with self.session.get(url) as response:
                if response.status != 200:
                    return {}

                text = await response.text()
                lines = text.strip().split("\n")

                if len(lines) < 2:  # Need header and at least one data line
                    return {}

                # Process the spectral wave data header
                headers = lines[0].strip().split()
                data = lines[1].strip().split()  # Most recent data

                result = {}
                wave_data_map = {
                    "WVHT": "wave_height",
                    "SwH": "swell_height",
                    "SwP": "swell_period",
                    "WWH": "wind_wave_height",
                    "WWP": "wind_wave_period",
                    "SwD": "swell_direction",
                    "WWD": "wind_wave_direction",
                    "STEEPNESS": "wave_steepness",
                    "APD": "average_wave_period",
                    "MWD": "mean_wave_direction",
                }

                for i, header in enumerate(headers):
                    if (
                        i < len(data)
                        and data[i] != "MM"
                        and header in wave_data_map
                        and wave_data_map[header] in self.selected_sensors
                    ):
                        try:
                            value = float(data[i])
                            sensor_id = f"wave_{wave_data_map[header]}"
                            result[sensor_id] = {
                                "state": value,
                                "attributes": {
                                    "raw_value": data[i],
                                    "parameter": header,
                                },
                            }
                        except ValueError:
                            continue

                return result

        except Exception as err:
            _LOGGER.error("Error fetching NDBC spectral wave data: %s", err)
            return {}

    async def _fetch_ndbc_ocean_current(self) -> dict[str, Any]:
        """Fetch ocean current data from NDBC."""
        try:
            url = const.NDBC_CURRENT_URL.format(buoy_id=self.station_id)
            async with self.session.get(url) as response:
                if response.status != 200:
                    return {}

                text = await response.text()
                lines = text.strip().split("\n")

                if len(lines) < 2:  # Need header and at least one data line
                    return {}

                headers = lines[0].strip().split()
                data = lines[1].strip().split()  # Most recent data

                result = {}
                current_data_map = {
                    "DEPTH": "current_depth",
                    "DRCT": "current_direction",
                    "SPDD": "current_speed",
                }

                for i, header in enumerate(headers):
                    if (
                        i < len(data)
                        and data[i] != "MM"
                        and header in current_data_map
                        and current_data_map[header] in self.selected_sensors
                    ):
                        try:
                            value = float(data[i])
                            # Convert speed from cm/s to m/s for metric
                            if (
                                header == "SPDD"
                                and self.unit_system == const.UNIT_METRIC
                            ):
                                value = value / 100
                            sensor_id = current_data_map[header]
                            result[sensor_id] = {
                                "state": value,
                                "attributes": {
                                    "raw_value": data[i],
                                    "parameter": header,
                                },
                            }
                        except ValueError:
                            continue

                return result

        except Exception as err:
            _LOGGER.error("Error fetching NDBC ocean current data: %s", err)
            return {}
