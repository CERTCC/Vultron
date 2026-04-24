---
title: Outbox Notes
status: active
description: Implementation guidance for outbox addressing requirements.
related_specs:
  - specs/outbox.md
relevant_packages:
  - fastapi
---

# Outbox Notes

Implementation guidance for outbox addressing requirements.

**Spec**: `specs/outbox.md` OX-08-001 through OX-08-004  
**Source idea**: IDEA-26041001

---

## Context

The `D5-7-TRIGNOTIFY-1` task fixed missing `to:` fields in trigger use-case
outbound activities. The root cause was the absence of a spec requirement and
enforcement mechanism. IDEA-26041001 formalises the rule: all outbound
Vultron activities are direct messages and MUST have a non-empty `to:` field.

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Which addressing fields are valid? | `to:` only | All Vultron exchanges are DMs; `cc`/`bto`/`bcc` unsupported |
| Where to enforce? | `handle_outbox_item` in `outbox_handler.py` | Already has the full activity; consistent with existing `VultronOutboxObjectIntegrityError` pattern |
| Exception class? | New `VultronOutboxToFieldMissingError` | Matches project exception naming convention; distinct from object-integrity errors |
| Scope? | All outbox activities, no exceptions | Every outbound activity must be addressed |
| What counts as valid `to:`? | Non-empty list (or scalar) of URI strings | Empty list is as bad as `None`; format validation out of scope |
| `cc`/`bto`/`bcc` presence? | Log WARNING, do not reject | Surfaces bugs without breaking delivery in edge cases |

---

## Implementation

### 1. Add `VultronOutboxToFieldMissingError` to `vultron/errors.py`

Place it alongside `VultronOutboxObjectIntegrityError`:

```python
class VultronOutboxToFieldMissingError(VultronError):
    """Raised when an outbound activity lacks a non-empty ``to:`` field.

    All Vultron protocol exchanges are direct messages.  Every outbound
    activity MUST address at least one recipient via ``to:``.
    See specs/outbox.md OX-08-001, OX-08-002.
    """

    def __init__(
        self,
        message: str,
        activity_id: str | None = None,
        activity_type: str | None = None,
    ):
        self.activity_id = activity_id
        self.activity_type = activity_type
        super().__init__(message)
```

### 2. Add the check in `handle_outbox_item`

Insert after the `VultronOutboxObjectIntegrityError` object-integrity check
and before `_extract_recipients`:

```python
# Validate to: field (OX-08-001, OX-08-002)
to_field = getattr(outbound_activity, "to", None)
_to_empty = to_field is None or (
    isinstance(to_field, list) and len(to_field) == 0
)
if _to_empty:
    raise VultronOutboxToFieldMissingError(
        f"Outbound {activity_type} activity '{activity_id}' has no `to:`"
        " field. All outbound Vultron activities MUST address at least"
        " one recipient via `to:` (OX-08-001).",
        activity_id=activity_id,
        activity_type=activity_type,
    )

# Warn if cc/bto/bcc are set (OX-08-004)
for _addr_field in ("cc", "bto", "bcc"):
    _val = getattr(outbound_activity, _addr_field, None)
    if _val is not None and _val != []:
        logger.warning(
            "Outbound %s activity '%s' has `%s:` set."
            " Vultron only uses `to:` for addressing (OX-08-004).",
            activity_type,
            activity_id,
            _addr_field,
        )
```

### 3. Import the new exception

Add to the import line in `outbox_handler.py`:

```python
from vultron.errors import (
    VultronOutboxObjectIntegrityError,
    VultronOutboxToFieldMissingError,
)
```

### 4. No call-site changes required

The check runs at delivery time; `outbox_append` / `record_outbox_item`
call sites do not need updating. If a use case or BT node accidentally omits
`to:`, the outbox handler will catch it, log an error, and re-queue the item
(up to the 3-error limit).

---

## Testing Patterns

```python
# Test: missing to: raises VultronOutboxToFieldMissingError
activity = make_test_activity(to=None)
dl.save(activity)
dl.outbox_append(activity.id_)
with pytest.raises(VultronOutboxToFieldMissingError):
    await handle_outbox_item(actor_id, activity.id_, dl, emitter)

# Test: empty list raises
activity = make_test_activity(to=[])
...

# Test: cc present but no to: raises
activity = make_test_activity(to=None, cc=["https://example.org/alice"])
...

# Test: to: present with cc: logs WARNING but delivers
activity = make_test_activity(
    to=["https://example.org/alice"],
    cc=["https://example.org/bob"],
)
with caplog.at_level(logging.WARNING):
    await handle_outbox_item(actor_id, activity.id_, dl, emitter)
assert any("cc" in r.message for r in caplog.records)
emitter.emit.assert_called_once()
```

---

## Layer / Import Rules

- `VultronOutboxToFieldMissingError` lives in `vultron/errors.py` (neutral
  module, same as `VultronOutboxObjectIntegrityError`)
- `outbox_handler.py` is in the driving adapter layer
  (`vultron/adapters/driving/fastapi/`) — importing from `vultron/errors.py`
  is permitted

---

## Related

- `specs/outbox.md` — OX-08-* requirements
- `vultron/adapters/driving/fastapi/outbox_handler.py` — enforcement point
- `vultron/errors.py` — exception hierarchy
- `test/adapters/driving/fastapi/test_outbox.py` — test location
