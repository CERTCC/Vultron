## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-04-29 BUG-471.6 — BTBridge.get_failure_reason vs result.feedback_message

When a `py_trees` Sequence fails because a child fails, the root Sequence
node's `feedback_message` is always `""`. Use `BTBridge.get_failure_reason(tree)`
(depth-first walk to the first failing leaf) to get a meaningful message.
Apply this pattern consistently wherever `result.feedback_message` is logged
after a BT failure — not just for EngageCaseBT.

### 2026-04-30 P472-BUG386 — Closed via sender-side inline-object fix

TASK-BUG-386 (deferred handling for unresolvable `Accept.object_` URIs) was
resolved by commit `62cdc48e` which made the parser embed the full inline typed
object in every `Accept`/`Reject` activity before it leaves the outbox. The
receiver-side dead-letter path (`UnresolvableObjectUseCase`) remains in place
for non-compliant or legacy senders; it was not changed. If a future need arises
to auto-retry deferred activities, implement a `DeferredActivityRecord` model
and a dispatcher post-hook (see issue #386 description for design sketch).

### 2026-04-30 TASK-DL-REHYDRATE — Do not name a method `list` in a Python class

Defining `def list(self, ...)` on a class causes Python to shadow the built-in
`list` type in the class body scope. Any annotation `list[str]` that appears
AFTER the `def list(...)` definition is evaluated at class-body execution time
with `list` resolving to the method (a function), producing `TypeError:
'function' object is not subscriptable`. `# type: ignore[valid-type]` only
suppresses mypy — it does NOT prevent the runtime error. Fix: rename the method
to avoid collision (e.g., `list_objects`). This affects any method that shares
a name with a Python built-in type (`dict`, `set`, `tuple`, etc.).

### 2026-04-30 BUG-26043001 — append-history: always use a Pydantic model for structured file formats

When a CLI tool writes structured files (frontmatter, YAML, JSON), define a
Pydantic model for the structure upfront. Without it, required-field validation
is either missing or duplicated across callers. The fallback-to-default pattern
(`metadata.get("source", "")`) makes it impossible to distinguish "absent field"
from "empty field". A Pydantic model with `ValidationError` on missing fields is
the single source of truth and forces callers to handle the error path explicitly.

### 2026-04-30 AF.8-10 — Factory return types are wire types, not domain models

After migrating call sites in `vocab/examples/` and `demo/` from internal
activity classes to factory functions, 91 mypy/pyright type errors emerged.
Root cause: factory functions return base AS2 wire types (`as_Offer`,
`as_Create`, etc.) from `vultron.wire.as2.vocab.base.*`, but the migrated
code had `-> VultronActivity` return type annotations. `VultronActivity` is
a domain model (`vultron/core/models/`); it is NOT a supertype of `as_Offer`.

Key patterns and fixes:

- `vocab/examples/*.py`: change `-> VultronActivity` to the specific AS2 base
  type that the factory returns (e.g., `-> as_Offer`, `-> as_Accept`). Chain
  calls between example functions (e.g., `submit_report()` passed to
  `rm_validate_report_activity()`) require the specific AS2 type, not
  `as_Activity`, since factory parameters are typed precisely.
- `demo/utils.py#get_offer_from_datalayer`: was wrapping `as_Offer(**data)`
  in `VultronActivity.model_validate(...)`. Remove the wrapping; return the
  `as_Offer` directly. This fixes all exchange demo files that passed the
  offer to `rm_validate_report_activity(offer: as_Offer)`.
- Demo scenario files: trigger endpoint responses should be parsed as
  `as_Activity.model_validate(...)` (or a specific subtype), not
  `VultronActivity.model_validate(...)`.
- When the parsed activity's `.object_` field is needed, parse it as the
  specific transitive type (e.g., `as_Create`, `as_Invite`) since
  `as_Activity` (base class) doesn't have `object_`; only transitive subtypes do.
- Pyright `[attr-defined]` errors on subtype-only attributes (e.g.,
  `ChoosePreferredEmbargoActivity.one_of` not on `as_Question`) are fixed
  with a runtime `isinstance` assertion for type narrowing, not
  `# type: ignore`.
