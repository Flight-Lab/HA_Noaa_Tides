"""Config flow for NOAA Tides integration."""

import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr

from .api import get_station_products
from .const import (
    CONF_STATION_ID,
    CONF_TIMEZONE,
    CONF_UNIT_SYSTEM,
    DEFAULT_NAME,
    DEFAULT_TIMEZONE,
    DEFAULT_UNIT_SYSTEM,
    DOMAIN,
    SENSOR_OPTIONS,
)
from .options_flow import NOAAOptionsFlow

_LOGGER = logging.getLogger(__name__)

NOAA_API_VALIDATION_URL = (
    "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{}.json"
)
NDBC_API_VALIDATION_URL = "https://www.ndbc.noaa.gov/data/realtime2/{}.txt"


async def validate_station_id(station_id: str) -> bool:
    """Validate station ID by checking NOAA API first and then NDBC API if needed."""
    async with aiohttp.ClientSession() as session:
        # First, try validating with the NOAA API
        noaa_url = NOAA_API_VALIDATION_URL.format(station_id)
        _LOGGER.debug(f"Validating NOAA Station ID: {station_id} with URL: {noaa_url}")
        try:
            async with session.get(noaa_url) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        if data.get("stations"):
                            return True  # Station is valid per NOAA API
                        _LOGGER.warning(
                            f"Station {station_id} found on NOAA but response structure is unexpected: {data}"
                        )
                    except aiohttp.ContentTypeError:
                        _LOGGER.error(
                            f"Invalid JSON response from NOAA API for station {station_id}"
                        )
                else:
                    _LOGGER.warning(
                        f"NOAA API returned {response.status} for station {station_id}"
                    )
        except aiohttp.ClientError as e:
            _LOGGER.error(
                f"Network error while validating station ID {station_id} on NOAA API: {e}"
            )
        except Exception as e:
            _LOGGER.error(
                f"Unexpected error validating station ID {station_id} on NOAA API: {e}"
            )

        # NOAA validation failed; now try the NDBC API
        ndbc_url = NDBC_API_VALIDATION_URL.format(station_id)
        _LOGGER.debug(f"Validating NDBC Station ID: {station_id} with URL: {ndbc_url}")
        try:
            async with session.get(ndbc_url) as response:
                if response.status == 200:
                    text = await response.text()
                    if text and "Error" not in text:
                        return True  # Station is valid per NDBC API
                    _LOGGER.warning(
                        f"Station {station_id} found on NDBC but response content is unexpected: {text}"
                    )
                else:
                    _LOGGER.warning(
                        f"NDBC API returned {response.status} for station {station_id}"
                    )
        except aiohttp.ClientError as e:
            _LOGGER.error(
                f"Network error while validating station ID {station_id} on NDBC API: {e}"
            )
        except Exception as e:
            _LOGGER.error(
                f"Unexpected error validating station ID {station_id} on NDBC API: {e}"
            )

    # If neither API confirmed the station, return False.
    return False  # Default to invalid if errors occur


class NOAAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for NOAA Tides."""

    VERSION = 1
    reauth_entry = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step of setting up NOAA Tides."""
        errors = {}

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]

            # Validate station ID
            is_valid = await validate_station_id(station_id)
            if not is_valid:
                errors["station_id"] = "invalid_station_id"

            if errors:
                data_schema = vol.Schema(
                    {
                        vol.Required(
                            CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                        ): cv.string,
                        vol.Required(CONF_STATION_ID, default=station_id): cv.string,
                        vol.Required(
                            CONF_TIMEZONE,
                            default=user_input.get(CONF_TIMEZONE, DEFAULT_TIMEZONE),
                        ): vol.In(["gmt", "lst", "lst_ldt"]),
                        vol.Required(
                            CONF_UNIT_SYSTEM,
                            default=user_input.get(
                                CONF_UNIT_SYSTEM, DEFAULT_UNIT_SYSTEM
                            ),
                        ): vol.In(["metric", "imperial"]),
                    }
                )
                return self.async_show_form(
                    step_id="user", data_schema=data_schema, errors=errors
                )
            # Fetch available sensors from the station-specific endpoints
            available_sensors = await get_station_products(station_id)
            self._user_data = user_input  # store the initial data
            if available_sensors:
                # Proceed to sensor selection step
                self._available_sensors = available_sensors
                return await self.async_step_select_sensors()
            else:
                # If no sensors are returned, just set sensors to an empty list and complete the flow.
                self._user_data["sensors"] = []
                return self.async_create_entry(
                    title=self._user_data[CONF_NAME], data=self._user_data
                )

        # Define the schema for the user form
        timezone_options = ["gmt", "lst", "lst_ldt"]
        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Required(CONF_STATION_ID): cv.string,
                vol.Required(CONF_TIMEZONE, default=DEFAULT_TIMEZONE): vol.In(
                    timezone_options
                ),
                vol.Required(CONF_UNIT_SYSTEM, default=DEFAULT_UNIT_SYSTEM): vol.In(
                    ["metric", "imperial"]
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_select_sensors(self, user_input=None):
        """Step for selecting sensors based on available NOAA products."""
        if user_input is not None:
            self._user_data["sensors"] = user_input["sensors"]
            await self.async_set_unique_id(self._user_data[CONF_STATION_ID])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._user_data[CONF_NAME], data=self._user_data
            )
        sensor_options = {
            sensor: SENSOR_OPTIONS[sensor] for sensor in self._available_sensors
        }
        data_schema = vol.Schema(
            {
                vol.Required(
                    "sensors", default=self._available_sensors
                ): cv.multi_select(sensor_options)
            }
        )
        return self.async_show_form(step_id="select_sensors", data_schema=data_schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NOAAOptionsFlow(config_entry)
