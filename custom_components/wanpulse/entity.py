"""Base entity for WANPulse."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WANPulseCoordinator

# Compat: DeviceEntryType location varies across HA versions.
try:
    from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
except ImportError:
    try:
        from homeassistant.helpers.entity import DeviceInfo
    except ImportError:
        from homeassistant.helpers.device_registry import DeviceInfo
    DeviceEntryType = None  # type: ignore[assignment,misc]


class WANPulseEntity(CoordinatorEntity[WANPulseCoordinator]):
    """Base entity for WANPulse."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WANPulseCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        device_kwargs: dict = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "WANPulse",
            "manufacturer": "WANPulse",
            "model": "WAN Monitor",
        }
        if DeviceEntryType is not None:
            device_kwargs["entry_type"] = DeviceEntryType.SERVICE
        self._attr_device_info = DeviceInfo(**device_kwargs)
