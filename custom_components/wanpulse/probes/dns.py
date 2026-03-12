"""DNS resolution probe engine."""

from __future__ import annotations

import asyncio
import socket
import time

from ..models import ProbeResult, ProbeTarget
from .base import ProbeEngine


class DNSProbeEngine(ProbeEngine):
    """Probe engine that measures DNS resolution time."""

    async def async_probe(
        self,
        target: ProbeTarget,
        timeout: float,
    ) -> ProbeResult:
        """Resolve a hostname and measure the time taken.

        Uses the system resolver via asyncio.getaddrinfo. The target host
        should be a hostname (e.g. www.google.com).
        """
        loop = asyncio.get_running_loop()
        start = time.monotonic()
        try:
            await asyncio.wait_for(
                loop.getaddrinfo(
                    target.host,
                    None,
                    family=socket.AF_UNSPEC,
                    type=socket.SOCK_STREAM,
                ),
                timeout=timeout,
            )
            elapsed_ms = (time.monotonic() - start) * 1000.0
            return ProbeResult(success=True, latency_ms=round(elapsed_ms, 2))
        except TimeoutError:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            return ProbeResult(
                success=False,
                latency_ms=round(elapsed_ms, 2),
                error=f"DNS resolution of {target.host} timed out",
            )
        except socket.gaierror as exc:
            return ProbeResult(
                success=False,
                error=f"DNS resolution of {target.host} failed: {exc}",
            )
        except OSError as exc:
            return ProbeResult(
                success=False,
                error=f"DNS resolution of {target.host} failed: {exc}",
            )
