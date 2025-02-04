"""Options flow for NOAA Tides integration."""

import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr

from .api import get_station_products, async_fetch_ndbc_data
from .const import (
    CONF_STATION_ID,
    CONF_TIMEZONE,
    CONF_UNIT_SYSTEM,
    DOMAIN,
    SENSOR_OPTIONS,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)


class NOAAOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for NOAA Tides integration."""

    def __init__(self, config_entry):
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            is_valid = await self._validate_station_id(user_input["station_id"])
            if not is_valid:
                return self.async_show_form(
                    step_id="init",
                    data_schema=await self._generate_schema(),
                    errors={"station_id": "invalid_station_id"},
                )
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={
                    CONF_NAME: user_input["name"],
                    CONF_STATION_ID: user_input["station_id"],
                    CONF_TIMEZONE: user_input["timezone"],
                    CONF_UNIT_SYSTEM: user_input["unit_system"],
                },
                options={
                    "sensors": user_input["sensors"],
                    "options_initialized": True,
                },
            )

            device_registry = dr.async_get(self.hass)
            device_registry.async_get_or_create(
                config_entry_id=self._config_entry.entry_id,
                identifiers={(DOMAIN, user_input["station_id"])},
                manufacturer="NOAA",
                name=f"NOAA Station {user_input['station_id']}",
                model="Tides and Currents",
                sw_version=VERSION,
            )
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="init", data_schema=await self._generate_schema()
        )

    async def _generate_schema(self):
        """Generate schema with default values for options flow."""
        station_id = self._config_entry.data.get(CONF_STATION_ID)
        current_options = self._config_entry.options
        station_type = self._config_entry.data.get("station_type", "NOAA")

        if station_type == "NDBC":
            # Define the default list of sensor keys for NDBC stations.
            sensor_keys = [
                "wind_speed",
                "wind_direction",
                "wave_height",
                "water_temp",
                "air_temp",
                "barometric_pressure",
            ]
            # Try to fetch the latest NDBC data so we can filter out sensors
            # that are returning "MM" (represented as None in our API function).
            unit_system = self._config_entry.data.get(CONF_UNIT_SYSTEM, "imperial")
            try:
                async with aiohttp.ClientSession() as session:
                    ndbc_data = await async_fetch_ndbc_data(
                        session, station_id, unit_system
                    )
                # Remove any sensor keys for which the data is missing (i.e. None)
                sensor_keys = [
                    key for key in sensor_keys if ndbc_data.get(key) is not None
                ]
            except Exception as e:
                _LOGGER.error("Error fetching NDBC data in options flow: %s", e)
                # If an error occurs, assume all sensors are available.
            available_sensor_options = {
                key: SENSOR_OPTIONS.get(key, key) for key in sensor_keys
            }
        else:
            # For NOAA stations, use the get_station_products routine.
            available_sensor_keys = await get_station_products(station_id)
            available_sensor_options = {
                sensor: SENSOR_OPTIONS[sensor] for sensor in available_sensor_keys
            }

        current_sensors = current_options.get(
            "sensors", list(available_sensor_options.keys())
        )
        timezone_options = ["gmt", "lst", "lst_ldt"]

        return vol.Schema(
            {
                vol.Required(
                    "name", default=self._config_entry.data.get(CONF_NAME, "NOAA Tides")
                ): cv.string,
                vol.Required("station_id", default=station_id): cv.string,
                vol.Required(
                    "timezone",
                    default=self._config_entry.data.get(CONF_TIMEZONE, "lst_ldt"),
                ): vol.In(timezone_options),
                vol.Required(
                    "unit_system",
                    default=self._config_entry.data.get(CONF_UNIT_SYSTEM, "imperial"),
                ): vol.In(["imperial", "metric"]),
                vol.Optional("sensors", default=current_sensors): cv.multi_select(
                    available_sensor_options
                ),
            }
        )

    async def _validate_station_id(self, station_id: str) -> bool:
        """Validate NOAA station ID asynchronously."""
        url = f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station_id}.json"
        _LOGGER.debug(
            "Validating NOAA Station ID in options: %s with URL: %s", station_id, url
        )
        try:
            async with aiohttp.ClientSession() as session, session.get(url) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        if data.get("stations"):
                            return True
                        _LOGGER.warning(
                            "Station %s found, but response structure is unexpected: %s",
                            station_id,
                            data,
                        )
                    except aiohttp.ContentTypeError:
                        _LOGGER.error(
                            "Invalid JSON response from NOAA API for station %s",
                            station_id,
                        )
                else:
                    _LOGGER.warning(
                        "NOAA API returned %s for station %s",
                        response.status,
                        station_id,
                    )
        except aiohttp.ClientError as e:
            _LOGGER.error(
                "Network error while validating station ID %s: %s", station_id, e
            )
        except Exception as e:
            _LOGGER.error(
                "Unexpected error validating station ID %s: %s", station_id, e
            )
        return False
