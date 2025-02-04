"""Sensor for the NOAA Tides and Currents component."""

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
    """Set up NOAA or NDBC sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    station_type = entry.data.get("station_type", "NOAA")
    if station_type == "NDBC":
        # If no sensor selection was made, supply a default set for NDBC buoys.
        selected_sensors = (
            entry.options.get("sensors")
            or entry.data.get("sensors")
            or [
                "wind_speed",
                "wind_direction",
                "wave_height",
                "water_temp",
                "air_temp",
                "barometric_pressure",
            ]
        )
        sensor_class_map = {
            "wind_speed": NDBCWindSpeedSensor,
            "wind_direction": NDBCWindDirectionSensor,
            "wave_height": NDBCWaveHeightSensor,
            "water_temp": NDBCWaterTempSensor,
            "air_temp": NDBCAirTempSensor,
            "barometric_pressure": NDBCBarometricPressureSensor,
        }
    else:
        selected_sensors = (
            entry.options.get("sensors") or entry.data.get("sensors") or []
        )
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


#
# --- NOAA sensor classes (unchanged) ---
#
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
            configuration_url=f"https://tidesandcurrents.noaa.gov/stationhome.html?id={self._station_id}",
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
        tide_time = (
            datetime.fromisoformat(data["next_tide_time"])
            .strftime("%I:%M %p")
            .lstrip("0")
        )
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


#
# --- New NDBC sensor classes ---
#
class NDBCBaseSensor(CoordinatorEntity, SensorEntity):
    """Base representation of an NDBC sensor."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._station_id = entry.data["station_id"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._station_id)},
            name=f"NDBC Station {self._station_id}",
            manufacturer="NDBC",
            configuration_url=f"https://www.ndbc.noaa.gov/station_page.php?station={self._station_id}",
        )

    @property
    def unique_id(self):
        return f"{DOMAIN}-{self._station_id}-{self._sensor_type}"

    @property
    def name(self):
        return (
            f"{self._entry.data['name']} {self._sensor_type.replace('_',' ').title()}"
        )

    @property
    def available(self):
        return super().available and self.coordinator.data is not None


class NDBCWindSpeedSensor(NDBCBaseSensor):
    """Sensor for wind speed from NDBC."""

    def __init__(self, coordinator, entry):
        self._sensor_type = "wind_speed"
        super().__init__(coordinator, entry)
        self._attr_icon = "mdi:weather-windy"

    @property
    def native_value(self):
        return self.coordinator.data.get("wind_speed")

    @property
    def native_unit_of_measurement(self):
        return "mph" if self.coordinator.unit_system.lower() == "imperial" else "m/s"


class NDBCWindDirectionSensor(NDBCBaseSensor):
    """Sensor for wind direction from NDBC."""

    def __init__(self, coordinator, entry):
        self._sensor_type = "wind_direction"
        super().__init__(coordinator, entry)
        self._attr_icon = "mdi:compass-outline"

    @property
    def native_value(self):
        return self.coordinator.data.get("wind_direction")

    @property
    def native_unit_of_measurement(self):
        return "°"


class NDBCWaveHeightSensor(NDBCBaseSensor):
    """Sensor for wave height from NDBC."""

    def __init__(self, coordinator, entry):
        self._sensor_type = "wave_height"
        super().__init__(coordinator, entry)
        self._attr_icon = "mdi:waves"

    @property
    def native_value(self):
        return self.coordinator.data.get("wave_height")

    @property
    def native_unit_of_measurement(self):
        return "ft" if self.coordinator.unit_system.lower() == "imperial" else "m"


class NDBCWaterTempSensor(NDBCBaseSensor):
    """Sensor for water temperature from NDBC."""

    def __init__(self, coordinator, entry):
        self._sensor_type = "water_temp"
        super().__init__(coordinator, entry)
        self._attr_icon = "mdi:coolant-temperature"
        self._attr_device_class = "temperature"
        self._attr_state_class = "measurement"

    @property
    def native_value(self):
        return self.coordinator.data.get("water_temperature")

    @property
    def native_unit_of_measurement(self):
        return (
            UnitOfTemperature.FAHRENHEIT
            if self.coordinator.unit_system.lower() == "imperial"
            else UnitOfTemperature.CELSIUS
        )


class NDBCAirTempSensor(NDBCBaseSensor):
    """Sensor for air temperature from NDBC."""

    def __init__(self, coordinator, entry):
        self._sensor_type = "air_temp"
        super().__init__(coordinator, entry)
        self._attr_icon = "mdi:thermometer"
        self._attr_device_class = "temperature"
        self._attr_state_class = "measurement"

    @property
    def native_value(self):
        return self.coordinator.data.get("air_temperature")

    @property
    def native_unit_of_measurement(self):
        return (
            UnitOfTemperature.FAHRENHEIT
            if self.coordinator.unit_system.lower() == "imperial"
            else UnitOfTemperature.CELSIUS
        )


class NDBCBarometricPressureSensor(NDBCBaseSensor):
    """Sensor for barometric pressure from NDBC."""

    def __init__(self, coordinator, entry):
        self._sensor_type = "barometric_pressure"
        super().__init__(coordinator, entry)
        self._attr_icon = "mdi:weather-cloudy"
        self._attr_device_class = "pressure"
        self._attr_state_class = "measurement"

    @property
    def native_value(self):
        return self.coordinator.data.get("barometric_pressure")

    @property
    def native_unit_of_measurement(self):
        return "inHg" if self.coordinator.unit_system.lower() == "imperial" else "hPa"
