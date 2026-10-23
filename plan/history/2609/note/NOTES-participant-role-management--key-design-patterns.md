---
source: NOTES-participant-role-management--key-design-patterns
timestamp: '2026-09-17T17:32:54.164187+00:00'
title: Key Design Patterns (roles API)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** case_participant.py roles property + add_role/remove_role; wire subclass

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
