"""NDBC buoy sensor definitions for NOAA Tides integration."""

from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    DEGREE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)

from ..types import NoaaTidesSensorEntityDescription

# Sensor descriptions for NDBC Buoy
NDBC_SENSOR_TYPES: Final[dict[str, NoaaTidesSensorEntityDescription]] = {
    # Meteorological Sensors
    "meteo_wdir": NoaaTidesSensorEntityDescription(
        key="meteo_wdir",
        name="Wind Direction",
        device_class=None,  # Direction doesn't need conversion
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass",
        is_ndbc=True,
    ),
    "meteo_wspd": NoaaTidesSensorEntityDescription(
        key="meteo_wspd",
        name="Wind Speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfSpeed.METERS_PER_SECOND,
        unit_imperial=UnitOfSpeed.MILES_PER_HOUR,
        is_ndbc=True,
    ),
    "meteo_gst": NoaaTidesSensorEntityDescription(
        key="meteo_gst",
        name="Wind Gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfSpeed.METERS_PER_SECOND,
        unit_imperial=UnitOfSpeed.MILES_PER_HOUR,
        icon="mdi:weather-windy-variant",
        is_ndbc=True,
    ),
    "meteo_wvht": NoaaTidesSensorEntityDescription(
        key="meteo_wvht",
        name="Wave Height",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfLength.METERS,
        unit_imperial=UnitOfLength.FEET,
        icon="mdi:waves",
        is_ndbc=True,
    ),
    "meteo_dpd": NoaaTidesSensorEntityDescription(
        key="meteo_dpd",
        name="Dominant Wave Period",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="s",  # Periods don't need conversion
        icon="mdi:wave",
        is_ndbc=True,
    ),
    "meteo_apd": NoaaTidesSensorEntityDescription(
        key="meteo_apd",
        name="Average Wave Period",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="s",  # Periods don't need conversion
        icon="mdi:wave",
        is_ndbc=True,
    ),
    "meteo_mwd": NoaaTidesSensorEntityDescription(
        key="meteo_mwd",
        name="Wave Direction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,  # Directions don't need conversion
        icon="mdi:compass",
        is_ndbc=True,
    ),
    # Temperature sensors: Always use Celsius - HA will handle conversion automatically
    "meteo_wtmp": NoaaTidesSensorEntityDescription(
        key="meteo_wtmp",
        name="Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # HA handles conversion
        is_ndbc=True,
    ),
    "meteo_atmp": NoaaTidesSensorEntityDescription(
        key="meteo_atmp",
        name="Air Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # HA handles conversion
        is_ndbc=True,
    ),
    "meteo_dewp": NoaaTidesSensorEntityDescription(
        key="meteo_dewp",
        name="Dew Point",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,  # HA handles conversion
        is_ndbc=True,
    ),
    # Non-temperature sensors with manual conversion
    "meteo_pres": NoaaTidesSensorEntityDescription(
        key="meteo_pres",
        name="Barometric Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfPressure.HPA,
        unit_imperial=UnitOfPressure.INHG,
        is_ndbc=True,
    ),
    "meteo_ptdy": NoaaTidesSensorEntityDescription(
        key="meteo_ptdy",
        name="Pressure Tendency",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfPressure.HPA,
        unit_imperial=UnitOfPressure.INHG,
        is_ndbc=True,
    ),
    "meteo_tide": NoaaTidesSensorEntityDescription(
        key="meteo_tide",
        name="Tide Level",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfLength.METERS,
        unit_imperial=UnitOfLength.FEET,
        icon="mdi:waves",
        is_ndbc=True,
    ),
    # Spectral Wave Sensors
    "spec_wave_wvht": NoaaTidesSensorEntityDescription(
        key="spec_wave_wvht",
        name="Wave Height",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfLength.METERS,
        unit_imperial=UnitOfLength.FEET,
        icon="mdi:waves",
        is_ndbc=True,
    ),
    "spec_wave_swh": NoaaTidesSensorEntityDescription(
        key="spec_wave_swh",
        name="Swell Height",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfLength.METERS,
        unit_imperial=UnitOfLength.FEET,
        icon="mdi:waves",
        is_ndbc=True,
    ),
    "spec_wave_swp": NoaaTidesSensorEntityDescription(
        key="spec_wave_swp",
        name="Swell Period",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="s",  # Periods don't need conversion
        icon="mdi:timer",
        is_ndbc=True,
    ),
    "spec_wave_wwh": NoaaTidesSensorEntityDescription(
        key="spec_wave_wwh",
        name="Wind Wave Height",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfLength.METERS,
        unit_imperial=UnitOfLength.FEET,
        icon="mdi:waves",
        is_ndbc=True,
    ),
    "spec_wave_wwp": NoaaTidesSensorEntityDescription(
        key="spec_wave_wwp",
        name="Wind Wave Period",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="s",  # Periods don't need conversion
        icon="mdi:timer",
        is_ndbc=True,
    ),
    "spec_wave_swd": NoaaTidesSensorEntityDescription(
        key="spec_wave_swd",
        name="Swell Direction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,  # Directions don't need conversion
        icon="mdi:compass",
        is_ndbc=True,
    ),
    "spec_wave_wwd": NoaaTidesSensorEntityDescription(
        key="spec_wave_wwd",
        name="Wind Wave Direction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,  # Directions don't need conversion
        icon="mdi:compass",
        is_ndbc=True,
    ),
    "spec_wave_steepness": NoaaTidesSensorEntityDescription(
        key="spec_wave_steepness",
        name="Wave Steepness",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sine-wave",
        is_ndbc=True,
    ),
    "spec_wave_apd": NoaaTidesSensorEntityDescription(
        key="spec_wave_apd",
        name="Average Wave Period",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="s",  # Periods don't need conversion
        icon="mdi:timer",
        is_ndbc=True,
    ),
    "spec_wave_mwd": NoaaTidesSensorEntityDescription(
        key="spec_wave_mwd",
        name="Mean Wave Direction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,  # Directions don't need conversion
        icon="mdi:compass",
        is_ndbc=True,
    ),
    # Ocean Current Sensors
    "current_depth": NoaaTidesSensorEntityDescription(
        key="current_depth",
        name="Current Depth",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        is_ndbc=True,
    ),
    "current_drct": NoaaTidesSensorEntityDescription(
        key="current_drct",
        name="Current Direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass",
        state_class=SensorStateClass.MEASUREMENT,
        is_ndbc=True,
    ),
    "current_spdd": NoaaTidesSensorEntityDescription(
        key="current_spdd",
        name="Current Speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        is_ndbc=True,
    ),
}
