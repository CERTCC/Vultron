## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

## 2026-03-11 — P65-4 scope narrowed after P65-3

V-20 and V-21 were resolved as side effects of P65-2 and P65-3 respectively.
P65-4 scope is now **V-03-R only**:

- `behavior_dispatcher.py` line 10 imports `extract_intent` (and redundantly
  `find_matching_semantics`) from `vultron.wire.as2.extractor`.
- Fix: move `extract_intent()` call from `prepare_for_dispatch()` upstream
  into `inbox_handler.py`. After that, drop the wire import from
  `behavior_dispatcher.py` entirely.
- `prepare_for_dispatch()` should be deleted or relocated to the adapter
  layer (`inbox_handler.py` or `adapters/driving/`).
- The `test_prepare_for_dispatch_*` test in `test/test_behavior_dispatcher.py`
  will move alongside `prepare_for_dispatch`.

---

## 2026-03-11 — P65-6a: VultronEvent design notes

P65-6a introduces the typed domain event hierarchy (VultronEvent). Key
design decisions are captured in `notes/domain-model-separation.md`
"Discriminated Event Hierarchy" section. Summary for the implementing agent:

- `VultronEvent` base class lives in `core/models/events/base.py` with a
  `semantic_type: MessageSemantics` discriminator and shared ID fields.
- Per-semantic subclasses in `core/models/events/` grouped by category
  (`report.py`, `case.py`, `embargo.py`, etc.) following the naming convention
  `FooReceivedEvent` for inbound (handler-side) events.
- `extract_intent()` in `wire/as2/extractor.py` should return a discriminated
  union of `VultronEvent` subclasses rather than the flat `InboundPayload`.
- Handlers receive the typed event via `dispatchable.payload`; the
  `@verify_semantics` decorator continues to work based on `semantic_type`.
- Do **not** add fields speculatively — only include what handler code
  actually needs after the P65-3 audit (already complete).
- See `specs/code-style.md` CS-10-002 for the `FooActivity` vs `FooEvent`
  naming convention.


---
## 2026-03-11 — CVDRoles should be list of StrEnum, not Flag

The `CVDRoles` enum in `vultron/bt/roles/states.py` is too clever for its 
own good. This was an old design choice from the BT simulator. We should not 
use it anywhere outside of `vultron/bt`. For current 
uses, we should instead create a new `CVDRole` `StrEnum` class with members 
like `FINDER`, `REPORTER`, `VENDOR`, `COORDINATOR`, `OTHER`, etc. Then when 
these show up in case objects or participant objects, they should be lists 
of `CVDRoles` rather than bitwise flags. This makes it much easier to work 
with and check for membership without worrying about bitwise operations. The 
old `CVDRoles` class can be renamed to `CVDRoleFlags` and kept where it 
lives assuming anything still uses it, but the new `CVDRole` `StrEnum` 
should be the primary way we represent roles going forward.

This change should be carried through both `core` and `wire`.

## 2026-03-11 — Use individual modules for core objects

A number of objects are defined in `vultron/core/models/vultron_types.py` 
and these should be split into separate modules for better organization. 

## 2026-03-11 — Avoid Any in type hints whenever possible

Don't get lazy. Use real types in type hints whenever this is known or 
possible to determine. If the type is complex, consider defining a new  
Pydantic model or type alias to represent it rather than using `Any`. This 
will improve code readability and maintainability. If you find yourself 
needing to use `Any`, consider whether this is a sign that you need to  
refactor the code to be more explicit about the types involved.

## 2026-03-11 — Extract enums into an `enums.py` module wherever they occur

Make it easier to find and manage enums by putting them in dedicated `enums.
py` modules at the appropriate level of the package hierarchy. For example, 
`vultron/core/models/events/enums.py` could hold `MessageSemantics` instead 
of it belonging to `base.py`. Similarly, there are enums scattered 
throughout other parts of the codebase that could be centralized in `enums.
py` files where they belong. Enums imported from outside `core` to be used 
in `core` are candidates for relocation into `core` (refactoring from their 
original location as needed). Pay particular attention to enums in 
`vultron/bt` and `vultron/case_states` as these really should migrate to 
`core` somewhere (probably `core/models/enums`). If 
there 
are a lot of 
enums in a given area, 
split them into an `enums/` subpackage with multiple files as needed. The  
goal is to have a clear, consistent place to look for enums rather than  
having them scattered throughout the codebase.

## 2026-03-11 Technical debt: The `as_` prefix in `core` objects is a relic

Core objects that have fields with the `as_` prefix are a relic of the 
original blending of wire and core models. This prefix was mostly used to 
avoid naming conflicts between wire models and python keywords (`as_object`, 
`as_type`) or to indicate that a field contained AS2-specific data. Now that 
core and wire are more clearly separated, we should remove the `as_` prefix from
core models where it still exists. 
