---
source: NOTES-participant-role-management--testing-patterns
timestamp: '2026-09-17T17:32:54.693745+00:00'
title: Testing Patterns (roles API)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** test/architecture/test_participant_case_roles.py

---

## Testing Patterns

Tests live in `test/core/models/test_participant.py`.

### `add_role()` Tests

```python
def test_add_role_new():
    p = make_participant()
    p.add_role(CVDRole.VENDOR)
    assert CVDRole.VENDOR in p.roles

def test_add_role_idempotent(caplog):
    p = make_participant(roles=[CVDRole.VENDOR])
    with caplog.at_level(logging.INFO):
        p.add_role(CVDRole.VENDOR)
    assert caplog.text.count("already present") >= 1
    assert p.roles.count(CVDRole.VENDOR) == 1

def test_add_role_raise_when_present():
    p = make_participant(roles=[CVDRole.VENDOR])
    with pytest.raises(KeyError):
        p.add_role(CVDRole.VENDOR, raise_when_present=True)
```

### `remove_role()` Tests

```python
def test_remove_role_present():
    p = make_participant(roles=[CVDRole.VENDOR])
    p.remove_role(CVDRole.VENDOR)
    assert CVDRole.VENDOR not in p.roles

def test_remove_role_idempotent(caplog):
    p = make_participant()
    with caplog.at_level(logging.INFO):
        p.remove_role(CVDRole.VENDOR)
    assert "not present" in caplog.text

def test_remove_role_raise_when_missing():
    p = make_participant()
    with pytest.raises(KeyError):
        p.remove_role(CVDRole.VENDOR, raise_when_missing=True)
```

### `has_role()` Tests

```python
def test_has_role_present():
    p = make_participant(roles=[CVDRole.VENDOR])
    assert p.has_role(CVDRole.VENDOR) is True

def test_has_role_absent():
    p = make_participant()
    assert p.has_role(CVDRole.VENDOR) is False
```

### Architecture Test (Fast Scan)

```python
import re
from pathlib import Path

CORE_ROOT = Path(__file__).parents[2] / "vultron" / "core"
PARTICIPANT_MODULE = CORE_ROOT / "models" / "participant.py"

# Patterns that indicate direct case_roles mutation
_MUTATION_RE = re.compile(r"\.case_roles\s*=|\.case_roles\s*\.\s*append")


def test_no_direct_case_roles_mutation_in_core():
    violations = []
    for py_file in CORE_ROOT.rglob("*.py"):
        if py_file == PARTICIPANT_MODULE:
            continue
        text = py_file.read_text()
        for lineno, line in enumerate(text.splitlines(), 1):
            if _MUTATION_RE.search(line):
                violations.append(f"{py_file.relative_to(CORE_ROOT)}:{lineno}: {line.strip()}")
    assert not violations, "Direct case_roles mutations found in core:\n" + "\n".join(violations)
```

This scan reads only files under `vultron/core/` (a small, bounded
directory) and uses a compiled regex, completing well within the 1-second
budget on modern hardware.
