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
        """GIVEN a config entry with one valid TCP target and a passing probe."""
        entry = _make_entry(hass)
        mock_result = ProbeResult(success=True, latency_ms=10.0)

        """WHEN the config entry is set up."""
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_result,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        """THEN the entry is loaded and runtime data is populated."""
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data is not None
        assert entry.runtime_data.coordinator is not None

    @pytest.mark.asyncio
    async def test_setup_no_targets(self, hass: HomeAssistant) -> None:
        """GIVEN a config entry with an empty targets list."""
        entry = _make_entry(hass, targets=[])

        """WHEN the config entry is set up."""
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        """THEN the entry state is SETUP_ERROR."""
        assert entry.state is ConfigEntryState.SETUP_ERROR

    @pytest.mark.asyncio
    async def test_setup_invalid_method_targets(self, hass: HomeAssistant) -> None:
        """GIVEN a config entry whose only target uses an invalid probe method."""
        entry = _make_entry(
            hass,
            targets=[{"host": "1.1.1.1", "label": "CF", "method": "invalid"}],
        )

        """WHEN the config entry is set up."""
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        """THEN the entry state is SETUP_ERROR because no valid targets remain."""
        assert entry.state is ConfigEntryState.SETUP_ERROR

    @pytest.mark.asyncio
    async def test_setup_aggressive_polling_creates_issue(self, hass: HomeAssistant) -> None:
        """GIVEN a config entry with a scan interval below the minimum threshold."""
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

        """WHEN the config entry is set up."""
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_result,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        """THEN an "aggressive_polling" repair issue is created."""
        issue_reg = ir.async_get(hass)
        assert issue_reg.async_get_issue(DOMAIN, "aggressive_polling") is not None

    @pytest.mark.asyncio
    async def test_options_initialized_on_first_setup(self, hass: HomeAssistant) -> None:
        """GIVEN a config entry with empty options and scan_interval in data."""
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

        """WHEN the config entry is set up for the first time."""
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_result,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        """THEN options are populated with the scan interval from data and defaults."""
        assert entry.options.get(CONF_SCAN_INTERVAL) == 30
        assert entry.options.get(CONF_TIMEOUT) is not None


class TestUnloadEntry:
    """Tests for async_unload_entry."""

    @pytest.mark.asyncio
    async def test_unload(self, hass: HomeAssistant) -> None:
        """GIVEN a fully loaded config entry."""
        entry = _make_entry(hass)
        mock_result = ProbeResult(success=True, latency_ms=10.0)
        with patch(
            "custom_components.wanpulse.probes.tcp.TCPProbeEngine.async_probe",
            return_value=mock_result,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        """WHEN the config entry is unloaded."""
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        """THEN the entry state becomes NOT_LOADED."""
        assert entry.state is ConfigEntryState.NOT_LOADED


class TestMigrateEntry:
    """Tests for config entry migration."""

    @pytest.mark.asyncio
    async def test_migrate_current_version(self, hass: HomeAssistant) -> None:
        """GIVEN a config entry at the current schema version."""
        from custom_components.wanpulse import async_migrate_entry

        entry = MockConfigEntry(domain=DOMAIN, title="WANPulse", data={}, unique_id=DOMAIN)
        entry.add_to_hass(hass)

        """WHEN migration is attempted."""
        result = await async_migrate_entry(hass, entry)

        """THEN migration succeeds without changes."""
        assert result is True


class TestBuildTargets:
    """Tests for _build_targets helper."""

    def test_valid_targets(self) -> None:
        """GIVEN a raw target list with one valid TCP entry."""
        from custom_components.wanpulse import _build_targets

        raw = [{"host": "1.1.1.1", "label": "CF", "method": "tcp"}]

        """WHEN _build_targets parses the list."""
        result = _build_targets(raw)

        """THEN exactly one target is returned with the correct host."""
        assert len(result) == 1
        assert result[0].host == "1.1.1.1"

    def test_invalid_method_skipped(self) -> None:
        """GIVEN a raw list with one valid TCP target and one unsupported ICMP target."""
        from custom_components.wanpulse import _build_targets

        raw = [
            {"host": "1.1.1.1", "label": "CF", "method": "tcp"},
            {"host": "2.2.2.2", "label": "Bad", "method": "icmp"},
        ]

        """WHEN _build_targets parses the list."""
        result = _build_targets(raw)

        """THEN only the valid TCP target is returned."""
        assert len(result) == 1
        assert result[0].host == "1.1.1.1"

    def test_default_method(self) -> None:
        """GIVEN a raw target without an explicit method."""
        from custom_components.wanpulse import _build_targets

        raw = [{"host": "1.1.1.1", "label": "CF"}]

        """WHEN _build_targets parses the list."""
        result = _build_targets(raw)

        """THEN the method defaults to "tcp"."""
        assert len(result) == 1
        assert result[0].method.value == "tcp"

    def test_label_defaults_to_host(self) -> None:
        """GIVEN a raw target without an explicit label."""
        from custom_components.wanpulse import _build_targets

        raw = [{"host": "1.1.1.1", "method": "tcp"}]

        """WHEN _build_targets parses the list."""
        result = _build_targets(raw)

        """THEN the label defaults to the host value."""
        assert result[0].label == "1.1.1.1"
