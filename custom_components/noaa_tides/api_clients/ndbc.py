"""NDBC API client for NOAA Tides integration."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from ..const import (
    DATA_METEOROLOGICAL,
    DATA_OCEAN_CURRENT,
    DATA_SPECTRAL_WAVE,
    NDBC_CURRENT_URL,
    NDBC_METEO_URL,
    NDBC_SPEC_URL,
    UNIT_IMPERIAL,
    UNIT_METRIC,
)
from ..types import ApiError, CoordinatorData
from ..utils import degrees_to_cardinal, handle_ndbc_api_error
from .base import BaseApiClient

_LOGGER: Final = logging.getLogger(__name__)


class NdbcApiClient(BaseApiClient):
    """API client for NDBC data sources."""

    def __init__(
        self,
        hass: HomeAssistant,
        station_id: str,
        timezone: str,
        unit_system: str,
        data_sections: list[str] | None = None,
    ) -> None:
        """Initialize the NDBC API client.

        Args:
            hass: The Home Assistant instance
            station_id: The buoy ID
            timezone: The timezone setting
            unit_system: The unit system to use
            data_sections: Selected data sections to monitor
        """
        super().__init__(hass, station_id, timezone, unit_system)
        self.data_sections = data_sections or []

    async def handle_error(self, error: Exception) -> ApiError:
        """Handle NDBC API errors and return user-friendly messages.

        Args:
            error: The exception that occurred

        Returns:
            ApiError: A structured error object with user-friendly messages
        """
        return await handle_ndbc_api_error(error, self.station_id)

    async def fetch_data(self, selected_sensors: list[str]) -> CoordinatorData:
        """Fetch data from NDBC APIs for selected sensors.

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

            # Create tasks based on selected data sections
            if DATA_METEOROLOGICAL in self.data_sections:
                tasks.append(self._fetch_meteorological())
            if DATA_SPECTRAL_WAVE in self.data_sections:
                tasks.append(self._fetch_spectral_wave())
            if DATA_OCEAN_CURRENT in self.data_sections:
                tasks.append(self._fetch_ocean_current())

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
            api_error = await self.handle_error(err)
            _LOGGER.error(
                "NDBC Buoy %s: Error fetching data: %s. Technical details: %s",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
            raise UpdateFailed(api_error.message)

    async def _fetch_meteorological(self) -> dict[str, Any]:
        """Fetch meteorological data from NDBC.

        Returns:
            dict[str, Any]: Dictionary containing meteorological sensor data if available
        """
        try:
            url = NDBC_METEO_URL.format(buoy_id=self.station_id)
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
                    try:
                        if i < len(data) and data[i] != "MM" and data[i] != "999":
                            # Store original value before conversion
                            original_value = float(data[i])
                            # Round original value to 2 decimal places
                            value = round(original_value, 2)

                            # Initialize attributes
                            attributes: dict[str, Any] = {
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            }

                            # Convert values if imperial units are requested
                            if self.unit_system == UNIT_IMPERIAL:
                                # Temperature conversions (ATMP, WTMP, DEWP) - Celsius to Fahrenheit
                                if header in ["ATMP", "WTMP", "DEWP"]:
                                    value = round((value * 9 / 5) + 32, 2)
                                    # Store original value and unit for reference
                                    attributes["raw_value"] = str(original_value)
                                    attributes["unit"] = "°C"

                                # Wind speed and gust conversions (WSPD, GST) - m/s to mph
                                elif header in ["WSPD", "GST"]:
                                    value = round(value * 2.23694, 2)
                                    attributes["raw_value"] = str(original_value)
                                    attributes["unit"] = "m/s"

                                # Wave height conversion (WVHT) - meters to feet
                                elif header == "WVHT":
                                    value = round(value * 3.28084, 2)
                                    attributes["raw_value"] = str(original_value)
                                    attributes["unit"] = "m"

                                # Pressure conversion (PRES) - hPa to inHg
                                elif header == "PRES":
                                    value = round(value * 0.02953, 2)
                                    attributes["raw_value"] = str(original_value)
                                    attributes["unit"] = "hPa"

                            # Add direction cardinal for direction measurements
                            if header in ["WDIR", "MWD"]:  # Direction sensors
                                cardinal = degrees_to_cardinal(value)
                                if cardinal:
                                    attributes["direction_cardinal"] = cardinal

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

    async def _fetch_spectral_wave(self) -> dict[str, Any]:
        """Fetch spectral wave data from NDBC.

        Returns:
            dict[str, Any]: Dictionary containing spectral wave sensor data if available
        """
        try:
            url = NDBC_SPEC_URL.format(buoy_id=self.station_id)
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
                            if self.unit_system == UNIT_IMPERIAL:
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

    async def _fetch_ocean_current(self) -> dict[str, Any]:
        """Fetch ocean current data from NDBC.

        Not all NDBC buoys have current sensors, so handle 404 errors gracefully.

        Returns:
            dict[str, Any]: Dictionary containing ocean current sensor data if available
        """
        try:
            url = NDBC_CURRENT_URL.format(buoy_id=self.station_id)

            async with self.session.get(url) as response:
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
