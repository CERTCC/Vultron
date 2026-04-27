---
title: Actor Knowledge Model — Implementation Notes
status: active
description: >
  Design decisions and implementation guidance for the Actor Knowledge Model
  (IDEA-26041601/02).
related_specs:
  - specs/actor-knowledge-model.yaml
  - specs/testability.yaml
relevant_packages:
  - fastapi
  - vultron/core/behaviors
  - vultron/core/use_cases
  - vultron/adapters/driving/fastapi
---

# Actor Knowledge Model — Implementation Notes

## Overview

These notes accompany `specs/actor-knowledge-model.yaml`. They record the design
decisions made when formalizing IDEA-26041601 and IDEA-26041602, and provide
implementation guidance for enforcing the Actor Knowledge Model in new and
existing code.

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Can Actors access each other's DataLayers under any circumstances? | No — never. | Architectural invariant, not an optimization. Even co-located actors must use the wire protocol. |
| Is the "round-trip to the sender's DataLayer" framing correct? | No — that framing implies access is possible but avoided for efficiency. Replace with "the recipient has no access to the sender's DataLayer". | Prevents agents and developers from treating DataLayer isolation as optional. |
| Should outbound activities include full inline objects? | Yes — always, with one approved exception (stub objects in `Invite.target`). | Recipients cannot resolve bare URIs without access to the sender's DataLayer, which they do not have. |
| Where is the authoritative runtime guard? | `outbox_handler.py` raises `VultronOutboxObjectIntegrityError` when `object_` is a bare string or `as_Link` after expansion. | Last-resort catch for code paths that bypass Pydantic construction-time narrowing. |
| Should we track what objects have been shared to avoid redundant transmission? | Deferred to `PROD_ONLY` MAY. Default is "always include full object when in doubt". | Premature optimization; adds bookkeeping complexity not justified at prototype stage. |

---

## The Core Invariant

An Actor's knowledge of the world is bounded by what it has **received** via
AS2 activities. There is no side channel. There is no shared memory. There is
no DataLayer access across Actor boundaries.

This has a direct corollary for outbound activity construction:

> **If an Actor sends a bare object URI in an outbound activity, the recipient
> cannot resolve it. The recipient has no access to the sender's DataLayer.**

This is not a performance concern or a "nice to have." It is the fundamental
isolation model.

---

## Common Violation Patterns

### Anti-Pattern: Bare string ID as `object_`

```python
# ❌ WRONG — recipient cannot resolve this
activity = RmSubmitReportActivity(
    actor=actor.id_,
    object_=report.id_,  # bare string URI
    to=[recipient.id_],
)
```

The recipient receives `object_="urn:uuid:abc123"`. When the inbox handler
tries to pattern-match the activity, `activity_object` is a string. Rehydration
from the recipient's own DataLayer fails because the recipient has no record of
this object. Pattern matching falls through to `MessageSemantics.UNKNOWN`.

### Correct Pattern: Full inline object

```python
# ✅ CORRECT — recipient receives full object
activity = RmSubmitReportActivity(
    actor=actor.id_,
    object_=report,  # full VulnerabilityReport instance
    to=[recipient.id_],
)
```

The recipient receives the full `VulnerabilityReport` inline. Pattern matching
succeeds because `activity.object_.type_` is directly accessible.

---

### Anti-Pattern: Passing `case.id_` in `Add` activity target

```python
# ❌ WRONG — recipient cannot look up case from their own DataLayer
activity = AddCaseLogEntryActivity(
    actor=actor.id_,
    object_=log_entry,
    target=case.id_,   # bare string — recipient may not have this case
    to=[recipient.id_],
)
```

### Correct Pattern: Full inline case as target

```python
# ✅ CORRECT
activity = AddCaseLogEntryActivity(
    actor=actor.id_,
    object_=log_entry,
    target=case,       # full VulnerabilityCase instance
    to=[recipient.id_],
)
```

---

## Detecting Violations: Audit Checklist

When auditing for AKM violations, search for these patterns:

1. **`object_=<model>.id_`** — check any `.id_` assignment to an `object_`
   field in activity construction:

   ```bash
   grep -rn "object_=.*\.id_" vultron/ --include="*.py"
   ```

2. **`target=<model>.id_`** — similar pattern for `target` fields:

   ```bash
   grep -rn "target=.*\.id_" vultron/ --include="*.py"
   ```

3. **`actor=.*\.id_`** — `actor` is generally an ID reference (correct), but
   confirm it is the *sender's own* ID, not a reference to a third-party object:

   ```bash
   grep -rn "actor=.*\.id_" vultron/ --include="*.py"
   ```

4. **String-typed `object_` in demo scripts** — demos may build activities
   using dict literals; check that `"object"` values are serialized full
   objects, not bare IDs:

   ```bash
   grep -rn '"object".*:.*id_\|"object".*id_' vultron/demo/ --include="*.py"
   ```

5. **`outbox_handler` expansion path** — any `logger.warning(... "bare string
   object_"...)` in the outbox handler indicates an AKM violation at runtime.
   These log lines are the smoke signal.

---

## Runtime Guard Location

`vultron/adapters/driving/fastapi/outbox_handler.py` contains the last-resort
enforcement. When an outbound activity's `object_` is still a bare string or
`as_Link` after an attempted DataLayer expansion, the handler raises
`VultronOutboxObjectIntegrityError` and aborts delivery.

This guard catches violations that bypass Pydantic's construction-time type
narrowing (e.g., activities loaded from DataLayer records that predate the
`INLINE-OBJ-A` narrowing change).

**Key log signature for violations:**

```text
WARNING  Outbound <Type> activity '<id>' has a bare string object_ '<uri>'.
         Attempting DataLayer expansion (MV-09-001 violation).
```

If this warning appears in logs, trace back to the activity builder that
created the activity and fix it to include the full inline object.

---

## Fixing the Misleading Docstring in `errors.py`

`VultronOutboxObjectIntegrityError` previously had this docstring:

```python
# ❌ OLD (misleading)
"""...so that recipients can determine the semantic type without a round-trip
to the sender's DataLayer."""
```

The phrase "without a round-trip" implies DataLayer access is *possible* but
*avoided for efficiency*. This is incorrect.

The corrected version (see commit):

```python
# ✅ NEW (accurate)
"""...because the recipient has no access to the sender's DataLayer."""
```

---

## Layer and Import Rules

- Activity builders in `vultron/core/use_cases/` and `vultron/core/behaviors/`
  MUST NOT receive raw string IDs where domain objects are expected. Pass the
  domain object, let the builder use `.id_` internally only if the field
  signature requires a string.
- The `outbox_handler` is the **only** place that MAY attempt DataLayer
  expansion as a backward-compatibility bridge. New code MUST NOT rely on
  this expansion path.
- Test fixtures that construct activities MUST use full domain objects, not
  string IDs, as `object_` values. See `specs/testability.yaml` TB-05-004.

---

## Testing Patterns

```python
# Verify runtime guard raises on bare string object_
def test_outbox_rejects_bare_string_object(dl, actor):
    activity = as_Offer(
        actor=actor.id_,
        object_="urn:uuid:not-expanded",
        to=["https://example.org/recipient"],
    )
    with pytest.raises(VultronOutboxObjectIntegrityError):
        deliver_outbound_activity(activity, dl)
```

```python
# Verify correct construction passes through outbox
def test_outbox_accepts_inline_object(dl, actor, report):
    activity = RmSubmitReportActivity(
        actor=actor.id_,
        object_=report,
        to=["https://example.org/recipient"],
    )
    # Should not raise
    deliver_outbound_activity(activity, dl)
```
