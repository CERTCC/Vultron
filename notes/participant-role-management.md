---
title: Participant Role Management Design Notes
status: active
description: >
  Design decisions and implementation guidance for the VultronParticipant and
  CaseParticipant role-management API (add_role, remove_role, has_role, roles
  property). Source: IDEA-26050401.
related_specs:
  - specs/participant-role-management.yaml
relevant_packages:
  - vultron/core/models/participant.py
  - vultron/wire/as2/vocab/objects/case_participant.py
  - vultron/core/use_cases/query/action_rules.py
  - test/core/models/test_participant.py
---

# Participant Role Management Design Notes

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Where do new tests go? | New `test/core/models/test_participant.py` | Mirrors source layout; keeps `test_base.py` focused on the base model contract |
| Should core code read `case_roles` directly? | No — use `roles` property | Decouples callers from storage field; allows future representation changes |
| What does the `roles` property return? | `list[CVDRole]` | Keeps callers working with domain types; `.value` extraction stays at call sites |
| Should `CaseParticipant` match the `VultronParticipant` interface? | Yes — full parity | Callers should not need to know which class they hold to manage roles |
| Should wire-layer `model_validator` role inits use `add_role()`? | Yes | Routes all role mutations through the single invariant-check point |
| Should an architecture test enforce the no-direct-mutation rule? | Yes, with ≤1 s budget | Machine-checkable enforcement; targeted scan stays fast |

---

## Key Design Patterns

### 1. `roles` Read-Only Property

Add a property to `VultronParticipant` that returns a copy of the internal
list:

```python
@property
def roles(self) -> list[CVDRole]:
    """Return the participant's current CVD roles (read-only copy)."""
    return list(self.case_roles)
```

This ensures callers cannot accidentally mutate the internal list via the
property reference.

### 2. `add_role()` and `remove_role()` Behaviour

Both methods use a `set` for O(1) membership tests and preserve list
semantics on assignment back. The methods are already implemented on
`VultronParticipant`; the pattern is:

```python
def add_role(self, role: CVDRole, raise_when_present: bool = False) -> None:
    roles = set(self.case_roles)
    if role not in roles:
        roles.add(role)
    else:
        logger.info("Attempted to add role %s to participant %s, but role was already present", role, self)
        if raise_when_present:
            raise KeyError(f"Role {role} was already present in participant.case_roles")
    self.case_roles = list(roles)
```

### 3. `CaseParticipant` Wire-Layer Update

The existing `CaseParticipant.add_role()` uses a simpler, non-idempotent
interface with a `reset` parameter. Replace it with the same signature as
`VultronParticipant.add_role()`, and add `remove_role()` and `has_role()`:

```python
# Before (wire layer)
def add_role(self, role: CVDRole, reset=False):
    if reset:
        self.case_roles = []
    self.case_roles.append(role)

# After (aligned with VultronParticipant)
def add_role(self, role: CVDRole, raise_when_present: bool = False) -> None:
    roles = set(self.case_roles)
    if role not in roles:
        roles.add(role)
    else:
        logger.info("Attempted to add role %s, but already present", role)
        if raise_when_present:
            raise KeyError(f"Role {role} was already present in case_roles")
    self.case_roles = list(roles)

def remove_role(self, role: CVDRole, raise_when_missing: bool = False) -> None:
    roles = set(self.case_roles)
    if role in roles:
        roles.remove(role)
    else:
        logger.info("Attempted to remove role %s, but not present", role)
        if raise_when_missing:
            raise KeyError(f"Role {role} was not present in case_roles")
    self.case_roles = list(roles)

def has_role(self, role: CVDRole) -> bool:
    return role in self.case_roles
```

> **Note on `reset` parameter**: The old `reset=True` pattern (clear roles
> then add one) is replaced in `model_validator` subclasses by direct
> `self.case_roles = [...]` assignment inside the validator, which is
> acceptable for initialization. The `add_role()` method is for
> post-construction mutations only.

### 4. Wire-Layer Subclass Validators

`FinderParticipant`, `VendorParticipant`, and similar subclasses use
`model_validator(mode="after")` to set their single role. After the
`add_role()` interface update, update these validators to use `add_role()`:

```python
# Before
@model_validator(mode="after")
def set_role(self):
    self.case_roles = [CVDRole.FINDER]
    return self

# After
@model_validator(mode="after")
def set_role(self):
    self.case_roles = []          # reset list (initialization context — not a mutation)
    self.add_role(CVDRole.FINDER)
    return self
```

For `FinderReporterParticipant` (two roles):

```python
@model_validator(mode="after")
def set_roles(self) -> FinderReporterParticipant:
    self.case_roles = []
    self.add_role(CVDRole.FINDER)
    self.add_role(CVDRole.REPORTER)
    return self
```

---

## Call-Site Migration Guide

### `action_rules.py`

Current code:

```python
roles = [r.value for r in (participant.case_roles or [])]
```

Updated code:

```python
roles = [r.value for r in participant.roles]
```

The `roles` property always returns a list (never `None`), so the `or []`
guard can be dropped.

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
