"""DataUpdateCoordinator for WANPulse."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FAILURE_THRESHOLD,
    CONF_PROBE_COUNT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_PROBE_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MAX_CONCURRENT_PROBES,
    MAX_MEASUREMENTS_PER_TARGET,
    WINDOW_1H_SECONDS,
    WINDOW_24H_SECONDS,
)
from .models import (
    CoordinatorSnapshot,
    ProbeMeasurement,
    ProbeTarget,
    TargetSnapshot,
    WindowStats,
    filter_measurements_by_window,
)
from .probes import get_probe_engine

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

CURRENT_WINDOW_MULTIPLIER = 5


@dataclass
class _TargetState:
    """Mutable internal state for a single probe target."""

    target: ProbeTarget
    measurements: deque[ProbeMeasurement] = field(
        default_factory=lambda: deque(maxlen=MAX_MEASUREMENTS_PER_TARGET)
    )
    consecutive_failures: int = 0
    in_outage: bool = False
    outage_start: datetime | None = None
    outage_count: int = 0
    total_outage_seconds: float = 0.0


@dataclass
class _AggregateState:
    """Mutable internal state for aggregate WAN health."""

    was_online: bool = True
    in_outage: bool = False
    outage_start: datetime | None = None
    outage_count: int = 0
    total_outage_seconds: float = 0.0


class WANPulseCoordinator(DataUpdateCoordinator[CoordinatorSnapshot]):
    """Coordinator that manages WAN probe cycles and statistics."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        targets: list[ProbeTarget],
    ) -> None:
        """Initialize."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

        self._targets = targets
        self._timeout: float = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        self._probe_count: int = entry.options.get(CONF_PROBE_COUNT, DEFAULT_PROBE_COUNT)
        self._failure_threshold: int = entry.options.get(
            CONF_FAILURE_THRESHOLD, DEFAULT_FAILURE_THRESHOLD
        )
        self._scan_interval_sec: int = scan_interval

        self._target_states: dict[str, _TargetState] = {
            t.target_id: _TargetState(target=t) for t in targets
        }
        self._aggregate_state = _AggregateState()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROBES)

    @property
    def targets(self) -> list[ProbeTarget]:
        """Return the list of probe targets."""
        return list(self._targets)

    async def _async_update_data(self) -> CoordinatorSnapshot:
        """Run probe cycle and return immutable snapshot."""
        now = dt_util.utcnow()

        try:
            await self._run_probe_cycle(now)
        except Exception as exc:
            raise UpdateFailed(f"Probe cycle failed: {exc}") from exc

        return self._build_snapshot(now)

    async def _run_probe_cycle(self, now: datetime) -> None:
        """Run probes for all targets concurrently."""
        tasks = [self._probe_target(state, now) for state in self._target_states.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _probe_target(self, state: _TargetState, now: datetime) -> None:
        """Run probe_count probes for a single target."""
        target = state.target
        engine = get_probe_engine(target.method.value)

        results = []
        for _ in range(self._probe_count):
            async with self._semaphore:
                try:
                    result = await engine.async_probe(target, self._timeout)
                except Exception as exc:  # noqa: BLE001
                    from .models import ProbeResult

                    result = ProbeResult(
                        success=False,
                        error=f"Probe error: {exc}",
                    )
                results.append(result)

        measurement = ProbeMeasurement.from_probe_results(
            target_id=target.target_id,
            results=results,
            timestamp=now,
        )
        state.measurements.append(measurement)
        self._update_target_outage_state(state, measurement, now)

    def _update_target_outage_state(
        self,
        state: _TargetState,
        measurement: ProbeMeasurement,
        now: datetime,
    ) -> None:
        """Update outage tracking for a target."""
        if measurement.success:
            if state.in_outage and state.outage_start is not None:
                duration = (now - state.outage_start).total_seconds()
                state.total_outage_seconds += duration
            state.consecutive_failures = 0
            state.in_outage = False
            state.outage_start = None
        else:
            state.consecutive_failures += 1
            if not state.in_outage and state.consecutive_failures >= self._failure_threshold:
                state.in_outage = True
                state.outage_start = now
                state.outage_count += 1

    def _build_snapshot(self, now: datetime) -> CoordinatorSnapshot:
        """Build an immutable snapshot from current state."""
        current_window_sec = self._scan_interval_sec * CURRENT_WINDOW_MULTIPLIER

        target_snapshots: dict[str, TargetSnapshot] = {}
        all_current_measurements: list[ProbeMeasurement] = []
        all_hour_measurements: list[ProbeMeasurement] = []
        all_day_measurements: list[ProbeMeasurement] = []

        any_online = False

        for tid, state in self._target_states.items():
            current_m = filter_measurements_by_window(state.measurements, now, current_window_sec)
            hour_m = filter_measurements_by_window(state.measurements, now, WINDOW_1H_SECONDS)
            day_m = filter_measurements_by_window(state.measurements, now, WINDOW_24H_SECONDS)

            all_current_measurements.extend(current_m)
            all_hour_measurements.extend(hour_m)
            all_day_measurements.extend(day_m)

            is_online = state.consecutive_failures < self._failure_threshold
            if is_online:
                any_online = True

            outage_duration = state.total_outage_seconds
            if state.in_outage and state.outage_start is not None:
                outage_duration += (now - state.outage_start).total_seconds()

            last_m = state.measurements[-1] if state.measurements else None

            target_snapshots[tid] = TargetSnapshot(
                target=state.target,
                is_online=is_online,
                consecutive_failures=state.consecutive_failures,
                last_measurement=last_m,
                current=WindowStats.from_measurements(current_m),
                hour=WindowStats.from_measurements(hour_m),
                day=WindowStats.from_measurements(day_m),
                outage_count=state.outage_count,
                total_outage_duration=timedelta(seconds=outage_duration),
            )

        self._update_aggregate_outage_state(any_online, now)

        agg_outage_sec = self._aggregate_state.total_outage_seconds
        if self._aggregate_state.in_outage and self._aggregate_state.outage_start:
            agg_outage_sec += (now - self._aggregate_state.outage_start).total_seconds()

        return CoordinatorSnapshot(
            targets=target_snapshots,
            wan_is_online=any_online,
            aggregate_current=WindowStats.from_measurements(all_current_measurements),
            aggregate_hour=WindowStats.from_measurements(all_hour_measurements),
            aggregate_day=WindowStats.from_measurements(all_day_measurements),
            outage_count=self._aggregate_state.outage_count,
            total_outage_duration=timedelta(seconds=agg_outage_sec),
            last_update=now,
        )

    def _update_aggregate_outage_state(self, any_online: bool, now: datetime) -> None:
        """Update aggregate WAN outage tracking."""
        agg = self._aggregate_state
        if any_online:
            if agg.in_outage and agg.outage_start is not None:
                duration = (now - agg.outage_start).total_seconds()
                agg.total_outage_seconds += duration
            agg.in_outage = False
            agg.outage_start = None
            agg.was_online = True
        elif agg.was_online and not any_online:
            agg.in_outage = True
            agg.outage_start = now
            agg.outage_count += 1
            agg.was_online = False
        elif not agg.was_online and not any_online:
            agg.was_online = False
