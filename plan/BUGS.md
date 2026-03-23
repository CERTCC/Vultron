# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

## BUG-001 — `outbox_handler` crashes when actor is `None`

**File**: `vultron/adapters/driving/fastapi/outbox_handler.py`

**Discovered**: 2026-03-23 (during OX-1.4 test writing)

**Description**: `outbox_handler` checks `if actor is None` and logs a
warning, but does NOT return early. The very next line (`while
actor.outbox.items:`) will raise `AttributeError: 'NoneType' object has no
attribute 'outbox'` if `dl.read(actor_id)` returns `None`.

**Reproduction**:

```python
import asyncio
from unittest.mock import MagicMock
from vultron.adapters.driving.fastapi import outbox_handler as oh

mock_dl = MagicMock()
mock_dl.read.return_value = None  # actor not found

oh_mod = oh  # monkeypatch get_datalayer
import vultron.adapters.driving.fastapi.outbox_handler as _mod
_mod.get_datalayer = lambda: mock_dl
asyncio.run(_mod.outbox_handler("missing-actor"))  # → AttributeError
```

**Fix**: Add `return` (or `return None`) immediately after the
`logger.warning(...)` line when `actor is None`.

**Priority**: Low (only triggered for unknown actor IDs; current callers
always pass a valid actor_id).
