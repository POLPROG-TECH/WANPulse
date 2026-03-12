"""Sensor platform for WANPulse."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

# Compat: EntityCategory moved between modules across HA versions.
try:
    from homeassistant.const import EntityCategory
except ImportError:
    from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]

try:
    from homeassistant.const import UnitOfTime
except ImportError:
    # Compat: UnitOfTime added in HA 2023.1.
    class UnitOfTime:  # type: ignore[no-redef]
        """Fallback UnitOfTime constants."""

        MILLISECONDS = "ms"
        MINUTES = "min"


from homeassistant.const import PERCENTAGE

from .entity import WANPulseEntity
from .models import CoordinatorSnapshot, TargetSnapshot

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import StateType

    from .coordinator import WANPulseCoordinator


@dataclass(frozen=True, kw_only=True)
class WANPulseAggregateSensorDescription(SensorEntityDescription):
    """Description for aggregate sensors."""

    value_fn: Callable[[CoordinatorSnapshot], StateType]


@dataclass(frozen=True, kw_only=True)
class WANPulseTargetSensorDescription(SensorEntityDescription):
    """Description for per-target sensors."""

    value_fn: Callable[[TargetSnapshot], StateType]


def _fmt_duration(seconds: float) -> float:
    """Format duration as minutes, rounded."""
    return round(seconds / 60.0, 1)


AGGREGATE_SENSORS: tuple[WANPulseAggregateSensorDescription, ...] = (
    WANPulseAggregateSensorDescription(
        key="average_latency",
        translation_key="average_latency",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: s.aggregate_current.avg_latency_ms,
    ),
    WANPulseAggregateSensorDescription(
        key="packet_loss",
        translation_key="packet_loss",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: s.aggregate_current.packet_loss_pct,
    ),
    WANPulseAggregateSensorDescription(
        key="jitter",
        translation_key="jitter",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: s.aggregate_current.jitter_ms,
    ),
    WANPulseAggregateSensorDescription(
        key="availability_1h",
        translation_key="availability_1h",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda s: s.aggregate_hour.availability_pct,
    ),
    WANPulseAggregateSensorDescription(
        key="availability_24h",
        translation_key="availability_24h",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda s: s.aggregate_day.availability_pct,
    ),
    WANPulseAggregateSensorDescription(
        key="outage_count_24h",
        translation_key="outage_count_24h",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: s.outage_count,
    ),
    WANPulseAggregateSensorDescription(
        key="min_latency",
        translation_key="min_latency",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.aggregate_current.min_latency_ms,
    ),
    WANPulseAggregateSensorDescription(
        key="max_latency",
        translation_key="max_latency",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.aggregate_current.max_latency_ms,
    ),
    WANPulseAggregateSensorDescription(
        key="consecutive_failures",
        translation_key="consecutive_failures",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: max((t.consecutive_failures for t in s.targets.values()), default=0),
    ),
    WANPulseAggregateSensorDescription(
        key="outage_duration_24h",
        translation_key="outage_duration_24h",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda s: _fmt_duration(s.total_outage_duration.total_seconds()),
    ),
)

TARGET_SENSORS: tuple[WANPulseTargetSensorDescription, ...] = (
    WANPulseTargetSensorDescription(
        key="target_latency",
        translation_key="target_latency",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.current.avg_latency_ms,
    ),
    WANPulseTargetSensorDescription(
        key="target_packet_loss",
        translation_key="target_packet_loss",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.current.packet_loss_pct,
    ),
    WANPulseTargetSensorDescription(
        key="target_jitter",
        translation_key="target_jitter",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.current.jitter_ms,
    ),
    WANPulseTargetSensorDescription(
        key="target_availability_1h",
        translation_key="target_availability_1h",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.hour.availability_pct,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WANPulse sensors."""
    coordinator: WANPulseCoordinator = entry.runtime_data.coordinator

    entities: list[SensorEntity] = []

    for description in AGGREGATE_SENSORS:
        entities.append(WANPulseAggregateSensor(coordinator, entry.entry_id, description))

    for target in coordinator.targets:
        for description in TARGET_SENSORS:
            entities.append(
                WANPulseTargetSensor(
                    coordinator, entry.entry_id, target.target_id, target.label, description
                )
            )

    async_add_entities(entities)


class WANPulseAggregateSensor(WANPulseEntity, SensorEntity):
    """Aggregate sensor for WANPulse."""

    entity_description: WANPulseAggregateSensorDescription

    def __init__(
        self,
        coordinator: WANPulseCoordinator,
        entry_id: str,
        description: WANPulseAggregateSensorDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def suggested_object_id(self) -> str:
        """Return stable object ID independent of translations."""
        return self.entity_description.key

    @property
    def native_value(self) -> StateType:
        """Return the current sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)


class WANPulseTargetSensor(WANPulseEntity, SensorEntity):
    """Per-target sensor for WANPulse."""

    entity_description: WANPulseTargetSensorDescription

    def __init__(
        self,
        coordinator: WANPulseCoordinator,
        entry_id: str,
        target_id: str,
        target_label: str,
        description: WANPulseTargetSensorDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._target_id = target_id
        self._target_label = target_label
        self._attr_unique_id = f"{entry_id}_{target_id}_{description.key}"
        self._attr_translation_placeholders = {"target": target_label}

    @property
    def suggested_object_id(self) -> str:
        """Return stable object ID independent of translations."""
        from homeassistant.util import slugify

        return f"{slugify(self._target_label)}_{self.entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the current sensor value."""
        if self.coordinator.data is None:
            return None
        target_snap = self.coordinator.data.targets.get(self._target_id)
        if target_snap is None:
            return None
        return self.entity_description.value_fn(target_snap)
