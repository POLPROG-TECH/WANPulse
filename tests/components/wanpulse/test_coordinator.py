"""Tests for WANPulse coordinator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.wanpulse.const import (
    CONF_FAILURE_THRESHOLD,
    CONF_PROBE_COUNT,
    CONF_SCAN_INTERVAL,
    CONF_TARGETS,
    CONF_TIMEOUT,
)
from custom_components.wanpulse.coordinator import WANPulseCoordinator
from custom_components.wanpulse.models import (
    ProbeMethod,
    ProbeResult,
    ProbeTarget,
)


def _make_entry(
    targets: list[dict] | None = None,
    scan_interval: int = 60,
    timeout: int = 10,
    probe_count: int = 3,
    failure_threshold: int = 3,
) -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = {CONF_TARGETS: targets or [{"host": "1.1.1.1", "label": "CF", "method": "tcp"}]}
    entry.options = {
        CONF_SCAN_INTERVAL: scan_interval,
        CONF_TIMEOUT: timeout,
        CONF_PROBE_COUNT: probe_count,
        CONF_FAILURE_THRESHOLD: failure_threshold,
    }
    entry.entry_id = "test_entry"
    return entry


class TestCoordinatorInit:
    """Tests for coordinator initialization."""

    def test_creates_target_states(self, hass: HomeAssistant) -> None:
        """GIVEN two TCP probe targets."""
        targets = [
            ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP),
            ProbeTarget(host="8.8.8.8", label="G", method=ProbeMethod.TCP),
        ]
        entry = _make_entry()
        coordinator = WANPulseCoordinator(hass, entry, targets)

        """THEN internal target states are initialised for each target."""
        assert len(coordinator._target_states) == 2
        assert "tcp_1_1_1_1" in coordinator._target_states
        assert "tcp_8_8_8_8" in coordinator._target_states

    def test_reads_options(self, hass: HomeAssistant) -> None:
        """GIVEN a config entry with custom options."""
        targets = [ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)]
        entry = _make_entry(scan_interval=30, timeout=5, probe_count=5, failure_threshold=5)
        coordinator = WANPulseCoordinator(hass, entry, targets)

        """THEN the coordinator stores the configured option values."""
        assert coordinator._timeout == 5
        assert coordinator._probe_count == 5
        assert coordinator._failure_threshold == 5


class TestCoordinatorProbing:
    """Tests for probe execution."""

    @pytest.mark.asyncio
    async def test_successful_probe_cycle(self, hass: HomeAssistant) -> None:
        """GIVEN a coordinator with one TCP target and a successful probe result."""
        targets = [ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)]
        entry = _make_entry(probe_count=2)
        coordinator = WANPulseCoordinator(hass, entry, targets)
        mock_result = ProbeResult(success=True, latency_ms=15.0)

        """WHEN a probe cycle completes successfully."""
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_result,
        ):
            snapshot = await coordinator._async_update_data()

        """THEN WAN is online and the target reports no failures."""
        assert snapshot.wan_is_online is True
        assert "tcp_1_1_1_1" in snapshot.targets
        target_snap = snapshot.targets["tcp_1_1_1_1"]
        assert target_snap.is_online is True
        assert target_snap.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_failed_probe_cycle(self, hass: HomeAssistant) -> None:
        """GIVEN a coordinator with failure threshold of 1 and a failing probe."""
        targets = [ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)]
        entry = _make_entry(probe_count=1, failure_threshold=1)
        coordinator = WANPulseCoordinator(hass, entry, targets)
        mock_result = ProbeResult(success=False, error="timeout")

        """WHEN a probe cycle fails."""
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_result,
        ):
            snapshot = await coordinator._async_update_data()

        """THEN WAN is offline and consecutive failures are recorded."""
        assert snapshot.wan_is_online is False
        target_snap = snapshot.targets["tcp_1_1_1_1"]
        assert target_snap.is_online is False
        assert target_snap.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_partial_failure_keeps_wan_online(self, hass: HomeAssistant) -> None:
        """GIVEN a coordinator with two TCP targets where one succeeds and one fails."""
        targets = [
            ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP),
            ProbeTarget(host="8.8.8.8", label="G", method=ProbeMethod.TCP),
        ]
        entry = _make_entry(probe_count=1, failure_threshold=1)
        coordinator = WANPulseCoordinator(hass, entry, targets)

        success = ProbeResult(success=True, latency_ms=10.0)
        failure = ProbeResult(success=False, error="timeout")

        call_count = 0

        async def mock_probe(target, timeout):
            nonlocal call_count
            call_count += 1
            if target.host == "1.1.1.1":
                return success
            return failure

        """WHEN a probe cycle runs with mixed results."""
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            side_effect=mock_probe,
        ):
            snapshot = await coordinator._async_update_data()

        """THEN WAN stays online because at least one target succeeded."""
        assert snapshot.wan_is_online is True
        assert snapshot.targets["tcp_1_1_1_1"].is_online is True
        assert snapshot.targets["tcp_8_8_8_8"].is_online is False

    @pytest.mark.asyncio
    async def test_partial_target_failure(self, hass: HomeAssistant) -> None:
        """GIVEN a coordinator with two TCP targets and a probe that fails for one."""
        targets = [
            ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP),
            ProbeTarget(host="8.8.8.8", label="Google", method=ProbeMethod.TCP),
        ]
        entry = _make_entry(probe_count=3, failure_threshold=1)
        coordinator = WANPulseCoordinator(hass, entry, targets)

        success = ProbeResult(success=True, latency_ms=10.0)
        fail = ProbeResult(success=False, error="timeout")

        async def mock_probe(target, timeout):
            if target.host == "1.1.1.1":
                return success
            return fail

        """WHEN a probe cycle runs."""
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            side_effect=mock_probe,
        ):
            snapshot = await coordinator._async_update_data()

        """THEN one target is online, one is offline, and aggregate WAN is online."""
        # One target online, one offline - aggregate should be online
        assert snapshot.wan_is_online is True
        assert snapshot.targets["tcp_1_1_1_1"].is_online is True
        assert snapshot.targets["tcp_1_1_1_1"].last_measurement.success is True
        assert snapshot.targets["tcp_8_8_8_8"].is_online is False
        assert snapshot.targets["tcp_8_8_8_8"].last_measurement.success is False


class TestOutageTracking:
    """Tests for outage state management."""

    @pytest.mark.asyncio
    async def test_outage_detection(self, hass: HomeAssistant) -> None:
        """GIVEN a coordinator with failure threshold of 2 and a failing probe."""
        targets = [ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)]
        entry = _make_entry(probe_count=1, failure_threshold=2)
        coordinator = WANPulseCoordinator(hass, entry, targets)
        mock_fail = ProbeResult(success=False, error="timeout")

        """WHEN two consecutive probe cycles fail."""
        """THEN an outage is detected."""
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_fail,
        ):
            # First failure - not yet in outage
            snapshot = await coordinator._async_update_data()
            assert snapshot.targets["tcp_1_1_1_1"].outage_count == 0
            assert snapshot.targets["tcp_1_1_1_1"].consecutive_failures == 1

            # Second failure - now in outage
            snapshot = await coordinator._async_update_data()
            assert snapshot.targets["tcp_1_1_1_1"].outage_count == 1
            assert snapshot.targets["tcp_1_1_1_1"].consecutive_failures == 2

    @pytest.mark.asyncio
    async def test_recovery_from_outage(self, hass: HomeAssistant) -> None:
        """GIVEN a coordinator with failure threshold of 1."""
        targets = [ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)]
        entry = _make_entry(probe_count=1, failure_threshold=1)
        coordinator = WANPulseCoordinator(hass, entry, targets)
        mock_fail = ProbeResult(success=False, error="timeout")
        mock_success = ProbeResult(success=True, latency_ms=10.0)

        """WHEN a probe cycle fails and a subsequent one succeeds."""
        # Fail first
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_fail,
        ):
            snapshot = await coordinator._async_update_data()
            assert snapshot.targets["tcp_1_1_1_1"].outage_count == 1

        # Recover
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_success,
        ):
            snapshot = await coordinator._async_update_data()

            """THEN the target recovers but the outage count is preserved."""
            assert snapshot.targets["tcp_1_1_1_1"].is_online is True
            assert snapshot.targets["tcp_1_1_1_1"].consecutive_failures == 0
            # Outage count doesn't decrease
            assert snapshot.targets["tcp_1_1_1_1"].outage_count == 1

    @pytest.mark.asyncio
    async def test_outage_duration_accumulates(self, hass: HomeAssistant) -> None:
        """GIVEN a coordinator with failure threshold of 1."""
        targets = [ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)]
        entry = _make_entry(probe_count=1, failure_threshold=1)
        coordinator = WANPulseCoordinator(hass, entry, targets)
        mock_fail = ProbeResult(success=False, error="timeout")
        mock_success = ProbeResult(success=True, latency_ms=10.0)

        """WHEN a failure causes an outage followed by recovery."""
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_fail,
        ):
            await coordinator._async_update_data()

        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_success,
        ):
            snapshot = await coordinator._async_update_data()

        """THEN the total outage duration is non-negative."""
        assert snapshot.targets["tcp_1_1_1_1"].total_outage_duration.total_seconds() >= 0


class TestAggregateMetrics:
    """Tests for aggregate statistics."""

    @pytest.mark.asyncio
    async def test_aggregate_with_all_online(self, hass: HomeAssistant) -> None:
        """GIVEN a coordinator with two TCP targets and all probes succeeding."""
        targets = [
            ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP),
            ProbeTarget(host="8.8.8.8", label="G", method=ProbeMethod.TCP),
        ]
        entry = _make_entry(probe_count=1)
        coordinator = WANPulseCoordinator(hass, entry, targets)
        mock_result = ProbeResult(success=True, latency_ms=15.0)

        """WHEN a probe cycle completes."""
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_result,
        ):
            snapshot = await coordinator._async_update_data()

        """THEN aggregate metrics show 100% availability with latency data."""
        assert snapshot.wan_is_online is True
        assert snapshot.aggregate_current.availability_pct == 100.0
        assert snapshot.aggregate_current.avg_latency_ms is not None

    @pytest.mark.asyncio
    async def test_aggregate_outage_count(self, hass: HomeAssistant) -> None:
        """GIVEN a coordinator with failure threshold of 1 and a failing probe."""
        targets = [ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)]
        entry = _make_entry(probe_count=1, failure_threshold=1)
        coordinator = WANPulseCoordinator(hass, entry, targets)
        mock_fail = ProbeResult(success=False, error="timeout")

        """WHEN a probe cycle fails."""
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_fail,
        ):
            snapshot = await coordinator._async_update_data()

            """THEN the aggregate outage count is incremented."""
            assert snapshot.outage_count == 1
