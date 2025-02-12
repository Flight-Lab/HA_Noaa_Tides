"""The NOAA Tides integration."""

from __future__ import annotations

import logging
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from . import const
from .coordinator import NoaaTidesDataUpdateCoordinator

_LOGGER: Final = logging.getLogger(__name__)

# Define platforms
PLATFORMS: Final[list[Platform]] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NOAA Tides from a config entry.

    Args:
        hass: The HomeAssistant instance
        entry: The ConfigEntry to set up

    Returns:
        bool: True if setup was successful, False otherwise

    Raises:
        ConfigEntryNotReady: If initial data fetch fails
    """
    # Create coordinator with proper type hints
    coordinator = NoaaTidesDataUpdateCoordinator(
        hass,
        hub_type=entry.data[const.CONF_HUB_TYPE],
        station_id=entry.data.get(const.CONF_STATION_ID)
        or entry.data.get(const.CONF_BUOY_ID),
        selected_sensors=entry.data.get("sensors", []),
        timezone=entry.data.get(const.CONF_TIMEZONE, const.DEFAULT_TIMEZONE),
        unit_system=entry.data.get(const.CONF_UNIT_SYSTEM, const.DEFAULT_UNIT_SYSTEM),
        update_interval=entry.data.get(
            const.CONF_UPDATE_INTERVAL, const.DEFAULT_UPDATE_INTERVAL
        ),
        data_sections=entry.data.get(const.CONF_DATA_SECTIONS, []),
    )

    # Store coordinator before first refresh to ensure it's available for the platforms
    hass.data.setdefault(const.DOMAIN, {})
    hass.data[const.DOMAIN][entry.entry_id] = coordinator

    # Set up platforms first so entities are ready for the data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Now fetch initial data
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        # Remove the config entry from domain data if initial refresh failed
        hass.data[const.DOMAIN].pop(entry.entry_id)
        raise ConfigEntryNotReady(
            f"Failed to fetch initial data from "
            f"{'NOAA station' if entry.data[const.CONF_HUB_TYPE] == const.HUB_TYPE_NOAA else 'NDBC buoy'} "
            f"{coordinator.station_id}"
        )

    # Register update listener for config entry changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options for the NOAA Tides integration.

    Args:
        hass: The HomeAssistant instance
        entry: The ConfigEntry being updated
    """
    # Force an immediate reload of the entry when options change
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: The HomeAssistant instance
        entry: The ConfigEntry to unload

    Returns:
        bool: True if unload was successful, False otherwise
    """
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove config entry from domain data
    if unload_ok:
        hass.data[const.DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry to new version.

    Args:
        hass: The HomeAssistant instance
        entry: The ConfigEntry to migrate

    Returns:
        bool: True if migration was successful, False otherwise
    """
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        # Currently no migrations needed
        return True

    return False
