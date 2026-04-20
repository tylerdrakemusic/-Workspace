---
description: "Use when writing or reviewing test files for any project. Covers pytest conventions, fixture patterns, DB test isolation, mocking strategies, and naming standards for all workspace project test suites."
applyTo: "**/tests/**/*.py"
---

# Testing Base Instructions

Shared test conventions for all projects in this workspace. Apply these standards to every test file.

## Framework & Tooling
- **Framework:** pytest (>=8.0)
- **Coverage:** pytest-cov (>=5.0), target 50% initially
- **Mocking:** pytest-mock (>=3.14) + `unittest.mock`
- **Python:** 3.11+ with type hints on test helper functions
- **Runner:** `C:\G\python.exe -m pytest`

## Directory Layout
```
<project>/
  tests/
    __init__.py
    conftest.py          # Project-specific fixtures
    test_<module>.py     # One test file per source module
```

## Naming Conventions
- Test files: `test_<module_name>.py`
- Test functions: `test_<what_is_being_tested>()`
- Test classes (if grouping): `TestClassName`
- Fixtures: descriptive noun (`db_conn`, `sample_tip`, `mock_api_response`)

## Database Test Isolation
**NEVER touch production databases in tests.**

```python
# Projects with SQLite databases — in-memory isolation
import sqlite3
import pytest

@pytest.fixture
def db_conn():
    """Provide a fresh in-memory database with schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    # Apply schema here or import project's init function
    yield conn
    conn.close()
```

```python
# Projects with file-based state (caches, data files) — temp directory isolation
import pytest
from pathlib import Path

@pytest.fixture
def tmp_data(tmp_path: Path) -> Path:
    """Provide a temporary data file for testing."""
    data_file = tmp_path / "test_data.txt"
    data_file.write_text("sample content")
    return data_file
```

## Mocking External Services
```python
# Mock HTTP calls (scrapers, APIs)
def test_scraper(mocker):
    mock_resp = mocker.patch("requests.get")
    mock_resp.return_value.status_code = 200
    mock_resp.return_value.json.return_value = {"data": []}
    # test logic here

# Mock external services (IBM Quantum, DistroKid, etc.)
def test_external_service(mocker):
    mocker.patch("my_module.ExternalServiceClient")
    # test logic here
```

## Fixture Scope
- **function** (default): Fresh state per test — use for DB connections, mutable state
- **module**: Shared across test file — use for expensive read-only setup
- **session**: Shared across entire run — use for truly global setup (rare)

## Assertion Style
```python
# Preferred: plain assert with descriptive messages
assert len(results) == 3, f"Expected 3 results, got {len(results)}"
assert "marker_name" in row.keys()

# For exceptions
with pytest.raises(ValueError, match="invalid dosage"):
    process_dosage(-1)

# For approximate floats
assert result == pytest.approx(3.14, rel=1e-2)
```

## What NOT to Test
- Third-party library internals
- Simple data classes with no logic
- `__init__.py` files that only re-export
- Private helper functions (test through public interface)

## Coverage Reporting
```bash
C:\G\python.exe -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html:reports/coverage
```
