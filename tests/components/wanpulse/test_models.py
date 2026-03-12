"""Tests for WANPulse domain models."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.wanpulse.models import (
    ProbeMeasurement,
    ProbeMethod,
    ProbeResult,
    ProbeTarget,
    WindowStats,
    _compute_jitter,
    filter_measurements_by_window,
)


class TestProbeTarget:
    """Tests for ProbeTarget."""

    def test_target_id_tcp(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)
        assert target.target_id == "tcp_1_1_1_1"

    def test_target_id_http(self) -> None:
        target = ProbeTarget(host="https://example.com", label="Ex", method=ProbeMethod.HTTP)
        assert target.target_id == "http_https___example_com"

    def test_target_id_dns(self) -> None:
        target = ProbeTarget(host="www.google.com", label="G", method=ProbeMethod.DNS)
        assert target.target_id == "dns_www_google_com"


class TestProbeResult:
    """Tests for ProbeResult."""

    def test_success_result(self) -> None:
        result = ProbeResult(success=True, latency_ms=10.5)
        assert result.success is True
        assert result.latency_ms == 10.5
        assert result.error is None

    def test_failure_result(self) -> None:
        result = ProbeResult(success=False, error="timeout")
        assert result.success is False
        assert result.latency_ms is None
        assert result.error == "timeout"


class TestProbeMeasurement:
    """Tests for ProbeMeasurement."""

    def test_from_empty_results(self) -> None:
        now = datetime.now(tz=UTC)
        m = ProbeMeasurement.from_probe_results("t1", [], now)
        assert m.success is False
        assert m.error == "No probes executed"

    def test_from_all_successful(self) -> None:
        now = datetime.now(tz=UTC)
        results = [
            ProbeResult(success=True, latency_ms=10.0),
            ProbeResult(success=True, latency_ms=20.0),
            ProbeResult(success=True, latency_ms=15.0),
        ]
        m = ProbeMeasurement.from_probe_results("t1", results, now)
        assert m.success is True
        assert m.avg_latency_ms == 15.0
        assert m.min_latency_ms == 10.0
        assert m.max_latency_ms == 20.0
        assert m.jitter_ms is not None
        assert m.packet_loss_pct == 0.0
        assert m.probes_sent == 3
        assert m.probes_received == 3

    def test_from_partial_failure(self) -> None:
        now = datetime.now(tz=UTC)
        results = [
            ProbeResult(success=True, latency_ms=10.0),
            ProbeResult(success=False, error="timeout"),
            ProbeResult(success=True, latency_ms=20.0),
        ]
        m = ProbeMeasurement.from_probe_results("t1", results, now)
        assert m.success is True
        assert m.probes_sent == 3
        assert m.probes_received == 2
        assert m.packet_loss_pct == pytest.approx(33.3, abs=0.1)

    def test_from_all_failed(self) -> None:
        now = datetime.now(tz=UTC)
        results = [
            ProbeResult(success=False, error="err1"),
            ProbeResult(success=False, error="err2"),
        ]
        m = ProbeMeasurement.from_probe_results("t1", results, now)
        assert m.success is False
        assert m.avg_latency_ms is None
        assert m.packet_loss_pct == 100.0
        assert m.error is not None
        assert "err1" in m.error
        assert "err2" in m.error

    def test_jitter_with_single_result(self) -> None:
        now = datetime.now(tz=UTC)
        results = [ProbeResult(success=True, latency_ms=10.0)]
        m = ProbeMeasurement.from_probe_results("t1", results, now)
        assert m.jitter_ms is None

    def test_rounding_precision(self) -> None:
        """Test that latencies are properly rounded."""
        now = datetime.now(tz=UTC)
        results = [
            ProbeResult(success=True, latency_ms=10.123456),
            ProbeResult(success=True, latency_ms=20.654321),
        ]
        m = ProbeMeasurement.from_probe_results("t1", results, now)
        assert m.avg_latency_ms is not None
        # Should be rounded to 2 decimal places
        assert m.avg_latency_ms == round((10.123456 + 20.654321) / 2, 2)

    def test_multiple_errors_joined(self) -> None:
        """Test error messages are joined."""
        now = datetime.now(tz=UTC)
        results = [
            ProbeResult(success=False, error="Error A"),
            ProbeResult(success=False, error="Error B"),
        ]
        m = ProbeMeasurement.from_probe_results("t1", results, now)
        assert m.error is not None
        assert "Error A" in m.error
        assert "Error B" in m.error


class TestWindowStats:
    """Tests for WindowStats."""

    def test_empty_measurements(self) -> None:
        stats = WindowStats.from_measurements([])
        assert stats.avg_latency_ms is None
        assert stats.availability_pct == 100.0
        assert stats.total_probes == 0

    def test_all_successful(self) -> None:
        now = datetime.now(tz=UTC)
        measurements = [
            ProbeMeasurement(
                timestamp=now,
                target_id="t1",
                success=True,
                avg_latency_ms=10.0,
                min_latency_ms=8.0,
                max_latency_ms=12.0,
                jitter_ms=2.0,
            ),
            ProbeMeasurement(
                timestamp=now,
                target_id="t1",
                success=True,
                avg_latency_ms=20.0,
                min_latency_ms=18.0,
                max_latency_ms=22.0,
                jitter_ms=3.0,
            ),
        ]
        stats = WindowStats.from_measurements(measurements)
        assert stats.avg_latency_ms == 15.0
        assert stats.min_latency_ms == 8.0
        assert stats.max_latency_ms == 22.0
        assert stats.jitter_ms == 2.5
        assert stats.availability_pct == 100.0
        assert stats.packet_loss_pct == 0.0
        assert stats.total_probes == 2
        assert stats.successful_probes == 2

    def test_mixed_results(self) -> None:
        now = datetime.now(tz=UTC)
        measurements = [
            ProbeMeasurement(
                timestamp=now,
                target_id="t1",
                success=True,
                avg_latency_ms=10.0,
                min_latency_ms=10.0,
                max_latency_ms=10.0,
            ),
            ProbeMeasurement(
                timestamp=now,
                target_id="t1",
                success=False,
            ),
        ]
        stats = WindowStats.from_measurements(measurements)
        assert stats.availability_pct == 50.0
        assert stats.packet_loss_pct == 50.0
        assert stats.total_probes == 2
        assert stats.successful_probes == 1

    def test_single_measurement(self) -> None:
        """Test stats from a single measurement."""
        now = datetime.now(tz=UTC)
        m = ProbeMeasurement(
            timestamp=now,
            target_id="t1",
            success=True,
            avg_latency_ms=10.0,
            min_latency_ms=10.0,
            max_latency_ms=10.0,
            jitter_ms=0.0,
            packet_loss_pct=0.0,
            probes_sent=3,
            probes_received=3,
        )
        stats = WindowStats.from_measurements([m])
        assert stats.avg_latency_ms == 10.0
        assert stats.jitter_ms == 0.0
        assert stats.availability_pct == 100.0

    def test_all_failed_measurements(self) -> None:
        """Test stats when all measurements failed."""
        now = datetime.now(tz=UTC)
        m = ProbeMeasurement(
            timestamp=now,
            target_id="t1",
            success=False,
            avg_latency_ms=None,
            min_latency_ms=None,
            max_latency_ms=None,
            jitter_ms=None,
            packet_loss_pct=100.0,
            probes_sent=3,
            probes_received=0,
        )
        stats = WindowStats.from_measurements([m])
        assert stats.availability_pct == 0.0
        assert stats.avg_latency_ms is None


class TestComputeJitter:
    """Tests for jitter computation."""

    def test_single_value(self) -> None:
        assert _compute_jitter([10.0]) == 0.0

    def test_empty(self) -> None:
        assert _compute_jitter([]) == 0.0

    def test_constant_latency(self) -> None:
        assert _compute_jitter([10.0, 10.0, 10.0]) == 0.0

    def test_varying_latency(self) -> None:
        result = _compute_jitter([10.0, 20.0, 10.0])
        assert result == 10.0


class TestFilterMeasurementsByWindow:
    """Tests for window filtering."""

    def test_filter_recent(self) -> None:
        now = datetime.now(tz=UTC)
        measurements = deque(
            [
                ProbeMeasurement(
                    timestamp=now - timedelta(seconds=30),
                    target_id="t1",
                    success=True,
                ),
                ProbeMeasurement(
                    timestamp=now - timedelta(seconds=90),
                    target_id="t1",
                    success=True,
                ),
                ProbeMeasurement(
                    timestamp=now - timedelta(seconds=200),
                    target_id="t1",
                    success=True,
                ),
            ]
        )
        result = filter_measurements_by_window(measurements, now, 60)
        assert len(result) == 1

        result = filter_measurements_by_window(measurements, now, 120)
        assert len(result) == 2

    def test_empty_deque(self) -> None:
        now = datetime.now(tz=UTC)
        result = filter_measurements_by_window(deque(), now, 60)
        assert len(result) == 0
