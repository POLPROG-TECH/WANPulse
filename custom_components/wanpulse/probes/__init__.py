"""Probe engine package for WANPulse."""

from __future__ import annotations

from .base import ProbeEngine
from .dns import DNSProbeEngine
from .http import HTTPProbeEngine
from .tcp import TCPProbeEngine

__all__ = [
    "DNSProbeEngine",
    "HTTPProbeEngine",
    "ProbeEngine",
    "TCPProbeEngine",
    "get_probe_engine",
]

_ENGINES: dict[str, type[ProbeEngine]] = {
    "tcp": TCPProbeEngine,
    "http": HTTPProbeEngine,
    "dns": DNSProbeEngine,
}


def get_probe_engine(method: str) -> ProbeEngine:
    """Get a probe engine for the given method."""
    engine_cls = _ENGINES.get(method)
    if engine_cls is None:
        msg = f"Unknown probe method: {method}"
        raise ValueError(msg)
    return engine_cls()
