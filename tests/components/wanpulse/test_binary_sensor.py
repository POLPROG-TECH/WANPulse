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

    """GIVEN a snapshot where WAN is online"""
    def test_wan_status_online(self) -> None:
        snapshot = _make_snapshot(wan_online=True)
        desc = AGGREGATE_BINARY_SENSORS[0]
        """WHEN wan status online is evaluated"""

        """THEN the value function returns True"""
        assert desc.value_fn(snapshot) is True

    """GIVEN a snapshot where WAN is offline"""
    def test_wan_status_offline(self) -> None:
        snapshot = _make_snapshot(wan_online=False)
        desc = AGGREGATE_BINARY_SENSORS[0]
        """WHEN wan status offline is evaluated"""

        """THEN the value function returns False"""
        assert desc.value_fn(snapshot) is False

    """GIVEN a coordinator with snapshot data and the first aggregate descriptor"""
    def test_entity_unique_id(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = AGGREGATE_BINARY_SENSORS[0]

        """WHEN the aggregate binary sensor is created"""
        sensor = WANPulseAggregateBinarySensor(coordinator, "test_entry", desc)

        """THEN its unique_id combines the entry id and sensor key"""
        assert sensor.unique_id == "test_entry_wan_status"

    """GIVEN a coordinator with snapshot data and the first aggregate descriptor"""
    def test_suggested_object_id(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = AGGREGATE_BINARY_SENSORS[0]

        """WHEN the aggregate binary sensor is created"""
        sensor = WANPulseAggregateBinarySensor(coordinator, "test_entry", desc)

        """THEN its suggested_object_id matches the sensor key"""
        assert sensor.suggested_object_id == "wan_status"

    """GIVEN a coordinator with no snapshot data"""
    def test_value_none_when_no_data(self) -> None:
        coordinator = MagicMock()
        coordinator.data = None
        desc = AGGREGATE_BINARY_SENSORS[0]

        """WHEN the aggregate binary sensor is created"""
        sensor = WANPulseAggregateBinarySensor(coordinator, "test_entry", desc)

        """THEN is_on returns None"""
        assert sensor.is_on is None


class TestTargetBinarySensor:
    """Tests for per-target binary sensors."""

    """GIVEN a target snapshot where the target is online"""
    def test_target_online(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)
        snap = TargetSnapshot(target=target, is_online=True)
        desc = TARGET_BINARY_SENSORS[0]
        """WHEN target online is evaluated"""

        """THEN the value function returns True"""
        assert desc.value_fn(snap) is True

    """GIVEN a target snapshot where the target is offline"""
    def test_target_offline(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="CF", method=ProbeMethod.TCP)
        snap = TargetSnapshot(target=target, is_online=False)
        desc = TARGET_BINARY_SENSORS[0]
        """WHEN target offline is evaluated"""

        """THEN the value function returns False"""
        assert desc.value_fn(snap) is False

    """GIVEN a coordinator with snapshot data and the first target descriptor"""
    def test_entity_unique_id(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = TARGET_BINARY_SENSORS[0]

        """WHEN the target binary sensor is created"""
        sensor = WANPulseTargetBinarySensor(coordinator, "test_entry", "tcp_1_1_1_1", "CF", desc)

        """THEN its unique_id combines the entry id, target slug, and sensor key"""
        assert sensor.unique_id == "test_entry_tcp_1_1_1_1_target_status"

    """GIVEN a coordinator with snapshot data and the first target descriptor"""
    def test_suggested_object_id(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = TARGET_BINARY_SENSORS[0]

        """WHEN the target binary sensor is created with a human-readable label"""
        sensor = WANPulseTargetBinarySensor(
            coordinator, "test_entry", "tcp_1_1_1_1", "Cloudflare DNS", desc
        )

        """THEN its suggested_object_id is derived from the label and sensor key"""
        assert sensor.suggested_object_id == "cloudflare_dns_target_status"

    """GIVEN a coordinator with snapshot data but a nonexistent target slug"""
    def test_value_none_when_target_missing(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = TARGET_BINARY_SENSORS[0]

        """WHEN the target binary sensor references a missing target"""
        sensor = WANPulseTargetBinarySensor(coordinator, "test_entry", "nonexistent", "X", desc)

        """THEN is_on returns None"""
        assert sensor.is_on is None

    """GIVEN a coordinator with snapshot data and the first target descriptor"""
    def test_translation_placeholders(self) -> None:
        coordinator = MagicMock()
        coordinator.data = _make_snapshot()
        desc = TARGET_BINARY_SENSORS[0]

        """WHEN the target binary sensor is created with a label"""
        sensor = WANPulseTargetBinarySensor(
            coordinator, "test_entry", "tcp_1_1_1_1", "Cloudflare DNS", desc
        )

        """THEN translation_placeholders includes the target label"""
        assert sensor.translation_placeholders == {"target": "Cloudflare DNS"}
