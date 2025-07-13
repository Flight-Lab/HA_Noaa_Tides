"""Sensor platform for NOAA Tides integration."""

from __future__ import annotations

import logging
from typing import Any, Final

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .coordinator import NoaaTidesDataUpdateCoordinator
from .data_constants import LogMessages
from .sensors import NDBC_SENSOR_TYPES, NOAA_SENSOR_TYPES
from .types import (
    BaseSensorAttributes,
    CurrentsAttributes,
    MeteoAttributes,
    NoaaTidesSensorEntityDescription,
    TidePredictionAttributes,
    WaterLevelAttributes,
    WindAttributes,
)
from .utils import get_related_sensors, get_unit_for_sensor, is_part_of_composite_sensor

_LOGGER: Final = logging.getLogger(__name__)


def get_tide_icon(tide_factor: float, next_tide_type: str) -> str:
    """
    Get tide icon.

    Logic:
    - Low tide state (≤25%): Single wave icon
    - High tide state (≥75%): Multiple waves icon
    - Rising transition (25-75% toward high): Wave arrow up
    - Falling transition (75-25% toward low): Wave arrow down

    Args:
        tide_factor: Current tide factor (0-100)
        next_tide_type: Type of next tide ("High" or "Low")

    Returns:
        str: Material Design icon name
    """
    # Extreme states
    if tide_factor <= LOW_TIDE_THRESHOLD:
        return "mdi:wave"  # Low tide - single wave
    elif tide_factor >= HIGH_TIDE_THRESHOLD:
        return "mdi:waves"  # High tide - triple waves

    # Transition states
    elif next_tide_type == "High":
        return "mdi:wave-arrow-up"  # Rising toward high tide
    else:
        return "mdi:wave-arrow-down"  # Falling toward low tide


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NOAA Tides sensors based on a config entry.

    Args:
        hass: The HomeAssistant instance
        entry: The ConfigEntry to set up
        async_add_entities: Callback to add entities

    Raises:
        ConfigEntryNotReady: If sensor setup fails
    """
    coordinator: NoaaTidesDataUpdateCoordinator = hass.data[const.DOMAIN][
        entry.entry_id
    ]

    # Get the user-configured name from the config entry
    # Clean up station name for entity ID creation
    station_name = entry.data.get("name", "").lower().replace(" ", "_")

    # Determine which sensor descriptions to use based on hub type
    sensor_types = (
        NOAA_SENSOR_TYPES
        if coordinator.hub_type == const.HUB_TYPE_NOAA
        else NDBC_SENSOR_TYPES
    )

    # Create sensor entities for each selected sensor
    entities = []
    for sensor_id in coordinator.selected_sensors:
        if sensor_id in sensor_types:
            entities.append(
                NoaaTidesSensor(
                    coordinator=coordinator,
                    description=sensor_types[sensor_id],
                    entry_id=entry.entry_id,
                    station_name=station_name,
                    entry=entry,
                )
            )
        else:
            _LOGGER.warning(
                f"Selected sensor '{sensor_id}' not found in sensor types for "
                f"{'NOAA station' if coordinator.hub_type == const.HUB_TYPE_NOAA else 'NDBC buoy'}. Skipping."
            )

    if entities:
        async_add_entities(entities)
        _LOGGER.debug(
            LogMessages.SENSORS_DISCOVERED.format(
                source_type="NOAA Station"
                if coordinator.hub_type == const.HUB_TYPE_NOAA
                else "NDBC Buoy",
                source_id=coordinator.station_id,
                sensor_count=len(entities),
            )
        )
    else:
        error_msg = (
            f"No sensors were set up for {coordinator.station_id}. Check configuration."
        )
        _LOGGER.error(error_msg)
        raise ConfigEntryNotReady(error_msg)


class NoaaTidesSensor(CoordinatorEntity[NoaaTidesDataUpdateCoordinator], SensorEntity):
    """Representation of a NOAA Tides sensor."""

    entity_description: NoaaTidesSensorEntityDescription
    _attr_has_entity_name = True
    _attr_unique_id: str
    _attr_device_info: DeviceInfo
    _attr_native_unit_of_measurement: str | None
    _attr_native_value: float | str | None = None
    _attr_extra_state_attributes: (
        BaseSensorAttributes
        | WindAttributes
        | WaterLevelAttributes
        | TidePredictionAttributes
        | CurrentsAttributes
        | MeteoAttributes
    ) = {}

    def __init__(
        self,
        coordinator: NoaaTidesDataUpdateCoordinator,
        description: NoaaTidesSensorEntityDescription,
        entry_id: str,
        station_name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: The data update coordinator
            description: The sensor entity description
            entry_id: The config entry ID
            station_name: The station name for entity ID
            entry: The config entry
        """
        super().__init__(coordinator)
        self.entity_description = description
        self.entry = entry

        # Generate a unique ID
        self._attr_unique_id = f"{entry_id}_{description.key}"

        # Set the entity ID to include station name - ensure clean entity ID
        clean_station_name = station_name.lower().replace(" ", "_")
        self.entity_id = f"sensor.{clean_station_name}_{description.key}"

        # Reference the device that was created in __init__.py
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, entry_id)},
        )

        # Set the native unit of measurement using the utility function
        self._attr_native_unit_of_measurement = get_unit_for_sensor(
            description, coordinator.unit_system, coordinator.hub_type, description.key
        )

    @property
    def icon(self) -> str | None:
        """Return dynamic icon based on tide state for tide prediction sensors."""
        # Only apply dynamic icons to tide prediction sensors
        if self.entity_description.key != "tide_predictions":
            return self.entity_description.icon

        # Ensure we have coordinator data
        if not self.coordinator.data:
            return "mdi:waves"  # Safe fallback

        # Get tide prediction data
        tide_data = self.coordinator.data.get("tide_predictions")
        if not tide_data or not isinstance(tide_data, dict):
            return "mdi:waves"  # Safe fallback

        # Extract attributes for icon determination
        attributes = tide_data.get("attributes", {})
        tide_factor = attributes.get("tide_factor", 50.0)
        next_tide_type = attributes.get("next_tide_type", "High")

        # Return appropriate icon
        return get_tide_icon(tide_factor, next_tide_type)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            # No data available, mark entity as unavailable
            self._attr_available = False
            self.async_write_ha_state()
            return

        # Get sensor data for this entity's key
        sensor_data = self.coordinator.data.get(self.entity_description.key)

        # Handle the data based on its structure type
        if sensor_data is not None:
            if isinstance(sensor_data, dict):
                # Handle dictionary format (common in newer code)
                self._attr_native_value = sensor_data.get("state")
                self._attr_extra_state_attributes = sensor_data.get(
                    "attributes", {})
            else:
                # Handle object format with state/attributes properties
                self._attr_native_value = sensor_data.state
                self._attr_extra_state_attributes = sensor_data.attributes

            # Ensure numeric values have correct data type
            if self._attr_native_value is not None:
                if self.entity_description.device_class in [
                    SensorDeviceClass.TEMPERATURE,
                    SensorDeviceClass.PRESSURE,
                    SensorDeviceClass.HUMIDITY,
                    SensorDeviceClass.DISTANCE,
                    SensorDeviceClass.SPEED,
                ]:
                    try:
                        self._attr_native_value = float(
                            self._attr_native_value)
                    except (ValueError, TypeError):
                        _LOGGER.debug(
                            f"{'NOAA Station' if self.coordinator.hub_type == const.HUB_TYPE_NOAA else 'NDBC Buoy'} "
                            f"{self.coordinator.station_id}: Could not convert value '{self._attr_native_value}' "
                            f"to float for sensor {self.entity_description.key}"
                        )
                        # Keep the original value

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Check if coordinator has data
        if self.coordinator.data is None:
            return False

        # Get sensor data for this entity
        sensor_data = self.coordinator.data.get(self.entity_description.key)
        if sensor_data is None:
            # Check if this is a composite sensor that might be part of another sensor
            if is_part_of_composite_sensor(self.entity_description.key):
                return self._check_composite_availability()
            return False

        # Handle both dict and structured data types
        if isinstance(sensor_data, dict):
            return sensor_data.get("state") is not None

        try:
            return sensor_data.state is not None
        except AttributeError:
            _LOGGER.debug(
                f"{'NOAA Station' if self.coordinator.hub_type == const.HUB_TYPE_NOAA else 'NDBC Buoy'} "
                f"{self.coordinator.station_id}: Sensor data for {self.entity_description.key} "
                f"does not have a state attribute"
            )
            return False

    def _check_composite_availability(self) -> bool:
        """Check availability of related sensors in this sensor's composite group."""
        related_sensors = get_related_sensors(self.entity_description.key)

        for related_sensor in related_sensors:
            if related_sensor in self.coordinator.data:
                sensor_data = self.coordinator.data[related_sensor]
                if isinstance(sensor_data, dict):
                    if sensor_data.get("state") is not None:
                        return True
                else:
                    try:
                        if sensor_data.state is not None:
                            return True
                    except AttributeError:
                        _LOGGER.debug(
                            f"{'NOAA Station' if self.coordinator.hub_type == const.HUB_TYPE_NOAA else 'NDBC Buoy'} "
                            f"{self.coordinator.station_id}: Related sensor data for {related_sensor} "
                            f"does not have a state attribute"
                        )
                        continue
        return False
