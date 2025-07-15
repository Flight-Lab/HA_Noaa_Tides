"""Config flow for NOAA Tides integration."""

from __future__ import annotations

import logging
from typing import Any, Final

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from . import const
from .data_constants import LogMessages
from .types import ConfigFlowData
from .utils import (
    discover_ndbc_sensors,
    discover_noaa_sensors,
)

_LOGGER = logging.getLogger(__name__)


class NoaaTidesConfigFlow(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Handle a config flow for NOAA Tides integration."""

    VERSION: Final = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: ConfigFlowData = ConfigFlowData(
            name="",
            sensors=[],
            station_type="",
            timezone=const.DEFAULT_TIMEZONE,
            unit_system=const.DEFAULT_UNIT_SYSTEM,
            update_interval=const.DEFAULT_UPDATE_INTERVAL,
        )
        self._available_sensors: dict[str, str] = {}
        self._detected_station_id: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - station ID."""
        errors: dict[str, str] = {}
    
        if user_input is not None:
            station_id = user_input.get("station_id", "").strip().upper()
    
            if not station_id:
                errors["station_id"] = "Station ID cannot be empty"
            else:
                # Try to auto-detect the station type
                detected_type = await self._auto_detect_station_type(station_id)
    
                if detected_type is None:
                    # Neither NOAA nor NDBC recognized this ID
                    errors["station_id"] = (
                        "Station/Buoy ID not found. Please verify the ID is correct."
                    )
                else:
                    # Successfully detected - store the data and continue
                    self._data[const.CONF_STATION_TYPE] = detected_type
                    self._detected_station_id = station_id
    
                    # Set the appropriate ID field based on detected type
                    if detected_type == const.STATION_TYPE_NOAA:
                        self._data[const.CONF_STATION_ID] = station_id
                        _LOGGER.info(
                            f"Auto-detected NOAA Station: {station_id}")
                    else:
                        self._data[const.CONF_BUOY_ID] = station_id
                        self._data[const.CONF_DATA_SECTIONS] = list(
                            const.DATA_SECTIONS)
                        _LOGGER.info(f"Auto-detected NDBC Buoy: {station_id}")
    
                    return await self.async_step_configure()
    
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("station_id"): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "noaa_help": const.NOAA_STATION_MAP_URL,
                "ndbc_help": const.NDBC_STATION_MAP_URL,
            },
        )

    async def _auto_detect_station_type(self, station_id: str) -> str | None:
        """Auto-detect whether the station ID is NOAA or NDBC."""
        _LOGGER.debug(f"Auto-detecting station type for ID: {station_id}")

        # Try NOAA first - if it has sensors, it's a NOAA station
        try:
            noaa_sensors = await discover_noaa_sensors(self.hass, station_id)
            if noaa_sensors:
                _LOGGER.debug(
                    f"Station {station_id} identified as NOAA station ({len(noaa_sensors)} sensors)"
                )
                return const.STATION_TYPE_NOAA
        except Exception as err:
            _LOGGER.debug(
                f"NOAA sensor discovery failed for {station_id}: {err}")

        # Try NDBC if NOAA didn't work
        try:
            ndbc_sensors = await discover_ndbc_sensors(
                self.hass, station_id, list(const.DATA_SECTIONS)
            )
            if ndbc_sensors:
                _LOGGER.debug(
                    f"Station {station_id} identified as NDBC buoy ({len(ndbc_sensors)} sensors)"
                )
                return const.STATION_TYPE_NDBC
        except Exception as err:
            _LOGGER.debug(
                f"NDBC sensor discovery failed for {station_id}: {err}")

        # Neither worked
        _LOGGER.warning(
            f"Station/Buoy ID {station_id} not found in either NOAA or NDBC databases"
        )
        return None

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the configuration step."""
        errors: dict[str, str] = {}

        # Discover sensors if we haven't already
        if not self._available_sensors:
            try:
                self._available_sensors = await self._discover_sensors()
            except Exception as err:
                _LOGGER.error(f"Error discovering sensors: {err}")
                errors["base"] = "no_sensors"
                return self.async_show_form(
                    step_id="configure",
                    errors=errors,
                    description_placeholders={
                        "detected_type": "NOAA Station"
                        if self._data[const.CONF_STATION_TYPE] == const.STATION_TYPE_NOAA
                        else "NDBC Buoy",
                        "station_id": self._detected_station_id,
                    },
                )

        if not self._available_sensors:
            errors["base"] = "no_sensors"
            return self.async_show_form(
                step_id="configure",
                errors=errors,
                description_placeholders={
                    "detected_type": "NOAA Station"
                    if self._data[const.CONF_STATION_TYPE] == const.STATION_TYPE_NOAA
                    else "NDBC Buoy",
                    "station_id": self._detected_station_id,
                },
            )

        if user_input is not None:
            # Validate that at least one sensor was selected
            if not user_input.get("sensors"):
                errors["sensors"] = "At least one sensor must be selected"
            else:
                self._data.update(user_input)
                return self.async_create_entry(
                    title=self._data["name"],
                    data=self._data,
                )

        # Determine default name based on detected type
        is_noaa = self._data[const.CONF_STATION_TYPE] == const.STATION_TYPE_NOAA
        default_name = (
            f"NOAA Station {self._detected_station_id}"
            if is_noaa
            else f"NDBC Buoy {self._detected_station_id}"
        )

        # Show detected type in the form description
        detected_type_name = "NOAA Station" if is_noaa else "NDBC Buoy"

        schema = {
            vol.Required("name", default=default_name): str,
            vol.Required("sensors"): cv.multi_select(self._available_sensors),
            vol.Required(const.CONF_TIMEZONE, default=const.DEFAULT_TIMEZONE): vol.In(
                const.TIMEZONE_OPTIONS
            ),
            vol.Required(
                const.CONF_UNIT_SYSTEM, default=const.DEFAULT_UNIT_SYSTEM
            ): vol.In(const.UNIT_OPTIONS),
            vol.Required(
                const.CONF_UPDATE_INTERVAL, default=const.DEFAULT_UPDATE_INTERVAL
            ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
        }

        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "detected_type": detected_type_name,
                "station_id": self._detected_station_id,
                "sensor_count": str(len(self._available_sensors)),
            },
        )

    async def _discover_sensors(self) -> dict[str, str]:
        """Discover available sensors based on detected type."""
        if self._data[const.CONF_STATION_TYPE] == const.STATION_TYPE_NOAA:
            return await discover_noaa_sensors(
                self.hass, self._data[const.CONF_STATION_ID]
            )
        else:
            # For NDBC buoys, check all data sections
            return await discover_ndbc_sensors(
                self.hass,
                self._data[const.CONF_BUOY_ID],
                list(const.DATA_SECTIONS),
            )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NoaaTidesOptionsFlow:
        """Get the options flow for this handler."""
        return NoaaTidesOptionsFlow(config_entry)


class NoaaTidesOptionsFlow(config_entries.OptionsFlow):
    """Handle options for the NOAA Tides integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Required(
                const.CONF_UPDATE_INTERVAL,
                default=self._config_entry.options.get(
                    const.CONF_UPDATE_INTERVAL, const.DEFAULT_UPDATE_INTERVAL
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
