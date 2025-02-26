"""Base API client for NOAA Tides integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..types import ApiError, CoordinatorData

_LOGGER: Final = logging.getLogger(__name__)


class BaseApiClient:
    """Base API client for NOAA and NDBC data sources."""

    def __init__(
        self,
        hass: HomeAssistant,
        station_id: str,
        timezone: str,
        unit_system: str,
    ) -> None:
        """Initialize the API client.

        Args:
            hass: The Home Assistant instance
            station_id: The station or buoy ID
            timezone: The timezone setting
            unit_system: The unit system to use
        """
        self.hass = hass
        self.station_id = station_id
        self.timezone = timezone
        self.unit_system = unit_system
        self.session = async_get_clientsession(hass)

    async def fetch_data(self, selected_sensors: list[str]) -> CoordinatorData:
        """Fetch data from the API.

        Args:
            selected_sensors: List of sensors to fetch

        Returns:
            CoordinatorData: The fetched data

        Raises:
            NotImplementedError: If the subclass does not implement this method
        """
        raise NotImplementedError("Subclasses must implement this method")

    async def handle_error(self, error: Exception) -> ApiError:
        """Handle API errors.

        Args:
            error: The exception that occurred

        Returns:
            ApiError: A structured error object

        Raises:
            NotImplementedError: If the subclass does not implement this method
        """
        raise NotImplementedError("Subclasses must implement this method")
