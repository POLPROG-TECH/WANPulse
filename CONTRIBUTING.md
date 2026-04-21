# Contributing to WANPulse

Thank you for your interest in contributing! WANPulse is a community-driven project and welcomes contributions of all kinds.

## Development Setup

### Prerequisites

- Python 3.12+
- Home Assistant development environment (or a running HA instance for manual testing)
- Git

### Local Setup

```bash
# Clone the repository
git clone https://github.com/polprog-tech/WANPulse.git
cd WANPulse

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install development dependencies
pip install -r requirements_test.txt
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=custom_components/wanpulse --cov-report=term-missing

# Run a specific test file
pytest tests/components/wanpulse/test_models.py -v
```

### Linting & Formatting

```bash
# Check for lint errors
ruff check .

# Auto-fix lint errors
ruff check --fix .

# Format code
ruff format .
```

### Pre-commit hook

Install the bundled hook to run lint, format, and tests before every commit:

```bash
cp scripts/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

## Project Structure

```
custom_components/wanpulse/
├── __init__.py          # Integration setup and platform forwarding
├── config_flow.py       # Config and options flow
├── const.py             # Constants, enums (ProbeMethod, etc.)
├── models.py            # Domain models (ProbeTarget, ProbeResult, snapshots)
├── coordinator.py       # DataUpdateCoordinator orchestration
├── entity.py            # Base entity class
├── sensor.py            # Sensor entities
├── binary_sensor.py     # Binary sensor entities
├── button.py            # Manual probe button entity
├── diagnostics.py       # Diagnostics support
├── probes/
│   ├── __init__.py      # Probe engine registry and factory
│   ├── base.py          # ProbeEngine abstract base class
│   ├── dns.py           # DNS probe engine
│   ├── http.py          # HTTP probe engine
│   └── tcp.py           # TCP probe engine
├── manifest.json
├── strings.json
└── translations/
    ├── en.json
    └── pl.json
```

## Architecture Guidelines

### Adding a New Probe Method

1. Create `custom_components/wanpulse/probes/your_method.py`
2. Extend `ProbeEngine` from `probes/base.py`
3. Implement the `async_probe` method
4. Register in `probes/__init__.py`
5. Add `"your_method"` to `PROBE_METHODS` in `const.py`
6. Write tests in `tests/components/wanpulse/test_probes.py`
7. Update `strings.json` with any new user-facing text
8. Update `README.md` probe method table

```python
from .base import ProbeEngine

class YourProbeEngine(ProbeEngine):
    async def async_probe(self, target: ProbeTarget, timeout: float) -> ProbeResult:
        ...
```

### Adding a New Entity

1. Add a new `EntityDescription` to the appropriate sensor tuple in `sensor.py` or `binary_sensor.py`
2. Provide a `value_fn` that extracts the value from `CoordinatorSnapshot` or `TargetSnapshot`
3. Set `entity_registry_enabled_default=False` for non-essential entities
4. Add translation keys in `strings.json`
5. Write tests

### Key Principles

- **Async-first** - never block the event loop
- **Typed** - all functions must have type annotations
- **Keep entities thin** - they project backend state, don't contain business logic
- **Use `translation_key`** for all entity names - no hardcoded English in entities
- **Use appropriate `device_class`, `state_class`, and `native_unit_of_measurement`**
- **No print statements** - use `logging.getLogger(__name__)` instead
- **Docstrings** - Google-style docstrings for all public classes and functions
- **Test everything** - aim for high coverage on core logic
- **Probes must not require elevated privileges** (no raw sockets) and should work on all HA installation types

## Branching & PR Guidance

- **main** - stable release branch
- Feature branches: `feature/description`
- Bug fixes: `fix/description`
- PRs should include tests and pass all CI checks
- Keep commits atomic and well-described

## Commit Messages

Use conventional commits:

```
feat: add DNS probe engine
fix: handle jitter calculation for single-sample windows
test: add tests for HTTP probe timeout handling
docs: update probe method table in README
refactor: extract common probe logic into base class
```

## Testing Philosophy

WANPulse uses **scenario-oriented Given/When/Then (GWT) style tests** for readability and maintainability.

### Structure

Every test follows a clear three-part structure:

1. **Given** - Set up preconditions (create targets, configure mocks)
2. **When** - Perform the action under test (run a probe, call a service, submit a flow)
3. **Then** - Assert the expected outcome (check return values, verify state changes)

### In Practice

- Test classes are organized by **feature/scenario**, not by module. For example, `TestTCPProbeEngine` rather than `TestProbes`.
- Test method names describe the scenario: `test_successful_connect`, `test_timeout_returns_failure`.
- Each test uses `GIVEN`, `WHEN`, `THEN` docstrings - a class-level GIVEN above the `def` (or decorator), plus WHEN and THEN docstrings inside the method body.
- We include **happy-path**, **edge-case**, and **failure-path** scenarios for every feature.

### Example

```python
class TestTCPProbeOnTimeout:
    """Tests for TCP probe behavior on timeout."""

    """GIVEN a TCP target that does not respond in time"""
    @pytest.mark.asyncio
    async def test_returns_failure_with_error(self):
        target = ProbeTarget(host="10.0.0.1", label="Slow", method=ProbeMethod.TCP, port=443)

        """WHEN the probe is executed"""
        result = await engine.async_probe(target, timeout=0.001)

        """THEN the result indicates failure"""
        assert result.success is False
        assert result.error is not None
```

### Guidelines

- Prefer **many small test classes** (one scenario each) over large test classes with mixed scenarios.
- Use descriptive class docstrings that read as "Given ..." to set context.
- Aim for high coverage on core logic (models, coordinator, probes).
- Test both the happy path and meaningful edge cases (empty inputs, timeouts, unreachable hosts).

---

## Code Review Checklist

- [ ] All tests pass
- [ ] Ruff check passes
- [ ] New code has tests
- [ ] Strings are translatable (no hardcoded English in entities)
- [ ] No blocking I/O on the event loop
- [ ] Docstrings present for public API
- [ ] CHANGELOG.md updated

## License

See [LICENSE](LICENSE).
