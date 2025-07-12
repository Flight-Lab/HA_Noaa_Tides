"""Data update coordinator for the NOAA Tides integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any, Final, Literal

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const
from .api_clients import NoaaApiClient, NdbcApiClient
from .data_constants import MAX_CONSECUTIVE_FAILURES, LogMessages
from .errors import NoaaApiError, NdbcApiError, ApiError
from .types import CoordinatorData
from .utils import determine_required_data_sections

_LOGGER: Final = logging.getLogger(__name__)


class NoaaTidesDataUpdateCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Class to manage fetching NOAA Tides data.

    Error handling strategy:
    - Tracks consecutive failures to provide better error messages
    - Falls back to cached data for transient errors when possible
    - Raises UpdateFailed with user-friendly messages for UI display
    """

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

        # For NDBC, determine required data sections based on selected sensors
        if hub_type == const.HUB_TYPE_NDBC:
            self.data_sections: Final = determine_required_data_sections(
                selected_sensors
            )
            _LOGGER.debug(
                f"NDBC Buoy {station_id}: Using data sections {self.data_sections} based on selected sensors"
            )
        else:
            self.data_sections: Final = data_sections or []

        # Initialize the appropriate API client
        if hub_type == const.HUB_TYPE_NOAA:
            self.api_client: Final = NoaaApiClient(
                hass, station_id, timezone, unit_system
            )
        else:
            self.api_client: Final = NdbcApiClient(
                hass, station_id, timezone, unit_system, self.data_sections
            )

        super().__init__(
            hass,
            _LOGGER,
            name=const.DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

        # Track consecutive failures for better error reporting
        self._consecutive_failures = 0
        self._max_consecutive_failures = MAX_CONSECUTIVE_FAILURES
        # Track partially failed sensors
        self._failed_sensors: dict[str, int] = {}

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch data from NOAA/NDBC APIs.

        Handles various error conditions:
        - Connection timeouts (retries with backoff)
        - API errors (converts to user-friendly messages)
        - Data validation errors (logs details for debugging)
        - Server errors (uses cached data if available)

        Returns:
            CoordinatorData: The fetched data

        Raises:
            UpdateFailed: If there's an error fetching data after retries
        """
        source_type = (
            "NOAA station" if self.hub_type == const.HUB_TYPE_NOAA else "NDBC buoy"
        )

        try:
            # Set a timeout for the entire data fetch operation
            async with asyncio.timeout(30):
                # Attempt to fetch data
                data = await self.api_client.fetch_data(self.selected_sensors)

                # Check if we got any data at all
                if not data:
                    self._consecutive_failures += 1

                    # Provide more detailed error after multiple consecutive failures
                    if self._consecutive_failures >= self._max_consecutive_failures:
                        raise UpdateFailed(
                            f"No data available from {source_type} {self.station_id} "
                            f"after {self._consecutive_failures} attempts. "
                            f"The service may be experiencing issues."
                        )
                    else:
                        _LOGGER.warning(
                            f"{source_type.capitalize()} {self.station_id}: No data returned "
                            f"(attempt {self._consecutive_failures}/{self._max_consecutive_failures})"
                        )
                        # If we have previous data, use it instead of failing completely
                        if self.data:
                            _LOGGER.info(
                                f"{source_type.capitalize()} {self.station_id}: Using cached data for this update"
                            )
                            return self.data

                        raise UpdateFailed(
                            f"No data available from {source_type} {self.station_id}. "
                            f"Will retry."
                        )

                # Check for partial failures by identifying missing sensors
                missing_sensors = self._get_missing_sensors(data)

                if missing_sensors:
                    # Update failure counts for missing sensors
                    for sensor in missing_sensors:
                        self._failed_sensors[sensor] = (
                            self._failed_sensors.get(sensor, 0) + 1
                        )

                        # Log at warning level if the sensor has failed multiple times
                        if (
                            self._failed_sensors[sensor]
                            >= self._max_consecutive_failures
                        ):
                            _LOGGER.warning(
                                f"{source_type.capitalize()} {self.station_id}: Sensor '{sensor}' has failed to return data "
                                f"{self._failed_sensors[sensor]} times in a row"
                            )
                        else:
                            _LOGGER.debug(
                                f"{source_type.capitalize()} {self.station_id}: Sensor '{sensor}' returned no data "
                                f"(attempt {self._failed_sensors[sensor]}/{self._max_consecutive_failures})"
                            )

                # Reset the consecutive failure counter since we got some data
                self._consecutive_failures = 0

                # Reset failure counts for sensors that are now working
                for sensor in list(self._failed_sensors.keys()):
                    if sensor not in missing_sensors:
                        del self._failed_sensors[sensor]

                return data

        except asyncio.TimeoutError:
            self._consecutive_failures += 1

            _LOGGER.error(
                LogMessages.CONNECTION_TIMEOUT.format(
                    source_type=source_type.capitalize(),
                    source_id=self.station_id,
                    operation="data fetch"
                ) + f" (attempt {self._consecutive_failures}/{self._max_consecutive_failures})"
            )

            # Provide more detailed error after multiple consecutive timeouts
            if self._consecutive_failures >= self._max_consecutive_failures:
                raise UpdateFailed(
                    f"Timeout fetching data from {source_type} {self.station_id} "
                    f"after {self._consecutive_failures} attempts. "
                    f"Check your internet connection and the service status."
                )
            else:
                # If we have previous data, use it instead of failing completely
                if self.data:
                    _LOGGER.info(
                        f"{source_type.capitalize()} {self.station_id}: Using cached data for this update due to timeout"
                    )
                    return self.data

                raise UpdateFailed(
                    f"Timeout fetching data from {source_type} {self.station_id}. "
                    f"Will retry."
                )

        except UpdateFailed as err:
            # For UpdateFailed exceptions, track failures but re-raise with the same message
            self._consecutive_failures += 1
            _LOGGER.error(
                f"{source_type.capitalize()} {self.station_id}: Update failed "
                f"(attempt {self._consecutive_failures}/{self._max_consecutive_failures}): {err}"
            )

            # If we have previous data and haven't failed too many times, use cached data
            if (
                self.data
                and self._consecutive_failures < self._max_consecutive_failures
            ):
                _LOGGER.info(
                    f"{source_type.capitalize()} {self.station_id}: Using cached data for this update due to error"
                )
                return self.data

            raise

        except (NoaaApiError, NdbcApiError) as err:
            self._consecutive_failures += 1

            # Extract the ApiError details for better error messages
            api_error = getattr(err, "api_error", None)

            # Format a helpful error message
            if api_error and isinstance(api_error, ApiError):
                error_msg = (
                    f"{'NOAA Station' if self.hub_type == const.HUB_TYPE_NOAA else 'NDBC Buoy'} "
                    f"{self.station_id}: {api_error.message} (Error code: {api_error.code})"
                )
                if api_error.help_url:
                    error_msg += f" See {api_error.help_url} for more information."
            else:
                error_msg = (
                    f"{'NOAA Station' if self.hub_type == const.HUB_TYPE_NOAA else 'NDBC Buoy'} "
                    f"{self.station_id}: {err}"
                )

            _LOGGER.error(error_msg)

            # If we have previous data and haven't failed too many times, use cached data
            if (
                self.data
                and self._consecutive_failures < self._max_consecutive_failures
            ):
                _LOGGER.info(
                    f"{source_type.capitalize()} {self.station_id}: Using cached data for this update due to error"
                )
                return self.data

            raise UpdateFailed(error_msg) from err

        except Exception as err:
            # For all other exceptions, create a nice message and track failures
            self._consecutive_failures += 1

            _LOGGER.error(
                f"{source_type.capitalize()} {self.station_id}: Unexpected error fetching data "
                f"(attempt {self._consecutive_failures}/{self._max_consecutive_failures}): {err} ({type(err).__name__})"
            )

            # If we have previous data and haven't failed too many times, use cached data
            if (
                self.data
                and self._consecutive_failures < self._max_consecutive_failures
            ):
                _LOGGER.info(
                    f"{source_type.capitalize()} {self.station_id}: Using cached data for this update due to error"
                )
                return self.data

            raise UpdateFailed(
                f"Error fetching data from {source_type} {self.station_id}: {err}"
            )

    def _get_missing_sensors(self, data: CoordinatorData) -> list[str]:
        """Identify selected sensors that are missing from the data.

        Used to track partial failures when some sensors don't return data.

        Args:
            data: The data returned from the API

        Returns:
            list[str]: List of selected sensors that are missing from the data
        """
        missing_sensors = []

        for sensor in self.selected_sensors:
            # Skip checking sensors that are part of composite data
            if self._is_composite_sensor(sensor, data):
                continue

            # Check if the sensor data exists and has a state
            if sensor not in data or not self._has_valid_state(data[sensor]):
                missing_sensors.append(sensor)

        return missing_sensors

    def _is_composite_sensor(self, sensor_id: str, data: CoordinatorData) -> bool:
        """Check if a sensor is part of composite data created from other sensors.

        Some sensors like wind_direction and wind_speed are fetched together.

        Args:
            sensor_id: The sensor ID to check
            data: The current data

        Returns:
            bool: True if this sensor's data is part of a composite
        """
        # Define composite relationships
        composites = {
            "wind_direction": ["wind_speed"],
            "wind_speed": ["wind_direction"],
            "currents_direction": ["currents_speed"],
            "currents_speed": ["currents_direction"],
        }

        # Check if any of the composite's related sensors are in the data
        if sensor_id in composites:
            return any(
                dep in data and self._has_valid_state(data[dep])
                for dep in composites[sensor_id]
            )

        return False

    def _has_valid_state(self, sensor_data: Any) -> bool:
        """Check if sensor data has a valid state.

        Args:
            sensor_data: The sensor data to check

        Returns:
            bool: True if the sensor has valid state data
        """
        if not sensor_data:
            return False

        # Check both dictionary format and direct state attributes
        if isinstance(sensor_data, dict):
            return "state" in sensor_data and sensor_data["state"] is not None

        # If it has a state attribute directly
        return hasattr(sensor_data, "state") and sensor_data.state is not None
