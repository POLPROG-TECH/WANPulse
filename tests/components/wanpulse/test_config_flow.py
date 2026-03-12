"""Tests for WANPulse config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.wanpulse.config_flow import (
    _parse_targets,
    _targets_to_text,
    _validate_targets,
)
from custom_components.wanpulse.const import (
    CONF_FAILURE_THRESHOLD,
    CONF_PROBE_COUNT,
    CONF_SCAN_INTERVAL,
    CONF_TARGETS,
    CONF_TIMEOUT,
    DOMAIN,
)


class TestParseTargets:
    """Tests for target text parsing."""

    def test_single_target(self) -> None:
        result = _parse_targets("1.1.1.1, Cloudflare DNS, tcp")
        assert len(result) == 1
        assert result[0]["host"] == "1.1.1.1"
        assert result[0]["label"] == "Cloudflare DNS"
        assert result[0]["method"] == "tcp"

    def test_multiple_targets(self) -> None:
        text = "1.1.1.1, Cloudflare DNS, tcp\n8.8.8.8, Google DNS, tcp"
        result = _parse_targets(text)
        assert len(result) == 2

    def test_minimal_target(self) -> None:
        result = _parse_targets("1.1.1.1")
        assert len(result) == 1
        assert result[0]["host"] == "1.1.1.1"
        assert result[0]["label"] == "1.1.1.1"
        assert result[0]["method"] == "tcp"

    def test_empty_lines_ignored(self) -> None:
        text = "1.1.1.1, CF, tcp\n\n\n8.8.8.8, Google, tcp\n"
        result = _parse_targets(text)
        assert len(result) == 2

    def test_empty_string(self) -> None:
        result = _parse_targets("")
        assert len(result) == 0

    def test_whitespace_trimming(self) -> None:
        result = _parse_targets("  1.1.1.1 ,  Cloudflare  ,  tcp  ")
        assert result[0]["host"] == "1.1.1.1"
        assert result[0]["label"] == "Cloudflare"
        assert result[0]["method"] == "tcp"

    def test_http_method(self) -> None:
        result = _parse_targets("https://example.com, Example, http")
        assert result[0]["method"] == "http"

    def test_dns_method(self) -> None:
        result = _parse_targets("www.google.com, Google, dns")
        assert result[0]["method"] == "dns"

    def test_empty_label_defaults_to_host(self) -> None:
        """Parse '1.1.1.1,, tcp' → label should default to host."""
        result = _parse_targets("1.1.1.1,, tcp")
        assert len(result) == 1
        assert result[0]["label"] == "1.1.1.1"

    def test_method_case_insensitive(self) -> None:
        """Parse '1.1.1.1, CF, TCP' → method should be lowercased to 'tcp'."""
        result = _parse_targets("1.1.1.1, CF, TCP")
        assert result[0]["method"] == "tcp"

    def test_only_commas(self) -> None:
        """Parse ',,' → should return empty list (no valid host)."""
        result = _parse_targets(",,")
        assert len(result) == 0


class TestValidateTargets:
    """Tests for target validation."""

    def test_valid_targets(self) -> None:
        targets = [{"host": "1.1.1.1", "label": "CF", "method": "tcp"}]
        assert _validate_targets(targets) is None

    def test_no_targets(self) -> None:
        assert _validate_targets([]) == "no_targets"

    def test_too_many_targets(self) -> None:
        targets = [{"host": f"10.0.0.{i}", "method": "tcp"} for i in range(11)]
        assert _validate_targets(targets) == "too_many_targets"

    def test_invalid_method(self) -> None:
        targets = [{"host": "1.1.1.1", "method": "icmp"}]
        assert _validate_targets(targets) == "invalid_method"

    def test_empty_host(self) -> None:
        targets = [{"host": "", "method": "tcp"}]
        assert _validate_targets(targets) == "invalid_host"

    def test_missing_host_key(self) -> None:
        """Validate target dict missing 'host' key."""
        targets = [{"method": "tcp"}]
        assert _validate_targets(targets) == "invalid_host"

    def test_none_host(self) -> None:
        """Validate target dict with host=None."""
        targets = [{"host": None, "method": "tcp"}]
        assert _validate_targets(targets) == "invalid_host"


class TestTargetsToText:
    """Tests for target list to text conversion."""

    def test_roundtrip(self) -> None:
        targets = [
            {"host": "1.1.1.1", "label": "Cloudflare DNS", "method": "tcp"},
            {"host": "8.8.8.8", "label": "Google DNS", "method": "tcp"},
        ]
        text = _targets_to_text(targets)
        parsed = _parse_targets(text)
        assert len(parsed) == 2
        assert parsed[0]["host"] == "1.1.1.1"
        assert parsed[1]["host"] == "8.8.8.8"


class TestConfigFlow:
    """Tests for the WANPulse config flow."""

    @pytest.mark.asyncio
    async def test_user_step_shows_form(self, hass: HomeAssistant) -> None:
        """Test that user step shows form with defaults."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_user_step_creates_entry(self, hass: HomeAssistant) -> None:
        """Test successful entry creation."""
        with patch(
            "custom_components.wanpulse.config_flow._test_target_reachability",
            return_value=[],
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_TARGETS: "1.1.1.1, Cloudflare DNS, tcp",
                    CONF_SCAN_INTERVAL: 60,
                },
            )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "WANPulse"
        assert len(result["data"][CONF_TARGETS]) == 1
        assert result["data"][CONF_TARGETS][0]["host"] == "1.1.1.1"

    @pytest.mark.asyncio
    async def test_user_step_invalid_targets(self, hass: HomeAssistant) -> None:
        """Test form shown again on invalid targets."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TARGETS: "",
                CONF_SCAN_INTERVAL: 60,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"][CONF_TARGETS] == "no_targets"

    @pytest.mark.asyncio
    async def test_user_step_invalid_method(self, hass: HomeAssistant) -> None:
        """Test form shown again on invalid probe method."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TARGETS: "1.1.1.1, CF, icmp",
                CONF_SCAN_INTERVAL: 60,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"][CONF_TARGETS] == "invalid_method"

    @pytest.mark.asyncio
    async def test_user_step_all_unreachable(self, hass: HomeAssistant) -> None:
        """Test error when all targets are unreachable."""
        with patch(
            "custom_components.wanpulse.config_flow._test_target_reachability",
            return_value=["Cloudflare DNS"],
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_TARGETS: "1.1.1.1, Cloudflare DNS, tcp",
                    CONF_SCAN_INTERVAL: 60,
                },
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "all_targets_unreachable"

    @pytest.mark.asyncio
    async def test_duplicate_entry_prevented(self, hass: HomeAssistant) -> None:
        """Test that duplicate entries are prevented."""
        with patch(
            "custom_components.wanpulse.config_flow._test_target_reachability",
            return_value=[],
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_TARGETS: "1.1.1.1, CF, tcp",
                    CONF_SCAN_INTERVAL: 60,
                },
            )
            assert result["type"] is FlowResultType.CREATE_ENTRY

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_TARGETS: "8.8.8.8, Google, tcp",
                    CONF_SCAN_INTERVAL: 60,
                },
            )
            assert result["type"] is FlowResultType.ABORT
            assert result["reason"] == "already_configured"


class TestOptionsFlow:
    """Tests for the WANPulse options flow."""

    @pytest.mark.asyncio
    async def test_options_step_shows_form(self, hass: HomeAssistant, mock_config_entry) -> None:
        """Test that options step shows form."""
        mock_config_entry.add_to_hass(hass)

        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_step_saves(self, hass: HomeAssistant, mock_config_entry) -> None:
        """Test that options are saved correctly."""
        mock_config_entry.add_to_hass(hass)

        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SCAN_INTERVAL: 30,
                CONF_TIMEOUT: 5,
                CONF_PROBE_COUNT: 5,
                CONF_FAILURE_THRESHOLD: 5,
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert mock_config_entry.options[CONF_SCAN_INTERVAL] == 30
        assert mock_config_entry.options[CONF_TIMEOUT] == 5

    @pytest.mark.asyncio
    async def test_options_rejects_invalid_scan_interval(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Test options rejects scan interval outside bounds."""
        from homeassistant.data_entry_flow import InvalidData

        mock_config_entry.add_to_hass(hass)

        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        with pytest.raises(InvalidData):
            await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    CONF_SCAN_INTERVAL: 1,
                    CONF_TIMEOUT: 10,
                    CONF_PROBE_COUNT: 3,
                    CONF_FAILURE_THRESHOLD: 3,
                },
            )


class TestReconfigureFlow:
    """Tests for reconfigure flow."""

    @pytest.mark.asyncio
    async def test_reconfigure_shows_form(self, hass: HomeAssistant, mock_config_entry) -> None:
        """Test reconfigure step shows form with current targets."""
        mock_config_entry.add_to_hass(hass)
        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()
        result = await mock_config_entry.start_reconfigure_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

    @pytest.mark.asyncio
    async def test_reconfigure_updates_targets(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Test reconfigure updates targets and reloads."""
        mock_config_entry.add_to_hass(hass)
        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()
        with patch(
            "custom_components.wanpulse.config_flow._test_target_reachability",
            return_value=[],
        ):
            result = await mock_config_entry.start_reconfigure_flow(hass)
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_TARGETS: "9.9.9.9, Quad9, tcp"},
            )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

    @pytest.mark.asyncio
    async def test_reconfigure_invalid_targets(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Test reconfigure rejects invalid targets."""
        mock_config_entry.add_to_hass(hass)
        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()
        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TARGETS: ""},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"][CONF_TARGETS] == "no_targets"
