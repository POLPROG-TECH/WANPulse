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
        """GIVEN a target text with one TCP target."""

        """WHEN parsing the text."""
        result = _parse_targets("1.1.1.1, Cloudflare DNS, tcp")

        """THEN a single target with correct host, label, and method is returned."""
        assert len(result) == 1
        assert result[0]["host"] == "1.1.1.1"
        assert result[0]["label"] == "Cloudflare DNS"
        assert result[0]["method"] == "tcp"

    def test_multiple_targets(self) -> None:
        """GIVEN a target text with two TCP targets on separate lines."""
        text = "1.1.1.1, Cloudflare DNS, tcp\n8.8.8.8, Google DNS, tcp"

        """WHEN parsing the text."""
        result = _parse_targets(text)

        """THEN both targets are returned."""
        assert len(result) == 2

    def test_minimal_target(self) -> None:
        """GIVEN a target text with only a host."""

        """WHEN parsing the text."""
        result = _parse_targets("1.1.1.1")

        """THEN label defaults to the host and method defaults to tcp."""
        assert len(result) == 1
        assert result[0]["host"] == "1.1.1.1"
        assert result[0]["label"] == "1.1.1.1"
        assert result[0]["method"] == "tcp"

    def test_empty_lines_ignored(self) -> None:
        """GIVEN a target text containing empty lines between valid targets."""
        text = "1.1.1.1, CF, tcp\n\n\n8.8.8.8, Google, tcp\n"

        """WHEN parsing the text."""
        result = _parse_targets(text)

        """THEN only valid targets are returned."""
        assert len(result) == 2

    def test_empty_string(self) -> None:
        """GIVEN an empty string."""

        """WHEN parsing the text."""
        result = _parse_targets("")

        """THEN no targets are returned."""
        assert len(result) == 0

    def test_whitespace_trimming(self) -> None:
        """GIVEN a target text with extra whitespace around each field."""

        """WHEN parsing the text."""
        result = _parse_targets("  1.1.1.1 ,  Cloudflare  ,  tcp  ")

        """THEN all fields are trimmed of surrounding whitespace."""
        assert result[0]["host"] == "1.1.1.1"
        assert result[0]["label"] == "Cloudflare"
        assert result[0]["method"] == "tcp"

    def test_http_method(self) -> None:
        """GIVEN a target text specifying the http probe method."""

        """WHEN parsing the text."""
        result = _parse_targets("https://example.com, Example, http")

        """THEN the method is set to http."""
        assert result[0]["method"] == "http"

    def test_dns_method(self) -> None:
        """GIVEN a target text specifying the dns probe method."""

        """WHEN parsing the text."""
        result = _parse_targets("www.google.com, Google, dns")

        """THEN the method is set to dns."""
        assert result[0]["method"] == "dns"

    def test_empty_label_defaults_to_host(self) -> None:
        """GIVEN a target text with an empty label field."""

        """WHEN parsing the text."""
        result = _parse_targets("1.1.1.1,, tcp")

        """THEN the label defaults to the host value."""
        assert len(result) == 1
        assert result[0]["label"] == "1.1.1.1"

    def test_method_case_insensitive(self) -> None:
        """GIVEN a target text with an uppercase method."""

        """WHEN parsing the text."""
        result = _parse_targets("1.1.1.1, CF, TCP")

        """THEN the method is lowercased."""
        assert result[0]["method"] == "tcp"

    def test_only_commas(self) -> None:
        """GIVEN a target text containing only commas."""

        """WHEN parsing the text."""
        result = _parse_targets(",,")

        """THEN no targets are returned."""
        assert len(result) == 0


class TestValidateTargets:
    """Tests for target validation."""

    def test_valid_targets(self) -> None:
        """GIVEN a list with one valid TCP target."""
        targets = [{"host": "1.1.1.1", "label": "CF", "method": "tcp"}]

        """THEN validation passes with no error."""
        assert _validate_targets(targets) is None

    def test_no_targets(self) -> None:
        """GIVEN an empty target list."""

        """THEN validation returns "no_targets" error."""
        assert _validate_targets([]) == "no_targets"

    def test_too_many_targets(self) -> None:
        """GIVEN a list of 11 targets exceeding the max of 10."""
        targets = [{"host": f"10.0.0.{i}", "method": "tcp"} for i in range(11)]

        """THEN validation returns "too_many_targets" error."""
        assert _validate_targets(targets) == "too_many_targets"

    def test_invalid_method(self) -> None:
        """GIVEN a target with an unsupported probe method."""
        targets = [{"host": "1.1.1.1", "method": "icmp"}]

        """THEN validation returns "invalid_method" error."""
        assert _validate_targets(targets) == "invalid_method"

    def test_empty_host(self) -> None:
        """GIVEN a target with an empty host string."""
        targets = [{"host": "", "method": "tcp"}]

        """THEN validation returns "invalid_host" error."""
        assert _validate_targets(targets) == "invalid_host"

    def test_missing_host_key(self) -> None:
        """GIVEN a target dict without a "host" key."""
        targets = [{"method": "tcp"}]

        """THEN validation returns "invalid_host" error."""
        assert _validate_targets(targets) == "invalid_host"

    def test_none_host(self) -> None:
        """GIVEN a target dict with host set to None."""
        targets = [{"host": None, "method": "tcp"}]

        """THEN validation returns "invalid_host" error."""
        assert _validate_targets(targets) == "invalid_host"


class TestTargetsToText:
    """Tests for target list to text conversion."""

    def test_roundtrip(self) -> None:
        """GIVEN a list of two targets."""
        targets = [
            {"host": "1.1.1.1", "label": "Cloudflare DNS", "method": "tcp"},
            {"host": "8.8.8.8", "label": "Google DNS", "method": "tcp"},
        ]

        """WHEN converting to text and parsing back."""
        text = _targets_to_text(targets)
        parsed = _parse_targets(text)

        """THEN the roundtrip preserves all targets."""
        assert len(parsed) == 2
        assert parsed[0]["host"] == "1.1.1.1"
        assert parsed[1]["host"] == "8.8.8.8"


class TestConfigFlow:
    """Tests for the WANPulse config flow."""

    @pytest.mark.asyncio
    async def test_user_step_shows_form(self, hass: HomeAssistant) -> None:
        """GIVEN a Home Assistant instance."""

        """WHEN initiating the config flow from the user source."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        """THEN a form is shown for the "user" step."""
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_user_step_creates_entry(self, hass: HomeAssistant) -> None:
        """GIVEN reachability check is mocked to succeed."""

        """WHEN submitting the user step with a valid target."""
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

        """THEN a config entry is created with the correct data."""
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "WANPulse"
        assert len(result["data"][CONF_TARGETS]) == 1
        assert result["data"][CONF_TARGETS][0]["host"] == "1.1.1.1"

    @pytest.mark.asyncio
    async def test_user_step_invalid_targets(self, hass: HomeAssistant) -> None:
        """GIVEN the user step form is displayed."""

        """WHEN submitting with an empty targets string."""
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

        """THEN the form is shown again with a "no_targets" error."""
        assert result["type"] is FlowResultType.FORM
        assert result["errors"][CONF_TARGETS] == "no_targets"

    @pytest.mark.asyncio
    async def test_user_step_invalid_method(self, hass: HomeAssistant) -> None:
        """GIVEN the user step form is displayed."""

        """WHEN submitting with an unsupported probe method."""
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

        """THEN the form is shown again with an "invalid_method" error."""
        assert result["type"] is FlowResultType.FORM
        assert result["errors"][CONF_TARGETS] == "invalid_method"

    @pytest.mark.asyncio
    async def test_user_step_all_unreachable(self, hass: HomeAssistant) -> None:
        """GIVEN reachability check reports all targets as unreachable."""

        """WHEN submitting the user step with a valid target."""
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

        """THEN the form is shown again with an "all_targets_unreachable" error."""
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "all_targets_unreachable"

    @pytest.mark.asyncio
    async def test_duplicate_entry_prevented(self, hass: HomeAssistant) -> None:
        """GIVEN a config entry already exists."""
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

            """WHEN attempting to create a second entry."""
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

            """THEN the flow is aborted as already configured."""
            assert result["type"] is FlowResultType.ABORT
            assert result["reason"] == "already_configured"


class TestOptionsFlow:
    """Tests for the WANPulse options flow."""

    @pytest.mark.asyncio
    async def test_options_step_shows_form(self, hass: HomeAssistant, mock_config_entry) -> None:
        """GIVEN a configured and loaded config entry."""
        mock_config_entry.add_to_hass(hass)
        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        """WHEN initiating the options flow."""
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        """THEN a form is shown for the "init" step."""
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_step_saves(self, hass: HomeAssistant, mock_config_entry) -> None:
        """GIVEN a configured and loaded config entry."""
        mock_config_entry.add_to_hass(hass)
        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        """WHEN submitting the options form with new values."""
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

        """THEN the options are saved to the config entry."""
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert mock_config_entry.options[CONF_SCAN_INTERVAL] == 30
        assert mock_config_entry.options[CONF_TIMEOUT] == 5

    @pytest.mark.asyncio
    async def test_options_rejects_invalid_scan_interval(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """GIVEN a configured and loaded config entry."""
        from homeassistant.data_entry_flow import InvalidData

        mock_config_entry.add_to_hass(hass)
        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        """WHEN submitting the options form with scan interval below minimum."""
        """THEN InvalidData is raised."""
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
        """GIVEN a configured and loaded config entry."""
        mock_config_entry.add_to_hass(hass)
        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        """WHEN starting the reconfigure flow."""
        result = await mock_config_entry.start_reconfigure_flow(hass)

        """THEN a form is shown for the "reconfigure" step."""
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

    @pytest.mark.asyncio
    async def test_reconfigure_updates_targets(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """GIVEN a configured and loaded config entry with reachability mocked to succeed."""
        mock_config_entry.add_to_hass(hass)
        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        """WHEN submitting the reconfigure form with new targets."""
        with patch(
            "custom_components.wanpulse.config_flow._test_target_reachability",
            return_value=[],
        ):
            result = await mock_config_entry.start_reconfigure_flow(hass)
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_TARGETS: "9.9.9.9, Quad9, tcp"},
            )

        """THEN the flow aborts with a success reason."""
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

    @pytest.mark.asyncio
    async def test_reconfigure_invalid_targets(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """GIVEN a configured and loaded config entry."""
        mock_config_entry.add_to_hass(hass)
        with patch("custom_components.wanpulse.async_setup_entry", return_value=True):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        """WHEN submitting the reconfigure form with an empty targets string."""
        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TARGETS: ""},
        )

        """THEN the form is shown again with a "no_targets" error."""
        assert result["type"] is FlowResultType.FORM
        assert result["errors"][CONF_TARGETS] == "no_targets"
