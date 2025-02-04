"""Sensor for the NOAA Tides and Currents API."""

from datetime import datetime
import logging
import math

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up NOAA Tides sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    selected_sensors = entry.options.get("sensors") or entry.data.get("sensors") or []

    sensor_class_map = {
        "tide_state": NOAATidesSensor,
        "measured_level": NOAAMeasuredLevelSensor,
        "water_temp": NOAAWaterTempSensor,
        "air_temp": NOAAAirTempSensor,
    }

    entities = [
        sensor_class_map[sensor_key](coordinator, entry)
        for sensor_key in selected_sensors
        if sensor_key in sensor_class_map
    ]

    async_add_entities(entities)


class NOAABaseSensor(CoordinatorEntity, SensorEntity):
    """Base representation of a NOAA sensor."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._station_id = entry.data["station_id"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._station_id)},
            name=f"NOAA Station {self._station_id}",
            manufacturer="NOAA",
            configuration_url="https://tidesandcurrents.noaa.gov/map/index.html?type=datums",
        )

    @property
    def unique_id(self):
        """Return a unique ID for this sensor."""
        #  domain-stationid-sensortype
        return f"{DOMAIN}-{self._station_id}-{self._sensor_type}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return (
            f"{self._entry.data['name']} {self._sensor_type.replace('_',' ').title()}"
        )

    @property
    def available(self):
        """Return if entity is available."""
        return super().available and self.coordinator.data is not None


class NOAATidesSensor(NOAABaseSensor):
    """Sensor for displaying next tide status."""

    def __init__(self, coordinator, entry):
        """Initialize the tide state sensor."""
        self._sensor_type = "tide_state"
        super().__init__(coordinator, entry)
        self._attr_icon = "mdi:waves"
        self._attr_extra_state_attributes = {}

    @property
    def native_value(self):
        """Return the main sensor state: next tide type and time as a combined string."""
        data = self.coordinator.data
        if not data:
            return None
        tide_time = datetime.fromisoformat(data["next_tide_time"]).strftime("%I:%M %p").lstrip("0")
        return f"{data['next_tide_type']} at {tide_time}"

    @property
    def extra_state_attributes(self):
        """Calculate and return tide factor along with other attributes."""
        data = self.coordinator.data
        if not data:
            return {}

        now = datetime.utcnow()

        try:
            next_tide_time = datetime.fromisoformat(data.get("next_tide_time"))
            last_tide_time = datetime.fromisoformat(data.get("last_tide_time"))
        except (TypeError, ValueError):
            return {}

        # Update attributes from data
        attributes = {
            "current_tide_event": data.get("current_tide_event"),
            "next_tide_type": data.get("next_tide_type"),
            "next_tide_time": next_tide_time.strftime("%I:%M %p"),
            "last_tide_type": data.get("last_tide_type"),
            "last_tide_time": last_tide_time.strftime("%I:%M %p"),
            "next_tide_level": data.get("next_tide_level"),
            "last_tide_level": data.get("last_tide_level"),
        }

        # Calculate tide factor
        predicted_period = (next_tide_time - last_tide_time).total_seconds()
        elapsed_time = (now - last_tide_time).total_seconds()

        if elapsed_time < 0 or elapsed_time > predicted_period:
            return attributes  # Avoid calculations if time is out of range

        if attributes["next_tide_type"] == "High":
            tide_factor = 50 - (
                50 * math.cos(elapsed_time * math.pi / predicted_period)
            )
        else:
            tide_factor = 50 + (
                50 * math.cos(elapsed_time * math.pi / predicted_period)
            )

        # calculate tide percentage
        tide_percentage = (elapsed_time / predicted_period) * 50
        if attributes["next_tide_type"] == "High":
            tide_percentage += 50

        attributes["tide_factor"] = round(tide_factor, 2)
        attributes["tide_percentage"] = round(tide_percentage, 2)

        return attributes


class NOAAMeasuredLevelSensor(NOAABaseSensor):
    """Sensor for displaying the measured water level."""

    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        self._sensor_type = "measured_level"
        super().__init__(coordinator, entry)
        self._attr_icon = "mdi:waves-arrow-up"
        self._attr_state_class = "measurement"

    @property
    def native_value(self):
        """Return the measured water level."""
        data = self.coordinator.data
        if not data:
            return None
        return data.get("measured_level")

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.coordinator.unit_system.lower() == "imperial":
            return "ft"
        return "m"


class NOAAWaterTempSensor(NOAABaseSensor):
    """Sensor for water temperature."""

    def __init__(self, coordinator, entry):
        self._sensor_type = "water_temp"
        super().__init__(coordinator, entry)
        self._attr_icon = "mdi:coolant-temperature"
        self._attr_device_class = "temperature"
        self._attr_state_class = "measurement"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.coordinator.unit_system.lower() == "imperial":
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def native_value(self):
        """Return the water temperature."""
        data = self.coordinator.data
        if not data:
            return None
        return data.get("water_temperature")


class NOAAAirTempSensor(NOAABaseSensor):
    """Sensor for air temperature."""

    def __init__(self, coordinator, entry):
        self._sensor_type = "air_temp"
        super().__init__(coordinator, entry)
        self._attr_icon = "mdi:thermometer"
        self._attr_device_class = "temperature"
        self._attr_state_class = "measurement"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.coordinator.unit_system.lower() == "imperial":
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def native_value(self):
        """Return the air temperature."""
        data = self.coordinator.data
        if not data:
            return None
        return data.get("air_temperature")
