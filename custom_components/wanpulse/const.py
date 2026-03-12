"""Constants for the WANPulse integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "wanpulse"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
]

# Config entry keys (stored in entry.data)
CONF_TARGETS = "targets"
CONF_TARGET_HOST = "host"
CONF_TARGET_LABEL = "label"
CONF_TARGET_METHOD = "method"
CONF_TARGET_PORT = "port"

# Options keys (stored in entry.options)
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_PROBE_COUNT = "probe_count"
CONF_FAILURE_THRESHOLD = "failure_threshold"

# Probe methods
PROBE_METHODS = ["tcp", "http", "dns"]

# Defaults
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_TIMEOUT = 10
DEFAULT_PROBE_COUNT = 3
DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_PORT_TCP = 443

DEFAULT_TARGETS_TEXT = "1.1.1.1, Cloudflare DNS, tcp\n8.8.8.8, Google DNS, tcp"

# Limits
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600
MIN_TIMEOUT = 1
MAX_TIMEOUT = 60
MAX_TARGETS = 10
MAX_PROBE_COUNT = 10
MAX_FAILURE_THRESHOLD = 50

# Rolling window durations in seconds
WINDOW_1H_SECONDS = 3600
WINDOW_24H_SECONDS = 86400

# Max measurements to keep in memory per target (24h at 10s interval + buffer)
MAX_MEASUREMENTS_PER_TARGET = 9000

# Concurrency
MAX_CONCURRENT_PROBES = 10
