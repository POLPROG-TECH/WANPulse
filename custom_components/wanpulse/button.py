"""Button platform for WANPulse."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription

from .entity import WANPulseEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import WANPulseCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WANPulse buttons."""
    coordinator: WANPulseCoordinator = entry.runtime_data.coordinator
    async_add_entities([WANPulseProbeButton(coordinator, entry.entry_id)])


class WANPulseProbeButton(WANPulseEntity, ButtonEntity):
    """Button to trigger an immediate probe cycle."""

    entity_description = ButtonEntityDescription(
        key="probe_now",
        translation_key="probe_now",
    )

    def __init__(
        self,
        coordinator: WANPulseCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_probe_now"

    @property
    def suggested_object_id(self) -> str:
        """Return stable object ID independent of translations."""
        return self.entity_description.key

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_refresh()
