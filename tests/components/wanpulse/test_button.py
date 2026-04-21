"""Tests for WANPulse button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.wanpulse.button import WANPulseProbeButton


class TestProbeButton:
    """Tests for the probe now button."""

    """GIVEN a probe button entity"""
    def test_unique_id(self) -> None:
        coordinator = MagicMock()

        button = WANPulseProbeButton(coordinator, "test_entry")
        """WHEN unique id is evaluated"""

        """THEN unique_id includes the entry id and button key"""
        assert button.unique_id == "test_entry_probe_now"

    """GIVEN a probe button entity"""
    def test_suggested_object_id(self) -> None:
        coordinator = MagicMock()

        button = WANPulseProbeButton(coordinator, "test_entry")
        """WHEN suggested object id is evaluated"""

        """THEN suggested_object_id matches the expected value"""
        assert button.suggested_object_id == "probe_now"

    """GIVEN a probe button with a mock coordinator"""
    @pytest.mark.asyncio
    async def test_press_triggers_refresh(self) -> None:
        coordinator = MagicMock()
        coordinator.async_refresh = AsyncMock()
        button = WANPulseProbeButton(coordinator, "test_entry")

        """WHEN the button is pressed"""
        await button.async_press()

        """THEN the coordinator triggers a data refresh"""
        coordinator.async_refresh.assert_awaited_once()

    """GIVEN a probe button entity"""
    def test_has_entity_name(self) -> None:
        coordinator = MagicMock()

        button = WANPulseProbeButton(coordinator, "test_entry")
        """WHEN has entity name is evaluated"""

        """THEN the button reports it has an entity name"""
        assert button.has_entity_name is True

    """GIVEN a probe button entity"""
    def test_translation_key(self) -> None:
        coordinator = MagicMock()

        button = WANPulseProbeButton(coordinator, "test_entry")
        """WHEN translation key is evaluated"""

        """THEN the translation key matches the expected value"""
        assert button.entity_description.translation_key == "probe_now"
