"""Binary sensor platform for WANPulse."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .entity import WANPulseEntity
from .models import CoordinatorSnapshot, TargetSnapshot

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import WANPulseCoordinator


@dataclass(frozen=True, kw_only=True)
class WANPulseAggregateBinarySensorDescription(BinarySensorEntityDescription):
    """Description for aggregate binary sensors."""

    value_fn: Callable[[CoordinatorSnapshot], bool | None]


@dataclass(frozen=True, kw_only=True)
class WANPulseTargetBinarySensorDescription(BinarySensorEntityDescription):
    """Description for per-target binary sensors."""

    value_fn: Callable[[TargetSnapshot], bool | None]


AGGREGATE_BINARY_SENSORS: tuple[WANPulseAggregateBinarySensorDescription, ...] = (
    WANPulseAggregateBinarySensorDescription(
        key="wan_status",
        translation_key="wan_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda s: s.wan_is_online,
    ),
)

TARGET_BINARY_SENSORS: tuple[WANPulseTargetBinarySensorDescription, ...] = (
    WANPulseTargetBinarySensorDescription(
        key="target_status",
        translation_key="target_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.is_online,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WANPulse binary sensors."""
    coordinator: WANPulseCoordinator = entry.runtime_data.coordinator

    entities: list[BinarySensorEntity] = []

    for description in AGGREGATE_BINARY_SENSORS:
        entities.append(WANPulseAggregateBinarySensor(coordinator, entry.entry_id, description))

    for target in coordinator.targets:
        for description in TARGET_BINARY_SENSORS:
            entities.append(
                WANPulseTargetBinarySensor(
                    coordinator, entry.entry_id, target.target_id, target.label, description
                )
            )

    async_add_entities(entities)


class WANPulseAggregateBinarySensor(WANPulseEntity, BinarySensorEntity):
    """Aggregate binary sensor for WANPulse."""

    entity_description: WANPulseAggregateBinarySensorDescription

    def __init__(
        self,
        coordinator: WANPulseCoordinator,
        entry_id: str,
        description: WANPulseAggregateBinarySensorDescription,
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
    def is_on(self) -> bool | None:
        """Return true if the WAN is online."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)


class WANPulseTargetBinarySensor(WANPulseEntity, BinarySensorEntity):
    """Per-target binary sensor for WANPulse."""

    entity_description: WANPulseTargetBinarySensorDescription

    def __init__(
        self,
        coordinator: WANPulseCoordinator,
        entry_id: str,
        target_id: str,
        target_label: str,
        description: WANPulseTargetBinarySensorDescription,
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
    def is_on(self) -> bool | None:
        """Return true if the target is online."""
        if self.coordinator.data is None:
            return None
        target_snap = self.coordinator.data.targets.get(self._target_id)
        if target_snap is None:
            return None
        return self.entity_description.value_fn(target_snap)
