# Contributing to WANPulse

Thank you for your interest in contributing to WANPulse! This document outlines the process and standards for contributions.

## Development Setup

```bash
git clone https://github.com/polprog-tech/WANPulse.git
cd WANPulse
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements_test.txt
```

## Coding Standards

- **Python 3.12+** — Use modern Python features (type hints, StrEnum, etc.)
- **Async-first** — All I/O must be async. Never block the event loop.
- **Typed** — All functions must have type annotations.
- **Ruff** — Code must pass `ruff check .` and `ruff format --check .`
- **Docstrings** — Google-style docstrings for all public classes and functions.
- **No print statements** — Use `logging.getLogger(__name__)` instead.

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=custom_components/wanpulse --cov-report=term-missing

# Run a specific test file
pytest tests/components/wanpulse/test_models.py -v
```

## Branching & PRs

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests and linting
5. Commit with a clear message
6. Push to your fork
7. Open a Pull Request against `main`

### Commit Messages

Use clear, imperative commit messages:
- `Add DNS probe engine`
- `Fix jitter calculation for single-sample windows`
- `Update strings.json for new entity translations`

## How to Add a Probe Method

1. Create `custom_components/wanpulse/probes/your_method.py`
2. Implement `ProbeEngine` abstract base class:
   ```python
   class YourProbeEngine(ProbeEngine):
       async def async_probe(self, target: ProbeTarget, timeout: float) -> ProbeResult:
           ...
   ```
3. Register in `probes/__init__.py`:
   ```python
   _ENGINES["your_method"] = YourProbeEngine
   ```
4. Add `"your_method"` to `PROBE_METHODS` in `const.py`
5. Add tests in `tests/components/wanpulse/test_probes.py`
6. Update `strings.json` with any new user-facing text
7. Update `README.md` probe method table

### Probe Method Guidelines

- Must be fully async (no blocking calls)
- Must respect the `timeout` parameter
- Must catch all exceptions and return `ProbeResult(success=False, error=...)`
- Must not require elevated privileges (no raw sockets)
- Should work on all HA installation types

## How to Add Entities

1. Add a new `EntityDescription` to the appropriate sensor tuple in `sensor.py` or `binary_sensor.py`
2. Provide a `value_fn` that extracts the value from `CoordinatorSnapshot` or `TargetSnapshot`
3. Set `entity_registry_enabled_default=False` for non-essential entities
4. Add translation keys in `strings.json`
5. Add tests

### Entity Guidelines

- Entities must be thin — no business logic, just data extraction
- Use `translation_key` for all entity names
- Use appropriate `device_class`, `state_class`, and `native_unit_of_measurement`
- Consider whether the entity should be enabled by default (avoid bloat)

## Code Review Checklist

- [ ] All tests pass
- [ ] Ruff check passes
- [ ] New code has tests
- [ ] Strings are translatable (no hardcoded English in entities)
- [ ] No blocking I/O on the event loop
- [ ] Docstrings present for public API
- [ ] CHANGELOG.md updated
