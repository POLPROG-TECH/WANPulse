"""Tests for WANPulse button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.wanpulse.button import WANPulseProbeButton


class TestProbeButton:
    """Tests for the probe now button."""

    def test_unique_id(self) -> None:
        coordinator = MagicMock()
        button = WANPulseProbeButton(coordinator, "test_entry")
        assert button.unique_id == "test_entry_probe_now"

    def test_suggested_object_id(self) -> None:
        coordinator = MagicMock()
        button = WANPulseProbeButton(coordinator, "test_entry")
        assert button.suggested_object_id == "probe_now"

    @pytest.mark.asyncio
    async def test_press_triggers_refresh(self) -> None:
        coordinator = MagicMock()
        coordinator.async_refresh = AsyncMock()

        button = WANPulseProbeButton(coordinator, "test_entry")
        await button.async_press()

        coordinator.async_refresh.assert_awaited_once()

    def test_has_entity_name(self) -> None:
        coordinator = MagicMock()
        button = WANPulseProbeButton(coordinator, "test_entry")
        assert button.has_entity_name is True

    def test_translation_key(self) -> None:
        coordinator = MagicMock()
        button = WANPulseProbeButton(coordinator, "test_entry")
        assert button.entity_description.translation_key == "probe_now"
