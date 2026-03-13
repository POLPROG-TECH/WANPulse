"""Tests for WANPulse button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.wanpulse.button import WANPulseProbeButton


class TestProbeButton:
    """Tests for the probe now button."""

    def test_unique_id(self) -> None:
        """GIVEN a probe button entity."""
        coordinator = MagicMock()

        button = WANPulseProbeButton(coordinator, "test_entry")

        """THEN unique_id includes the entry id and button key."""
        assert button.unique_id == "test_entry_probe_now"

    def test_suggested_object_id(self) -> None:
        """GIVEN a probe button entity."""
        coordinator = MagicMock()

        button = WANPulseProbeButton(coordinator, "test_entry")

        """THEN suggested_object_id matches the expected value."""
        assert button.suggested_object_id == "probe_now"

    @pytest.mark.asyncio
    async def test_press_triggers_refresh(self) -> None:
        """GIVEN a probe button with a mock coordinator."""
        coordinator = MagicMock()
        coordinator.async_refresh = AsyncMock()
        button = WANPulseProbeButton(coordinator, "test_entry")

        """WHEN the button is pressed."""
        await button.async_press()

        """THEN the coordinator triggers a data refresh."""
        coordinator.async_refresh.assert_awaited_once()

    def test_has_entity_name(self) -> None:
        """GIVEN a probe button entity."""
        coordinator = MagicMock()

        button = WANPulseProbeButton(coordinator, "test_entry")

        """THEN the button reports it has an entity name."""
        assert button.has_entity_name is True

    def test_translation_key(self) -> None:
        """GIVEN a probe button entity."""
        coordinator = MagicMock()

        button = WANPulseProbeButton(coordinator, "test_entry")

        """THEN the translation key matches the expected value."""
        assert button.entity_description.translation_key == "probe_now"
