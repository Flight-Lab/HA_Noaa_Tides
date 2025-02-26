"""Data update coordinator for the NOAA Tides integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Final, Literal

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const
from .api_clients import NoaaApiClient, NdbcApiClient
from .types import CoordinatorData

_LOGGER: Final = logging.getLogger(__name__)


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

        # Initialize the appropriate API client
        if hub_type == const.HUB_TYPE_NOAA:
            self.api_client: Final = NoaaApiClient(
                hass, station_id, timezone, unit_system
            )
        else:
            self.api_client: Final = NdbcApiClient(
                hass, station_id, timezone, unit_system, data_sections
            )

        super().__init__(
            hass,
            _LOGGER,
            name=const.DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch data from NOAA/NDBC APIs.

        Returns:
            CoordinatorData: The fetched data

        Raises:
            UpdateFailed: If there's an error fetching data
        """
        try:
            async with asyncio.timeout(30):
                return await self.api_client.fetch_data(self.selected_sensors)
        except asyncio.TimeoutError as err:
            api_error = await self.api_client.handle_error(err)
            _LOGGER.error(
                "%s %s: %s Technical details: %s",
                "NOAA Station" if self.hub_type == const.HUB_TYPE_NOAA else "NDBC Buoy",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
            raise UpdateFailed(api_error.message)
        except Exception as err:
            api_error = await self.api_client.handle_error(err)
            _LOGGER.error(
                "%s %s: %s Technical details: %s",
                "NOAA Station" if self.hub_type == const.HUB_TYPE_NOAA else "NDBC Buoy",
                self.station_id,
                api_error.message,
                api_error.technical_detail or "None",
            )
            raise UpdateFailed(api_error.message)
