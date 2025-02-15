"""Data update coordinator for the NOAA Tides integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import math
from typing import Any, Final, Literal, NotRequired, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const

from .utils import degrees_to_cardinal, handle_ndbc_api_error, handle_noaa_api_error

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

    state: str
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
            error_handler = (
                handle_noaa_api_error
                if self.hub_type == const.HUB_TYPE_NOAA
                else handle_ndbc_api_error
            )
            api_error = await error_handler(err, self.station_id)
            _LOGGER.error(
                "%s %s: %s Technical details: %s",
                "NOAA Station" if self.hub_type == const.HUB_TYPE_NOAA else "NDBC Buoy",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
            raise UpdateFailed(api_error.message)
        except Exception as err:
            error_handler = (
                handle_noaa_api_error
                if self.hub_type == const.HUB_TYPE_NOAA
                else handle_ndbc_api_error
            )
            api_error = await error_handler(err, self.station_id)
            _LOGGER.error(
                "%s %s: %s Technical details: %s",
                "NOAA Station" if self.hub_type == const.HUB_TYPE_NOAA else "NDBC Buoy",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
            raise UpdateFailed(api_error.message)

    async def _fetch_noaa_data(self) -> dict[str, Any]:
        """Fetch data from NOAA API."""
        try:
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
                    _LOGGER.error(
                        "NOAA Station %s: Error processing sensor data: %s",
                        self.station_id,
                        err,
                    )

            return data
        except Exception as err:
            api_error = await handle_noaa_api_error(err, self.station_id)
            _LOGGER.error(
                "NOAA Station %s: Error fetching data: %s. Technical details: %s",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
            raise UpdateFailed(api_error.message)

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
                    error_msg = f"NOAA Station{self.station_id}: Error fetching tide predictions"
                    _LOGGER.error("%s: HTTP %s", error_msg, response.status)
                    raise UpdateFailed(error_msg)

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

                # Format the tide state to show next tide and time
                next_tide_type = "High" if next_tide["type"] == "H" else "Low"
                next_tide_time = next_tide["time"].strftime("%-I:%M %p")
                tide_state = f"{next_tide_type} tide at {next_tide_time}"

                return {
                    "tide_predictions": {
                        "state": tide_state,
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
            api_error = await handle_noaa_api_error(err, self.station_id)
            _LOGGER.error(
                "NOAA Station %s: Error calculating tide predictions: %s. Technical details: %s",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )

    async def _fetch_noaa_sensor_data(self, sensor_type: str) -> dict[str, Any]:
        """Fetch data for a specific NOAA sensor.

        Args:
            sensor_type: The type of sensor to fetch data for (e.g., 'water_level')

        Returns:
            dict[str, Any]: Dictionary containing the sensor data if available
        """
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
                "NOAA Station %s: Fetching sensor data for %s with params: %s",
                self.station_id,
                sensor_type,
                {
                    k: v for k, v in params.items() if k != "format"
                },  # Exclude format for cleaner logs
            )

            async with self.session.get(const.NOAA_DATA_URL, params=params) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "NOAA Station %s: Error fetching %s data. Status: %s",
                        self.station_id,
                        sensor_type,
                        response.status,
                    )
                    return {}

                data = await response.json()

                if not data.get("data"):
                    _LOGGER.error(
                        "NOAA Station %s: No data returned for %s. Response: %s",
                        self.station_id,
                        sensor_type,
                        data,
                    )
                    return {}

                latest = data["data"][0]

                # Only log the latest data point for water level at debug level
                if sensor_type == "water_level":
                    _LOGGER.debug(
                        "NOAA Station %s: Latest water level reading - Value: %s %s, Time: %s, Datum: MLLW",
                        self.station_id,
                        latest.get("v", "N/A"),
                        "meters" if self.unit_system == const.UNIT_METRIC else "feet",
                        latest.get("t", "N/A"),
                    )

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
                "NOAA Station %s: Error fetching sensor data for %s: %s",
                self.station_id,
                sensor_type,
                err,
            )
            return {}

    async def _fetch_noaa_currents_predictions(self) -> dict[str, Any]:
        """Fetch NOAA currents predictions.

        Handles two different API response formats:
        1. Predictions with explicit Type (slack/ebb/flood)
        2. Predictions with just Velocity_Major where direction must be inferred

        Returns:
            dict[str, Any]: Dictionary containing currents prediction data if available
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
                        f"{self.station_id}: Error fetching currents predictions: {response.status}"
                    )

                data = await response.json()

                # Get the predictions array
                predictions = data.get("current_predictions", {}).get("cp", [])

                if not predictions:
                    _LOGGER.debug(
                        "NOAA Station %s: No currents predictions data available",
                        self.station_id,
                    )
                    return {}

                # Get the most recent prediction
                latest = predictions[0]

                # Log only relevant fields from the latest prediction
                _LOGGER.debug(
                    "NOAA Station %s: Latest currents prediction - Time: %s, Velocity: %s, Type: %s, "
                    "Flood Dir: %s, Ebb Dir: %s",
                    self.station_id,
                    latest.get("Time", "N/A"),
                    latest.get("Velocity_Major", "N/A"),
                    latest.get("Type", "N/A"),
                    latest.get("meanFloodDir", "N/A"),
                    latest.get("meanEbbDir", "N/A"),
                )

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

                # Log the processed and structured return data
                _LOGGER.debug(
                    "NOAA Station %s: Processed currents prediction - State: %s, Direction: %.1f°, "
                    "Speed: %.2f %s, Time: %s",
                    self.station_id,
                    type_value,
                    direction,
                    abs(velocity),
                    "m/s" if self.unit_system == const.UNIT_METRIC else "knots",
                    time,
                )

                return return_data

        except Exception as err:
            api_error = await handle_noaa_api_error(err, self.station_id)
            _LOGGER.error(
                "NOAA Station %s: Error fetching currents predictions: %s. Technical details: %s",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
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
                        "NOAA Station %s: Error fetching currents data. Status: %s",
                        self.station_id,
                        response.status,
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
            api_error = await handle_noaa_api_error(err, self.station_id)
            _LOGGER.error(
                "NOAA Station %s: Error fetching currents data: %s. Technical details: %s",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
            return {}

    async def _fetch_noaa_wind_data(self) -> dict[str, Any]:
        """Fetch wind data from NOAA API."""
        _LOGGER.debug("NOAA Station %s: Fetching wind data", self.station_id)

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
                        "NOAA Station %s: Error fetching wind data. Status: %s",
                        self.station_id,
                        response.status,
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
            api_error = await handle_noaa_api_error(err, self.station_id)
            _LOGGER.error(
                "NOAA Station %s: Error fetching wind data: %s. Technical details: %s",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
            return {}

    async def _fetch_noaa_sensor_reading(self, sensor_type: str) -> dict[str, Any]:
        """Fetch the latest reading for a NOAA environmental sensor."""
        if sensor_type == "wind":
            return await self._fetch_noaa_wind_data()
        try:
            params = {
                "station": self.station_id,
                "date": "latest",
                "time_zone": self.timezone,
                "units": "metric"
                if self.unit_system == const.UNIT_METRIC
                else "english",
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

        except asyncio.TimeoutError as err:
            api_error = await handle_noaa_api_error(err, self.station_id)
            _LOGGER.error(
                "NOAA Station %s: Timeout fetching sensor %s: %s. Technical details: %s",
                self.station_id,
                sensor_type,
                api_error.message,
                api_error.technical_detail or "None",
            )
            return {}
        except ValueError as err:
            # Handle value conversion errors
            _LOGGER.error(
                "NOAA Station %s: Invalid value received for sensor %s at station %s: %s",
                self.station_id,
                sensor_type,
                err,
            )
            return {}
        except Exception as err:
            api_error = await handle_noaa_api_error(err, self.station_id)
            _LOGGER.error(
                "NOAA Station %s: Error fetching sensor %s: %s. Technical details: %s",
                self.station_id,
                sensor_type,
                api_error.message,
                api_error.technical_detail or "None",
            )
            return {}

    async def _fetch_ndbc_data(self) -> dict[str, Any]:
        """Fetch data from NDBC APIs."""
        try:
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
                    _LOGGER.error(
                        "NDBC Buoy %s: Error processing data: %s", self.station_id, err
                    )

            return data
        except Exception as err:
            api_error = await handle_ndbc_api_error(err, self.station_id)
            _LOGGER.error(
                "NDBC Buoy %s: Error fetching data: %s. Technical details: %s",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
            raise UpdateFailed(api_error.message)

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
                                # Round initial value to 2 decimal places
                                value = round(float(data[i]), 2)

                                # Convert values if imperial units are requested
                                if self.unit_system == const.UNIT_IMPERIAL:
                                    # Temperature conversions (ATMP, WTMP, DEWP) - Celsius to Fahrenheit
                                    if header in ["ATMP", "WTMP", "DEWP"]:
                                        value = round((value * 9 / 5) + 32, 2)

                                    # Wind speed and gust conversions (WSPD, GST) - m/s to mph
                                    elif header in ["WSPD", "GST"]:
                                        value = round(value * 2.23694, 2)

                                    # Wave height conversion (WVHT) - meters to feet
                                    elif header == "WVHT":
                                        value = round(value * 3.28084, 2)

                                    # Pressure conversion (PRES) - hPa to inHg
                                    elif header == "PRES":
                                        value = round(value * 0.02953, 2)

                                # Initialize empty attributes dictionary
                                attributes = {}

                                # Add attributes based on sensor type
                                if header in ["WDIR", "MWD"]:  # Direction sensors
                                    cardinal = degrees_to_cardinal(value)
                                    if cardinal:
                                        attributes["direction_cardinal"] = cardinal
                                elif header in [
                                    "WSPD",
                                    "GST",
                                    "WVHT",
                                    "PRES",
                                    "ATMP",
                                    "WTMP",
                                    "DEWP",
                                ]:
                                    # Store the original (unconverted) value and unit
                                    attributes["raw_value"] = str(
                                        round(float(data[i]), 2)
                                    )
                                    attributes["unit"] = (
                                        units[i] if i < len(units) else None
                                    )

                                result[sensor_id] = {
                                    "state": value,
                                    "attributes": attributes,
                                }
                        except (ValueError, IndexError):
                            _LOGGER.debug(
                                "Buoy %s: Invalid data for sensor %s: %s",
                                self.station_id,
                                sensor_id,
                                data[i] if i < len(data) else "missing",
                            )
                            continue

                return result

        except Exception as err:
            api_error = await handle_ndbc_api_error(err, self.station_id)
            _LOGGER.error(
                "NDBC Buoy %s: Error fetching NDBC meteorological data: %s. Technical details: %s",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
            return {}

    async def _fetch_ndbc_spectral_wave(self) -> dict[str, Any]:
        """Fetch spectral wave data from NDBC."""
        try:
            url = const.NDBC_SPEC_URL.format(buoy_id=self.station_id)
            async with self.session.get(url) as response:
                if response.status != 200:
                    _LOGGER.error(
                        "NDBC Buoy %s: Error fetching spectral wave data. Status: %s",
                        self.station_id,
                        response.status,
                    )
                    return {}

                text = await response.text()
                lines = text.strip().split("\n")

                if len(lines) < 3:  # Need header, units, and at least one data line
                    _LOGGER.warning(
                        "NDBC Buoy %s: Insufficient data in spectral wave response",
                        self.station_id,
                    )
                    return {}

                headers = lines[0].strip().split()
                units = lines[1].strip().split()  # Units line
                data = lines[2].strip().split()  # Most recent data line

                result = {}
                for i, header in enumerate(headers):
                    sensor_id = f"spec_wave_{header.lower()}"
                    if sensor_id not in self.selected_sensors:
                        continue

                    try:
                        if i < len(data) and data[i] not in [
                            "MM",
                            "999",
                            "999.0",
                            "",
                            "N/A",
                        ]:
                            # Round initial value to 2 decimal places
                            value = round(float(data[i]), 2)

                            # Convert values if imperial units are requested
                            if self.unit_system == const.UNIT_IMPERIAL:
                                # Wave height conversions (WVHT, SwH, WWH) - meters to feet
                                if header in ["WVHT", "SwH", "WWH"]:
                                    value = round(value * 3.28084, 2)

                            # Initialize empty attributes dictionary
                            attributes = {}

                            # Add attributes based on sensor type
                            if header in ["SwD", "WWD", "MWD"]:  # Direction sensors
                                cardinal = degrees_to_cardinal(value)
                                if cardinal:
                                    attributes["direction_cardinal"] = cardinal
                            elif header in ["WVHT", "SwH", "WWH"]:
                                # Store the original (unconverted) value and unit
                                attributes["raw_value"] = str(round(float(data[i]), 2))
                                attributes["unit"] = (
                                    units[i] if i < len(units) else None
                                )

                            result[sensor_id] = {
                                "state": value,
                                "attributes": attributes,
                            }
                    except (ValueError, IndexError):
                        _LOGGER.debug(
                            "NDBC Buoy %s: Invalid data for sensor %s: %s",
                            self.station_id,
                            sensor_id,
                            data[i] if i < len(data) else "missing",
                        )
                        continue

                _LOGGER.debug(
                    "NDBC Buoy %s: Spectral wave sensors processed: %s",
                    self.station_id,
                    list(result.keys()),
                )
                return result

        except Exception as err:
            api_error = await handle_ndbc_api_error(err, self.station_id)
            _LOGGER.error(
                "NDBC Buoy %s: Error processing spectral wave data: %s. Technical details: %s",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
            return {}

    async def _fetch_ndbc_ocean_current(self) -> dict[str, Any]:
        """Fetch ocean current data from NDBC.

        Not all NDBC buoys have current sensors, so handle 404 errors gracefully.

        Returns:
            dict[str, Any]: Dictionary containing ocean current sensor data if available
        """
        try:
            session = async_get_clientsession(self.hass)
            url = const.NDBC_CURRENT_URL.format(buoy_id=self.station_id)

            async with session.get(url) as response:
                if response.status == 404:
                    _LOGGER.debug(
                        "NDBC Buoy %s: Ocean current data not available - this is normal as not all buoys have current sensors",
                        self.station_id,
                    )
                    return {}

                if response.status != 200:
                    _LOGGER.error(
                        "NDBC Buoy %s: Error fetching ocean current data. Status: %s",
                        self.station_id,
                        response.status,
                    )
                    return {}

                text = await response.text()
                lines = text.strip().split("\n")

                if len(lines) < 2:  # Need header and at least one data line
                    _LOGGER.debug(
                        "NDBC Buoy %s: Insufficient ocean current data in response",
                        self.station_id,
                    )
                    return {}

                headers = lines[0].strip().split()
                # Get recent data lines for validation
                data_lines = [line.strip().split() for line in lines[1:6]]

                result = {}
                for i, header in enumerate(headers):
                    # Create sensor_id in the same format as utils.py discovery
                    sensor_id = f"current_{header.lower()}"
                    if sensor_id not in self.selected_sensors:
                        continue

                    # Validate sensor data across recent readings
                    valid_readings = False
                    latest_value = None

                    for data_line in data_lines:
                        try:
                            if (
                                i < len(data_line)
                                and data_line[i]
                                not in ["MM", "999", "999.0", "", "N/A"]
                                and float(data_line[i])
                            ):
                                valid_readings = True
                                if latest_value is None:  # Store first valid reading
                                    latest_value = float(data_line[i])
                                break
                        except (ValueError, IndexError):
                            continue

                    if valid_readings and latest_value is not None:
                        # Initialize empty attributes dictionary
                        attributes = {}

                        # Add attributes based on sensor type
                        if header == "DRCT":  # Direction sensors
                            attributes["direction_cardinal"] = degrees_to_cardinal(
                                latest_value
                            )
                        elif header in ["DEPTH", "SPDD"]:  # Measurement sensors
                            attributes["raw_value"] = str(latest_value)
                            attributes["units"] = (
                                "meters" if header == "DEPTH" else "m/s"
                            )

                        result[sensor_id] = {
                            "state": latest_value,
                            "attributes": attributes,
                        }

                _LOGGER.debug(
                    "NDBC Buoy %s: Ocean current sensors processed: %s",
                    self.station_id,
                    list(result.keys()),
                )
                return result

        except Exception as err:
            _LOGGER.error(
                "NDBC Buoy %s: Error processing ocean current data: %s",
                self.station_id,
                err,
            )
            return {}
