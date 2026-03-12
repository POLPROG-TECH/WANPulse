"""The WANPulse integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_FAILURE_THRESHOLD,
    CONF_PROBE_COUNT,
    CONF_SCAN_INTERVAL,
    CONF_TARGET_HOST,
    CONF_TARGET_LABEL,
    CONF_TARGET_METHOD,
    CONF_TARGET_PORT,
    CONF_TARGETS,
    CONF_TIMEOUT,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_PROBE_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    PLATFORMS,
)
from .coordinator import WANPulseCoordinator
from .models import ProbeMethod, ProbeTarget

_LOGGER = logging.getLogger(__name__)


@dataclass
class WANPulseRuntimeData:
    """Runtime data for the WANPulse integration."""

    coordinator: WANPulseCoordinator


WANPulseConfigEntry = ConfigEntry[WANPulseRuntimeData]


def _build_targets(raw_targets: list[dict[str, str]]) -> list[ProbeTarget]:
    """Build ProbeTarget objects from config entry data."""
    targets: list[ProbeTarget] = []
    for raw in raw_targets:
        method_str = raw.get(CONF_TARGET_METHOD, "tcp")
        try:
            method = ProbeMethod(method_str)
        except ValueError:
            _LOGGER.warning("Skipping target with invalid method: %s", method_str)
            continue
        targets.append(
            ProbeTarget(
                host=raw[CONF_TARGET_HOST],
                label=raw.get(CONF_TARGET_LABEL, raw[CONF_TARGET_HOST]),
                method=method,
                port=raw.get(CONF_TARGET_PORT),
            )
        )
    return targets


async def async_setup_entry(hass: HomeAssistant, entry: WANPulseConfigEntry) -> bool:
    """Set up WANPulse from a config entry."""
    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={
                CONF_SCAN_INTERVAL: entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
                CONF_PROBE_COUNT: DEFAULT_PROBE_COUNT,
                CONF_FAILURE_THRESHOLD: DEFAULT_FAILURE_THRESHOLD,
            },
        )

    raw_targets = entry.data.get(CONF_TARGETS, [])
    targets = _build_targets(raw_targets)

    if not targets:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "no_valid_targets",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="no_valid_targets",
        )
        return False

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    if scan_interval < MIN_SCAN_INTERVAL:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "aggressive_polling",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="aggressive_polling",
        )

    coordinator = WANPulseCoordinator(hass, entry, targets)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = WANPulseRuntimeData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WANPulseConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: WANPulseConfigEntry) -> bool:
    """Migrate old config entries.

    Currently at version 1.1, so no migration needed yet.
    This function is prepared for future schema changes.
    """
    _LOGGER.debug(
        "Migrating WANPulse config entry from version %s.%s",
        entry.version,
        entry.minor_version,
    )

    return True
