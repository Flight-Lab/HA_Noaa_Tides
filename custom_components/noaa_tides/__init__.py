"""The NOAA Tides component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import NOAADataCoordinator
from .const import CONF_STATION_ID, CONF_TIMEZONE, CONF_UNIT_SYSTEM, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the noaa_tides integration from a ConfigEntry."""
    _LOGGER.debug(
        "Setting up noaa_tides integration from ConfigEntry: %s", entry.as_dict()
    )

    # Extract configuration details
    station_id = entry.data[CONF_STATION_ID]
    timezone = entry.data[CONF_TIMEZONE]
    unit_system = entry.data[CONF_UNIT_SYSTEM]
    station_type = entry.data.get("station_type", "NOAA")

    # Read sensor configuration from options first (if available) then fallback to data.
    selected_sensors = entry.options.get("sensors", entry.data.get("sensors", []))

    # Initialize the data coordinator, which manages API calls, updates, and caching.
    coordinator = NOAADataCoordinator(
        hass, station_id, timezone, unit_system, station_type
    )
    # Perform the initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator and config entry in hass.data so sensors (and possibly other platforms) can access it.
    hass.data.setdefault(DOMAIN, {})  # Ensure domain key exists
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "entry": entry,
        "sensors": selected_sensors,
    }

    # Forward the configuration entry to the relevant platforms (sensors, etc.)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry and clean up resources."""
    _LOGGER.debug("Unloading noaa_tides ConfigEntry: %s", entry.entry_id)

    # Attempt to unload the integration's platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Remove the entry from hass.data to free up memory and prevent conflicts
        hass.data[DOMAIN].pop(entry.entry_id, None)

        # If there are no remaining entries, remove the domain data entirely
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


async def async_get_options_flow(config_entry: ConfigEntry):
    """Return the options flow handler for this integration, enabling reconfiguration."""
    from .options_flow import NOAAOptionsFlow

    return NOAAOptionsFlow(config_entry)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle reloading of a configuration entry."""
    _LOGGER.info("Reloading NOAA Tides config entry: %s", entry.entry_id)

    # Unload the entry first
    await async_unload_entry(hass, entry)

    # Reload the entry
    return await async_setup_entry(hass, entry)
