---
source: NOTES-behavioral-conformance-specs--schema-changes-and-new-spec-files
timestamp: '2026-09-17T17:10:50.846740+00:00'
title: 'Behavioral conformance: Schema Changes Required and New Spec Files'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** specs/{rm,em,cs}-behavior.yaml; vultron/metadata/specs/schema.py

---

## Schema Changes Required

Four additions to `vultron/metadata/specs/schema.py`:

### 1. New `RelationType` value

```python
SATISFIES = "satisfies"
```

### 2. New `TriggerType` enum

```python
class TriggerType(StrEnum):
    MESSAGE_RECEIVED = "message_received"
    STATE_ENTERED = "state_entered"
```

Enumerate known trigger kinds so a third kind (e.g., `timer_expired`,
`external_event`) can be added explicitly rather than via free text.

### 3. New `Trigger` model

```python
class Trigger(BaseModel):
    type: TriggerType
    value: str   # e.g. "EP" (message name) or "RM.VALID" (state)
```

### 4. Extend `Precondition` with typed state fields

```python
class Precondition(BaseModel):
    rm_state: list[RMState] | None = None      # e.g. [RM.VALID, RM.ACCEPTED]
    em_state: list[EMState] | None = None      # e.g. [EM.ACTIVE]
    cs_pattern: str | None = None              # 6-char vfdpxa regex, e.g. "...pxa"
    role: list[CVDRole] | None = None          # e.g. [CVDRole.VENDOR]
    description: str                           # required: prose summary of all typed fields
```

`description` is **required** (not `Optional[str]`). It MUST be a non-empty
prose summary of the complete precondition, derived from all typed fields
present.  Use a consistent "mad lib" pattern synthesised from each typed
field that is set:

- `rm_state: [X]` → `"Participant is in RM X"`
- `rm_state: [R,I,V,D,A]` → `"Participant is in an active RM state (Received/Invalid/Valid/Deferred/Accepted)"`
- `em_state: [X]` → `"EM state is X"`
- `em_state: [X, Y]` → `"EM state is X or Y"`
- `role: [X]` → `"Participant holds the X role"`
- `cs_pattern: "abc..."` → `"CS matches pattern abc..."`

Combine multiple clauses with `"; "` separator, in field order:
`rm_state` → `em_state` → `role` → `cs_pattern`.

> **Field order in `Precondition`**: the class declares fields in the order
> `rm_state`, `em_state`, `role`, `cs_pattern`, `description`. The prose
> clauses MUST follow the same order so machine-generated and hand-authored
> descriptions are consistent.

The RM/EM/CS enums are stable (unchanged for several years); coupling
`Precondition` to them is safe. `cs_pattern` uses the same 6-char regex
convention as `potential_actions.py` — uppercase = event occurred, lowercase =
not yet, `.` = don't-care.

### 5. Add `trigger` to `SpecGroup`

```python
class SpecGroup(BaseModel):
    # ... existing fields ...
    trigger: Trigger | None = None
```

`BehavioralSpec` (with `preconditions`, `steps`, `postconditions`) already
exists in the schema but is unused. These changes activate it for real use.

## New Spec Files

Three new files, each using `BehavioralSpec` items (not `StatementSpec`):

| File | ID prefix | Trigger types | Groups |
|---|---|---|---|
| `specs/rm-behavior.yaml` | `RMB` | message_received (RS,RI,RV,RD,RA,RC,RE,RK), state_entered (RM.R/V/I/D/A/C) | 14 |
| `specs/em-behavior.yaml` | `EMB` | message_received (EP,EA,EV,EJ,EC,ER,ET,EE,EK), state_entered (EM.P/A/R/X) | 13 |
| `specs/cs-behavior.yaml` | `CSB` | message_received (CV,CF,CD,CP,CX,CA,CE,CK), state_entered (CS.V/F/D/P/X/A) | 14 |

Each group carries a `trigger:` annotation at the group level.
Items within a group carry `preconditions:` (structured, using the typed
fields above) and `relationships:` pointing to VP items via `satisfies`.
