"""Fixtures for WANPulse tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.wanpulse.const import (
    CONF_FAILURE_THRESHOLD,
    CONF_PROBE_COUNT,
    CONF_SCAN_INTERVAL,
    CONF_TARGETS,
    CONF_TIMEOUT,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_PROBE_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from custom_components.wanpulse.models import ProbeResult

MOCK_TARGETS = [
    {"host": "1.1.1.1", "label": "Cloudflare DNS", "method": "tcp"},
    {"host": "8.8.8.8", "label": "Google DNS", "method": "tcp"},
]

MOCK_OPTIONS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_PROBE_COUNT: DEFAULT_PROBE_COUNT,
    CONF_FAILURE_THRESHOLD: DEFAULT_FAILURE_THRESHOLD,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Create a mock config entry."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="WANPulse",
        data={CONF_TARGETS: MOCK_TARGETS},
        source="user",
        options=MOCK_OPTIONS,
        unique_id=DOMAIN,
    )
    return entry


@pytest.fixture
def mock_successful_probe() -> Generator[AsyncMock]:
    """Mock all probe engines to return success."""
    result = ProbeResult(success=True, latency_ms=15.5)
    with (
        patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=result,
        ) as mock_tcp,
        patch(
            "custom_components.wanpulse.probes.http.HTTPProbeEngine.async_probe",
            return_value=result,
        ),
        patch(
            "custom_components.wanpulse.probes.dns.DNSProbeEngine.async_probe",
            return_value=result,
        ),
    ):
        yield mock_tcp


@pytest.fixture
def mock_failed_probe() -> Generator[AsyncMock]:
    """Mock all probe engines to return failure."""
    result = ProbeResult(success=False, error="Connection refused")
    with (
        patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=result,
        ) as mock_tcp,
        patch(
            "custom_components.wanpulse.probes.http.HTTPProbeEngine.async_probe",
            return_value=result,
        ),
        patch(
            "custom_components.wanpulse.probes.dns.DNSProbeEngine.async_probe",
            return_value=result,
        ),
    ):
        yield mock_tcp
