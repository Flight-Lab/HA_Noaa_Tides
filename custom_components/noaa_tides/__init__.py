"""The NOAA Tides integration."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntryType, async_get

from . import const
from .coordinator import NoaaTidesDataUpdateCoordinator

_LOGGER: Final = logging.getLogger(__name__)


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

    # Register device immediately to ensure it exists before entity creation
    device_registry = async_get(hass)

    # Create device entry with proper identifiers
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(const.DOMAIN, entry.entry_id)},
        name=entry.data.get("name", ""),
        manufacturer=(
            "The National Oceanic & Atmospheric Administration"
            if entry.data[const.CONF_HUB_TYPE] == const.HUB_TYPE_NOAA
            else "The National Data Buoy Center"
        ),
        model=(
            f"NOAA Station {coordinator.station_id}"
            if entry.data[const.CONF_HUB_TYPE] == const.HUB_TYPE_NOAA
            else f"NDBC Buoy {coordinator.station_id}"
        ),
        entry_type=DeviceEntryType.SERVICE,
    )

    # Set up platforms first so entities are ready for the data
    await hass.config_entries.async_forward_entry_setups(entry, const.PLATFORMS)

    # Now fetch initial data
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        # Remove the config entry from domain data if initial refresh failed
        hass.data[const.DOMAIN].pop(entry.entry_id)
        source_type = (
            "NOAA station" if entry.data[const.CONF_HUB_TYPE] == const.HUB_TYPE_NOAA 
            else "NDBC buoy"
        )
        raise ConfigEntryNotReady(
            f"Failed to fetch initial data from {source_type} {coordinator.station_id}"
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
    unload_ok = await hass.config_entries.async_unload_platforms(entry, const.PLATFORMS)

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
    _LOGGER.debug(f"Migrating from version {entry.version}")

    if entry.version == 1:
        # Currently no migrations needed
        return True

    return False
