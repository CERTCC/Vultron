## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

## 2026-03-11 — P65-4 scope narrowed after P65-3

~~V-20 and V-21 were resolved as side effects of P65-2 and P65-3 respectively.
P65-4 scope is now **V-03-R only**:~~

~~- `behavior_dispatcher.py` line 10 imports `extract_intent` (and redundantly
  `find_matching_semantics`) from `vultron.wire.as2.extractor`.
- Fix: move `extract_intent()` call from `prepare_for_dispatch()` upstream
  into `inbox_handler.py`. After that, drop the wire import from
  `behavior_dispatcher.py` entirely.
- `prepare_for_dispatch()` should be deleted or relocated to the adapter
  layer (`inbox_handler.py` or `adapters/driving/`).
- The `test_prepare_for_dispatch_*` test in `test/test_behavior_dispatcher.py`
  will move alongside `prepare_for_dispatch`.~~

→ Captured in `notes/architecture-review.md` V-03-R (P65-4 remediation plan added).

---

## 2026-03-11 — P65-6a: VultronEvent design notes

~~P65-6a introduces the typed domain event hierarchy (VultronEvent). Key
design decisions are captured in `notes/domain-model-separation.md`
"Discriminated Event Hierarchy" section.~~

→ Captured in `notes/domain-model-separation.md`:
"Discriminated Event Hierarchy" and new
"P65-6a: `extract_intent()` Should Return a Discriminated Union" sections.

---

## 2026-03-11 — CVDRoles should be list of StrEnum, not Flag

~~The `CVDRoles` enum in `vultron/bt/roles/states.py` uses bitwise `Flag`
semantics and should not be used outside `vultron/bt`. New code in `core`
and `wire` should use a `CVDRole` `StrEnum` and represent roles as
`list[CVDRole]`.~~

→ Captured in `notes/codebase-structure.md` "`CVDRoles` Design Decision:
StrEnum List, Not Flag" section.

## 2026-03-11 — Use individual modules for core objects

~~`vultron/core/models/vultron_types.py` should be split into separate
modules for better organization.~~

→ Captured in `notes/codebase-structure.md` "Core Object Modules: Split
`vultron_types.py`" section.

## 2026-03-11 — Avoid Any in type hints whenever possible

~~Use real types in type hints whenever possible. Define a Pydantic model or
type alias rather than using `Any`.~~

→ Captured in `specs/code-style.md` CS-11-001.

## 2026-03-11 — Extract enums into an `enums.py` module wherever they occur

~~Place enums in dedicated `enums.py` modules at the appropriate level of the
package hierarchy. Enums in `vultron/bt` and `vultron/case_states` should
migrate to `core/models/enums/`.~~

→ Captured in `notes/codebase-structure.md` "Enum Refactoring" section (enriched).

## 2026-03-11 Technical debt: The `as_` prefix in `core` objects is a relic

~~Core objects with `as_` prefix fields are a relic of the original wire/core
blending. Remove the `as_` prefix from core models. For reserved-word
conflicts use trailing underscore + Pydantic alias.~~

→ Captured in `specs/code-style.md` CS-07-001/CS-07-002 and `AGENTS.md`
Naming Conventions.

## 2026-03-11 Performance tests are premature

~~Performance testing is premature; mark performance requirements `PROD_ONLY`.
Existing performance-assertion tests may be marked skip/xfail if not critical
for correctness.~~

→ Captured in `specs/prototype-shortcuts.md` PROTO-07-001.

## 2026-03-11 Add architecture tests once we have separated core and wire

~~Add tests that verify architectural boundaries once core/wire separation is
complete.~~

→ Captured in `specs/testability.md` TB-10-001.

## 2026-03-11 Classes like `VultronOffer` should be more use-case centric names

~~Core model class names should reflect the CVD domain concept, not mirror
wire-format names (e.g., `CaseTransferOffer` not `VultronOffer`).~~

→ Captured in `specs/code-style.md` CS-12-001.
