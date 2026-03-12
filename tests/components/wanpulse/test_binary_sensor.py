"""Tests for WANPulse binary sensor platform."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from custom_components.wanpulse.binary_sensor import (
    AGGREGATE_BINARY_SENSORS,
    TARGET_BINARY_SENSORS,
    WANPulseAggregateBinarySensor,
    WANPulseTargetBinarySensor,
)
from custom_components.wanpulse.models import (
    CoordinatorSnapshot,
    ProbeMethod,
    ProbeTarget,
    TargetSnapshot,
)


def _make_snapshot(wan_online: bool = True, target_online: bool = True) -> CoordinatorSnapshot:
    target = ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)
    return CoordinatorSnapshot(
        targets={
            "tcp_1_1_1_1": TargetSnapshot(
                target=target,
                is_online=target_online,
            ),
        },
        wan_is_online=wan_online,
        last_update=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


class TestAggregateBinarySensor:
    """Tests for aggregate binary sensors."""

    def test_wan_status_online(self) -> None:
        snapshot = _make_snapshot(wan_online=True)
        desc = AGGREGATE_BINARY_SENSORS[0]
        assert desc.value_fn(snapshot) is True

    def test_wan_status_offline(self) -> None:
        snapshot = _make_snapshot(wan_online=False)
        desc = AGGREGATE_BINARY_SENSORS[0]
        assert desc.value_fn(snapshot) is False

    def test_entity_unique_id(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = AGGREGATE_BINARY_SENSORS[0]

        sensor = WANPulseAggregateBinarySensor(coordinator, "test_entry", desc)
        assert sensor.unique_id == "test_entry_wan_status"

    def test_suggested_object_id(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = AGGREGATE_BINARY_SENSORS[0]

        sensor = WANPulseAggregateBinarySensor(coordinator, "test_entry", desc)
        assert sensor.suggested_object_id == "wan_status"

    def test_value_none_when_no_data(self) -> None:
        coordinator = MagicMock()
        coordinator.data = None
        desc = AGGREGATE_BINARY_SENSORS[0]

        sensor = WANPulseAggregateBinarySensor(coordinator, "test_entry", desc)
        assert sensor.is_on is None


class TestTargetBinarySensor:
    """Tests for per-target binary sensors."""

    def test_target_online(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)
        snap = TargetSnapshot(target=target, is_online=True)
        desc = TARGET_BINARY_SENSORS[0]
        assert desc.value_fn(snap) is True

    def test_target_offline(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)
        snap = TargetSnapshot(target=target, is_online=False)
        desc = TARGET_BINARY_SENSORS[0]
        assert desc.value_fn(snap) is False

    def test_entity_unique_id(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = TARGET_BINARY_SENSORS[0]

        sensor = WANPulseTargetBinarySensor(coordinator, "test_entry", "tcp_1_1_1_1", "CF", desc)
        assert sensor.unique_id == "test_entry_tcp_1_1_1_1_target_status"

    def test_suggested_object_id(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = TARGET_BINARY_SENSORS[0]

        sensor = WANPulseTargetBinarySensor(
            coordinator, "test_entry", "tcp_1_1_1_1", "Cloudflare DNS", desc
        )
        assert sensor.suggested_object_id == "cloudflare_dns_target_status"

    def test_value_none_when_target_missing(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = TARGET_BINARY_SENSORS[0]

        sensor = WANPulseTargetBinarySensor(coordinator, "test_entry", "nonexistent", "X", desc)
        assert sensor.is_on is None

    def test_translation_placeholders(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = TARGET_BINARY_SENSORS[0]

        sensor = WANPulseTargetBinarySensor(
            coordinator, "test_entry", "tcp_1_1_1_1", "Cloudflare DNS", desc
        )
        assert sensor.translation_placeholders == {"target": "Cloudflare DNS"}
