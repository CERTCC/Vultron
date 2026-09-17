---
source: NOTES-outbox--implementation
timestamp: '2026-09-17T17:32:38.518792+00:00'
title: Implementation (to-field enforcement)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** vultron/errors.py VultronOutboxToFieldMissingError; outbox_handler.py_validate_to_field

---

## Implementation

### 1. Add `VultronOutboxToFieldMissingError` to `vultron/errors.py`

Place it alongside `VultronOutboxObjectIntegrityError`:

```python
class VultronOutboxToFieldMissingError(VultronError):
    """Raised when an outbound activity lacks a non-empty ``to:`` field.

    All Vultron protocol exchanges are direct messages.  Every outbound
    activity MUST address at least one recipient via ``to:``.
    See specs/outbox.yaml OX-08-001, OX-08-002.
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

# Warn if cc/bto/bcc are set (OX-08-004), except for purposeful CASE_MANAGER
# self-copy: a cc: list consisting solely of the originating actor's own ID
# is the only valid non-to: addressing in the protocol (CLP-10-001).
_actor_id = getattr(outbound_activity, "actor", None)
for _addr_field in ("cc", "bto", "bcc"):
    _val = getattr(outbound_activity, _addr_field, None)
    if _val is not None and _val != []:
        _is_self_copy = (
            _addr_field == "cc"
            and isinstance(_val, list)
            and _val == [_actor_id]
        )
        if not _is_self_copy:
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
