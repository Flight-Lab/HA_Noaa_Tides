"""NOAA station sensor definitions for NOAA Tides integration."""

from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)

from ..types import NoaaTidesSensorEntityDescription

# Sensor descriptions for NOAA Station
NOAA_SENSOR_TYPES: Final[dict[str, NoaaTidesSensorEntityDescription]] = {
    "water_level": NoaaTidesSensorEntityDescription(
        key="water_level",
        name="Water Level",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfLength.METERS,
        unit_imperial=UnitOfLength.FEET,
        is_ndbc=False,
    ),
    "tide_predictions": NoaaTidesSensorEntityDescription(
        key="tide_predictions",
        name="Tide State",
        # Icon determined dynamically by sensor's icon property
        is_ndbc=False,
    ),
    "currents_speed": NoaaTidesSensorEntityDescription(
        key="currents_speed",
        name="Currents Speed",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfSpeed.METERS_PER_SECOND,
        unit_imperial=UnitOfSpeed.KNOTS,
        is_ndbc=False,
    ),
    "currents_direction": NoaaTidesSensorEntityDescription(
        key="currents_direction",
        name="Currents Direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass",
        state_class=SensorStateClass.MEASUREMENT,
        is_ndbc=False,
    ),
    "currents_predictions": NoaaTidesSensorEntityDescription(
        key="currents_predictions",
        name="Predicted Currents State",
        icon="mdi:wave",
        is_ndbc=False,
    ),
    "air_temperature": NoaaTidesSensorEntityDescription(
        key="air_temperature",
        name="Air Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfTemperature.CELSIUS,
        unit_imperial=UnitOfTemperature.FAHRENHEIT,
        is_ndbc=False,
    ),
    "water_temperature": NoaaTidesSensorEntityDescription(
        key="water_temperature",
        name="Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfTemperature.CELSIUS,
        unit_imperial=UnitOfTemperature.FAHRENHEIT,
        is_ndbc=False,
    ),
    "wind_speed": NoaaTidesSensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfSpeed.KILOMETERS_PER_HOUR,
        unit_imperial=UnitOfSpeed.MILES_PER_HOUR,
        is_ndbc=False,
    ),
    "wind_direction": NoaaTidesSensorEntityDescription(
        key="wind_direction",
        name="Wind Direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass",
        state_class=SensorStateClass.MEASUREMENT,
        is_ndbc=False,
    ),
    "air_pressure": NoaaTidesSensorEntityDescription(
        key="air_pressure",
        name="Barometric Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfPressure.HPA,
        unit_imperial=UnitOfPressure.INHG,
        is_ndbc=False,
    ),
    "humidity": NoaaTidesSensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        is_ndbc=False,
    ),
    "conductivity": NoaaTidesSensorEntityDescription(
        key="conductivity",
        name="Conductivity",
        icon="mdi:flash",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mS/cm",
        is_ndbc=False,
    ),
}
