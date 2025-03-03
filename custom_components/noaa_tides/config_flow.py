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
from .types import ConfigFlowData
from .utils import (
    discover_ndbc_sensors,
    discover_noaa_sensors,
    validate_ndbc_buoy,
    validate_noaa_station,
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
            hub_type="",
            timezone=const.DEFAULT_TIMEZONE,
            unit_system=const.DEFAULT_UNIT_SYSTEM,
            update_interval=const.DEFAULT_UPDATE_INTERVAL,
        )
        self._available_sensors: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - hub type selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            # If NDBC buoy, automatically set all data sections
            if self._data[const.CONF_HUB_TYPE] == const.HUB_TYPE_NDBC:
                self._data[const.CONF_DATA_SECTIONS] = list(const.DATA_SECTIONS)
            return await self.async_step_station_config()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(const.CONF_HUB_TYPE): vol.In(
                        {
                            const.HUB_TYPE_NOAA: "NOAA Station",
                            const.HUB_TYPE_NDBC: "NDBC Buoy",
                        }
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_station_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the station configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate station/buoy ID based on hub type
            is_noaa = self._data[const.CONF_HUB_TYPE] == const.HUB_TYPE_NOAA
            station_id = user_input.get(
                const.CONF_STATION_ID if is_noaa else const.CONF_BUOY_ID
            )
            station_valid = await self._validate_station(station_id)

            if not station_valid:
                errors["base"] = (
                    const.ERROR_INVALID_STATION if is_noaa else const.ERROR_INVALID_BUOY
                )
            else:
                self._data.update(user_input)
                # For NDBC buoys, automatically set all data sections
                if not is_noaa:
                    self._data[const.CONF_DATA_SECTIONS] = list(const.DATA_SECTIONS)

                return await self.async_step_sensor_select()

        # Build schema based on hub type
        is_noaa = self._data[const.CONF_HUB_TYPE] == const.HUB_TYPE_NOAA
        schema = {
            vol.Required(const.CONF_STATION_ID if is_noaa else const.CONF_BUOY_ID): str,
            vol.Required(
                "name",
                default=const.DEFAULT_NAME_NOAA if is_noaa else const.DEFAULT_NAME_NDBC,
            ): str,
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
            step_id="station_config",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_sensor_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle sensor selection."""
        errors: dict[str, str] = {}

        try:
            if not self._available_sensors:
                self._available_sensors = await self._discover_sensors()

            _LOGGER.debug(
                "Available sensors for selection: %s", self._available_sensors
            )

            if not self._available_sensors:
                errors["base"] = "no_sensors"
                return self.async_show_form(
                    step_id="sensor_select",
                    errors=errors,
                    description_placeholders={
                        "station_id": self._data.get("station_id")
                        or self._data.get("buoy_id", "unknown")
                    },
                )

            if user_input is not None:
                self._data.update(user_input)
                return self.async_create_entry(
                    title=self._data["name"],
                    data=self._data,
                )

            return self.async_show_form(
                step_id="sensor_select",
                data_schema=vol.Schema(
                    {
                        vol.Required("sensors"): cv.multi_select(
                            self._available_sensors
                        ),
                    }
                ),
                errors=errors,
            )
        except Exception as ex:
            _LOGGER.exception("Unexpected error in sensor selection: %s", ex)
            errors["base"] = "unknown"
            return self.async_show_form(
                step_id="sensor_select",
                data_schema=vol.Schema(
                    {
                        vol.Required("sensors"): cv.multi_select({}),
                    }
                ),
                errors=errors,
            )

    async def _validate_station(self, station_id: str) -> bool:
        """Validate the station/buoy ID."""
        if self._data[const.CONF_HUB_TYPE] == const.HUB_TYPE_NOAA:
            return await validate_noaa_station(self.hass, station_id)
        else:
            # For NDBC buoys, check all data sections
            return await validate_ndbc_buoy(self.hass, station_id)

    async def _discover_sensors(self) -> dict[str, str]:
        """Discover available sensors based on hub type and configuration."""
        if self._data[const.CONF_HUB_TYPE] == const.HUB_TYPE_NOAA:
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
