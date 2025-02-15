"""Sensor platform for NOAA Tides integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, TypedDict

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .coordinator import NoaaTidesDataUpdateCoordinator, SensorData


class WindSensorAttributes(TypedDict):
    """Wind sensor attributes type."""

    direction: float | None
    direction_cardinal: str | None
    gust: float | None
    time: str
    flags: str | None


class TideSensorAttributes(TypedDict):
    """Tide sensor attributes type."""

    time: str
    units: str
    datum: str


class MeteoSensorAttributes(TypedDict):
    """Meteorological sensor attributes type."""

    raw_value: str
    parameter: str


@dataclass(frozen=True)
class NoaaTidesSensorEntityDescription(SensorEntityDescription):
    """Class describing NOAA Tides sensor entities."""

    unit_metric: str | None = None
    unit_imperial: str | None = None


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
    ),
    "tide_predictions": NoaaTidesSensorEntityDescription(
        key="tide_predictions",
        name="Tide State",
        icon="mdi:waves",
    ),
    "currents_speed": NoaaTidesSensorEntityDescription(
        key="currents_speed",
        name="Currents Speed",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfSpeed.METERS_PER_SECOND,
        unit_imperial=UnitOfSpeed.KNOTS,
    ),
    "currents_direction": NoaaTidesSensorEntityDescription(
        key="currents_direction",
        name="Currents Direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "currents_predictions": NoaaTidesSensorEntityDescription(
        key="currents_predictions",
        name="Predicted Currents State",
        icon="mdi:wave",
    ),
    "air_temperature": NoaaTidesSensorEntityDescription(
        key="air_temperature",
        name="Air Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfTemperature.CELSIUS,
        unit_imperial=UnitOfTemperature.FAHRENHEIT,
    ),
    "water_temperature": NoaaTidesSensorEntityDescription(
        key="water_temperature",
        name="Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfTemperature.CELSIUS,
        unit_imperial=UnitOfTemperature.FAHRENHEIT,
    ),
    "wind_speed": NoaaTidesSensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfSpeed.KILOMETERS_PER_HOUR,
        unit_imperial=UnitOfSpeed.MILES_PER_HOUR,
    ),
    "wind_direction": NoaaTidesSensorEntityDescription(
        key="wind_direction",
        name="Wind Direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "air_pressure": NoaaTidesSensorEntityDescription(
        key="air_pressure",
        name="Barometric Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfPressure.HPA,
        unit_imperial=UnitOfPressure.INHG,
    ),
    "humidity": NoaaTidesSensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "conductivity": NoaaTidesSensorEntityDescription(
        key="conductivity",
        name="Conductivity",
        icon="mdi:flash",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mS/cm",
    ),
}

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
    ),
    "meteo_wspd": NoaaTidesSensorEntityDescription(
        key="meteo_wspd",
        name="Wind Speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfSpeed.METERS_PER_SECOND,
        unit_imperial=UnitOfSpeed.MILES_PER_HOUR,
    ),
    "meteo_gst": NoaaTidesSensorEntityDescription(
        key="meteo_gst",
        name="Wind Gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfSpeed.METERS_PER_SECOND,
        unit_imperial=UnitOfSpeed.MILES_PER_HOUR,
        icon="mdi:weather-windy-variant",
    ),
    "meteo_wvht": NoaaTidesSensorEntityDescription(
        key="meteo_wvht",
        name="Wave Height",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfLength.METERS,
        unit_imperial=UnitOfLength.FEET,
        icon="mdi:waves",
    ),
    "meteo_dpd": NoaaTidesSensorEntityDescription(
        key="meteo_dpd",
        name="Dominant Wave Period",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="s",  # Periods don't need conversion
        icon="mdi:wave",
    ),
    "meteo_apd": NoaaTidesSensorEntityDescription(
        key="meteo_apd",
        name="Average Wave Period",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="s",  # Periods don't need conversion
        icon="mdi:wave",
    ),
    "meteo_mwd": NoaaTidesSensorEntityDescription(
        key="meteo_mwd",
        name="Wave Direction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,  # Directions don't need conversion
        icon="mdi:compass",
    ),
    "meteo_wtmp": NoaaTidesSensorEntityDescription(
        key="meteo_wtmp",
        name="Water Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfTemperature.CELSIUS,
        unit_imperial=UnitOfTemperature.FAHRENHEIT,
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
    ),
    "spec_wave_swh": NoaaTidesSensorEntityDescription(
        key="spec_wave_swh",
        name="Swell Height",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfLength.METERS,
        unit_imperial=UnitOfLength.FEET,
        icon="mdi:waves",
    ),
    "spec_wave_swp": NoaaTidesSensorEntityDescription(
        key="spec_wave_swp",
        name="Swell Period",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="s",  # Periods don't need conversion
        icon="mdi:timer",
    ),
    "spec_wave_wwh": NoaaTidesSensorEntityDescription(
        key="spec_wave_wwh",
        name="Wind Wave Height",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_metric=UnitOfLength.METERS,
        unit_imperial=UnitOfLength.FEET,
        icon="mdi:waves",
    ),
    "spec_wave_wwp": NoaaTidesSensorEntityDescription(
        key="spec_wave_wwp",
        name="Wind Wave Period",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="s",  # Periods don't need conversion
        icon="mdi:timer",
    ),
    "spec_wave_swd": NoaaTidesSensorEntityDescription(
        key="spec_wave_swd",
        name="Swell Direction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,  # Directions don't need conversion
        icon="mdi:compass",
    ),
    "spec_wave_wwd": NoaaTidesSensorEntityDescription(
        key="spec_wave_wwd",
        name="Wind Wave Direction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,  # Directions don't need conversion
        icon="mdi:compass",
    ),
    "spec_wave_steepness": NoaaTidesSensorEntityDescription(
        key="spec_wave_steepness",
        name="Wave Steepness",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sine-wave",
    ),
    "spec_wave_apd": NoaaTidesSensorEntityDescription(
        key="spec_wave_apd",
        name="Average Wave Period",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="s",  # Periods don't need conversion
        icon="mdi:timer",
    ),
    "spec_wave_mwd": NoaaTidesSensorEntityDescription(
        key="spec_wave_mwd",
        name="Mean Wave Direction",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,  # Directions don't need conversion
        icon="mdi:compass",
    ),
    # Ocean Current Sensors
    "current_depth": NoaaTidesSensorEntityDescription(
        key="current_depth",
        name="Current Depth",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "current_drct": NoaaTidesSensorEntityDescription(
        key="current_drct",
        name="Current Direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "current_spdd": NoaaTidesSensorEntityDescription(
        key="current_spdd",
        name="Current Speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up NOAA Tides sensors based on a config entry."""
    coordinator: NoaaTidesDataUpdateCoordinator = hass.data[const.DOMAIN][
        entry.entry_id
    ]

    # Get the user-configured name from the config entry
    station_name = entry.data.get("name", "").lower().replace(" ", "_")

    # Determine which sensor descriptions to use based on hub type
    sensor_types = (
        NOAA_SENSOR_TYPES
        if coordinator.hub_type == const.HUB_TYPE_NOAA
        else NDBC_SENSOR_TYPES
    )

    # Create sensor entities for each selected sensor using list comprehension
    entities = [
        NoaaTidesSensor(
            coordinator=coordinator,
            description=sensor_types[sensor_id],
            entry_id=entry.entry_id,
            station_name=station_name,
        )
        for sensor_id in coordinator.selected_sensors
        if sensor_id in sensor_types
    ]

    async_add_entities(entities)
    return True


class NoaaTidesSensor(CoordinatorEntity[NoaaTidesDataUpdateCoordinator], SensorEntity):
    """Representation of a NOAA Tides sensor."""

    entity_description: NoaaTidesSensorEntityDescription
    _attr_has_entity_name = True
    _attr_unique_id: str
    _attr_device_info: DeviceInfo
    _attr_native_unit_of_measurement: str | None
    _attr_native_value: float | str | None = None
    _attr_extra_state_attributes: dict[str, Any] = {}

    def __init__(
        self,
        coordinator: NoaaTidesDataUpdateCoordinator,
        description: NoaaTidesSensorEntityDescription,
        entry_id: str,
        station_name: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: The data update coordinator
            description: The sensor entity description
            entry_id: The config entry ID
            station_name: The station name for entity ID

        """
        super().__init__(coordinator)
        self.entity_description = description

        # Generate a unique ID
        self._attr_unique_id = f"{entry_id}_{description.key}"

        # Set the entity ID to include station name
        self.entity_id = f"sensor.{station_name}_{description.key}"

        # Set up device info
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, entry_id)},
            name=(
                f"NOAA Station {coordinator.station_id}"
                if coordinator.hub_type == const.HUB_TYPE_NOAA
                else f"NDBC Buoy {coordinator.station_id}"
            ),
            manufacturer=(
                "NOAA" if coordinator.hub_type == const.HUB_TYPE_NOAA else "NDBC"
            ),
            model=coordinator.hub_type,
        )

        # Set the native unit of measurement based on unit system and sensor type
        if coordinator.hub_type == const.HUB_TYPE_NDBC:
            # Handle NDBC sensors
            if coordinator.unit_system == const.UNIT_IMPERIAL:
                if description.key.endswith(("_wspd", "_gst")):
                    self._attr_native_unit_of_measurement = UnitOfSpeed.MILES_PER_HOUR
                elif description.key.endswith(("_atmp", "_wtmp", "_dewp")):
                    self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
                elif description.key.endswith(("_wvht", "_swh", "_wwh")):
                    self._attr_native_unit_of_measurement = UnitOfLength.FEET
                elif description.key.endswith("_pres"):
                    self._attr_native_unit_of_measurement = UnitOfPressure.INHG
                else:
                    # For sensors that don't need conversion (directions, periods)
                    self._attr_native_unit_of_measurement = (
                        description.native_unit_of_measurement
                    )
            elif (
                description.key.endswith(("_wvht", "_swh", "_wwh"))
                or "wave" in description.key
            ):
                self._attr_native_unit_of_measurement = UnitOfLength.METERS
            else:
                self._attr_native_unit_of_measurement = (
                    description.native_unit_of_measurement
                )
        elif description.unit_metric and description.unit_imperial:
            # Handle NOAA sensors - use description's unit configuration
            self._attr_native_unit_of_measurement = (
                description.unit_metric
                if coordinator.unit_system == const.UNIT_METRIC
                else description.unit_imperial
            )
        else:
            self._attr_native_unit_of_measurement = (
                description.native_unit_of_measurement
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self.coordinator.data is not None
            and self.entity_description.key in self.coordinator.data
        ):
            sensor_data: SensorData = self.coordinator.data[self.entity_description.key]
            self._attr_native_value = sensor_data.get("state")
            self._attr_extra_state_attributes = sensor_data.get("attributes", {})

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self.coordinator.data is None:
            return False
        return (
            self.entity_description.key in self.coordinator.data
            and self.coordinator.data[self.entity_description.key].get("state")
            is not None
        )
