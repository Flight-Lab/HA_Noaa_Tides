"""Sensor platform for NOAA Tides integration."""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Final

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .coordinator import NoaaTidesDataUpdateCoordinator
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
                "Selected sensor '%s' not found in sensor types for %s. Skipping.",
                sensor_id,
                "NOAA station"
                if coordinator.hub_type == const.HUB_TYPE_NOAA
                else "NDBC buoy",
            )

    if entities:
        async_add_entities(entities)
        _LOGGER.debug("Set up %d sensors for %s", len(entities), coordinator.station_id)
    else:
        _LOGGER.warning(
            "No sensors were set up for %s. Check configuration.",
            coordinator.station_id,
        )

    return True


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

        # Get original name with proper case from config entry
        original_name = entry.data.get("name", "")
        clean_station_name = original_name.strip()

        # Set up device info - using cleaner approach
        self._attr_device_info = DeviceInfo(
            identifiers={(const.DOMAIN, entry_id)},
            name=clean_station_name,
            manufacturer=(
                "The National Oceanic & Atmospheric Administration"
                if coordinator.hub_type == const.HUB_TYPE_NOAA
                else "The National Data Buoy Center"
            ),
            model=(
                f"NOAA Station {coordinator.station_id}"
                if coordinator.hub_type == const.HUB_TYPE_NOAA
                else f"NDBC Buoy {coordinator.station_id}"
            ),
        )

        # Set the native unit of measurement using the utility function
        self._attr_native_unit_of_measurement = get_unit_for_sensor(
            description, coordinator.unit_system, coordinator.hub_type, description.key
        )

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
                self._attr_extra_state_attributes = sensor_data.get("attributes", {})
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
                    with contextlib.suppress(ValueError, TypeError):
                        self._attr_native_value = float(self._attr_native_value)

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

        with contextlib.suppress(AttributeError):
            return sensor_data.state is not None

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
                    with contextlib.suppress(AttributeError):
                        if sensor_data.state is not None:
                            return True
        return False
