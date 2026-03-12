"""TCP connect probe engine."""

from __future__ import annotations

import asyncio
import time

from ..const import DEFAULT_PORT_TCP
from ..models import ProbeResult, ProbeTarget
from .base import ProbeEngine


class TCPProbeEngine(ProbeEngine):
    """Probe engine that measures TCP connection time."""

    async def async_probe(
        self,
        target: ProbeTarget,
        timeout: float,
    ) -> ProbeResult:
        """Open a TCP connection and measure the time to connect."""
        port = target.port or DEFAULT_PORT_TCP
        start = time.monotonic()
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(target.host, port),
                timeout=timeout,
            )
            elapsed_ms = (time.monotonic() - start) * 1000.0
            writer.close()
            await writer.wait_closed()
            return ProbeResult(success=True, latency_ms=round(elapsed_ms, 2))
        except TimeoutError:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            return ProbeResult(
                success=False,
                latency_ms=round(elapsed_ms, 2),
                error=f"TCP connect to {target.host}:{port} timed out",
            )
        except OSError as exc:
            return ProbeResult(
                success=False,
                error=f"TCP connect to {target.host}:{port} failed: {exc}",
            )
