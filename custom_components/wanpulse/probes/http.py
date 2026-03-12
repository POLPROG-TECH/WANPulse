"""HTTP HEAD probe engine."""

from __future__ import annotations

import time

import aiohttp

from ..models import ProbeResult, ProbeTarget
from .base import ProbeEngine


class HTTPProbeEngine(ProbeEngine):
    """Probe engine that measures HTTP HEAD response time."""

    async def async_probe(
        self,
        target: ProbeTarget,
        timeout: float,
    ) -> ProbeResult:
        """Send an HTTP HEAD request and measure response time.

        The target host is interpreted as a URL. If no scheme is present,
        https:// is prepended.
        """
        url = target.host
        if not url.startswith(("http://", "https://")):
            port = target.port or 443
            scheme = "https" if port == 443 else "http"
            url = f"{scheme}://{target.host}:{port}"

        client_timeout = aiohttp.ClientTimeout(total=timeout)
        start = time.monotonic()
        try:
            async with (
                aiohttp.ClientSession(timeout=client_timeout) as session,
                session.head(url, allow_redirects=True, ssl=False) as resp,
            ):
                elapsed_ms = (time.monotonic() - start) * 1000.0
                # Any HTTP response means the target is reachable
                _ = resp.status
                return ProbeResult(success=True, latency_ms=round(elapsed_ms, 2))
        except TimeoutError:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            return ProbeResult(
                success=False,
                latency_ms=round(elapsed_ms, 2),
                error=f"HTTP HEAD to {url} timed out",
            )
        except aiohttp.ClientError as exc:
            return ProbeResult(
                success=False,
                error=f"HTTP HEAD to {url} failed: {exc}",
            )
        except OSError as exc:
            return ProbeResult(
                success=False,
                error=f"HTTP HEAD to {url} failed: {exc}",
            )
