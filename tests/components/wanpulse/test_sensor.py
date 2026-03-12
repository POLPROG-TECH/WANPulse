"""Tests for WANPulse sensor platform."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from custom_components.wanpulse.models import (
    CoordinatorSnapshot,
    ProbeMethod,
    ProbeTarget,
    TargetSnapshot,
    WindowStats,
)
from custom_components.wanpulse.sensor import (
    AGGREGATE_SENSORS,
    TARGET_SENSORS,
    WANPulseAggregateSensor,
    WANPulseTargetSensor,
)


def _make_coordinator(snapshot: CoordinatorSnapshot) -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = snapshot
    targets = [
        ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP),
    ]
    coordinator.targets = targets
    return coordinator


def _make_snapshot(
    latency: float = 15.0,
    loss: float = 0.0,
    availability: float = 100.0,
    online: bool = True,
) -> CoordinatorSnapshot:
    """Create a test snapshot."""
    target = ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)
    return CoordinatorSnapshot(
        targets={
            "tcp_1_1_1_1": TargetSnapshot(
                target=target,
                is_online=online,
                current=WindowStats(
                    avg_latency_ms=latency,
                    min_latency_ms=latency - 2,
                    max_latency_ms=latency + 2,
                    jitter_ms=1.5,
                    packet_loss_pct=loss,
                    availability_pct=availability,
                    total_probes=10,
                    successful_probes=10,
                ),
                hour=WindowStats(availability_pct=availability),
                day=WindowStats(availability_pct=availability),
            ),
        },
        wan_is_online=online,
        aggregate_current=WindowStats(
            avg_latency_ms=latency,
            min_latency_ms=latency - 2,
            max_latency_ms=latency + 2,
            jitter_ms=1.5,
            packet_loss_pct=loss,
            availability_pct=availability,
            total_probes=10,
            successful_probes=10,
        ),
        aggregate_hour=WindowStats(availability_pct=availability),
        aggregate_day=WindowStats(availability_pct=availability),
        last_update=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


class TestAggregateSensorDescriptions:
    """Tests for aggregate sensor descriptions."""

    def test_all_descriptions_have_value_fn(self) -> None:
        for desc in AGGREGATE_SENSORS:
            assert callable(desc.value_fn)

    def test_average_latency_value(self) -> None:
        snapshot = _make_snapshot(latency=25.3)
        desc = next(d for d in AGGREGATE_SENSORS if d.key == "average_latency")
        assert desc.value_fn(snapshot) == 25.3

    def test_packet_loss_value(self) -> None:
        snapshot = _make_snapshot(loss=5.5)
        desc = next(d for d in AGGREGATE_SENSORS if d.key == "packet_loss")
        assert desc.value_fn(snapshot) == 5.5

    def test_availability_1h_value(self) -> None:
        snapshot = _make_snapshot(availability=99.5)
        desc = next(d for d in AGGREGATE_SENSORS if d.key == "availability_1h")
        assert desc.value_fn(snapshot) == 99.5

    def test_outage_count_value(self) -> None:
        snapshot = _make_snapshot()
        snapshot = CoordinatorSnapshot(
            targets=snapshot.targets,
            wan_is_online=True,
            aggregate_current=snapshot.aggregate_current,
            aggregate_hour=snapshot.aggregate_hour,
            aggregate_day=snapshot.aggregate_day,
            outage_count=3,
            last_update=snapshot.last_update,
        )
        desc = next(d for d in AGGREGATE_SENSORS if d.key == "outage_count_24h")
        assert desc.value_fn(snapshot) == 3


class TestTargetSensorDescriptions:
    """Tests for target sensor descriptions."""

    def test_all_descriptions_have_value_fn(self) -> None:
        for desc in TARGET_SENSORS:
            assert callable(desc.value_fn)

    def test_target_latency_value(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)
        target_snap = TargetSnapshot(
            target=target,
            is_online=True,
            current=WindowStats(avg_latency_ms=12.5),
        )
        desc = next(d for d in TARGET_SENSORS if d.key == "target_latency")
        assert desc.value_fn(target_snap) == 12.5

    def test_target_packet_loss_value(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)
        target_snap = TargetSnapshot(
            target=target,
            current=WindowStats(packet_loss_pct=10.0),
        )
        desc = next(d for d in TARGET_SENSORS if d.key == "target_packet_loss")
        assert desc.value_fn(target_snap) == 10.0


class TestSensorEntity:
    """Tests for sensor entity behavior."""

    def test_aggregate_sensor_unique_id(self) -> None:
        snapshot = _make_snapshot()
        coordinator = _make_coordinator(snapshot)
        desc = AGGREGATE_SENSORS[0]  # average_latency

        sensor = WANPulseAggregateSensor(coordinator, "test_entry", desc)
        assert sensor.unique_id == f"test_entry_{desc.key}"

    def test_aggregate_sensor_suggested_object_id(self) -> None:
        snapshot = _make_snapshot()
        coordinator = _make_coordinator(snapshot)
        desc = AGGREGATE_SENSORS[0]  # average_latency

        sensor = WANPulseAggregateSensor(coordinator, "test_entry", desc)
        assert sensor.suggested_object_id == desc.key

    def test_target_sensor_unique_id(self) -> None:
        snapshot = _make_snapshot()
        coordinator = _make_coordinator(snapshot)
        desc = TARGET_SENSORS[0]

        sensor = WANPulseTargetSensor(coordinator, "test_entry", "tcp_1_1_1_1", "CF", desc)
        assert sensor.unique_id == f"test_entry_tcp_1_1_1_1_{desc.key}"

    def test_target_sensor_suggested_object_id(self) -> None:
        snapshot = _make_snapshot()
        coordinator = _make_coordinator(snapshot)
        desc = TARGET_SENSORS[0]

        sensor = WANPulseTargetSensor(
            coordinator, "test_entry", "tcp_1_1_1_1", "Cloudflare DNS", desc
        )
        assert sensor.suggested_object_id == f"cloudflare_dns_{desc.key}"

    def test_aggregate_sensor_value_none_when_no_data(self) -> None:
        coordinator = MagicMock()
        coordinator.data = None
        desc = AGGREGATE_SENSORS[0]

        sensor = WANPulseAggregateSensor(coordinator, "test_entry", desc)
        assert sensor.native_value is None

    def test_target_sensor_value_none_when_target_missing(self) -> None:
        snapshot = _make_snapshot()
        coordinator = _make_coordinator(snapshot)
        desc = TARGET_SENSORS[0]

        sensor = WANPulseTargetSensor(coordinator, "test_entry", "nonexistent_target", "X", desc)
        assert sensor.native_value is None
