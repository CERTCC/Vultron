## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

### 2026-03-18: VultronActivity.actor now required — test fixture update

**Issue**: `VultronActivity.actor` was changed from `Optional[NonEmptyString]`
to required `NonEmptyString`. This caused 17 test failures because tests
instantiated `VultronActivity`, `VultronOffer`, `VultronAccept`, and
`VultronCreateCaseActivity` without providing `actor`.

**Root cause**: Every AS2 Activity MUST have an actor (the agent performing the
activity). Making `actor` required enforces this protocol invariant at the
model layer.

**Fix**: Updated test fixtures in three files to supply a valid `actor` URL:
- `test/core/models/test_base.py`: Added `actor` to `REQUIRED_KWARGS` for all
  four activity classes; updated `test_vultron_activity_as_type_required` and
  `test_domain_object_expected_as_types` inline instantiations.
- `test/test_behavior_dispatcher.py`: Added `actor` to `VultronActivity()`
  call.
- `test/core/behaviors/case/test_create_tree.py`: Added `actor` to
  `VultronOffer()` calls inside `FakeActivity` class bodies; also added
  `actor_id` as an explicit fixture parameter to both affected test functions.
  **Gotcha**: Python class bodies do NOT receive pytest fixture values from
  their enclosing function scope — the name `actor_id` at class-body level
  resolves to the fixture *function* object, not the string value, causing a
  Pydantic `ValidationError`. The fix is to add `actor_id` as a named
  parameter on the test function so pytest injects the string value into the
  function's local scope, making it accessible inside the class body.


## `wire` needs pydantic field aliases, `core` does not

The field aliases found in `BaseModel`-derived classes in `vultron/wire/as2` 
are there to ensure that JSON serialization and deserialization produces the 
correct field names as defined in the AS2 specification, which often include
names that are also python reserved keywords (e.g., `type`, `object`, `id`).
These aliases allow us to use valid Python identifiers in our code while 
still adhering to the AS2 spec when converting to and from JSON.

However, in the parallel models in `vultron/core/models`, we do not want to  
use field aliases because these models are for internal core use so we don't 
need to adhere to the AS2 field naming conventions in our internal code. 
Using aliases in the core models just adds unneeded complexity and 
indirection when working with these models in the core logic. 

---

## Datalayer depends too much on wire format

The datalayer port used by core relies on an object registry for rehydration 
that is currently implemented in a way that is tightly coupled to the AS2 
wire format for type names. This was less of a problem before we separated 
wire and core from each other but it is now showing up in complex ways in 
rehydration, find_in_vocabulary, etc.,
hindering progress. We need to resolve this quickly. 

The data model was roughly intended to map different AS2 types onto 
different tables in the datalayer so that we could easily query for specific
types of objects. So now that that there is a separation between wire and 
core types we are running into issues where the datalayer is expecting to 
find AS2 type names, but the core would make better use of more semantically 
relevant object types. If we need to continue storing raw AS2 objects in the 
datalayer, we might need to separate those out from the core's interactions 
with the datalayer so they are not conflicting with each other.

This requires some planning effort to understand the problem and determine 
the best way forward. Refactoring both wire and core's interactions with the 
datalayer may be necessary to resolve this issue.

---

## Refactor large tests

`test/api/v2/backend/test_handlers.py` is far too large and it no longer 
maps to the current code structure. Refactor it to be more modular and 
reflect the move from api/v2/backend to adapters.

## Unblocking VCR-030

VCR-030 (delete `vultron/sim/`) was found to have callers in `vultron/bt/`:
- `vultron/bt/states.py`
- `vultron/bt/messaging/outbound/behaviors.py`
- `vultron/bt/messaging/inbound/fuzzer.py`
- `vultron/bt/report_management/_behaviors/report_to_others.py`

All import `vultron.sim.messages.Message`. VCR-030 can be resolved by moving 
the `Message` class into `vultron/bt/messaging/message.py` (create as new 
module). This is a more appropriate location for `Message` anyway as it is 
only relevant to the older `vultron/bt` simulator anyway.
