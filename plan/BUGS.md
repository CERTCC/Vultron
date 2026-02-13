# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

## 2026-02-13 - FIXED: Activities not being added to actor inboxes

**Status**: ✅ RESOLVED

**Root Cause**: The `@model_validator(mode="after")` in `vultron/as_vocab/base/objects/actors.py` was unconditionally creating new empty `OrderedCollection` objects for `inbox` and `outbox`, overwriting any existing values during Pydantic model validation.

**Impact**: 
- Activities posted to `/actors/{actor_id}/inbox/` were stored in the datalayer but not added to the actor's inbox collection
- All three demos in `receive_report_demo.py` were failing because response activities weren't appearing in the finder's inbox
- Case creation notifications weren't appearing in the outbox

**Fix**: Modified the `set_collections` validator to only create inbox/outbox collections if they don't already exist (check for `None` before creating).

**Files Changed**:
- `vultron/as_vocab/base/objects/actors.py`: Fixed validator to preserve existing collections
- `vultron/api/v2/backend/handlers.py`: Fixed `dl.update()` call to use correct signature
- `vultron/api/v2/routers/actors.py`: Minor cleanup and improved logging

**Verification**:
- ✅ Demo test passes (test/scripts/test_receive_report_demo.py)
- ✅ All handler tests pass (test/api/v2/backend/test_handlers.py)
- ✅ Inbox items persist correctly after POST
- ✅ Outbox items persist correctly in validate_report handler