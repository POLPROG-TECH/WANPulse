"""Base probe engine abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import ProbeResult, ProbeTarget


class ProbeEngine(ABC):
    """Abstract base class for probe engines."""

    @abstractmethod
    async def async_probe(
        self,
        target: ProbeTarget,
        timeout: float,
    ) -> ProbeResult:
        """Execute a single probe against the target.

        Args:
            target: The probe target configuration.
            timeout: Maximum time in seconds to wait for a response.

        Returns:
            ProbeResult with success status and latency.

        """
