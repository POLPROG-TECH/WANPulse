# Changelog

All notable changes to WANPulse will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-06-29

### Fixed

- **Entity IDs are now stable and language-independent.** Previously, entity IDs were generated from translated entity names, causing mismatches when HA language changed or translations were updated. Entity IDs are now based on internal keys (e.g., `sensor.wanpulse_average_latency` instead of `sensor.wanpulse_internet_latency`).
- Dashboard cards now use correct entity IDs that match the stable format.

### Added

- Polish translation (`translations/pl.json`)
- English translation file (`translations/en.json`)
- New FAQ entry: "Dashboard cards show entity not found"
- Entity ID migration guide in README
- Tests for `suggested_object_id` on all entity types

### Changed

- All dashboard YAML files updated with stable entity IDs
- Entity ID reference table added to Upgrading section

### Migration

If upgrading from 1.0.x: delete and re-add the WANPulse integration to regenerate entity IDs. See README for details.

## [1.0.0] - 2026-03-12

### Added

- Initial release of WANPulse
- TCP connect probe engine (default, most portable)
- HTTP HEAD probe engine
- DNS resolution probe engine
- Config flow with default targets (Cloudflare DNS, Google DNS)
- Options flow for scan interval, timeout, probe count, and failure threshold
- Reconfigure flow for target management
- Aggregate WAN health binary sensor
- Per-target online status binary sensors
- Aggregate metrics: average latency, packet loss, jitter
- Rolling availability: 1-hour and 24-hour windows
- Outage tracking: count and duration
- Additional metrics (disabled by default): min/max latency, consecutive failures, outage duration
- Per-target metrics (disabled by default): latency, packet loss, jitter, availability
- "Probe now" button for manual probe cycles
- Diagnostics support with host/label redaction
- Repair issues for invalid configuration
- Translated strings for all UI text
- Full test suite
- CI workflows for linting, testing, and HACS/hassfest validation
- Architecture documentation
- Contributing guidelines
