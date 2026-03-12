"""Config flow for WANPulse."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback

# Compat: ConfigFlowResult added in HA 2024.4.
try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult

# Compat: OptionsFlowWithConfigEntry added in HA 2024.1.
try:
    from homeassistant.config_entries import OptionsFlowWithConfigEntry
except ImportError:

    class OptionsFlowWithConfigEntry(OptionsFlow):  # type: ignore[no-redef]
        """Shim for HA versions without OptionsFlowWithConfigEntry."""

        def __init__(self, config_entry: ConfigEntry) -> None:
            """Initialize."""
            self.config_entry = config_entry
            self.options = dict(config_entry.options)


from .const import (
    CONF_FAILURE_THRESHOLD,
    CONF_PROBE_COUNT,
    CONF_SCAN_INTERVAL,
    CONF_TARGETS,
    CONF_TIMEOUT,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_PROBE_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TARGETS_TEXT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MAX_FAILURE_THRESHOLD,
    MAX_PROBE_COUNT,
    MAX_SCAN_INTERVAL,
    MAX_TARGETS,
    MAX_TIMEOUT,
    MIN_SCAN_INTERVAL,
    MIN_TIMEOUT,
    PROBE_METHODS,
)

_LOGGER = logging.getLogger(__name__)

_HOST_RE = re.compile(
    r"^("
    r"https?://[^\s,]+"
    r"|[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*"
    r"|(\d{1,3}\.){3}\d{1,3}"
    r"|\[[0-9a-fA-F:]+\]"
    r")$"
)


def _is_valid_host(host: str, method: str) -> bool:
    """Check if host has a valid format for the given probe method."""
    if method == "http":
        if host.startswith(("http://", "https://")):
            return bool(_HOST_RE.match(host))
        return bool(_HOST_RE.match(host))
    return bool(_HOST_RE.match(host))


def _parse_targets(text: str) -> list[dict[str, str]]:
    """Parse targets from multiline text.

    Format: one target per line, comma-separated: host, label, method
    """
    targets: list[dict[str, str]] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if not parts or not parts[0]:
            continue
        host = parts[0]
        label = parts[1] if len(parts) > 1 and parts[1] else host
        method = parts[2].lower() if len(parts) > 2 and parts[2] else "tcp"
        targets.append({"host": host, "label": label, "method": method})
    return targets


def _validate_targets(targets: list[dict[str, str]]) -> str | None:
    """Validate parsed targets, returns error key or None."""
    if not targets:
        return "no_targets"
    if len(targets) > MAX_TARGETS:
        return "too_many_targets"
    for target in targets:
        host = target.get("host", "")
        if not host:
            return "invalid_host"
        method = target.get("method", "tcp")
        if method not in PROBE_METHODS:
            return "invalid_method"
        if not _is_valid_host(host, method):
            return "invalid_host_format"
    return None


async def _test_target_reachability(
    targets: list[dict[str, str]],
    timeout: float = 5.0,
) -> list[str]:
    """Quick reachability test. Returns list of unreachable host labels."""
    unreachable: list[str] = []
    for target in targets:
        host = target["host"]
        method = target.get("method", "tcp")
        label = target.get("label", host)
        try:
            if method == "http":
                url = host if host.startswith(("http://", "https://")) else f"https://{host}"
                import aiohttp

                async with asyncio.timeout(timeout):
                    async with aiohttp.ClientSession() as session:
                        async with session.head(url, allow_redirects=True):
                            pass
            elif method == "dns":
                dns_host = host.replace("https://", "").replace("http://", "")
                await asyncio.wait_for(
                    asyncio.get_event_loop().getaddrinfo(dns_host, None),
                    timeout=timeout,
                )
            else:  # tcp
                port = 443
                tcp_host = host
                if ":" in host and not host.startswith("["):
                    parts = host.rsplit(":", 1)
                    if parts[1].isdigit():
                        tcp_host = parts[0]
                        port = int(parts[1])
                _reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(tcp_host, port),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
        except Exception:  # noqa: BLE001
            unreachable.append(label)
    return unreachable


def _targets_to_text(targets: list[dict[str, str]]) -> str:
    """Convert target list back to multiline text."""
    lines = []
    for t in targets:
        lines.append(f"{t['host']}, {t.get('label', t['host'])}, {t.get('method', 'tcp')}")
    return "\n".join(lines)


class WANPulseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WANPulse."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            targets_text = user_input.get(CONF_TARGETS, "")
            targets = _parse_targets(targets_text)

            error = _validate_targets(targets)
            if error:
                errors[CONF_TARGETS] = error
            else:
                unreachable = await _test_target_reachability(targets)
                if unreachable:
                    labels = ", ".join(unreachable)
                    description_placeholders["unreachable"] = labels
                    if len(unreachable) == len(targets):
                        errors["base"] = "all_targets_unreachable"
                    else:
                        _LOGGER.warning("Some targets unreachable during setup: %s", labels)

                if not errors:
                    await self.async_set_unique_id(DOMAIN)
                    self._abort_if_unique_id_configured()

                    scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

                    return self.async_create_entry(
                        title="WANPulse",
                        data={
                            CONF_TARGETS: targets,
                            CONF_SCAN_INTERVAL: scan_interval,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TARGETS,
                        default=DEFAULT_TARGETS_TEXT,
                    ): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=DEFAULT_SCAN_INTERVAL,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of targets."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            targets_text = user_input.get(CONF_TARGETS, "")
            targets = _parse_targets(targets_text)

            error = _validate_targets(targets)
            if error:
                errors[CONF_TARGETS] = error
            else:
                unreachable = await _test_target_reachability(targets)
                if unreachable:
                    labels = ", ".join(unreachable)
                    description_placeholders["unreachable"] = labels
                    if len(unreachable) == len(targets):
                        errors["base"] = "all_targets_unreachable"
                    else:
                        _LOGGER.warning(
                            "Some targets unreachable during reconfigure: %s",
                            labels,
                        )

                if not errors:
                    # Compat: async_update_reload_and_abort added in HA 2024.11.
                    if hasattr(self, "async_update_reload_and_abort"):
                        return self.async_update_reload_and_abort(
                            entry,
                            data={CONF_TARGETS: targets},
                        )
                    self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, CONF_TARGETS: targets}
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reconfigure_successful")

        current_targets = entry.data.get(CONF_TARGETS, [])
        current_text = (
            _targets_to_text(current_targets) if current_targets else DEFAULT_TARGETS_TEXT
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TARGETS,
                        default=current_text,
                    ): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> WANPulseOptionsFlow:
        """Get the options flow handler."""
        return WANPulseOptionsFlow(config_entry)


class WANPulseOptionsFlow(OptionsFlowWithConfigEntry):
    """Handle WANPulse options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage operational settings."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_TIMEOUT: user_input[CONF_TIMEOUT],
                    CONF_PROBE_COUNT: user_input[CONF_PROBE_COUNT],
                    CONF_FAILURE_THRESHOLD: user_input[CONF_FAILURE_THRESHOLD],
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Required(
                        CONF_TIMEOUT,
                        default=self.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_TIMEOUT, max=MAX_TIMEOUT),
                    ),
                    vol.Required(
                        CONF_PROBE_COUNT,
                        default=self.options.get(CONF_PROBE_COUNT, DEFAULT_PROBE_COUNT),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=1, max=MAX_PROBE_COUNT),
                    ),
                    vol.Required(
                        CONF_FAILURE_THRESHOLD,
                        default=self.options.get(CONF_FAILURE_THRESHOLD, DEFAULT_FAILURE_THRESHOLD),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=1, max=MAX_FAILURE_THRESHOLD),
                    ),
                }
            ),
        )
