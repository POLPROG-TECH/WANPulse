# WANPulse Architecture

## Design Goals

1. **Portable** — Works on Home Assistant OS, Container, Core, and Supervised without requiring elevated privileges
2. **Efficient** — Minimal network traffic and system resources; bounded memory usage
3. **Correct** — Accurate latency, jitter, and availability metrics with well-defined failure semantics
4. **Maintainable** — Clean module boundaries, typed Python, immutable data flow, thin entities
5. **HA-native** — Uses DataUpdateCoordinator, ConfigEntry.runtime_data, has_entity_name, translation keys, and other current HA patterns

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Config Entry                       │
│  data: {targets: [...]}                             │
│  options: {scan_interval, timeout, probe_count, ...}│
│  runtime_data: WANPulseRuntimeData(coordinator)     │
└─────────────┬───────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│              WANPulseCoordinator                     │
│  DataUpdateCoordinator[CoordinatorSnapshot]          │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ _TargetState  │  │ _TargetState  │  (per target) │
│  │  measurements │  │  measurements │                │
│  │  outage state │  │  outage state │                │
│  └──────┬───────┘  └──────┬───────┘                 │
│         │                  │                         │
│         ▼                  ▼                         │
│  ┌──────────────────────────────────┐               │
│  │     Probe Engines (async)        │               │
│  │  TCPProbeEngine                  │               │
│  │  HTTPProbeEngine                 │               │
│  │  DNSProbeEngine                  │               │
│  └──────────────────────────────────┘               │
│                                                      │
│  Output: CoordinatorSnapshot (immutable)             │
└─────────────┬───────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────┐
│              Entity Platforms                         │
│  binary_sensor.py  — WAN/target online status       │
│  sensor.py         — latency, jitter, loss, etc.    │
│  button.py         — manual probe trigger           │
│                                                      │
│  Entities are thin: read snapshot, extract value     │
└─────────────────────────────────────────────────────┘
```

## Probe Abstraction

All probe engines implement the `ProbeEngine` abstract base class:

```python
class ProbeEngine(ABC):
    @abstractmethod
    async def async_probe(self, target: ProbeTarget, timeout: float) -> ProbeResult: ...
```

**TCP** — `asyncio.open_connection` to host:port (default 443). Measures connection establishment time. Most portable approach.

**HTTP** — `aiohttp.ClientSession.head()` to a URL. Measures full HTTP response time. Tests through proxies.

**DNS** — `asyncio.getaddrinfo()` for hostname resolution. Measures DNS query time via system resolver.

### Why No ICMP?

ICMP echo requires `CAP_NET_RAW` or root privileges. This is not reliably available on:
- Home Assistant OS (sandboxed containers)
- Docker deployments without `--cap-add=NET_RAW`
- Rootless container environments

TCP connect to port 443 is universally available and provides equivalent reachability indication.

## Statistics Pipeline

```
ProbeEngine.async_probe() → ProbeResult
     ↓ (N results per cycle)
ProbeMeasurement.from_probe_results() → ProbeMeasurement
     ↓ (stored in deque per target)
filter_measurements_by_window() → list[ProbeMeasurement]
     ↓
WindowStats.from_measurements() → WindowStats
     ↓
CoordinatorSnapshot (assembled from all target stats)
     ↓
Entity.native_value (extracts single field from snapshot)
```

### Rolling Windows

- **Current** — Last `scan_interval × 5` seconds (e.g., 5 minutes at 60s interval)
- **1 hour** — Last 3600 seconds
- **24 hours** — Last 86400 seconds

Measurements are stored in bounded deques (`maxlen=9000` per target, sufficient for 24h at 10s intervals).

### Jitter Calculation

Mean absolute difference between consecutive latency samples (RFC 3550 approximation):
```
jitter = mean(|L[i] - L[i-1]| for i in 1..N)
```

## Entity Model

All entities use `has_entity_name = True` and `translation_key` for naming. Entity names are translated via `strings.json`.

### Device

One service-type device per config entry: "WANPulse"

### Entity Categories

- **Default entities** (enabled by default): WAN status, average latency, packet loss, jitter, availability, outage count
- **Diagnostic entities** (disabled by default): consecutive failures
- **Detailed entities** (disabled by default): min/max latency, outage duration, per-target metrics

This prevents entity bloat while giving power users access to detailed metrics.

## Update Strategy

- Coordinator runs on `update_interval` (default 60s, min 10s)
- Each cycle probes all targets concurrently (bounded by semaphore, max 10 concurrent)
- Each target receives `probe_count` sequential probes per cycle
- Results are aggregated into a `ProbeMeasurement`
- Snapshot is rebuilt from all target states
- Entities passively read the latest snapshot

### Recorder Interaction

- Sensors with `state_class` are automatically tracked by the HA recorder
- No custom database or storage — rely on HA's built-in long-term statistics
- In-memory rolling windows are for live dashboard display
- After restart, windows rebuild naturally as new measurements accumulate

## Config Entry Schema

```
entry.data = {
    "targets": [
        {"host": "1.1.1.1", "label": "Cloudflare DNS", "method": "tcp"},
        {"host": "8.8.8.8", "label": "Google DNS", "method": "tcp"},
    ],
    "scan_interval": 60,  # from initial setup
}

entry.options = {
    "scan_interval": 60,
    "timeout": 10,
    "probe_count": 3,
    "failure_threshold": 3,
}
```

`entry.data` holds target definitions (changed via reconfigure flow).
`entry.options` holds operational parameters (changed via options flow, triggers reload).

## Failure Semantics

- **Target offline**: `consecutive_failures >= failure_threshold`
- **WAN offline**: ALL targets are offline
- **Partial failure**: If 1 of 3 targets fails, WAN is still online. That target shows as offline.
- **No fresh data**: After restart, entities show as unavailable until first probe completes
- **Probe exception**: Caught and recorded as failure; does not crash the coordinator

## Why DataUpdateCoordinator?

- Built-in polling schedule management
- Automatic retry with exponential backoff on `UpdateFailed`
- Listener pattern for efficient entity updates
- First-refresh validation during setup
- Cancellation-safe
- Well-tested in HA core
