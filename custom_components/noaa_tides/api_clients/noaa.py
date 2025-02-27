"""NOAA API client for NOAA Tides integration."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import math
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from ..const import (
    ATTR_CURRENTS_DIRECTION,
    ATTR_CURRENTS_SPEED,
    ATTR_CURRENTS_TIME,
    ATTR_FOLLOWING_TIDE_LEVEL,
    ATTR_FOLLOWING_TIDE_TIME,
    ATTR_FOLLOWING_TIDE_TYPE,
    ATTR_LAST_TIDE_LEVEL,
    ATTR_LAST_TIDE_TIME,
    ATTR_LAST_TIDE_TYPE,
    ATTR_NEXT_TIDE_LEVEL,
    ATTR_NEXT_TIDE_TIME,
    ATTR_NEXT_TIDE_TYPE,
    ATTR_TIDE_FACTOR,
    ATTR_TIDE_PERCENTAGE,
    NOAA_DATA_URL,
    UNIT_IMPERIAL,
    UNIT_METRIC,
)
from ..types import CoordinatorData
from .base import BaseApiClient

_LOGGER: Final = logging.getLogger(__name__)


class NoaaApiClient(BaseApiClient):
    """API client for NOAA data sources.

    Handles fetching data from NOAA APIs with appropriate error handling
    and data processing for each endpoint.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        station_id: str,
        timezone: str,
        unit_system: str,
    ) -> None:
        """Initialize the NOAA API client.

        Args:
            hass: The Home Assistant instance
            station_id: The station ID
            timezone: The timezone setting
            unit_system: The unit system to use
        """
        super().__init__(hass, station_id, timezone, unit_system)
        self._is_noaa = True

    async def fetch_data(self, selected_sensors: list[str]) -> CoordinatorData:
        """Fetch data from NOAA API for selected sensors.

        Args:
            selected_sensors: List of sensors to fetch

        Returns:
            CoordinatorData: The fetched data

        Raises:
            UpdateFailed: If there's an error fetching data
        """
        try:
            data: CoordinatorData = {}
            tasks = []

            # Prepare tasks for selected sensors
            has_wind = (
                "wind_speed" in selected_sensors or "wind_direction" in selected_sensors
            )
            has_currents = (
                "currents_speed" in selected_sensors
                or "currents_direction" in selected_sensors
            )

            for sensor in selected_sensors:
                if sensor == "tide_predictions":
                    tasks.append(self._fetch_tide_predictions())
                elif sensor == "currents_predictions":
                    tasks.append(self._fetch_currents_predictions())
                elif sensor in ["currents_speed", "currents_direction"]:
                    if has_currents:
                        tasks.append(self._fetch_currents_data())
                        has_currents = False  # Prevent duplicate tasks
                elif sensor == "water_level":
                    tasks.append(self._fetch_sensor_data(sensor))
                elif sensor in ["wind_speed", "wind_direction"]:
                    # Only add wind task once if either wind sensor is selected
                    if has_wind:
                        tasks.append(self._fetch_wind_data())
                        has_wind = False  # Prevent duplicate tasks
                else:
                    tasks.append(self._fetch_sensor_reading(sensor))

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
                        "NOAA Station %s: Error processing sensor data: %s (%s)",
                        self.station_id,
                        str(err),
                        type(err).__name__,
                    )

            return data

        except Exception as err:
            api_error = await self.handle_error(err)
            self._log_error(api_error)
            raise UpdateFailed(api_error.message)

    async def _fetch_tide_predictions(self) -> dict[str, Any]:
        """Fetch tide predictions and calculate tide state.

        Returns:
            dict[str, Any]: Dictionary containing tide prediction data if available
        """
        params = {
            "station": self.station_id,
            "product": "predictions",
            "datum": "MLLW",
            "time_zone": self.timezone,
            "units": "metric" if self.unit_system == UNIT_METRIC else "english",
            "format": "json",
            "interval": "hilo",  # Get only high/low predictions
            "begin_date": datetime.now().strftime("%Y%m%d"),
            "range": 48,  # Get 48 hours of predictions
        }

        try:
            data = await self._safe_request_with_retry(
                NOAA_DATA_URL, params=params, operation="fetching tide predictions"
            )
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
            predicted_period = (next_tide["time"] - last_tide["time"]).total_seconds()
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
                        ATTR_NEXT_TIDE_TYPE: "High"
                        if next_tide["type"] == "H"
                        else "Low",
                        ATTR_NEXT_TIDE_TIME: next_tide["time"].strftime("%-I:%M %p"),
                        ATTR_NEXT_TIDE_LEVEL: next_tide["level"],
                        ATTR_FOLLOWING_TIDE_TYPE: "High"
                        if following_tide["type"] == "H"
                        else "Low",
                        ATTR_FOLLOWING_TIDE_TIME: following_tide["time"].strftime(
                            "%-I:%M %p"
                        ),
                        ATTR_FOLLOWING_TIDE_LEVEL: following_tide["level"],
                        ATTR_LAST_TIDE_TYPE: "High"
                        if last_tide["type"] == "H"
                        else "Low",
                        ATTR_LAST_TIDE_TIME: last_tide["time"].strftime("%-I:%M %p"),
                        ATTR_LAST_TIDE_LEVEL: last_tide["level"],
                        ATTR_TIDE_FACTOR: round(tide_factor, 2),
                        ATTR_TIDE_PERCENTAGE: round(tide_percentage, 2),
                    },
                }
            }

        except UpdateFailed:
            return {}
        except Exception as err:
            _LOGGER.error(
                "NOAA Station %s: Error calculating tide predictions: %s (%s)",
                self.station_id,
                str(err),
                type(err).__name__,
            )
            return {}

    async def _fetch_sensor_data(self, sensor_type: str) -> dict[str, Any]:
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
            "units": "metric" if self.unit_system == UNIT_METRIC else "english",
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

            data = await self._safe_request_with_retry(
                NOAA_DATA_URL, params=params, operation=f"fetching {sensor_type} data"
            )

            if not data.get("data"):
                _LOGGER.debug(
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
                    "meters" if self.unit_system == UNIT_METRIC else "feet",
                    latest.get("t", "N/A"),
                )

            return {
                sensor_type: {
                    "state": float(latest.get("v", 0)),
                    "attributes": {
                        "time": latest.get("t"),
                        "datum": "MLLW",  # Add datum to attributes
                    },
                }
            }

        except UpdateFailed:
            return {}
        except Exception as err:
            _LOGGER.error(
                "NOAA Station %s: Error fetching sensor data for %s: %s (%s)",
                self.station_id,
                sensor_type,
                str(err),
                type(err).__name__,
            )
            return {}

    async def _fetch_currents_predictions(self) -> dict[str, Any]:
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
            "units": "metric" if self.unit_system == UNIT_METRIC else "english",
            "format": "json",
            "begin_date": datetime.now().strftime("%Y%m%d"),
            "range": 48,  # Get 48 hours of predictions
        }

        try:
            data = await self._safe_request_with_retry(
                NOAA_DATA_URL, params=params, operation="fetching currents predictions"
            )

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
                        ATTR_CURRENTS_DIRECTION: direction,
                        ATTR_CURRENTS_SPEED: abs(velocity),
                        ATTR_CURRENTS_TIME: time,
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
                "m/s" if self.unit_system == UNIT_METRIC else "knots",
                time,
            )

            return return_data

        except UpdateFailed:
            return {}
        except Exception as err:
            _LOGGER.error(
                "NOAA Station %s: Error fetching currents predictions: %s (%s)",
                self.station_id,
                str(err),
                type(err).__name__,
            )
            return {}

    async def _fetch_currents_data(self) -> dict[str, Any]:
        """Fetch NOAA currents data.

        Returns:
            dict[str, Any]: Dictionary containing currents data if available
        """
        params = {
            "station": self.station_id,
            "product": "currents",
            "time_zone": self.timezone,
            "units": "metric" if self.unit_system == UNIT_METRIC else "english",
            "format": "json",
            "date": "latest",
        }

        try:
            data = await self._safe_request_with_retry(
                NOAA_DATA_URL, params=params, operation="fetching currents data"
            )
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
                        "units": "m/s" if self.unit_system == UNIT_METRIC else "knots",
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

        except UpdateFailed:
            return {}
        except Exception as err:
            _LOGGER.error(
                "NOAA Station %s: Error fetching currents data: %s (%s)",
                self.station_id,
                str(err),
                type(err).__name__,
            )
            return {}

    async def _fetch_wind_data(self) -> dict[str, Any]:
        """Fetch wind data from NOAA API.

        Returns:
            dict[str, Any]: Dictionary containing wind data if available
        """
        _LOGGER.debug("NOAA Station %s: Fetching wind data", self.station_id)

        params = {
            "station": self.station_id,
            "product": "wind",
            "time_zone": self.timezone,
            "units": "metric" if self.unit_system == UNIT_METRIC else "english",
            "format": "json",
            "date": "latest",
        }

        try:
            data = await self._safe_request_with_retry(
                NOAA_DATA_URL, params=params, operation="fetching wind data"
            )
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

        except UpdateFailed:
            return {}
        except Exception as err:
            _LOGGER.error(
                "NOAA Station %s: Error fetching wind data: %s (%s)",
                self.station_id,
                str(err),
                type(err).__name__,
            )
            return {}

    async def _fetch_sensor_reading(self, sensor_type: str) -> dict[str, Any]:
        """Fetch the latest reading for a NOAA environmental sensor.

        Args:
            sensor_type: The type of sensor to fetch data for

        Returns:
            dict[str, Any]: Dictionary containing sensor data if available
        """
        if sensor_type == "wind":
            return await self._fetch_wind_data()
        try:
            params = {
                "station": self.station_id,
                "date": "latest",
                "time_zone": self.timezone,
                "units": "metric" if self.unit_system == UNIT_METRIC else "english",
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

            data = await self._safe_request_with_retry(
                NOAA_DATA_URL, params=params, operation=f"fetching {sensor_type} data"
            )
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

        except UpdateFailed:
            return {}
        except ValueError as err:
            # Handle value conversion errors
            _LOGGER.error(
                "NOAA Station %s: Invalid value received for sensor %s: %s (%s)",
                self.station_id,
                sensor_type,
                str(err),
                type(err).__name__,
            )
            return {}
        except Exception as err:
            _LOGGER.error(
                "NOAA Station %s: Error fetching sensor %s: %s (%s)",
                self.station_id,
                sensor_type,
                str(err),
                type(err).__name__,
            )
            return {}
