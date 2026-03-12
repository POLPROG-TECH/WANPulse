"""Tests for WANPulse init (setup/unload)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wanpulse.const import (
    CONF_FAILURE_THRESHOLD,
    CONF_PROBE_COUNT,
    CONF_SCAN_INTERVAL,
    CONF_TARGETS,
    CONF_TIMEOUT,
    DOMAIN,
)
from custom_components.wanpulse.models import ProbeResult


def _make_entry(hass, targets=None, options=None):
    """Create and add a config entry to hass."""
    entry = MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="WANPulse",
        data={
            CONF_TARGETS: targets
            if targets is not None
            else [{"host": "1.1.1.1", "label": "CF", "method": "tcp"}],
        },
        source="user",
        options=options
        or {
            CONF_SCAN_INTERVAL: 60,
            CONF_TIMEOUT: 10,
            CONF_PROBE_COUNT: 3,
            CONF_FAILURE_THRESHOLD: 3,
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)
    return entry


class TestSetupEntry:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_successful_setup(self, hass: HomeAssistant) -> None:
        """Test that the integration sets up successfully."""
        entry = _make_entry(hass)
        mock_result = ProbeResult(success=True, latency_ms=10.0)

        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_result,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data is not None
        assert entry.runtime_data.coordinator is not None

    @pytest.mark.asyncio
    async def test_setup_no_targets(self, hass: HomeAssistant) -> None:
        """Test setup fails with no valid targets."""
        entry = _make_entry(hass, targets=[])

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_ERROR

    @pytest.mark.asyncio
    async def test_setup_invalid_method_targets(self, hass: HomeAssistant) -> None:
        """Test setup with invalid method targets skips them."""
        entry = _make_entry(
            hass,
            targets=[{"host": "1.1.1.1", "label": "CF", "method": "invalid"}],
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_ERROR

    @pytest.mark.asyncio
    async def test_setup_aggressive_polling_creates_issue(self, hass: HomeAssistant) -> None:
        """Test that aggressive polling creates a repair issue."""
        from homeassistant.helpers import issue_registry as ir

        from custom_components.wanpulse.const import MIN_SCAN_INTERVAL

        entry = _make_entry(
            hass,
            targets=[{"host": "1.1.1.1", "label": "CF", "method": "tcp"}],
            options={
                CONF_SCAN_INTERVAL: MIN_SCAN_INTERVAL - 1,
                CONF_TIMEOUT: 10,
                CONF_PROBE_COUNT: 3,
                CONF_FAILURE_THRESHOLD: 3,
            },
        )
        mock_result = ProbeResult(success=True, latency_ms=10.0)
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_result,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        issue_reg = ir.async_get(hass)
        assert issue_reg.async_get_issue(DOMAIN, "aggressive_polling") is not None

    @pytest.mark.asyncio
    async def test_options_initialized_on_first_setup(self, hass: HomeAssistant) -> None:
        """Test that options are initialized from defaults on first setup."""
        entry = MockConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="WANPulse",
            data={
                CONF_TARGETS: [{"host": "1.1.1.1", "label": "CF", "method": "tcp"}],
                CONF_SCAN_INTERVAL: 30,
            },
            source="user",
            options={},
            unique_id=DOMAIN,
        )
        entry.add_to_hass(hass)

        mock_result = ProbeResult(success=True, latency_ms=10.0)
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_result,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert entry.options.get(CONF_SCAN_INTERVAL) == 30
        assert entry.options.get(CONF_TIMEOUT) is not None


class TestUnloadEntry:
    """Tests for async_unload_entry."""

    @pytest.mark.asyncio
    async def test_unload(self, hass: HomeAssistant) -> None:
        """Test that the integration unloads correctly."""
        entry = _make_entry(hass)
        mock_result = ProbeResult(success=True, latency_ms=10.0)

        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_result,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED


class TestMigrateEntry:
    """Tests for config entry migration."""

    @pytest.mark.asyncio
    async def test_migrate_current_version(self, hass: HomeAssistant) -> None:
        """Test migration of current version returns True."""
        from custom_components.wanpulse import async_migrate_entry

        entry = MockConfigEntry(domain=DOMAIN, title="WANPulse", data={}, unique_id=DOMAIN)
        entry.add_to_hass(hass)
        result = await async_migrate_entry(hass, entry)
        assert result is True


class TestBuildTargets:
    """Tests for _build_targets helper."""

    def test_valid_targets(self) -> None:
        from custom_components.wanpulse import _build_targets

        raw = [{"host": "1.1.1.1", "label": "CF", "method": "tcp"}]
        result = _build_targets(raw)
        assert len(result) == 1
        assert result[0].host == "1.1.1.1"

    def test_invalid_method_skipped(self) -> None:
        from custom_components.wanpulse import _build_targets

        raw = [
            {"host": "1.1.1.1", "label": "CF", "method": "tcp"},
            {"host": "2.2.2.2", "label": "Bad", "method": "icmp"},
        ]
        result = _build_targets(raw)
        assert len(result) == 1
        assert result[0].host == "1.1.1.1"

    def test_default_method(self) -> None:
        from custom_components.wanpulse import _build_targets

        raw = [{"host": "1.1.1.1", "label": "CF"}]
        result = _build_targets(raw)
        assert len(result) == 1
        assert result[0].method.value == "tcp"

    def test_label_defaults_to_host(self) -> None:
        from custom_components.wanpulse import _build_targets

        raw = [{"host": "1.1.1.1", "method": "tcp"}]
        result = _build_targets(raw)
        assert result[0].label == "1.1.1.1"
