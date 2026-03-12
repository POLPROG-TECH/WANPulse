"""Tests for WANPulse diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from custom_components.wanpulse.diagnostics import async_get_config_entry_diagnostics
from custom_components.wanpulse.models import (
    CoordinatorSnapshot,
    ProbeMethod,
    ProbeTarget,
    TargetSnapshot,
    WindowStats,
)


def _make_snapshot() -> CoordinatorSnapshot:
    """Create a test snapshot."""
    target = ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)
    target_snap = TargetSnapshot(
        target=target,
        is_online=True,
        consecutive_failures=0,
        outage_count=2,
        total_outage_duration=timedelta(minutes=5),
        current=WindowStats(
            avg_latency_ms=15.0,
            packet_loss_pct=0.0,
            availability_pct=100.0,
            total_probes=10,
        ),
        hour=WindowStats(
            avg_latency_ms=14.0,
            availability_pct=99.5,
            total_probes=60,
        ),
        day=WindowStats(
            avg_latency_ms=16.0,
            availability_pct=98.0,
            total_probes=1440,
        ),
    )
    return CoordinatorSnapshot(
        targets={"tcp_1_1_1_1": target_snap},
        wan_is_online=True,
        outage_count=2,
        total_outage_duration=timedelta(minutes=5),
        last_update=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


class TestDiagnostics:
    """Tests for diagnostics output."""

    @pytest.mark.asyncio
    async def test_diagnostics_redacts_hosts(self) -> None:
        """Test that host and label are redacted."""
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "targets": [
                {"host": "1.1.1.1", "label": "Cloudflare DNS", "method": "tcp"},
            ]
        }
        entry.options = {"scan_interval": 60, "timeout": 10}

        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = coordinator

        result = await async_get_config_entry_diagnostics(hass, entry)

        # Hosts and labels should be redacted
        for target in result["entry_data"]["targets"]:
            assert target["host"] == "**REDACTED**"
            assert target["label"] == "**REDACTED**"
            # Method should NOT be redacted
            assert target["method"] == "tcp"

    @pytest.mark.asyncio
    async def test_diagnostics_includes_coordinator_data(self) -> None:
        """Test that coordinator data is included."""
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {"targets": [{"host": "1.1.1.1", "label": "CF", "method": "tcp"}]}
        entry.options = {"scan_interval": 60}

        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = coordinator

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["coordinator"]["wan_is_online"] is True
        assert result["coordinator"]["outage_count"] == 2
        assert result["coordinator"]["target_count"] == 1

    @pytest.mark.asyncio
    async def test_diagnostics_includes_target_details(self) -> None:
        """Test that per-target details are included."""
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {"targets": []}
        entry.options = {}

        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = coordinator

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert "tcp_1_1_1_1" in result["targets"]
        target_diag = result["targets"]["tcp_1_1_1_1"]
        assert target_diag["is_online"] is True
        assert target_diag["outage_count"] == 2
        assert target_diag["current_window"]["avg_latency_ms"] == 15.0

    @pytest.mark.asyncio
    async def test_diagnostics_method_not_redacted(self) -> None:
        """Test that probe method is visible in diagnostics."""
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "targets": [
                {"host": "1.1.1.1", "label": "CF", "method": "tcp"},
            ]
        }
        entry.options = {"scan_interval": 60}

        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = coordinator

        diag = await async_get_config_entry_diagnostics(hass, entry)
        targets = diag["entry_data"]["targets"]
        for t in targets:
            assert t.get("method") == "tcp"
            assert "**REDACTED**" not in str(t.get("method", ""))
