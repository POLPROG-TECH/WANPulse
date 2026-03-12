"""Domain models for the WANPulse integration."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections import deque


class ProbeMethod(StrEnum):
    """Supported probe methods."""

    TCP = "tcp"
    HTTP = "http"
    DNS = "dns"


@dataclass(frozen=True)
class ProbeTarget:
    """A single probe target configuration."""

    host: str
    label: str
    method: ProbeMethod
    port: int | None = None

    @property
    def target_id(self) -> str:
        """Stable identifier derived from host and method."""
        slug = self.host.replace(".", "_").replace(":", "_").replace("/", "_")
        return f"{self.method}_{slug}"


@dataclass(frozen=True)
class ProbeResult:
    """Result of a single probe attempt."""

    success: bool
    latency_ms: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class ProbeMeasurement:
    """Aggregated result of one probe cycle for a target."""

    timestamp: datetime
    target_id: str
    success: bool
    avg_latency_ms: float | None = None
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    jitter_ms: float | None = None
    packet_loss_pct: float = 0.0
    probes_sent: int = 0
    probes_received: int = 0
    error: str | None = None

    @staticmethod
    def from_probe_results(
        target_id: str,
        results: list[ProbeResult],
        timestamp: datetime,
    ) -> ProbeMeasurement:
        """Create a measurement from a list of probe results."""
        if not results:
            return ProbeMeasurement(
                timestamp=timestamp,
                target_id=target_id,
                success=False,
                error="No probes executed",
            )

        successful = [r for r in results if r.success]
        latencies = [r.latency_ms for r in successful if r.latency_ms is not None]
        probes_sent = len(results)
        probes_received = len(successful)
        loss = 100.0 * (1.0 - probes_received / probes_sent) if probes_sent else 100.0

        avg_lat = statistics.mean(latencies) if latencies else None
        min_lat = min(latencies) if latencies else None
        max_lat = max(latencies) if latencies else None
        jitter = _compute_jitter(latencies) if len(latencies) >= 2 else None

        errors = [r.error for r in results if r.error]
        error_msg = "; ".join(errors) if errors else None

        return ProbeMeasurement(
            timestamp=timestamp,
            target_id=target_id,
            success=probes_received > 0,
            avg_latency_ms=round(avg_lat, 2) if avg_lat is not None else None,
            min_latency_ms=round(min_lat, 2) if min_lat is not None else None,
            max_latency_ms=round(max_lat, 2) if max_lat is not None else None,
            jitter_ms=round(jitter, 2) if jitter is not None else None,
            packet_loss_pct=round(loss, 1),
            probes_sent=probes_sent,
            probes_received=probes_received,
            error=error_msg,
        )


@dataclass(frozen=True)
class WindowStats:
    """Immutable stats for a time window."""

    avg_latency_ms: float | None = None
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    jitter_ms: float | None = None
    packet_loss_pct: float = 0.0
    availability_pct: float = 100.0
    total_probes: int = 0
    successful_probes: int = 0

    @staticmethod
    def from_measurements(measurements: list[ProbeMeasurement]) -> WindowStats:
        """Compute stats from a list of measurements."""
        if not measurements:
            return WindowStats()

        total = len(measurements)
        successful = [m for m in measurements if m.success]
        success_count = len(successful)

        latencies = [m.avg_latency_ms for m in successful if m.avg_latency_ms is not None]
        all_min = [m.min_latency_ms for m in successful if m.min_latency_ms is not None]
        all_max = [m.max_latency_ms for m in successful if m.max_latency_ms is not None]
        all_jitter = [m.jitter_ms for m in successful if m.jitter_ms is not None]

        return WindowStats(
            avg_latency_ms=round(statistics.mean(latencies), 2) if latencies else None,
            min_latency_ms=round(min(all_min), 2) if all_min else None,
            max_latency_ms=round(max(all_max), 2) if all_max else None,
            jitter_ms=round(statistics.mean(all_jitter), 2) if all_jitter else None,
            packet_loss_pct=round(100.0 * (1.0 - success_count / total), 1),
            availability_pct=round(100.0 * success_count / total, 2),
            total_probes=total,
            successful_probes=success_count,
        )


@dataclass(frozen=True)
class TargetSnapshot:
    """Immutable snapshot of a single target's state."""

    target: ProbeTarget
    is_online: bool = False
    consecutive_failures: int = 0
    last_measurement: ProbeMeasurement | None = None
    current: WindowStats = field(default_factory=WindowStats)
    hour: WindowStats = field(default_factory=WindowStats)
    day: WindowStats = field(default_factory=WindowStats)
    outage_count: int = 0
    total_outage_duration: timedelta = field(default_factory=timedelta)


@dataclass(frozen=True)
class CoordinatorSnapshot:
    """Immutable snapshot of the entire WANPulse state."""

    targets: dict[str, TargetSnapshot] = field(default_factory=dict)
    wan_is_online: bool = False
    aggregate_current: WindowStats = field(default_factory=WindowStats)
    aggregate_hour: WindowStats = field(default_factory=WindowStats)
    aggregate_day: WindowStats = field(default_factory=WindowStats)
    outage_count: int = 0
    total_outage_duration: timedelta = field(default_factory=timedelta)
    last_update: datetime | None = None


def _compute_jitter(latencies: list[float]) -> float:
    """Compute mean inter-sample jitter (RFC 3550 approximation)."""
    if len(latencies) < 2:
        return 0.0
    diffs = [abs(latencies[i] - latencies[i - 1]) for i in range(1, len(latencies))]
    return statistics.mean(diffs)


def filter_measurements_by_window(
    measurements: deque[ProbeMeasurement],
    now: datetime,
    window_seconds: int,
) -> list[ProbeMeasurement]:
    """Filter measurements within a time window."""
    cutoff = now - timedelta(seconds=window_seconds)
    return [m for m in measurements if m.timestamp >= cutoff]
