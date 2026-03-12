"""Diagnostics support for WANPulse."""

from __future__ import annotations

from typing import Any

from .const import CONF_TARGETS

# Compat: async_redact_data location may vary across HA versions.
try:
    from homeassistant.components.diagnostics import async_redact_data
except ImportError:

    def async_redact_data(data: dict, to_redact: set) -> dict:  # type: ignore[misc]
        """Simple fallback redaction."""
        return {k: "**REDACTED**" if k in to_redact else v for k, v in data.items()}

TO_REDACT_CONFIG = {"host", "label"}


async def async_get_config_entry_diagnostics(
    hass: Any,
    entry: Any,
) -> dict[str, Any]:
    """Return diagnostics for a WANPulse config entry."""
    targets_redacted = []
    for target in entry.data.get(CONF_TARGETS, []):
        targets_redacted.append(async_redact_data(target, TO_REDACT_CONFIG))

    coordinator = entry.runtime_data.coordinator
    snapshot = coordinator.data

    target_diagnostics = {}
    if snapshot and snapshot.targets:
        for tid, tsnap in snapshot.targets.items():
            target_diagnostics[tid] = {
                "is_online": tsnap.is_online,
                "consecutive_failures": tsnap.consecutive_failures,
                "outage_count": tsnap.outage_count,
                "total_outage_duration_seconds": tsnap.total_outage_duration.total_seconds(),
                "current_window": {
                    "avg_latency_ms": tsnap.current.avg_latency_ms,
                    "packet_loss_pct": tsnap.current.packet_loss_pct,
                    "availability_pct": tsnap.current.availability_pct,
                    "total_probes": tsnap.current.total_probes,
                },
                "hour_window": {
                    "avg_latency_ms": tsnap.hour.avg_latency_ms,
                    "availability_pct": tsnap.hour.availability_pct,
                    "total_probes": tsnap.hour.total_probes,
                },
                "day_window": {
                    "avg_latency_ms": tsnap.day.avg_latency_ms,
                    "availability_pct": tsnap.day.availability_pct,
                    "total_probes": tsnap.day.total_probes,
                },
            }

    return {
        "entry_data": {
            "targets": targets_redacted,
        },
        "entry_options": dict(entry.options),
        "coordinator": {
            "wan_is_online": snapshot.wan_is_online if snapshot else None,
            "outage_count": snapshot.outage_count if snapshot else None,
            "total_outage_duration_seconds": (
                snapshot.total_outage_duration.total_seconds() if snapshot else None
            ),
            "last_update": str(snapshot.last_update) if snapshot and snapshot.last_update else None,
            "target_count": len(snapshot.targets) if snapshot else 0,
        },
        "targets": target_diagnostics,
    }
