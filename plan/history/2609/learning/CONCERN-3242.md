---
source: CONCERN-3242
timestamp: '2026-09-23T16:29:48.539965+00:00'
title: AS2 collection types unregistered, so find_in_vocabulary returned core classes
  to wire callers
type: learning
---

## Original concern

The AS2 collection types are registered in neither wire registry, so
`find_in_vocabulary` cannot resolve them on the wire branch. `as_Collection` and
`as_OrderedCollection` exist in
`vultron/wire/as2/vocab/base/objects/collections.py`; they are simply never
registered. `test_registry_completeness.py` skips that module ("no own `type_`
annotation — semantic alias or abstract module"), so the gap is invisible to the
completeness ratchet.

Why it mattered: `find_in_vocabulary` falls back to `CORE_TYPE_MAP`
(ARCH-12-003), and `OrderedCollection` *is* registered there — as the core
`CoreActorCollection`. So a wire-tree lookup for a collection silently crossed
the wire/core boundary and returned a core class, which no wire parent field will
accept. That is the fault behind #3232: an inline actor's `inbox` expanded to a
`CoreActorCollection`, `as_VultronOrganization.inbox` rejected it, and the whole
actor was flattened to a bare `as_Link` on every inbound activity carrying an
inline actor.

Discovered during root-cause analysis for #3217 / #3232 (PR #3233), routed per
the upward-reflection checklist (BW-07-009).

## What planning found

The concern held, and re-deriving it against `main` @ `af69e7e60` changed the
diagnosis in three ways worth carrying forward.

**1. The collision was a vestigial class, not two live classes sharing a name.**
`CoreActor.inbox` / `.outbox` are `str | None` — a plain URL, with a
`mode="before"` validator that keeps only the `id` from a supplied collection
dict. Core does not model an inbox as a list. `CoreActorCollection` was left
behind when that reduction happened, and because it declares
`type_: Literal["OrderedCollection"]` it registers itself in `CORE_TYPE_MAP`
under that name. Nothing reads it: its only references were its own definition,
its `__all__` entry, an allow-list entry in `test_hierarchy_invariants.py`, and
three comments and assertions describing this bug. Its
sole live effect was to make the lookup answer a wire caller with a core class.
Deleting it removes the collision at its source, which is a much smaller fix than
the concern's "register the collection types and tighten the ratchet".

**2. Two mechanisms disagree about which classes are concrete, and the silent one
wins.** `as_Base.__init_subclass__` registers a class only if it declares its own
non-union `type_` annotation; `set_type_from_class_name` (VM-03-001) gives every
class that inherits no `type_` default a runtime `type_` from its class name. So a class that skipped
VM-03-002 — then only a SHOULD — presented a distinct wire `type` and registered
nothing. VM-03-002 is now a MUST for exactly this reason, and VM-01-007 phrases
the completeness invariant on the `type` a class *presents* rather than the module
it lives in. The old check's skip predicate ("no own `type_` annotation → semantic
alias or abstract module") **was the defect being tested for** — a check whose
skip condition is the fault cannot see the fault.

**3. A filter in one caller did not protect the others.** #3232 guarded
`parser._inline_vocab_class` with `issubclass(cls, as_Base)`. The FastAPI inbox
adapter's `_reparse_as_specific_type` had no such guard. Verified on `main`: an
inbound `Add(object={"type": "OrderedCollection", "id": ...})` was reconstructed
as a core `CoreActorCollection` and handed to the persistence write (a payload with
`totalItems` or `orderedItems` fails that validation and falls back to
`as_Object`). So the concern's
warning that "any future caller inherits the same trap" was already "one more
current caller does". VM-06-008 generalises the rule from one call site to the
lookup: wire-branch resolution returns `as_Base` subclasses only, and the core
fallback is opt-in. A permissive default hands the unsafe answer to every new
caller for free.

Two smaller findings. The gap was never collections-only — `as_Link` and
`as_Mention` are in the same hole. And most of the family is dead weight:
`as_CollectionPage`, `as_OrderedCollectionPage`, `as_Mention`, the
`following`/`followers`/`liked`/`streams` actor fields and every paging field had
zero readers.

**Found on the way, filed separately:** the inbox's activity-receipt recording and
duplicate detection both gate on `hasattr(actor.inbox, "items")`, which a string
never satisfies, so both silently do nothing and "have I already received this?"
always answers no (#3566). Same root cause — core dropped the collection and two
call sites still expect one.

**ADR determination: none needed.** The boundary rule is settled by ADR-0090 /
MV-04-003. What changed is that ARCH-12-010 stated its purpose as "the wire-layer
fallback path consulted by `find_in_vocabulary()`", which made a core answer to a
wire question look sanctioned. That phrasing is withdrawn; the registration duty
stands. ADR-0099 was checked and explicitly keeps the wire collection types
("an actor's inbox is an address"), so none of this is throwaway work.

**Resolved**: 2026-09-23 — implementation tracked in #3563, #3564, #3565; bug
filed as #3566.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3562>.
Spec: `specs/vocabulary-model.yaml` (VM-03-002 raised to MUST, VM-01-007 and
VM-06-008 added), `specs/architecture.yaml` (ARCH-12-010 amended).
Notes: `notes/vocabulary-registry.md` § "Why `OrderedCollection` Collided At All",
`notes/wire-core-boundary.md` § "ARCH-12-010 is a trap for wire-side callers".
