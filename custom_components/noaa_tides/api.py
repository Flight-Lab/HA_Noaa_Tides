"""API interactions and data coordinator for NOAA Tides component."""

from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
APPLICATION_NAME = "NoaaTidesIntegration"


async def get_station_products(station_id: str) -> list[str]:
    """Fetch available NOAA products and sensors for the given station.

    This function is used during config flow to list available NOAA data.
      - The products endpoint (products.json) to determine if "Water Levels" and "Tide Predictions" are available.
      - The sensors endpoint (sensors.json) to check for "Air Temperature" and "Water Temperature" sensors.

    Returns a list of internal sensor keys that the integration should create.
    """
    product_url = f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station_id}/products.json"
    sensors_url = f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station_id}/sensors.json"
    available_sensors = set()

    async with aiohttp.ClientSession() as session:
        # Try to fetch the products endpoint
        try:
            async with session.get(product_url) as prod_resp:
                if prod_resp.status == 200:
                    prod_data = await prod_resp.json()
                    products = prod_data.get("products") or []
                    for item in products:
                        name = item.get("name", "").lower()
                        # Check for water levels and tide predictions
                        if "water levels" in name:
                            available_sensors.add("measured_level")
                        if "tide predictions" in name:
                            available_sensors.add("tide_state")
                else:
                    _LOGGER.error(
                        "Products endpoint returned %s for station %s",
                        prod_resp.status,
                        station_id,
                    )
        except Exception as e:
            _LOGGER.error("Error fetching products for station %s: %s", station_id, e)

        # Try to fetch the sensors endpoint
        try:
            async with session.get(sensors_url) as sensor_resp:
                if sensor_resp.status == 200:
                    sensor_data = await sensor_resp.json()
                    sensors_list = sensor_data.get("sensors") or []
                    for sensor in sensors_list:
                        sensor_name = sensor.get("name", "").lower()
                        if "air temperature" in sensor_name:
                            available_sensors.add("air_temp")
                        if "water temperature" in sensor_name:
                            available_sensors.add("water_temp")
                else:
                    _LOGGER.error(
                        "Sensors endpoint returned %s for station %s",
                        sensor_resp.status,
                        station_id,
                    )
        except Exception as e:
            _LOGGER.error("Error fetching sensors for station %s: %s", station_id, e)

    _LOGGER.debug("Available sensors for station %s: %s", station_id, available_sensors)
    return list(available_sensors)


async def async_fetch_noaa_data(
    session: aiohttp.ClientSession,
    station_id: str,
    timezone: str,
    unit_system: str,
) -> dict[str, Any]:
    """Fetch data from NOAA's CO-OPS API using aiohttp."""
    noaa_units = "english" if unit_system == "imperial" else "metric"

    results = {
        "current_tide_event": None,
        "measured_level": None,
        "next_tide_type": None,
        "next_tide_time": None,
        "next_tide_level": None,
        "last_tide_type": None,
        "last_tide_time": None,
        "last_tide_level": None,
        "tide_factor": None,
        "tide_percentage": None,
        "water_temperature": None,
        "air_temperature": None,
    }

    now_utc = datetime.utcnow()
    begin_date = (now_utc - timedelta(hours=24)).strftime("%Y%m%d %H:%M")
    end_date = (now_utc + timedelta(hours=24)).strftime("%Y%m%d %H:%M")

    try:
        # Fetch tide predictions
        tide_params = {
            "station": station_id,
            "product": "predictions",
            "interval": "hilo",
            "time_zone": timezone,
            "units": noaa_units,
            "format": "json",
            "datum": "MLLW",
            "application": APPLICATION_NAME,
            "begin_date": begin_date,
            "end_date": end_date,
        }

        async with session.get(BASE_URL, params=tide_params) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"Failed to fetch tide predictions: {resp.status}")
            tide_data = await resp.json()

        if tide_data.get("predictions"):
            events = []
            for event in tide_data["predictions"]:
                event_time = datetime.strptime(event["t"], "%Y-%m-%d %H:%M")
                events.append((event_time, float(event["v"]), event["type"]))

            events.sort(key=lambda x: x[0])

            # Find the last tide before now and the next tide after now
            last_tide = None
            next_tide = None
            now = datetime.now()

            for event in events:
                event_time = event[0]
                if event_time <= now:
                    # Update last_tide if this event is closer to now_utc than the previous last_tidezz
                    if last_tide is None or event_time > last_tide[0]:
                        last_tide = event
                elif event_time > now:
                    # Assign next_tide to the first event after now_utc and break
                    next_tide = event
                    break

            if last_tide:
                results["last_tide_time"] = last_tide[0].isoformat()
                results["last_tide_level"] = last_tide[1]
                results["last_tide_type"] = "High" if last_tide[2] == "H" else "Low"

            if next_tide:
                results["next_tide_time"] = next_tide[0].isoformat()
                results["next_tide_level"] = next_tide[1]
                results["next_tide_type"] = "High" if next_tide[2] == "H" else "Low"

            # Determine current tide event
            if last_tide and next_tide:
                if last_tide[2] == "L" and next_tide[2] == "H":
                    results["current_tide_event"] = "Rising"
                elif last_tide[2] == "H" and next_tide[2] == "L":
                    results["current_tide_event"] = "Falling"
                else:
                    results["current_tide_event"] = "Unknown"

        # Fetch station data
        async def fetch_latest_data(product):
            params = {
                "station": station_id,
                "product": product,
                "time_zone": timezone,
                "units": noaa_units,
                "format": "json",
                "application": APPLICATION_NAME,
                "datum": "MLLW",
                "date": "latest",
            }
            async with session.get(BASE_URL, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data["data"][-1]["v"]) if data.get("data") else None
                return None

        results["measured_level"] = await fetch_latest_data("water_level")
        results["water_temperature"] = await fetch_latest_data("water_temperature")
        results["air_temperature"] = await fetch_latest_data("air_temperature")

    except Exception as err:
        _LOGGER.warning("Error fetching NOAA data: %s", err)
        raise UpdateFailed(f"Error fetching NOAA data: {err}") from err

    return results


async def async_fetch_ndbc_data(
    session: aiohttp.ClientSession,
    station_id: str,
    unit_system: str,
) -> dict[str, Any]:
    """Fetch data from the NDBC realtime text endpoint and parse sensor values."""
    url = f"https://www.ndbc.noaa.gov/data/realtime2/{station_id}.txt"
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"Failed to fetch NDBC data: {resp.status}")
            text = await resp.text()
    except Exception as err:
        _LOGGER.error("Error fetching NDBC data: %s", err)
        raise UpdateFailed(f"Error fetching NDBC data: {err}") from err

    lines = text.splitlines()
    if not lines:
        raise UpdateFailed("No data received from NDBC API")

    # Assume the first nonempty line is the header.
    header = lines[0].strip().split()
    if header[0].startswith("#"):
        header[0] = header[0].lstrip("#")

    # Many NDBC realtime files include a header (and sometimes units) then one or more data rows.
    # Here we try to use the second line if it can be parsed as data;
    # otherwise we use the last line.
    data_line = None
    if len(lines) > 1:
        try:
            parts = lines[1].strip().split()
            float(parts[0])
            data_line = parts
        except ValueError:
            if len(lines) > 2:
                data_line = lines[2].strip().split()
        if data_line is None:
            data_line = lines[-1].strip().split()
    else:
        raise UpdateFailed("Insufficient data from NDBC API")

    data_dict = dict(zip(header, data_line))

    timestamp = None
    if all(key in data_dict for key in ["YY", "MM", "DD", "hh", "mm"]):
        try:
            year = int(data_dict["YY"])
            if year < 100:
                year += 2000
            month = int(data_dict["MM"])
            day = int(data_dict["DD"])
            hour = int(data_dict["hh"])
            minute = int(data_dict["mm"])
            timestamp = datetime(year, month, day, hour, minute)
        except Exception as e:
            _LOGGER.error("Error parsing timestamp from NDBC data: %s", e)

    results = {
        "timestamp": timestamp.isoformat() if timestamp else None,
        "wind_direction": float(data_dict.get("WDIR", 0))
        if data_dict.get("WDIR") not in (None, "MM")
        else None,
        "wind_speed": float(data_dict.get("WSPD", 0))
        if data_dict.get("WSPD") not in (None, "MM")
        else None,
        "wave_height": float(data_dict.get("WVHT", 0))
        if data_dict.get("WVHT") not in (None, "MM")
        else None,
        "air_temperature": float(data_dict.get("ATMP", 0))
        if data_dict.get("ATMP") not in (None, "MM")
        else None,
        "water_temperature": float(data_dict.get("WTMP", 0))
        if data_dict.get("WTMP") not in (None, "MM")
        else None,
        "barometric_pressure": float(data_dict.get("PRES", 0))
        if data_dict.get("PRES") not in (None, "MM")
        else None,
    }

    # If imperial units are desired, convert some values.
    if unit_system.lower() == "imperial":
        if results["wind_speed"] is not None:
            results["wind_speed"] = round(
                results["wind_speed"] * 2.23694, 2
            )  # m/s to mph
        if results["wave_height"] is not None:
            results["wave_height"] = round(
                results["wave_height"] * 3.28084, 2
            )  # m to ft
        if results["air_temperature"] is not None:
            results["air_temperature"] = round(
                (results["air_temperature"] * 9 / 5) + 32, 2
            )
        if results["water_temperature"] is not None:
            results["water_temperature"] = round(
                (results["water_temperature"] * 9 / 5) + 32, 2
            )
        if results["barometric_pressure"] is not None:
            results["barometric_pressure"] = round(
                results["barometric_pressure"] * 0.02953, 2
            )  # hPa to inHg

    return results


class NOAADataCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch NOAA or NDBC data periodically and cache it."""

    def __init__(self, hass, station_id, timezone, unit_system, station_type="NOAA"):
        self._hass = hass
        self.station_id = station_id
        self.timezone = timezone
        self.unit_system = unit_system
        self.station_type = station_type

        super().__init__(
            hass,
            _LOGGER,
            name="NOAA/NDBC Data Coordinator",
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from NOAA or NDBC and return as a dictionary."""
        try:
            async with aiohttp.ClientSession() as session:
                if self.station_type == "NDBC":
                    data = await async_fetch_ndbc_data(
                        session, self.station_id, self.unit_system
                    )
                else:
                    data = await async_fetch_noaa_data(
                        session, self.station_id, self.timezone, self.unit_system
                    )
                return data
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
