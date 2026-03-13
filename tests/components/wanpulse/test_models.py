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
        """GIVEN a TCP probe target with host 1.1.1.1."""
        target = ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)

        """THEN target_id is derived from method and sanitised host."""
        assert target.target_id == "tcp_1_1_1_1"

    def test_target_id_http(self) -> None:
        """GIVEN an HTTP probe target with a URL host."""
        target = ProbeTarget(host="https://example.com", label="Ex", method=ProbeMethod.HTTP)

        """THEN target_id encodes the full URL with special chars replaced."""
        assert target.target_id == "http_https___example_com"

    def test_target_id_dns(self) -> None:
        """GIVEN a DNS probe target with a domain host."""
        target = ProbeTarget(host="www.google.com", label="G", method=ProbeMethod.DNS)

        """THEN target_id uses the dns prefix with dots replaced."""
        assert target.target_id == "dns_www_google_com"


class TestProbeResult:
    """Tests for ProbeResult."""

    def test_success_result(self) -> None:
        """GIVEN a successful probe result with latency."""
        result = ProbeResult(success=True, latency_ms=10.5)

        """THEN success is True, latency is recorded, and no error is set."""
        assert result.success is True
        assert result.latency_ms == 10.5
        assert result.error is None

    def test_failure_result(self) -> None:
        """GIVEN a failed probe result with an error message."""
        result = ProbeResult(success=False, error="timeout")

        """THEN success is False, latency is None, and error is captured."""
        assert result.success is False
        assert result.latency_ms is None
        assert result.error == "timeout"


class TestProbeMeasurement:
    """Tests for ProbeMeasurement."""

    def test_from_empty_results(self) -> None:
        """GIVEN an empty list of probe results."""
        now = datetime.now(tz=UTC)

        """WHEN creating a measurement."""
        m = ProbeMeasurement.from_probe_results("t1", [], now)

        """THEN the measurement indicates failure with an explanatory error."""
        assert m.success is False
        assert m.error == "No probes executed"

    def test_from_all_successful(self) -> None:
        """GIVEN three successful probe results with varying latencies."""
        now = datetime.now(tz=UTC)
        results = [
            ProbeResult(success=True, latency_ms=10.0),
            ProbeResult(success=True, latency_ms=20.0),
            ProbeResult(success=True, latency_ms=15.0),
        ]

        """WHEN creating a measurement."""
        m = ProbeMeasurement.from_probe_results("t1", results, now)

        """THEN aggregate statistics reflect full success with correct latency stats."""
        assert m.success is True
        assert m.avg_latency_ms == 15.0
        assert m.min_latency_ms == 10.0
        assert m.max_latency_ms == 20.0
        assert m.jitter_ms is not None
        assert m.packet_loss_pct == 0.0
        assert m.probes_sent == 3
        assert m.probes_received == 3

    def test_from_partial_failure(self) -> None:
        """GIVEN two successful and one failed probe result."""
        now = datetime.now(tz=UTC)
        results = [
            ProbeResult(success=True, latency_ms=10.0),
            ProbeResult(success=False, error="timeout"),
            ProbeResult(success=True, latency_ms=20.0),
        ]

        """WHEN creating a measurement."""
        m = ProbeMeasurement.from_probe_results("t1", results, now)

        """THEN the measurement is successful with ~33% packet loss."""
        assert m.success is True
        assert m.probes_sent == 3
        assert m.probes_received == 2
        assert m.packet_loss_pct == pytest.approx(33.3, abs=0.1)

    def test_from_all_failed(self) -> None:
        """GIVEN two failed probe results with distinct errors."""
        now = datetime.now(tz=UTC)
        results = [
            ProbeResult(success=False, error="err1"),
            ProbeResult(success=False, error="err2"),
        ]

        """WHEN creating a measurement."""
        m = ProbeMeasurement.from_probe_results("t1", results, now)

        """THEN the measurement is a failure with 100% packet loss and combined errors."""
        assert m.success is False
        assert m.avg_latency_ms is None
        assert m.packet_loss_pct == 100.0
        assert m.error is not None
        assert "err1" in m.error
        assert "err2" in m.error

    def test_jitter_with_single_result(self) -> None:
        """GIVEN a single successful probe result."""
        now = datetime.now(tz=UTC)
        results = [ProbeResult(success=True, latency_ms=10.0)]

        """WHEN creating a measurement."""
        m = ProbeMeasurement.from_probe_results("t1", results, now)

        """THEN jitter is None because it requires at least two samples."""
        assert m.jitter_ms is None

    def test_rounding_precision(self) -> None:
        """GIVEN two probe results with high-precision latencies."""
        now = datetime.now(tz=UTC)
        results = [
            ProbeResult(success=True, latency_ms=10.123456),
            ProbeResult(success=True, latency_ms=20.654321),
        ]

        """WHEN creating a measurement."""
        m = ProbeMeasurement.from_probe_results("t1", results, now)

        """THEN the average latency is rounded to 2 decimal places."""
        assert m.avg_latency_ms is not None
        # Should be rounded to 2 decimal places
        assert m.avg_latency_ms == round((10.123456 + 20.654321) / 2, 2)

    def test_multiple_errors_joined(self) -> None:
        """GIVEN two failed probe results with different error messages."""
        now = datetime.now(tz=UTC)
        results = [
            ProbeResult(success=False, error="Error A"),
            ProbeResult(success=False, error="Error B"),
        ]

        """WHEN creating a measurement."""
        m = ProbeMeasurement.from_probe_results("t1", results, now)

        """THEN the error string contains both error messages."""
        assert m.error is not None
        assert "Error A" in m.error
        assert "Error B" in m.error


class TestWindowStats:
    """Tests for WindowStats."""

    def test_empty_measurements(self) -> None:
        """GIVEN an empty list of measurements."""

        """WHEN computing window stats."""
        stats = WindowStats.from_measurements([])

        """THEN latency is None, availability defaults to 100%, and probe count is zero."""
        assert stats.avg_latency_ms is None
        assert stats.availability_pct == 100.0
        assert stats.total_probes == 0

    def test_all_successful(self) -> None:
        """GIVEN two successful measurements with different latency ranges."""
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

        """WHEN computing window stats."""
        stats = WindowStats.from_measurements(measurements)

        """THEN stats aggregate latencies, jitter, and report 100% availability."""
        assert stats.avg_latency_ms == 15.0
        assert stats.min_latency_ms == 8.0
        assert stats.max_latency_ms == 22.0
        assert stats.jitter_ms == 2.5
        assert stats.availability_pct == 100.0
        assert stats.packet_loss_pct == 0.0
        assert stats.total_probes == 2
        assert stats.successful_probes == 2

    def test_mixed_results(self) -> None:
        """GIVEN one successful and one failed measurement."""
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

        """WHEN computing window stats."""
        stats = WindowStats.from_measurements(measurements)

        """THEN availability and packet loss both reflect 50% success rate."""
        assert stats.availability_pct == 50.0
        assert stats.packet_loss_pct == 50.0
        assert stats.total_probes == 2
        assert stats.successful_probes == 1

    def test_single_measurement(self) -> None:
        """GIVEN a single fully-successful measurement."""
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

        """WHEN computing window stats."""
        stats = WindowStats.from_measurements([m])

        """THEN stats mirror the single measurement values."""
        assert stats.avg_latency_ms == 10.0
        assert stats.jitter_ms == 0.0
        assert stats.availability_pct == 100.0

    def test_all_failed_measurements(self) -> None:
        """GIVEN a single completely-failed measurement."""
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

        """WHEN computing window stats."""
        stats = WindowStats.from_measurements([m])

        """THEN availability is 0% and latency is None."""
        assert stats.availability_pct == 0.0
        assert stats.avg_latency_ms is None


class TestComputeJitter:
    """Tests for jitter computation."""

    def test_single_value(self) -> None:
        """GIVEN a single latency value."""

        """THEN jitter is 0.0."""
        assert _compute_jitter([10.0]) == 0.0

    def test_empty(self) -> None:
        """GIVEN an empty latency list."""

        """THEN jitter is 0.0."""
        assert _compute_jitter([]) == 0.0

    def test_constant_latency(self) -> None:
        """GIVEN three identical latency values."""

        """THEN jitter is 0.0."""
        assert _compute_jitter([10.0, 10.0, 10.0]) == 0.0

    def test_varying_latency(self) -> None:
        """GIVEN latencies that alternate by 10 ms."""

        """WHEN computing jitter."""
        result = _compute_jitter([10.0, 20.0, 10.0])

        """THEN jitter equals the mean absolute difference between consecutive samples."""
        assert result == 10.0


class TestFilterMeasurementsByWindow:
    """Tests for window filtering."""

    def test_filter_recent(self) -> None:
        """GIVEN three measurements at 30s, 90s, and 200s ago."""
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

        """WHEN filtering with a 60-second window."""
        result = filter_measurements_by_window(measurements, now, 60)

        """THEN only the recent measurement is included."""
        assert len(result) == 1

        result = filter_measurements_by_window(measurements, now, 120)
        assert len(result) == 2

    def test_empty_deque(self) -> None:
        """GIVEN an empty deque of measurements."""
        now = datetime.now(tz=UTC)

        """WHEN filtering."""
        result = filter_measurements_by_window(deque(), now, 60)

        """THEN no measurements are returned."""
        assert len(result) == 0
